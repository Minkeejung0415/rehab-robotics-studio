"""
ESP32 Bridge Node

Connects to one ESP32 node's TCP stream (step_node firmware v1.8+),
parses 14-channel Open Ephys binary frames, and publishes:

  /esp32/{node_id}/imu   →  sensor_msgs/Imu  (VQF-fused quat + raw accel/gyro)
  /esp32/{node_id}/raw   →  std_msgs/Float32MultiArray  (all 14 ch, normalised)

Channel map (step_node firmware, NUM_CHANNELS=14):
  ch[ 0- 2]  accel X/Y/Z    raw int16, default ±2g    → ÷16384 × 9.80665  m/s²
  ch[ 3- 5]  gyro  X/Y/Z    raw int16, default ±250dps → ÷131.072 × π/180  rad/s
  ch[ 6- 8]  mag   X/Y/Z    raw int16  (0 if no magnetometer)
  ch[ 9-12]  quat  W/X/Y/Z  Q15 int16 → ÷32767  (VQF-fused)
  ch[13]     DIO             packed int16 (edge count + stable state)

WiFi mode (default):
  PC joins STEP_ESP32 WiFi (pass: step1234), connects to 192.168.4.1:5000

USB mode:
  Run Plugin repo: python3 esp32/host/serial_tcp_bridge.py COM5 --plugin
  Then set host=127.0.0.1 below (or via ROS param)

Usage:
  ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args \\
    -p node_id:=master \\
    -p host:=192.168.4.1 \\
    -p port:=5000
"""
from __future__ import annotations

import asyncio
import contextlib
import math
import struct
import threading
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32MultiArray, Header

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

# ── Handshake strings the firmware expects ───────────────────────────────────
HANDSHAKE_CONNECT = b'REDPITAYA\n'
HANDSHAKE_START   = b'START\n'


class Esp32BridgeNode(Node):
    def __init__(self) -> None:
        super().__init__('esp32_bridge_node')

        self.declare_parameter('node_id', 'master')
        self.declare_parameter('host', '192.168.4.1')
        self.declare_parameter('port', 5000)
        self.declare_parameter('reconnect_delay_s', 5.0)

        self._node_id: str = self.get_parameter('node_id').value
        self._host: str   = self.get_parameter('host').value
        self._port: int   = self.get_parameter('port').value
        self._reconnect_s: float = self.get_parameter('reconnect_delay_s').value

        prefix = f'/esp32/{self._node_id}'
        self._pub_imu = self.create_publisher(Imu,               f'{prefix}/imu', 10)
        self._pub_raw = self.create_publisher(Float32MultiArray, f'{prefix}/raw', 10)

        self.get_logger().info(
            f'[{self._node_id}] → {self._host}:{self._port} | '
            f'topics: {prefix}/imu  {prefix}/raw'
        )

        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_until_complete,
                         args=(self._reconnect_forever(),),
                         daemon=True).start()

    # ── connection management ────────────────────────────────────────────────

    async def _reconnect_forever(self) -> None:
        while rclpy.ok():
            try:
                await self._connect_and_stream()
            except Exception as exc:
                self.get_logger().warning(
                    f'[{self._node_id}] connection lost: {exc} — '
                    f'retrying in {self._reconnect_s:.0f} s'
                )
            await asyncio.sleep(self._reconnect_s)

    async def _connect_and_stream(self) -> None:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        self.get_logger().info(f'[{self._node_id}] connected to {self._host}:{self._port}')

        try:
            await self._handshake(reader, writer)
            await self._read_frames(reader)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            self.get_logger().info(f'[{self._node_id}] disconnected')

    async def _handshake(self, reader: asyncio.StreamReader,
                         writer: asyncio.StreamWriter) -> None:
        """Exchange REDPITAYA / SENSORS / START as the firmware expects."""
        writer.write(HANDSHAKE_CONNECT)
        await writer.drain()

        # Firmware replies with STARTED and SENSORS lines
        for _ in range(3):
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            self.get_logger().debug(f'[{self._node_id}] hs< {line.strip()}')
            if line.upper().startswith(b'SENSORS'):
                break

        writer.write(HANDSHAKE_START)
        await writer.drain()

        ack = await asyncio.wait_for(reader.readline(), timeout=5.0)
        self.get_logger().info(f'[{self._node_id}] start ack: {ack.strip()}')

    # ── frame parsing ────────────────────────────────────────────────────────

    async def _read_frames(self, reader: asyncio.StreamReader) -> None:
        buf = bytearray()
        n_frames = 0

        while rclpy.ok():
            # Accumulate header
            while len(buf) < OE_HEADER_SIZE:
                chunk = await reader.read(4096)
                if not chunk:
                    raise EOFError('stream closed')
                buf.extend(chunk)

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

    def _publish_frame(self, payload: bytes, n_ch: int, n_per: int) -> None:
        """Parse one OE frame and publish Imu + raw topics."""
        # Channel-first layout: sample[ch * n_per + 0] is first sample of channel ch
        def s16(ch: int) -> int:
            i = ch * n_per * 2
            return int.from_bytes(payload[i:i + 2], 'little', signed=True)

        now_msg = self.get_clock().now().to_msg()

        # ── sensor_msgs/Imu ──────────────────────────────────────────────────
        if n_ch >= NUM_CHANNELS:
            imu = Imu()
            imu.header = Header()
            imu.header.stamp    = now_msg
            imu.header.frame_id = f'esp32_{self._node_id}'

            imu.orientation.w = s16(9)  * QUAT_SCALE
            imu.orientation.x = s16(10) * QUAT_SCALE
            imu.orientation.y = s16(11) * QUAT_SCALE
            imu.orientation.z = s16(12) * QUAT_SCALE

            imu.linear_acceleration.x = s16(0) * ACC_SCALE
            imu.linear_acceleration.y = s16(1) * ACC_SCALE
            imu.linear_acceleration.z = s16(2) * ACC_SCALE

            imu.angular_velocity.x = s16(3) * GYR_SCALE
            imu.angular_velocity.y = s16(4) * GYR_SCALE
            imu.angular_velocity.z = s16(5) * GYR_SCALE

            # Unknown covariance
            imu.orientation_covariance[0]          = -1.0
            imu.linear_acceleration_covariance[0]  = -1.0
            imu.angular_velocity_covariance[0]     = -1.0

            self._pub_imu.publish(imu)

        # ── std_msgs/Float32MultiArray (raw, normalised) ─────────────────────
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
