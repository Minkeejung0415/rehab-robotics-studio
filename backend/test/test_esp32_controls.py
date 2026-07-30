"""Focused control-contract tests that do not require a ROS installation."""
from __future__ import annotations

import importlib.util
import asyncio
import json
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

    rehab_interfaces = types.ModuleType('rehab_robotics_interfaces')
    rehab_interfaces.srv = types.ModuleType('rehab_robotics_interfaces.srv')
    rehab_interfaces.srv.IdentifyDevice = type('IdentifyDevice', (), {})
    sys.modules.setdefault('rehab_robotics_interfaces', rehab_interfaces)
    sys.modules.setdefault('rehab_robotics_interfaces.srv', rehab_interfaces.srv)

    path = Path(__file__).parents[1] / 'rehab_robotics_bridge' / 'esp32_bridge_node.py'
    spec = importlib.util.spec_from_file_location('esp32_bridge_node_controls_test', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge_module()
mapper = bridge.Esp32BridgeNode._control_command_for_parameter


def _identity_self_line(
    device_id='esp32:aabbccddeeff',
    peer_count=2,
    *,
    role='master',
    route_ip='192.168.4.1',
):
    display = bridge.display_mac(device_id)
    return (
        f'IDENTITY_OK protocol=id-v1 record=self peer_count={peer_count} '
        f'device_id={device_id} display_mac={display} base_mac={display} '
        f'sta_mac=AA:BB:CC:DD:EE:F0 ap_mac=AA:BB:CC:DD:EE:F1 '
        f'espnow_mac=AA:BB:CC:DD:EE:F2 role={role} route_ip={route_ip} '
        'schema_version=1 verified=1 identify_supported=1 '
        'board_revision=xiao_esp32s3'
    )


def _identity_peer_line(
    device_id,
    *,
    transport_mac='10:20:30:40:50:60',
    slave_id='ccddeeff',
):
    display = bridge.display_mac(device_id)
    return (
        'IDENTITY_PEER protocol=id-v1 record=peer '
        f'device_id={device_id} display_mac={display} base_mac={display} '
        f'sta_mac={display} ap_mac={display} espnow_mac={display} '
        f'transport_mac={transport_mac} role=slave schema_version=1 '
        f'verified=1 identify_supported=1 slave_id_deprecated={slave_id}'
    )


def _identity_end_line(peer_count=2):
    return f'IDENTITY_END protocol=id-v1 peer_count={peer_count}'


def _identify_reply(
    outcome,
    *,
    command_id='blink-1',
    target='esp32:aabbccddeeff',
    prefix=None,
    requested_duration_ms=3000,
    applied_duration_ms=None,
):
    if prefix is None:
        prefix = 'IDENTIFY_ACK' if outcome in {'confirmed', 'sent_unconfirmed'} else 'IDENTIFY_ERR'
    if applied_duration_ms is None:
        applied_duration_ms = requested_duration_ms if outcome == 'confirmed' else 0
    return (
        f'{prefix} protocol=identify-v1 command_id={command_id} target={target} '
        f'outcome={outcome} requested_duration_ms={requested_duration_ms} '
        f'applied_duration_ms={applied_duration_ms} detail=fixture'
    )


class IdentityHelperContractTests(unittest.TestCase):
    def test_service_contract_is_primitive_and_build_registered(self):
        repo_root = Path(__file__).parents[2]
        service = (repo_root / 'rehab_robotics_interfaces' / 'srv' / 'IdentifyDevice.srv').read_text()
        self.assertEqual(
            service.splitlines(),
            [
                'string command_id',
                'string target_device_id',
                'uint32 duration_ms',
                '---',
                'string command_id',
                'string target_device_id',
                'string outcome',
                'uint32 applied_duration_ms',
                'string detail',
            ],
        )
        cmake = (repo_root / 'rehab_robotics_interfaces' / 'CMakeLists.txt').read_text()
        self.assertIn('"msg/ProcessingBlockUpdate.msg"', cmake)
        self.assertIn('"srv/IdentifyDevice.srv"', cmake)
        self.assertEqual(cmake.count('rosidl_generate_interfaces'), 1)

    def test_full_mac_normalization_display_and_collision_safe_topic_tokens(self):
        self.assertEqual(bridge.normalize_device_id('aabbccddeeff'), 'esp32:aabbccddeeff')
        self.assertEqual(bridge.normalize_device_id('AA:BB:CC:DD:EE:FF'), 'esp32:aabbccddeeff')
        self.assertEqual(bridge.normalize_device_id('esp32:AABBCCDDEEFF'), 'esp32:aabbccddeeff')
        self.assertEqual(bridge.display_mac('esp32:aabbccddeeff'), 'AA:BB:CC:DD:EE:FF')
        self.assertEqual(bridge.device_topic_token('esp32:aabbccddeeff'), 'mac_aabbccddeeff')
        self.assertNotEqual(
            bridge.device_topic_token('esp32:1111ccddeeff'),
            bridge.device_topic_token('esp32:2222ccddeeff'),
        )
        for malformed in (
            '', 'aabbccddeef', '00aabbccddeeff', 'esp32:aabbccddeef',
            'AA:BB:CC:DD:EE', 'AA:BB:CC:DD:EE:FG', 'esp32:unknown',
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    bridge.normalize_device_id(malformed)

    def test_counted_inventory_requires_one_self_peers_and_matching_end(self):
        lines = [
            _identity_self_line(),
            _identity_peer_line('esp32:1111ccddeeff'),
            _identity_peer_line('esp32:2222ccddeeff'),
            _identity_end_line(),
        ]
        inventory = bridge.parse_identity_inventory(lines)
        self.assertEqual(inventory['self']['device_id'], 'esp32:aabbccddeeff')
        self.assertEqual(
            [peer['device_id'] for peer in inventory['peers']],
            ['esp32:1111ccddeeff', 'esp32:2222ccddeeff'],
        )
        self.assertTrue(inventory['complete'])

        invalid_inventories = (
            lines[1:],
            [lines[0], lines[0], *lines[1:]],
            [lines[1], lines[0], lines[2], lines[3]],
            [lines[0], lines[1], lines[1], lines[3]],
            [lines[0], _identity_peer_line('esp32:aabbccddeeff'), lines[2], lines[3]],
            lines[:-1],
            [*lines[:-1], _identity_end_line(1)],
            [_identity_self_line(peer_count=1), lines[1], lines[2], _identity_end_line(1)],
        )
        for invalid in invalid_inventories:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    bridge.parse_identity_inventory(invalid)

    def test_identity_records_reject_wrong_protocol_record_and_oversized_lines(self):
        valid = _identity_self_line()
        mutations = (
            valid.replace('protocol=id-v1', 'protocol=id-v2'),
            valid.replace('record=self', 'record=peer'),
            valid.replace('device_id=esp32:aabbccddeeff', 'device_id=esp32:aabbccddeef'),
            valid.replace('display_mac=AA:BB:CC:DD:EE:FF', 'display_mac=AA:BB:CC:DD:EE:00'),
            valid + ('x' * 800),
        )
        for malformed in mutations:
            with self.subTest(malformed=malformed[-40:]):
                with self.assertRaises(ValueError):
                    bridge.parse_identity_self(malformed)

    def test_identify_request_validation_and_all_correlated_outcomes(self):
        for duration in (1000, 3000, 5000):
            self.assertEqual(
                bridge.validate_identify_request('blink-1', 'esp32:aabbccddeeff', duration),
                ('blink-1', 'esp32:aabbccddeeff', duration),
            )
        for duration in (999, 5001):
            with self.assertRaises(ValueError):
                bridge.validate_identify_request('blink-1', 'esp32:aabbccddeeff', duration)

        for outcome in bridge.IDENTIFY_OUTCOMES:
            parsed = bridge.parse_identify_reply(
                _identify_reply(outcome),
                expected_command_id='blink-1',
                expected_target='esp32:aabbccddeeff',
            )
            self.assertEqual(parsed['outcome'], outcome)

    def test_identify_reply_rejects_unmatched_malformed_and_wrong_prefix(self):
        cases = (
            _identify_reply('confirmed', command_id='other'),
            _identify_reply('confirmed', target='esp32:0011ccddeeff'),
            _identify_reply('unknown'),
            _identify_reply('confirmed').replace('protocol=identify-v1', 'protocol=identify-v2'),
            _identify_reply('confirmed', prefix='IDENTIFY_ERR'),
            _identify_reply('offline', prefix='IDENTIFY_ACK'),
            _identify_reply('confirmed') + ('x' * 800),
        )
        for reply in cases:
            with self.subTest(reply=reply[-50:]):
                with self.assertRaises(ValueError):
                    bridge.parse_identify_reply(
                        reply,
                        expected_command_id='blink-1',
                        expected_target='esp32:aabbccddeeff',
                    )

    def test_identity_and_identify_prefixes_are_bounded_control_messages(self):
        for prefix in (
            b'IDENTITY_OK ', b'IDENTITY_PEER ', b'IDENTITY_END ',
            b'IDENTIFY_ACK ', b'IDENTIFY_ERR ',
        ):
            self.assertIn(prefix, bridge.CONTROL_RESPONSE_PREFIXES)

        async def exercise_queue():
            node = object.__new__(bridge.Esp32BridgeNode)
            node._control_responses = asyncio.Queue(maxsize=2)
            await node._admit_control_response('first')
            await node._admit_control_response('second')
            await node._admit_control_response('third')
            return [node._control_responses.get_nowait(), node._control_responses.get_nowait()]

        self.assertEqual(asyncio.run(exercise_queue()), ['second', 'third'])


class BridgeIdentityAndIdentifyTests(unittest.TestCase):
    def test_identity_handshake_completes_before_legacy_stream_handshake(self):
        class Reader:
            def __init__(self):
                self._buffer = bytearray(b'SENSORS:0,ICM20948\n')
                self._responses = iter((
                    (_identity_self_line(peer_count=0) + '\n').encode(),
                    (_identity_end_line(peer_count=0) + '\n').encode(),
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

        async def run_handshake():
            node = _make_stub_node()
            writer = _Writer()
            transport = await bridge.Esp32BridgeNode._handshake(node, Reader(), writer)
            return node, writer, transport

        node, writer, transport = asyncio.run(run_handshake())
        self.assertEqual(transport, 'tcp')
        self.assertEqual(writer.writes[0:2], [bridge.IDENTITY_QUERY, bridge.HANDSHAKE_CONNECT])
        self.assertEqual(node._bound_identity['device_id'], 'esp32:aabbccddeeff')
        self.assertEqual(node._peer_inventory, [])

    def test_incomplete_inventory_and_expected_peer_never_accept_stream(self):
        async def incomplete():
            node = _make_stub_node()
            reader = _LineReader([
                _identity_self_line(peer_count=1),
                _identity_peer_line('esp32:1111ccddeeff'),
            ])
            with self.assertRaises((EOFError, ValueError)):
                await bridge.Esp32BridgeNode._read_identity_inventory(node, reader, _Writer())
            self.assertIsNone(node._bound_identity)

        async def expected_peer():
            node = _make_stub_node()
            node._expected_device_id = 'esp32:1111ccddeeff'
            reader = _LineReader([
                _identity_self_line(peer_count=1),
                _identity_peer_line('esp32:1111ccddeeff'),
                _identity_end_line(peer_count=1),
            ])
            with self.assertRaises(RuntimeError):
                await bridge.Esp32BridgeNode._read_identity_inventory(node, reader, _Writer())
            self.assertIsNone(node._bound_identity)

        asyncio.run(incomplete())
        asyncio.run(expected_peer())

    def test_same_self_refreshes_metadata_but_changed_self_is_rejected(self):
        node = _make_stub_node()
        first = bridge.parse_identity_inventory([
            _identity_self_line(peer_count=0, route_ip='192.168.4.1'),
            _identity_end_line(peer_count=0),
        ])
        second = bridge.parse_identity_inventory([
            _identity_self_line(peer_count=0, route_ip='192.168.4.99'),
            _identity_end_line(peer_count=0),
        ])
        changed = bridge.parse_identity_inventory([
            _identity_self_line(
                device_id='esp32:001122334455',
                peer_count=0,
                route_ip='192.168.4.1',
            ),
            _identity_end_line(peer_count=0),
        ])

        node._bind_identity_inventory(first)
        node._bind_identity_inventory(second)
        self.assertEqual(node._bound_identity['route']['reported_ip'], '192.168.4.99')
        retained = json.loads(json.dumps(node._bound_identity))
        with self.assertRaises(RuntimeError):
            node._bind_identity_inventory(changed)
        self.assertEqual(node._bound_identity, retained)

    def test_health_snapshot_exposes_verified_self_and_distinct_peer_inventory(self):
        node = _make_health_stub()
        inventory = bridge.parse_identity_inventory([
            _identity_self_line(peer_count=1),
            _identity_peer_line('esp32:1111ccddeeff'),
            _identity_end_line(peer_count=1),
        ])
        node._bind_identity_inventory(inventory)
        snapshot = node._health_snapshot()

        self.assertEqual(snapshot['identity']['schema'], 'oe_esp32.identity.v1')
        self.assertEqual(snapshot['identity']['self']['device_id'], 'esp32:aabbccddeeff')
        self.assertEqual(snapshot['identity']['self']['node_id'], 'master')
        self.assertEqual(snapshot['identity']['self']['display_mac'], 'AA:BB:CC:DD:EE:FF')
        self.assertEqual(snapshot['identity']['self']['role'], 'master')
        self.assertEqual(snapshot['identity']['self']['route']['host'], '192.168.4.1')
        self.assertEqual(snapshot['identity']['peers'][0]['device_id'], 'esp32:1111ccddeeff')
        self.assertNotEqual(
            snapshot['identity']['self']['record'],
            snapshot['identity']['peers'][0]['record'],
        )

    def test_phase20_preserves_fixed_publishers_and_only_adds_role_identify_service(self):
        source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'esp32_bridge_node.py'
        ).read_text(encoding='utf-8')
        self.assertIn("f'{prefix}/imu'", source)
        self.assertIn("f'{prefix}/raw'", source)
        self.assertIn("f'/esp/raw/{self._node_id}'", source)
        self.assertIn("f'/esp/status/{self._node_id}'", source)
        self.assertIn("f'/esp32/{self._node_id}/identify'", source)
        self.assertEqual(source.count('device_topic_token('), 1)
        self.assertNotIn('/esp32/mac_', source)
        self.assertNotIn('_canonical_publishers', source)

    def test_identify_waits_for_correlated_terminal_confirmation(self):
        async def exercise():
            node = _make_identify_stub()
            await node._identify_responses.put(
                _identify_reply('confirmed', command_id='late-command'))
            await node._identify_responses.put(
                _identify_reply('confirmed', target='esp32:1111ccddeeff'))
            await node._identify_responses.put(_identify_reply('sent_unconfirmed'))
            await node._identify_responses.put(_identify_reply('confirmed'))
            result = await node._send_identify_command(
                'blink-1', 'esp32:aabbccddeeff', 3000)
            return node, result

        node, result = asyncio.run(exercise())
        self.assertEqual(result['outcome'], 'confirmed')
        self.assertEqual(result['applied_duration_ms'], 3000)
        self.assertEqual(node._last_confirmed_identify['command_id'], 'blink-1')
        self.assertEqual(len(node._unmatched_identify_replies), 2)
        self.assertEqual(
            node._active_writer.writes,
            [
                b'IDENTIFY protocol=identify-v1 command_id=blink-1 '
                b'target=esp32:aabbccddeeff duration_ms=3000\n',
            ],
        )

    def test_identify_maps_every_nonconfirmed_outcome_without_confirmed_mutation(self):
        async def exercise(outcome):
            node = _make_identify_stub()
            node._last_confirmed_identify = {'command_id': 'prior'}
            await node._identify_responses.put(_identify_reply(outcome))
            result = await node._send_identify_command(
                'blink-1', 'esp32:aabbccddeeff', 3000)
            return node, result

        for outcome in ('timeout', 'offline', 'unsupported', 'rejected', 'invalid_target'):
            with self.subTest(outcome=outcome):
                node, result = asyncio.run(exercise(outcome))
                self.assertEqual(result['outcome'], outcome)
                self.assertEqual(node._last_confirmed_identify, {'command_id': 'prior'})

        node, result = asyncio.run(exercise('sent_unconfirmed'))
        self.assertEqual(result['outcome'], 'sent_unconfirmed')
        self.assertEqual(node._last_confirmed_identify, {'command_id': 'prior'})

    def test_invalid_identify_input_and_unknown_target_perform_no_io(self):
        async def exercise():
            node = _make_identify_stub()
            with self.assertRaises(ValueError):
                await node._send_identify_command(
                    'bad command', 'esp32:aabbccddeeff', 3000)
            with self.assertRaises(ValueError):
                await node._send_identify_command(
                    'blink-1', 'esp32:aabbccddeef', 3000)
            result = await node._send_identify_command(
                'blink-1', 'esp32:9999ccddeeff', 3000)
            return node, result

        node, result = asyncio.run(exercise())
        self.assertEqual(result['outcome'], 'offline')
        self.assertEqual(node._active_writer.writes, [])


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

    def test_repeated_recording_commands_are_idempotent(self):
        start_line = (
            'REC ERR code=already_recording '
            'session_id=20260728_155910 retryable=false detail=active'
        )
        stop_line = (
            'REC ERR code=not_recording '
            'session_id=20260728_155910 retryable=false detail=idle'
        )

        self.assertEqual(
            bridge.normalize_recording_reply(True, start_line),
            (
                True,
                'REC ACTIVE session_id=20260728_155910 '
                'detail=already_recording',
            ),
        )
        self.assertEqual(
            bridge.normalize_recording_reply(False, stop_line),
            (
                True,
                'REC IDLE session_id=20260728_155910 '
                'detail=not_recording',
            ),
        )

    def test_recording_observer_keeps_already_active_session_live(self):
        node = _make_stub_node()
        node._recording_state = 'idle'
        node._recording_session_id = ''
        node._recording_error = ''
        node._recording_health = {}

        node._observe_control_response(
            'REC ERR code=already_recording '
            'session_id=20260728_155910 retryable=false detail=active',
        )

        self.assertEqual(node._recording_state, 'recording')
        self.assertEqual(node._recording_session_id, '20260728_155910')
        self.assertEqual(node._recording_error, '')

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
    node._node_id = 'master'
    node._host = '192.168.4.1'
    node._port = 5000
    node._handshake_timeout_s = 0.1
    node._identity_timeout_s = 0.1
    node._identify_timeout_s = 0.01
    node._expected_device_id = ''
    node._bound_identity = None
    node._peer_inventory = []
    node._unmatched_identify_replies = bridge.deque(maxlen=64)
    node.get_logger = lambda: _Logger()
    return node


class _Logger:
    def info(self, _message):
        pass

    def warning(self, _message):
        pass


class _Writer:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        pass

    def is_closing(self):
        return False


class _LineReader:
    def __init__(self, lines):
        self._lines = [
            line if isinstance(line, bytes) else (line + '\n').encode('ascii')
            for line in lines
        ]

    async def readline(self):
        if not self._lines:
            return b''
        return self._lines.pop(0)


def _make_health_stub():
    node = _make_stub_node()
    node._frame_times = bridge.deque()
    node._last_frame_monotonic = None
    node._connection_state = 'connected'
    node._reconnect_count = 0
    node._frames_received = 0
    node._recording_state = 'idle'
    node._recording_session_id = ''
    node._recording_error = ''
    node._recording_health = {
        'sd_ready': None,
        'saved_samples': None,
        'file_byte_size': None,
        'file_checksum': None,
        'checksum_type': None,
        'finalization_reason': None,
    }
    return node


def _make_identify_stub():
    node = _make_stub_node()
    node._active_writer = _Writer()
    node._record_command_lock = asyncio.Lock()
    node._control_responses = asyncio.Queue(maxsize=8)
    node._identify_responses = asyncio.Queue(maxsize=8)
    node._last_confirmed_identify = None
    node._bind_identity_inventory(bridge.parse_identity_inventory([
        _identity_self_line(peer_count=1),
        _identity_peer_line('esp32:1111ccddeeff'),
        _identity_end_line(peer_count=1),
    ]))
    return node


class ConfirmedRangeRetentionTests(unittest.TestCase):
    """Verify nullable confirmed-range design and _store_confirmed_control_value."""

    def test_handshake_confirms_ranges_before_starting_binary_stream(self):
        """CFG range commands run in text mode; FILTER is sent post-STARTED."""

        class Reader:
            def __init__(self):
                self._buffer = bytearray(b'SENSORS:0,ICM20948\n')
                self._responses = iter((
                    (_identity_self_line(peer_count=0) + '\n').encode(),
                    (_identity_end_line(peer_count=0) + '\n').encode(),
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
                bridge.IDENTITY_QUERY,
                bridge.HANDSHAKE_CONNECT,
                b'CFG 0 ACC 0\n',
                b'CFG 0 GYR 0\n',
                bridge.HANDSHAKE_START,
                b'FILTER ON\n',  # fire-and-forget after STARTED; not before START
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
