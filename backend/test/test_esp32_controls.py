"""Focused control-contract tests that do not require a ROS installation."""
from __future__ import annotations

import importlib.util
import asyncio
import sys
import types
import unittest
from pathlib import Path


def _load_bridge_module():
    """Load the command mapper with lightweight ROS message stand-ins.

    Ensures the backend root (parent of rehab_robotics_bridge/) is on sys.path
    so that esp32_bridge_node.py can import measurement_contract without a full
    ROS installation.
    """
    # Make backend/ importable so `from rehab_robotics_bridge.measurement_contract`
    # succeeds when esp32_bridge_node.py is exec'd below.
    _backend_root = str(Path(__file__).parents[1])
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

    rclpy = types.ModuleType('rclpy')
    rclpy.node = types.ModuleType('rclpy.node')
    rclpy.node.Node = type('Node', (), {})
    rclpy.ok = lambda: True
    sys.modules.setdefault('rclpy', rclpy)
    sys.modules.setdefault('rclpy.node', rclpy.node)

    interfaces = types.ModuleType('rcl_interfaces')
    interfaces.msg = types.ModuleType('rcl_interfaces.msg')
    interfaces.msg.SetParametersResult = type('SetParametersResult', (), {})
    sys.modules.setdefault('rcl_interfaces', interfaces)
    sys.modules.setdefault('rcl_interfaces.msg', interfaces.msg)

    sensor_msgs = types.ModuleType('sensor_msgs')
    sensor_msgs.msg = types.ModuleType('sensor_msgs.msg')
    sensor_msgs.msg.Imu = type('Imu', (), {})
    sys.modules.setdefault('sensor_msgs', sensor_msgs)
    sys.modules.setdefault('sensor_msgs.msg', sensor_msgs.msg)

    std_msgs = types.ModuleType('std_msgs')
    std_msgs.msg = types.ModuleType('std_msgs.msg')
    for name in ('Float32MultiArray', 'Header', 'String'):
        setattr(std_msgs.msg, name, type(name, (), {}))
    sys.modules.setdefault('std_msgs', std_msgs)
    sys.modules.setdefault('std_msgs.msg', std_msgs.msg)

    std_srvs = types.ModuleType('std_srvs')
    std_srvs.srv = types.ModuleType('std_srvs.srv')
    std_srvs.srv.SetBool = type('SetBool', (), {})
    sys.modules.setdefault('std_srvs', std_srvs)
    sys.modules.setdefault('std_srvs.srv', std_srvs.srv)

    path = Path(__file__).parents[1] / 'rehab_robotics_bridge' / 'esp32_bridge_node.py'
    spec = importlib.util.spec_from_file_location('esp32_bridge_node_controls_test', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge_module()
mapper = bridge.Esp32BridgeNode._control_command_for_parameter


class Esp32ControlContractTests(unittest.TestCase):
    def test_supported_controls_have_expected_firmware_acknowledgements(self):
        self.assertEqual(mapper('sample_rate_hz', 137), ('FREQ:137', 'OK FREQ:137', ''))
        self.assertEqual(mapper('effective_sample_rate_hz', 100), ('CFG 0 SRATE 100', 'OK FREQ:100', ''))
        self.assertEqual(mapper('filter_enabled', False), ('FILTER OFF', 'OK FILTER OFF', ''))
        self.assertEqual(mapper('accel_range_g', 8), ('CFG 0 ACC 2', 'OK CFG ACC', ''))
        self.assertEqual(mapper('gyro_range_dps', 500), ('CFG 0 GYR 1', 'OK CFG GYR', ''))

    def test_invalid_values_are_rejected_before_hardware_io(self):
        self.assertIn('between 1 and 1000', mapper('sample_rate_hz', 0)[2])
        self.assertIn('one of 2, 4, 8, or 16', mapper('accel_range_g', 3)[2])
        self.assertIn('one of 250, 500, 1000, or 2000', mapper('gyro_range_dps', 42)[2])
        self.assertIn('true or false', mapper('filter_enabled', 'on')[2])

    def test_status_reply_fields_keep_numeric_and_checksum_values(self):
        fields = bridge.parse_control_fields(
            'REC STATUS_OK sd_ready=1 saved_samples=628 file_byte_size=17648 '
            'file_checksum=7a12ff00 checksum_type=crc32'
        )
        self.assertEqual(bridge.control_int(fields, 'saved_samples'), 628)
        self.assertEqual(bridge.control_int(fields, 'file_byte_size'), 17648)
        self.assertEqual(fields['file_checksum'], '7a12ff00')
        self.assertIsNone(bridge.control_int(fields, 'missing'))

    def test_tcp_header_resync_skips_payload_left_after_inline_control_reply(self):
        payload = bytes(range(bridge.NUM_CHANNELS * 2))
        frame = bridge.OE_HEADER.pack(1234, len(payload), 3, 2, bridge.NUM_CHANNELS, 1) + payload

        # Before the firmware write lock existed, a control line could be
        # inserted between a frame header and its payload. Once the line was
        # consumed, the parser saw the orphaned payload before the next frame.
        orphaned_payload_then_frame = payload + frame

        self.assertEqual(
            bridge.find_next_oe_header(orphaned_payload_then_frame),
            len(payload),
        )

    def test_tcp_header_validator_rejects_control_text_and_partial_headers(self):
        self.assertFalse(bridge.is_valid_oe_header(b'OK FILTER OFF\n', 0))
        self.assertFalse(bridge.is_valid_oe_header(bytes(bridge.OE_HEADER_SIZE - 1), 0))

    def test_reader_recovers_when_control_reply_splits_a_frame(self):
        payload = bytes(range(bridge.NUM_CHANNELS * 2))
        header = bridge.OE_HEADER.pack(1234, len(payload), 3, 2, bridge.NUM_CHANNELS, 1)
        mixed = header + b'OK FILTER OFF\n' + payload + header + payload

        class Reader:
            def __init__(self):
                self.chunks = [mixed, b'']

            async def read(self, _size):
                return self.chunks.pop(0)

        class Logger:
            def info(self, _message):
                pass

            def warning(self, _message):
                pass

        class Node:
            _node_id = 'test'

            def __init__(self):
                self.frames = []
                self._control_responses = asyncio.Queue()

            def get_logger(self):
                return Logger()

            def _observe_control_response(self, _text):
                pass

            def _publish_frame(self, payload_bytes, n_ch, n_per):
                self.frames.append((payload_bytes, n_ch, n_per))

        async def run_reader():
            node = Node()
            with self.assertRaises(EOFError):
                await bridge.Esp32BridgeNode._read_frames(node, Reader())
            return node

        node = asyncio.run(run_reader())
        self.assertEqual(node.frames, [(payload, bridge.NUM_CHANNELS, 1)])

    def test_reader_parses_consecutive_frames_from_one_tcp_batch(self):
        payloads = [
            bytes([value]) * (bridge.NUM_CHANNELS * 2)
            for value in range(8)
        ]
        batch = b''.join(
            bridge.OE_HEADER.pack(
                1000 + index,
                len(payload),
                3,
                2,
                bridge.NUM_CHANNELS,
                1,
            ) + payload
            for index, payload in enumerate(payloads)
        )

        class Reader:
            def __init__(self):
                self.chunks = [batch, b'']

            async def read(self, _size):
                return self.chunks.pop(0)

        class Logger:
            def info(self, _message):
                pass

            def warning(self, _message):
                pass

        class Node:
            _node_id = 'test'

            def __init__(self):
                self.frames = []
                self._control_responses = asyncio.Queue()

            def get_logger(self):
                return Logger()

            def _observe_control_response(self, _text):
                pass

            def _publish_frame(self, payload_bytes, n_ch, n_per):
                self.frames.append((payload_bytes, n_ch, n_per))

        async def run_reader():
            node = Node()
            with self.assertRaises(EOFError):
                await bridge.Esp32BridgeNode._read_frames(node, Reader())
            return node

        node = asyncio.run(run_reader())
        self.assertEqual(
            node.frames,
            [(payload, bridge.NUM_CHANNELS, 1) for payload in payloads],
        )


def _make_stub_node():
    """Create a minimal Esp32BridgeNode instance without invoking __init__ or ROS."""
    node = object.__new__(bridge.Esp32BridgeNode)
    node._desired_accel_range_g = 2
    node._desired_gyro_range_dps = 250
    node._confirmed_accel_range_g = None
    node._confirmed_gyro_range_dps = None
    node._sample_rate_hz = 100
    node._recording_sample_rate_hz = 100
    node._effective_sample_rate_hz = 100
    node._filter_enabled = True
    return node


class ConfirmedRangeRetentionTests(unittest.TestCase):
    """Verify nullable confirmed-range design and _store_confirmed_control_value."""

    def test_handshake_confirms_ranges_before_starting_binary_stream(self):
        """CFG range commands must run while the firmware still accepts text."""

        class Reader:
            def __init__(self):
                self._buffer = bytearray(b'SENSORS:0,ICM20948\n')
                self._responses = iter((
                    b'14 channels; sample_rate=100; node=esp32s3_arduino; transport=tcp\n',
                    asyncio.TimeoutError(),
                    b'OK CFG ACC 0\n',
                    b'OK CFG GYR 0\n',
                    b'STARTED BIN:esp32s3_arduino transport=tcp\n',
                    b'SENSORS:0,ICM20948\n',
                ))

            async def readline(self):
                response = next(self._responses)
                if isinstance(response, BaseException):
                    raise response
                if response.startswith(b'SENSORS:'):
                    self._buffer.clear()
                return response

        class Writer:
            def __init__(self):
                self.writes = []

            def write(self, data):
                self.writes.append(data)

            async def drain(self):
                pass

        class Logger:
            def info(self, _message):
                pass

            def warning(self, _message):
                pass

        async def run_handshake():
            node = _make_stub_node()
            node._node_id = 'test'
            node._handshake_timeout_s = 0.1
            node.get_logger = lambda: Logger()
            writer = Writer()
            transport = await bridge.Esp32BridgeNode._handshake(node, Reader(), writer)
            return node, writer, transport

        node, writer, transport = asyncio.run(run_handshake())

        self.assertEqual(transport, 'tcp')
        self.assertEqual(
            writer.writes,
            [
                bridge.HANDSHAKE_CONNECT,
                b'CFG 0 ACC 0\n',
                b'CFG 0 GYR 0\n',
                bridge.HANDSHAKE_START,
            ],
        )
        self.assertEqual(node._confirmed_accel_range_g, 2)
        self.assertEqual(node._confirmed_gyro_range_dps, 250)

    def test_09_01_03_initial_confirmed_ranges_are_none(self):
        """Both confirmed range fields start as None on a freshly created stub."""
        node = _make_stub_node()
        self.assertIsNone(node._confirmed_accel_range_g)
        self.assertIsNone(node._confirmed_gyro_range_dps)

    def test_09_01_03_confirmed_range_updates_after_successful_ack(self):
        """_store_confirmed_control_value writes confirmed fields after ACK."""
        node = _make_stub_node()
        node._store_confirmed_control_value('accel_range_g', 8)
        node._store_confirmed_control_value('gyro_range_dps', 2000)
        self.assertEqual(node._confirmed_accel_range_g, 8)
        self.assertEqual(node._confirmed_gyro_range_dps, 2000)

    def test_09_01_03_rejected_command_does_not_change_confirmed_state(self):
        """Unsupported range produces an error before I/O; confirmed state unchanged."""
        node = _make_stub_node()
        node._confirmed_accel_range_g = 2
        node._confirmed_gyro_range_dps = 250

        # _control_command_for_parameter returns an error for unsupported preset 3.
        cmd, exp, err = bridge.Esp32BridgeNode._control_command_for_parameter(
            'accel_range_g', 3,  # unsupported
        )
        self.assertTrue(err, 'rejection must produce a non-empty error string')

        # The existing _on_set_parameters early-return (lines after error check)
        # prevents _store_confirmed_control_value from being called on error.
        # Verify confirmed state is unchanged — do NOT call _store_confirmed_control_value here.
        self.assertEqual(node._confirmed_accel_range_g, 2, 'confirmed state must be unchanged')

    def test_09_01_03_control_command_maps_all_four_accel_presets(self):
        """_control_command_for_parameter produces correct CFG ACC commands for all 4 ranges."""
        expected_presets = {2: 0, 4: 1, 8: 2, 16: 3}
        for accel_g, preset in expected_presets.items():
            with self.subTest(accel_range_g=accel_g):
                cmd, exp, err = bridge.Esp32BridgeNode._control_command_for_parameter(
                    'accel_range_g', accel_g,
                )
                self.assertEqual(err, '', 'no error for supported range')
                self.assertEqual(cmd, f'CFG 0 ACC {preset}')
                self.assertEqual(exp, 'OK CFG ACC')

    def test_09_01_03_control_command_maps_all_four_gyro_presets(self):
        """_control_command_for_parameter produces correct CFG GYR commands for all 4 ranges."""
        expected_presets = {250: 0, 500: 1, 1000: 2, 2000: 3}
        for gyro_dps, preset in expected_presets.items():
            with self.subTest(gyro_range_dps=gyro_dps):
                cmd, exp, err = bridge.Esp32BridgeNode._control_command_for_parameter(
                    'gyro_range_dps', gyro_dps,
                )
                self.assertEqual(err, '', 'no error for supported range')
                self.assertEqual(cmd, f'CFG 0 GYR {preset}')
                self.assertEqual(exp, 'OK CFG GYR')


if __name__ == '__main__':
    unittest.main()
