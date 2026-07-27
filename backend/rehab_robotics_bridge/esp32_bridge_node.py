"""
ESP32 Bridge Node

Connects to one ESP32 node's TCP stream (step_node firmware v1.8),
parses 14-channel Open Ephys binary frames, and publishes:

  /esp32/{node_id}/imu   →  sensor_msgs/Imu  (VQF-fused quat + raw accel/gyro)
  /esp32/{node_id}/raw   →  std_msgs/Float32MultiArray  (all 14 ch, normalised)

Channel map (verified against step_node.ino packChannelsFromImu(), NUM_CHANNELS=14):
  ch[ 0- 2]  accel X/Y/Z    raw int16, default ±2g    → ÷16384 × 9.80665  m/s²
  ch[ 3- 5]  gyro  X/Y/Z    raw int16, default ±250dps → ÷131.072 × π/180  rad/s
  ch[ 6- 8]  mag   X/Y/Z    raw int16  (0 if no AK09916 magnetometer)
  ch[ 9-12]  quat  W/X/Y/Z  Q15 int16 → ÷32767  (VQF-fused, 6-DOF or 9-DOF)
  ch[13]     DIO             packed int16 (packDioCh6())

NOTE: esp32_to_opensim_bridge.py in the Plugin repo documents ch6=DIO, ch7-10=quat
(11-ch layout). That docstring is outdated — the v1.8 firmware expanded to 14 channels
by inserting mag at ch6-8 and moving quat to ch9-12 and DIO to ch13.

TCP frame: 22-byte packed OeHeader + 28-byte int16 payload = 50 bytes.

Network (all on STEP_ESP32 WiFi, pass: step1234):
  Master:  192.168.4.1:5000  (master starts Soft AP, fixed IP)
  Slave 1: 192.168.4.2:5000  (joins AP, DHCP)
  Slave N: 192.168.4.N+1:5000
  Each node runs its own TCP :5000 — aggregator connects to each independently.

USB fallback (single node only):
  Run Plugin repo: python3 esp32/host/serial_tcp_bridge.py /dev/ttyUSBx --plugin
  Then set host=127.0.0.1.

Usage:
  ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args \\
    -p node_id:=master \\
    -p host:=192.168.4.1 \\
    -p port:=5000
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import math
import socket
import struct
import threading
import time
from collections import deque
from concurrent.futures import TimeoutError as FutureTimeoutError

import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import SetParametersResult
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32MultiArray, Header, String
from std_srvs.srv import SetBool

from rehab_robotics_bridge.measurement_contract import (
    measurement_config,
    config_as_json,
    accel_count_to_mps2,
    gyro_count_to_rad_s,
)

# ── Open Ephys binary header ────────────────────────────────────────────────
OE_HEADER = struct.Struct('<iiHiii')   # offset, num_bytes, bit_depth, element_type, n_channels, n_samples_per_channel
OE_HEADER_SIZE = OE_HEADER.size

# ── ICM20948 default full-scale ranges (preset=0) ───────────────────────────
# Match kAccLsbPerG[0] and kGyrLsbPerDps[0] in step_node.ino
_GRAVITY = 9.80665
ACC_LSB_PER_G   = 16384.0   # ±2g
GYR_LSB_PER_DPS = 131.072   # ±250 dps
ACC_SCALE  = _GRAVITY / ACC_LSB_PER_G           # m/s² per LSB
GYR_SCALE  = (math.pi / 180.0) / GYR_LSB_PER_DPS  # rad/s per LSB
QUAT_SCALE = 1.0 / 32767.0                      # Q15 → float

NUM_CHANNELS = 14


def is_valid_oe_header(data: bytes | bytearray, offset: int = 0) -> bool:
    """Return whether *data* contains a complete STEP Open Ephys header."""
    if offset < 0 or len(data) - offset < OE_HEADER_SIZE:
        return False
    try:
        _frame_offset, num_bytes, bit_depth, elem, n_ch, n_per = OE_HEADER.unpack_from(data, offset)
    except struct.error:
        return False
    return (
        bit_depth == 3
        and elem == 2
        and n_ch == NUM_CHANNELS
        and n_per >= 1
        and num_bytes == n_ch * n_per * 2
        and num_bytes <= 4096
    )


def find_next_oe_header(data: bytes | bytearray, start: int = 0) -> int | None:
    """Find the next valid frame boundary in a mixed control/binary stream."""
    last = len(data) - OE_HEADER_SIZE
    for offset in range(max(0, start), last + 1):
        if is_valid_oe_header(data, offset):
            return offset
    return None

# ── Handshake strings the firmware expects ───────────────────────────────────
HANDSHAKE_CONNECT = b'REDPITAYA\n'
HANDSHAKE_START   = b'START\n'
CONTROL_RESPONSE_PREFIXES = (
    b'REC ', b'SLAVE_STATUS ', b'SD_STATUS ', b'SD_FINAL ',
    b'STOPPED', b'STARTED', b'SENSORS:', b'OK FREQ:', b'ERROR FREQ:',
    b'OK FILTER ', b'ERROR FILTER:', b'OK CFG ', b'ERROR CFG:',
)

ACCEL_RANGE_PRESETS = {2: 0, 4: 1, 8: 2, 16: 3}
GYRO_RANGE_PRESETS = {250: 0, 500: 1, 1000: 2, 2000: 3}


def parse_control_fields(line: str) -> dict[str, str]:
    """Parse the firmware's space-delimited key=value control reply fields."""
    return {
        key: value
        for field in line.split()
        if '=' in field
        for key, value in [field.split('=', 1)]
    }


def control_int(fields: dict[str, str], name: str) -> int | None:
    try:
        return int(fields[name])
    except (KeyError, ValueError):
        return None


class Esp32BridgeNode(Node):
    def __init__(self) -> None:
        super().__init__('esp32_bridge_node')

        self.declare_parameter('node_id', 'master')
        self.declare_parameter('host', '192.168.4.1')
        self.declare_parameter('port', 5000)
        self.declare_parameter('udp_port', 55001)
        self.declare_parameter('transport', 'auto')
        self.declare_parameter('body_segment', '')
        self.declare_parameter('reconnect_delay_s', 5.0)
        self.declare_parameter('handshake_timeout_s', 15.0)
        self.declare_parameter('publish_native_topics', True)
        self.declare_parameter('recording_sample_rate_hz', 100)
        self.declare_parameter('sample_rate_hz', 100)
        self.declare_parameter('filter_enabled', True)
        self.declare_parameter('accel_range_g', 2)
        self.declare_parameter('gyro_range_dps', 250)
        self.declare_parameter('effective_sample_rate_hz', 100)
        self.declare_parameter('recording_control_mode', 'active')

        self._node_id: str = self.get_parameter('node_id').value
        self._host: str   = self.get_parameter('host').value
        self._port: int   = self.get_parameter('port').value
        self._udp_port: int = self.get_parameter('udp_port').value
        self._transport: str = self.get_parameter('transport').value.lower()
        self._body_segment: str = self.get_parameter('body_segment').value
        self._reconnect_s: float = self.get_parameter('reconnect_delay_s').value
        self._handshake_timeout_s: float = self.get_parameter('handshake_timeout_s').value
        self._publish_native: bool = self.get_parameter('publish_native_topics').value
        self._retry_delay_s = self._reconnect_s
        self._recording_sample_rate_hz: int = self.get_parameter('recording_sample_rate_hz').value
        self._sample_rate_hz: int = self.get_parameter('sample_rate_hz').value
        self._filter_enabled: bool = self.get_parameter('filter_enabled').value
        self._desired_accel_range_g: int = self.get_parameter('accel_range_g').value
        self._desired_gyro_range_dps: int = self.get_parameter('gyro_range_dps').value
        self._confirmed_accel_range_g: int | None = None
        self._confirmed_gyro_range_dps: int | None = None
        self._effective_sample_rate_hz: int = self.get_parameter('effective_sample_rate_hz').value
        self._recording_control_mode: str = self.get_parameter('recording_control_mode').value.lower()
        self._active_writer: asyncio.StreamWriter | None = None
        self._control_responses: asyncio.Queue[str] = asyncio.Queue()
        self._record_command_lock: asyncio.Lock | None = None
        self._recording_session_id = ''
        self._recording_state = 'idle'
        self._recording_error = ''
        self._recording_health: dict[str, object] = {
            'sd_ready': None,
            'saved_samples': None,
            'file_byte_size': None,
            'file_checksum': None,
            'checksum_type': None,
            'finalization_reason': None,
        }
        self._connection_state = 'connecting'
        self._reconnect_count = 0
        self._last_frame_monotonic: float | None = None
        self._frame_times: deque[float] = deque()
        self._frames_received = 0
        self._latest_slave_health: dict[str, object] | None = None
        self.add_on_set_parameters_callback(self._on_set_parameters)

        prefix = f'/esp32/{self._node_id}'
        self._pub_imu = self.create_publisher(Imu,               f'{prefix}/imu', 10)
        self._pub_raw = self.create_publisher(Float32MultiArray, f'{prefix}/raw', 10)
        self._pub_raw_json = self.create_publisher(String, f'/esp/raw/{self._node_id}', 10)
        self._pub_health = self.create_publisher(String, f'/esp/status/{self._node_id}', 10)
        self._health_timer = self.create_timer(0.5, self._publish_health_status)
        if self._node_id == 'master':
            self._pub_pair_health = self.create_publisher(String, '/esp/status/pair', 10)
            self._slave_health_subscription = self.create_subscription(
                String, '/esp/status/slave', self._on_slave_health, 10,
            )

        self.get_logger().info(
            f'[{self._node_id}] → {self._host}:{self._port} | '
            f'topics: {prefix}/imu  {prefix}/raw'
        )

        if self._node_id == 'master':
            self.create_service(SetBool, '/esp/recording/set', self._set_recording)
            for sample_rate_hz in (100, 250, 500, 1000):
                self.create_service(
                    SetBool,
                    f'/esp/acquisition/sample_rate/set_{sample_rate_hz}',
                    lambda request, response, rate=sample_rate_hz: self._set_sample_rate(rate, request, response),
                )
            self.get_logger().info('master recording service: /esp/recording/set')
            self.get_logger().info('master sample-rate services enabled')

        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_until_complete,
                         args=(self._reconnect_forever(),),
                         daemon=True).start()

    def _set_recording(self, request: SetBool.Request, response: SetBool.Response) -> SetBool.Response:
        """Forward GUI recording requests through the master rec-v1 control path."""
        if not self._loop.is_running():
            response.success = False
            response.message = 'master stream is not connected'
            return response

        if request.data:
            requested_session = time.strftime('%Y%m%d_%H%M%S')
            command = (
                f'REC START sample_rate_hz={self._recording_sample_rate_hz} channels={NUM_CHANNELS} '
                f'format=sd-bin sd_required=true requested_session={requested_session}'
            )
            expected = 'REC STARTED'
        else:
            session_id = self._recording_session_id or 'latest'
            command = f'REC STOP session_id={session_id} reason=gui_stop'
            # The firmware acknowledges an accepted stop as FINALIZING before
            # its SD worker flushes and emits FINALIZED asynchronously.
            expected = 'REC FINALIZING'

        try:
            result = asyncio.run_coroutine_threadsafe(
                self._send_control_command(command, expected), self._loop
            ).result(timeout=8.0)
        except (TimeoutError, FutureTimeoutError):
            response.success = False
            response.message = (
                'master did not answer rec-v1; flash the plugin v1.8 SD/ESP-NOW firmware '
                'before using Record'
            )
            return response
        except Exception as exc:
            response.success = False
            detail = str(exc).strip()
            response.message = (
                f'recording command failed: {detail}' if detail else
                'master did not answer rec-v1; flash the plugin v1.8 SD/ESP-NOW firmware '
                'before using Record'
            )
            return response

        response.success = result.startswith(expected)
        response.message = result
        if response.success and request.data:
            for field in result.split():
                if field.startswith('session_id='):
                    self._recording_session_id = field.split('=', 1)[1]
                    break
            self._recording_state = 'recording'
            self._recording_error = ''
        if response.success and not request.data:
            self._recording_state = 'finalizing'
        self._observe_control_response(result)
        return response

    def _set_sample_rate(
        self, sample_rate_hz: int, request: SetBool.Request, response: SetBool.Response,
    ) -> SetBool.Response:
        """Apply a live rate to the master and its ESP-NOW-linked slave."""
        if not request.data or not self._loop.is_running():
            response.success = False
            response.message = 'master stream is not connected'
            return response
        try:
            result = asyncio.run_coroutine_threadsafe(
                self._send_control_command(f'FREQ:{sample_rate_hz}', f'OK FREQ:{sample_rate_hz}'), self._loop,
            ).result(timeout=8.0)
        except (TimeoutError, FutureTimeoutError):
            response.success = False
            response.message = f'master did not acknowledge {sample_rate_hz} Hz'
            return response
        except Exception as exc:
            response.success = False
            response.message = f'sample-rate command failed: {str(exc).strip() or "unknown error"}'
            return response
        response.success = result.startswith(f'OK FREQ:{sample_rate_hz}')
        response.message = result
        return response

    def _on_set_parameters(self, parameters) -> SetParametersResult:
        """Validate and apply acknowledged live acquisition settings from the GUI."""
        for parameter in parameters:
            if parameter.name not in {
                'sample_rate_hz', 'filter_enabled', 'accel_range_g',
                'gyro_range_dps', 'effective_sample_rate_hz',
            }:
                continue
            command, expected, error = self._control_command_for_parameter(parameter.name, parameter.value)
            if error:
                return SetParametersResult(successful=False, reason=error)
            if not self._loop.is_running():
                return SetParametersResult(successful=False, reason='master stream is not connected')
            try:
                result = asyncio.run_coroutine_threadsafe(
                    self._send_control_command(command, expected), self._loop,
                ).result(timeout=8.0)
            except Exception as exc:
                return SetParametersResult(
                    successful=False,
                    reason=f'{parameter.name} command failed: {str(exc).strip() or "unknown error"}',
                )
            if not result.startswith(expected):
                return SetParametersResult(successful=False, reason=result)
            self._store_confirmed_control_value(parameter.name, parameter.value)
        return SetParametersResult(successful=True, reason='')

    @staticmethod
    def _control_command_for_parameter(name: str, value) -> tuple[str, str, str]:
        """Map validated ROS parameters to firmware commands and terminal replies."""
        if name == 'sample_rate_hz':
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1000:
                return '', '', f'{name} must be an integer between 1 and 1000'
            return f'FREQ:{value}', f'OK FREQ:{value}', ''
        if name == 'effective_sample_rate_hz':
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1000:
                return '', '', f'{name} must be an integer between 1 and 1000'
            return f'CFG 0 SRATE {value}', f'OK FREQ:{value}', ''
        if name == 'filter_enabled':
            if not isinstance(value, bool):
                return '', '', 'filter_enabled must be true or false'
            state = 'ON' if value else 'OFF'
            return f'FILTER {state}', f'OK FILTER {state}', ''
        if name == 'accel_range_g':
            if not isinstance(value, int) or isinstance(value, bool) or value not in ACCEL_RANGE_PRESETS:
                return '', '', 'accel_range_g must be one of 2, 4, 8, or 16'
            return f'CFG 0 ACC {ACCEL_RANGE_PRESETS[value]}', 'OK CFG ACC', ''
        if name == 'gyro_range_dps':
            if not isinstance(value, int) or isinstance(value, bool) or value not in GYRO_RANGE_PRESETS:
                return '', '', 'gyro_range_dps must be one of 250, 500, 1000, or 2000'
            return f'CFG 0 GYR {GYRO_RANGE_PRESETS[value]}', 'OK CFG GYR', ''
        return '', '', f'unsupported control parameter: {name}'

    def _store_confirmed_control_value(self, name: str, value) -> None:
        if name == 'sample_rate_hz':
            self._sample_rate_hz = value
            self._effective_sample_rate_hz = value
            self._recording_sample_rate_hz = value
        elif name == 'effective_sample_rate_hz':
            self._effective_sample_rate_hz = value
            self._sample_rate_hz = value
            self._recording_sample_rate_hz = value
        elif name == 'filter_enabled':
            self._filter_enabled = value
        elif name == 'accel_range_g':
            self._confirmed_accel_range_g = value
        elif name == 'gyro_range_dps':
            self._confirmed_gyro_range_dps = value

    def _observe_control_response(self, line: str) -> None:
        """Keep recording/SD metadata from replies without issuing diagnostic traffic."""
        fields = parse_control_fields(line)
        if line.startswith('REC STARTED'):
            self._recording_state = 'recording'
            self._recording_session_id = fields.get('session_id', self._recording_session_id)
        elif line.startswith('REC FINALIZING'):
            self._recording_state = 'finalizing'
        elif line.startswith('REC FINALIZED'):
            self._recording_state = 'finalized'
        elif line.startswith('REC ERR'):
            self._recording_state = 'error'
            self._recording_error = fields.get('detail', line)

        if line.startswith(('REC STATUS_OK', 'SD_STATUS', 'SD_FINAL ', 'REC FINALIZED')):
            self._recording_health.update({
                'sd_ready': control_int(fields, 'sd_ready') if 'sd_ready' in fields else self._recording_health['sd_ready'],
                'saved_samples': control_int(fields, 'saved_samples') if 'saved_samples' in fields else self._recording_health['saved_samples'],
                'file_byte_size': control_int(fields, 'file_byte_size') if 'file_byte_size' in fields else self._recording_health['file_byte_size'],
                'file_checksum': fields.get('file_checksum', self._recording_health['file_checksum']),
                'checksum_type': fields.get('checksum_type', self._recording_health['checksum_type']),
                'finalization_reason': fields.get('finalization_reason', self._recording_health['finalization_reason']),
            })
            if fields.get('recording') == '1':
                self._recording_state = 'recording'

    def _health_snapshot(self) -> dict[str, object]:
        now = time.monotonic()
        while self._frame_times and now - self._frame_times[0] > 5.0:
            self._frame_times.popleft()
        observed_rate = 0.0
        if len(self._frame_times) >= 2:
            elapsed = self._frame_times[-1] - self._frame_times[0]
            if elapsed > 0:
                observed_rate = round((len(self._frame_times) - 1) / elapsed, 2)
        age_ms = None if self._last_frame_monotonic is None else round((now - self._last_frame_monotonic) * 1000, 1)
        return {
            'schema': 'oe_esp32.health.v1',
            'node_id': self._node_id,
            'timestamp_us': time.monotonic_ns() // 1000,
            'connection_state': self._connection_state,
            'reconnect_count': self._reconnect_count,
            'configured_rate_hz': self._sample_rate_hz,
            'effective_rate_hz': self._effective_sample_rate_hz,
            'observed_stream_rate_hz': observed_rate,
            'last_frame_age_ms': age_ms,
            'frames_received': self._frames_received,
            'recording': {
                'state': self._recording_state,
                'session_id': self._recording_session_id or None,
                'error': self._recording_error or None,
                **self._recording_health,
            },
            'diagnostics_mode': 'passive_no_usb_status_poll',
        }

    def _publish_health_status(self) -> None:
        snapshot = self._health_snapshot()
        message = String()
        message.data = json.dumps(snapshot, sort_keys=True, separators=(',', ':'))
        self._pub_health.publish(message)
        if self._node_id == 'master':
            pair = {
                'schema': 'oe_esp32.pair_health.v1',
                'timestamp_us': snapshot['timestamp_us'],
                'master': snapshot,
                'slave': self._latest_slave_health,
                'pair_available': self._latest_slave_health is not None
                and self._latest_slave_health.get('connection_state') == 'connected',
            }
            pair_message = String()
            pair_message.data = json.dumps(pair, sort_keys=True, separators=(',', ':'))
            self._pub_pair_health.publish(pair_message)

    def _on_slave_health(self, message: String) -> None:
        try:
            snapshot = json.loads(message.data)
        except (TypeError, json.JSONDecodeError):
            return
        if snapshot.get('schema') == 'oe_esp32.health.v1' and snapshot.get('node_id') == 'slave':
            self._latest_slave_health = snapshot

    # ── connection management ────────────────────────────────────────────────

    async def _reconnect_forever(self) -> None:
        while rclpy.ok():
            try:
                await self._connect_and_stream()
            except Exception as exc:
                self._connection_state = 'reconnecting'
                self._reconnect_count += 1
                self.get_logger().warning(
                    f'[{self._node_id}] connection lost: {exc} — '
                    f'retrying in {self._retry_delay_s:.0f} s'
                )
            await asyncio.sleep(self._retry_delay_s)
            self._retry_delay_s = min(self._retry_delay_s * 2.0, 30.0)

    async def _connect_and_stream(self) -> None:
        self._connection_state = 'connecting'
        reader, writer = await asyncio.open_connection(self._host, self._port)
        self.get_logger().info(f'[{self._node_id}] connected to {self._host}:{self._port}')

        try:
            transport = await self._handshake(reader, writer)
            if self._transport not in ('auto', 'tcp', 'udp'):
                raise RuntimeError(f'Unsupported transport setting: {self._transport!r}')
            if self._transport != 'auto' and self._transport != transport:
                raise RuntimeError(
                    f'Configured transport {self._transport!r} does not match ESP32 {transport!r}'
                )
            self._retry_delay_s = self._reconnect_s
            self._active_writer = writer
            self._record_command_lock = asyncio.Lock()
            self._connection_state = 'connected'
            if transport == 'udp':
                await self._read_udp_frames()
            else:
                await self._read_frames(reader)
        finally:
            if self._active_writer is writer:
                self._active_writer = None
            self._connection_state = 'reconnecting'
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            self.get_logger().info(f'[{self._node_id}] disconnected')

    async def _send_control_command(self, command: str, expected: str) -> str:
        """Send a typed control command and wait for success or an explicit rejection."""
        if self._recording_control_mode == 'separate':
            return await self._send_control_command_separate(command, expected)
        writer = self._active_writer
        lock = self._record_command_lock
        if writer is None or lock is None or writer.is_closing():
            raise RuntimeError('master stream is not connected')

        async with lock:
            while not self._control_responses.empty():
                self._control_responses.get_nowait()
            writer.write((command + '\n').encode('ascii'))
            await writer.drain()
            deadline = asyncio.get_running_loop().time() + 6.0
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f'timed out waiting for {expected}')
                line = await asyncio.wait_for(self._control_responses.get(), timeout=remaining)
                if line.startswith(expected) or line.startswith(('REC ERR', 'ERROR ')):
                    return line

    async def _send_control_command_separate(self, command: str, expected: str) -> str:
        """Use a dedicated TCP connection for USB control without interrupting stream clients."""
        reader, writer = await asyncio.open_connection(self._host, self._port)
        try:
            writer.write((command + '\n').encode('ascii'))
            await writer.drain()
            deadline = asyncio.get_running_loop().time() + 6.0
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f'timed out waiting for {expected}')
                line = (await asyncio.wait_for(reader.readline(), timeout=remaining)).decode(errors='replace').strip()
                self._observe_control_response(line)
                if line.startswith(expected) or line.startswith(('REC ERR', 'ERROR ')):
                    return line
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _handshake(self, reader: asyncio.StreamReader,
                         writer: asyncio.StreamWriter) -> str:
        """Perform the REDPITAYA / START handshake.

        Actual sequence (CFG commands inserted before START to stay in text mode):
          PC  → ESP32:  "REDPITAYA\\n"
          ESP32 → PC:   "14 channels; sample_rate=100; node=esp32s3_arduino; ...\\n"
          PC  → ESP32:  "CFG accel_range_g <N>\\n"   ← range confirm (text mode)
          ESP32 → PC:   "OK CFG accel_range_g <N>\\n"
          PC  → ESP32:  "CFG gyro_range_dps <N>\\n"  ← range confirm (text mode)
          ESP32 → PC:   "OK CFG gyro_range_dps <N>\\n"
          PC  → ESP32:  "START\\n"
          ESP32 → PC:   "STARTED BIN:esp32s3_arduino transport=tcp\\n"
          ESP32 → PC:   "SENSORS:0,ICM20948\\n"
          → binary StreamRecord frames begin (50 bytes each: 22 header + 28 payload)
        """
        # 1. Identify ourselves
        writer.write(HANDSHAKE_CONNECT)
        await writer.drain()

        # 2. Receive channel info line
        info = await asyncio.wait_for(reader.readline(), timeout=self._handshake_timeout_s)
        self.get_logger().info(f'[{self._node_id}] info: {info.decode(errors="replace").strip()}')
        try:
            extra_info = await asyncio.wait_for(reader.readline(), timeout=0.25)
            if extra_info:
                self.get_logger().info(
                    f'[{self._node_id}] info: {extra_info.decode(errors="replace").strip()}'
                )
        except asyncio.TimeoutError:
            pass

        # 3. Confirm desired ACC and GYR ranges BEFORE starting binary streaming.
        #    Must happen while ESP32 is still in text mode (before START is sent).
        accel_ok = await self._confirm_range_during_handshake(
            writer, reader,
            'accel_range_g', self._desired_accel_range_g,
        )
        if accel_ok:
            self._confirmed_accel_range_g = self._desired_accel_range_g
        else:
            # CFG exchange failed or firmware doesn't support it.  Fall back to
            # the desired (default 2 g) value — the ICM20948 powers on at ±2 g
            # so using the desired value is correct and avoids suppressing frames.
            self._confirmed_accel_range_g = self._desired_accel_range_g
            self.get_logger().warning(
                f'[{self._node_id}] handshake accel range confirmation failed; '
                f'assuming ±{self._desired_accel_range_g} g (firmware power-on default)'
            )

        gyro_ok = await self._confirm_range_during_handshake(
            writer, reader,
            'gyro_range_dps', self._desired_gyro_range_dps,
        )
        if gyro_ok:
            self._confirmed_gyro_range_dps = self._desired_gyro_range_dps
        else:
            self._confirmed_gyro_range_dps = self._desired_gyro_range_dps
            self.get_logger().warning(
                f'[{self._node_id}] handshake gyro range confirmation failed; '
                f'assuming ±{self._desired_gyro_range_dps} dps (firmware power-on default)'
            )

        # 4. Start streaming
        writer.write(HANDSHAKE_START)
        await writer.drain()

        # 5. Receive STARTED confirmation
        started = b''
        for _ in range(3):
            line = await asyncio.wait_for(reader.readline(), timeout=self._handshake_timeout_s)
            self.get_logger().info(f'[{self._node_id}] {line.decode(errors="replace").strip()}')
            if b'STARTED' in line:
                started = line
                break

        # 6. Receive SENSORS line (ignore content — we know it's ICM20948)
        if not started:
            raise RuntimeError('ESP32 did not acknowledge START')
        # Never call readline() blindly here: a proxy is allowed to start the
        # binary stream immediately, and that would consume part of a frame.
        for _ in range(5):
            await asyncio.sleep(0.02)
            if reader._buffer.startswith(b'SENSORS:'):
                sensors = await reader.readline()
                self.get_logger().info(
                    f'[{self._node_id}] {sensors.decode(errors="replace").strip()}'
                )
                break

        return 'udp' if b'transport=udp' in started else 'tcp'

    async def _confirm_range_during_handshake(
        self,
        writer: asyncio.StreamWriter,
        reader: asyncio.StreamReader,
        name: str,
        value: int,
    ) -> bool:
        """Send a CFG command on the handshake connection and await its reply.

        Returns True if the exact expected acknowledgement is received before
        timeout, False otherwise.  Does not use the shared _record_command_lock
        or _active_writer — those are not yet set during _handshake.
        """
        command, expected, error = self._control_command_for_parameter(name, value)
        if error:
            self.get_logger().warning(
                f'[{self._node_id}] cannot confirm {name}={value} during handshake: {error}'
            )
            return False
        try:
            writer.write((command + '\n').encode('ascii'))
            await writer.drain()
            # Firmware closes idle pre-START TCP clients after 2 s; stay well
            # under that.  If firmware responds in ~10 ms (normal), 0.8 s is
            # plenty; if firmware is slow/missing we fail fast and fall back to
            # the default range instead of blocking START for 6 seconds.
            deadline = asyncio.get_running_loop().time() + 0.8
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    self.get_logger().warning(
                        f'[{self._node_id}] timed out waiting for {expected}'
                    )
                    return False
                line_bytes = await asyncio.wait_for(reader.readline(), timeout=remaining)
                line = line_bytes.decode(errors='replace').strip()
                self.get_logger().info(f'[{self._node_id}] handshake cfg: {line}')
                self._observe_control_response(line)
                if line.startswith(expected):
                    return True
                if line.startswith(('ERROR ', 'REC ERR')):
                    self.get_logger().warning(
                        f'[{self._node_id}] firmware rejected {command!r}: {line}'
                    )
                    return False
        except (asyncio.TimeoutError, Exception) as exc:
            self.get_logger().warning(
                f'[{self._node_id}] {name} confirmation error: {exc}'
            )
            return False

    async def _read_udp_frames(self) -> None:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # asyncio's Unix selector loop on the ROS 2 Humble Python runtime does
        # not expose sock_recvfrom(). Receive in a worker so UDP works on both
        # that runtime and newer Python versions.
        udp_sock.settimeout(1.0)
        udp_sock.bind(('0.0.0.0', self._udp_port))
        sample_index = 0
        try:
            while rclpy.ok():
                try:
                    data, address = await asyncio.to_thread(udp_sock.recvfrom, 4096)
                except socket.timeout:
                    continue
                if address[0] != self._host or len(data) < OE_HEADER_SIZE:
                    continue
                _off, num_bytes, _bd, elem, n_ch, n_per = OE_HEADER.unpack_from(data, 0)
                expected_bytes = n_ch * n_per * 2
                if (elem != 2 or n_ch != NUM_CHANNELS or n_per < 1
                        or num_bytes != expected_bytes or num_bytes > len(data) - OE_HEADER_SIZE):
                    continue
                self._publish_frame(data[OE_HEADER_SIZE:OE_HEADER_SIZE + num_bytes], n_ch, n_per, sample_index)
                sample_index += 1
        finally:
            udp_sock.close()

    # ── frame parsing ────────────────────────────────────────────────────────

    async def _read_frames(self, reader: asyncio.StreamReader) -> None:
        buf = bytearray()
        n_frames = 0

        while rclpy.ok():
            control_offsets = [
                offset for prefix in CONTROL_RESPONSE_PREFIXES
                if (offset := buf.find(prefix)) >= 0
            ]
            if control_offsets:
                control_offset = min(control_offsets)
                if control_offset:
                    # USB serial control text can follow a partially forwarded
                    # binary frame while the bridge pauses/resumes acquisition.
                    del buf[:control_offset]
                while b'\n' not in buf:
                    chunk = await reader.read(4096)
                    if not chunk:
                        raise EOFError('stream closed while reading recording response')
                    buf.extend(chunk)
                line, _, remainder = buf.partition(b'\n')
                buf[:] = remainder
                text = line.decode(errors='replace').strip()
                self.get_logger().info(f'[{self._node_id}] control: {text}')
                self._observe_control_response(text)
                if text.startswith((
                    'REC ', 'SLAVE_STATUS ', 'SD_STATUS ', 'SD_FINAL ',
                    'OK FREQ:', 'ERROR FREQ:', 'OK FILTER ', 'ERROR FILTER:',
                    'OK CFG ', 'ERROR CFG:',
                )):
                    await self._control_responses.put(text)
                continue

            # Accumulate header
            while len(buf) < OE_HEADER_SIZE:
                chunk = await reader.read(4096)
                if not chunk:
                    raise EOFError('stream closed')
                buf.extend(chunk)

            # A single socket read can contain a frame header followed by an
            # inline control reply. Re-enter the control scanner before using
            # the bytes after that header as sensor payload.
            if any(buf.find(prefix) >= 0 for prefix in CONTROL_RESPONSE_PREFIXES):
                continue

            if not is_valid_oe_header(buf):
                # Older Wi-Fi firmware could write an ASCII control reply
                # between the binary header and payload. After consuming that
                # line, the orphaned payload is not a frame boundary. Scan for
                # the next complete header instead of tearing down a healthy
                # TCP session and poisoning reconnect attempts.
                sync_offset = find_next_oe_header(buf, 1)
                if sync_offset is not None:
                    self.get_logger().warning(
                        f'[{self._node_id}] discarded {sync_offset} mixed-stream bytes to resync'
                    )
                    del buf[:sync_offset]
                    continue

                chunk = await reader.read(4096)
                if not chunk:
                    raise EOFError('stream closed while resynchronizing')
                buf.extend(chunk)
                if len(buf) > 8192:
                    # Retain enough bytes for a header split across reads.
                    del buf[:-(OE_HEADER_SIZE - 1)]
                continue

            _off, num_bytes, _bd, elem, n_ch, n_per = OE_HEADER.unpack_from(buf, 0)

            # Accumulate payload
            total = OE_HEADER_SIZE + num_bytes
            while len(buf) < total:
                chunk = await reader.read(4096)
                if not chunk:
                    raise EOFError('stream closed during payload')
                buf.extend(chunk)

            payload = buf[OE_HEADER_SIZE:total]
            del buf[:total]

            if elem != 2:
                # Not int16 — skip (shouldn't happen with this firmware)
                continue

            self._publish_frame(payload, n_ch, max(1, num_bytes // (n_ch * 2)))
            n_frames += 1
            if n_frames % 500 == 0:
                self.get_logger().debug(f'[{self._node_id}] {n_frames} frames published')

    def _publish_frame(self, payload: bytes, n_ch: int, n_per: int, sample_index: int = 0) -> None:
        """Parse one OE frame and publish Imu + raw topics.

        Suppresses publication entirely when confirmed sensor ranges are not
        yet known (T-09-03: nullable guard prevents misleading physical values).
        """
        # ── Guard: confirmed config must be established before publication ────
        if self._confirmed_accel_range_g is None or self._confirmed_gyro_range_dps is None:
            # Track frame receipt for health reporting but suppress all publication
            # until the handshake or a live parameter ACK establishes scale context.
            frame_time = time.monotonic()
            self._last_frame_monotonic = frame_time
            self._frame_times.append(frame_time)
            self._frames_received += 1
            return

        # Build one immutable config snapshot used for both JSON metadata and Imu.
        config = measurement_config(self._confirmed_accel_range_g,
                                    self._confirmed_gyro_range_dps)

        frame_time = time.monotonic()
        self._last_frame_monotonic = frame_time
        self._frame_times.append(frame_time)
        self._frames_received += 1

        # Channel-first layout: sample[ch * n_per + 0] is first sample of channel ch
        def s16(ch: int) -> int:
            i = ch * n_per * 2
            return int.from_bytes(payload[i:i + 2], 'little', signed=True)

        now_msg = self.get_clock().now().to_msg()

        raw_json = {
            'sample_index': sample_index,
            'seq': sample_index,
            'time_us': time.monotonic_ns() // 1000,
            'node_role': self._node_id,
            'node_id': self._node_id,
            'topic_schema': 'oe_esp32.raw.v1',
            'body_segment': self._body_segment,
            'imu': {key: s16(index) for key, index in (
                ('ax', 0), ('ay', 1), ('az', 2), ('gx', 3), ('gy', 4), ('gz', 5),
                ('mx', 6), ('my', 7), ('mz', 8),
            )},
            'quat': {key: s16(index) for key, index in (
                ('qw', 9), ('qx', 10), ('qy', 11), ('qz', 12),
            )},
            'dio': s16(13),
            'sync': {},
            'sensor_config': config_as_json(config),
        }
        raw_message = String()
        raw_message.data = json.dumps(raw_json, sort_keys=True, separators=(',', ':'))
        self._pub_raw_json.publish(raw_message)

        # ── sensor_msgs/Imu ──────────────────────────────────────────────────
        if self._publish_native and n_ch >= NUM_CHANNELS:
            imu = Imu()
            imu.header = Header()
            imu.header.stamp    = now_msg
            imu.header.frame_id = f'esp32_{self._node_id}'

            imu.orientation.w = s16(9)  * QUAT_SCALE
            imu.orientation.x = s16(10) * QUAT_SCALE
            imu.orientation.y = s16(11) * QUAT_SCALE
            imu.orientation.z = s16(12) * QUAT_SCALE

            # Use config-derived conversion (same snapshot as raw JSON sensor_config)
            imu.linear_acceleration.x = accel_count_to_mps2(s16(0), config)
            imu.linear_acceleration.y = accel_count_to_mps2(s16(1), config)
            imu.linear_acceleration.z = accel_count_to_mps2(s16(2), config)

            imu.angular_velocity.x = gyro_count_to_rad_s(s16(3), config)
            imu.angular_velocity.y = gyro_count_to_rad_s(s16(4), config)
            imu.angular_velocity.z = gyro_count_to_rad_s(s16(5), config)

            # Unknown covariance
            imu.orientation_covariance[0]          = -1.0
            imu.linear_acceleration_covariance[0]  = -1.0
            imu.angular_velocity_covariance[0]     = -1.0

            self._pub_imu.publish(imu)

        # ── std_msgs/Float32MultiArray (raw, normalised) ─────────────────────
        if self._publish_native:
            raw = Float32MultiArray()
            raw.data = [s16(c) / 32767.0 for c in range(min(n_ch, NUM_CHANNELS))]
            self._pub_raw.publish(raw)


def main(args=None):
    rclpy.init(args=args)
    node = Esp32BridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
