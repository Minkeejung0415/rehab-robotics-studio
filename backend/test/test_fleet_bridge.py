"""Fleet registry and canonical mac_ topic contracts (no live ROS / STEP_ESP32)."""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

def _install_ros_stubs() -> None:
    _backend_root = str(Path(__file__).parents[1])
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

    rclpy = types.ModuleType('rclpy')
    rclpy.node = types.ModuleType('rclpy.node')
    rclpy.node.Node = type('Node', (), {})
    rclpy.qos = types.ModuleType('rclpy.qos')
    rclpy.qos.HistoryPolicy = types.SimpleNamespace(KEEP_LAST='keep_last')
    rclpy.qos.DurabilityPolicy = types.SimpleNamespace(TRANSIENT_LOCAL='transient_local')
    rclpy.qos.ReliabilityPolicy = types.SimpleNamespace(RELIABLE='reliable')
    rclpy.qos.QoSProfile = type('QoSProfile', (), {
        '__init__': lambda self, **kwargs: self.__dict__.update(kwargs),
    })
    rclpy.ok = lambda: True
    rclpy.init = lambda *a, **k: None
    rclpy.spin = lambda *a, **k: None
    rclpy.try_shutdown = lambda *a, **k: None
    sys.modules.setdefault('rclpy', rclpy)
    sys.modules.setdefault('rclpy.node', rclpy.node)
    sys.modules.setdefault('rclpy.qos', rclpy.qos)

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

    std_msgs = sys.modules.setdefault('std_msgs', types.ModuleType('std_msgs'))
    std_msgs.msg = sys.modules.setdefault(
        'std_msgs.msg', getattr(std_msgs, 'msg', types.ModuleType('std_msgs.msg'))
    )
    for name in ('Float32MultiArray', 'Header', 'String'):
        if not hasattr(std_msgs.msg, name):
            setattr(std_msgs.msg, name, type(name, (), {'__init__': lambda self, **kw: None}))

    std_srvs = types.ModuleType('std_srvs')
    std_srvs.srv = types.ModuleType('std_srvs.srv')
    std_srvs.srv.SetBool = type('SetBool', (), {})
    sys.modules.setdefault('std_srvs', std_srvs)
    sys.modules.setdefault('std_srvs.srv', std_srvs.srv)

    rehab_interfaces = sys.modules.setdefault(
        'rehab_robotics_interfaces', types.ModuleType('rehab_robotics_interfaces')
    )
    rehab_interfaces.srv = sys.modules.setdefault(
        'rehab_robotics_interfaces.srv',
        getattr(rehab_interfaces, 'srv', types.ModuleType('rehab_robotics_interfaces.srv')),
    )
    rehab_interfaces.srv.IdentifyDevice = type('IdentifyDevice', (), {})


def _load_fleet_module():
    _install_ros_stubs()
    path = Path(__file__).parents[1] / 'rehab_robotics_bridge' / 'fleet_bridge_node.py'
    spec = importlib.util.spec_from_file_location('fleet_bridge_node_test', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_install_ros_stubs()
from backend.test.test_esp32_controls import _load_bridge_module

bridge = _load_bridge_module()
fleet = _load_fleet_module()


LAYERED_FIELDS = (
    'discovery',
    'command',
    'route',
    'orientation_freshness',
    'synchronization',
    'rate',
)


class FleetSignalStatusProtocolTest(unittest.TestCase):
    """Resolved source-capability and unchanged-frame contracts for Phase 26."""

    DEVICE_ID = 'esp32:aabbccddeeff'
    VALID_STATUS = (
        'SIGNAL_STATUS_OK protocol=signal-cap-v1 '
        'device_id=esp32:aabbccddeeff accel=1 gyro=1 magnetometer=1 '
        'quaternion=1 magnetometer_model=AK09916 '
        'magnetometer_sensitivity_uT_per_count=0.15 '
        'sequence_transport=none acquisition_clock=none'
    )

    def _parser(self):
        parser = getattr(fleet, 'parse_signal_status', None)
        self.assertIsNotNone(
            parser,
            'signal_status_protocol absent: parse_signal_status is required',
        )
        return parser

    def test_signal_status_protocol_accepts_only_identity_bound_device_facts(self):
        parsed = self._parser()(self.VALID_STATUS, self.DEVICE_ID)
        self.assertEqual(parsed['protocol'], 'signal-cap-v1')
        self.assertEqual(parsed['device_id'], self.DEVICE_ID)
        self.assertEqual(
            parsed['capabilities'],
            {'accel': True, 'gyro': True, 'magnetometer': True, 'quaternion': True},
        )
        self.assertEqual(parsed['magnetometer_model'], 'AK09916')
        self.assertEqual(parsed['magnetometer_sensitivity_uT_per_count'], 0.15)
        self.assertEqual(parsed['sequence_transport'], 'none')
        self.assertEqual(parsed['acquisition_clock'], 'none')

    def test_signal_status_protocol_rejects_old_malformed_duplicate_and_wrong_mac(self):
        parser = self._parser()
        cases = {
            'old_firmware': 'STATUS icm_ok=1 mag_ok=1 filter=1',
            'malformed': self.VALID_STATUS.replace(' accel=1', ' accel=yes'),
            'duplicate': self.VALID_STATUS + ' accel=1',
            'wrong_mac': self.VALID_STATUS.replace(self.DEVICE_ID, 'esp32:112233445566'),
            'missing_field': self.VALID_STATUS.replace(' sequence_transport=none', ''),
        }
        for name, line in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                parser(line, self.DEVICE_ID)

    def test_signal_status_protocol_route_capabilities_are_expectation_only(self):
        parser = self._parser()
        expected = {'accel': True, 'gyro': True, 'magnetometer': False, 'quaternion': True}
        with self.assertRaisesRegex(ValueError, '^capability_expectation_mismatch$'):
            parser(self.VALID_STATUS, self.DEVICE_ID, expected_capabilities=expected)
        accepted = parser(self.VALID_STATUS, self.DEVICE_ID)
        self.assertTrue(accepted['capabilities']['magnetometer'])

    def test_signal_status_protocol_frame_bytes_remain_oe_header_plus_14_int16(self):
        values = tuple(range(-7, 7))
        payload = struct.pack('<14h', *values)
        frame = fleet.OE_HEADER.pack(0, len(payload), 0, 2, 14, 1) + payload
        self.assertEqual(len(frame), fleet.OE_HEADER_SIZE + 28)
        self.assertEqual(frame[fleet.OE_HEADER_SIZE:], payload)
        self.assertNotIn(struct.pack('<I', 0xA1B2C3D4), frame)
        master_source = (Path(__file__).parents[2] / 'firmware' / 'step_node' / 'step_node.ino').read_text(encoding='utf-8')
        self.assertIn('uint32_t seq;', master_source)
        self.assertIn('struct StreamRecord', master_source)

    def test_signal_status_protocol_calibration_authorizes_microtesla_only_when_valid(self):
        loader = getattr(fleet, 'load_signal_calibrations', None)
        self.assertIsNotNone(loader, 'signal_status_protocol absent: load_signal_calibrations is required')
        valid = {
            'schema': 'rehab.mag_calibration.1', 'device_id': self.DEVICE_ID,
            'sensor_model': 'AK09916', 'axis_convention': 'xyz',
            'calibration_id': 'lab-2026-08-16',
            'calibration_hash': 'sha256:' + 'a' * 64,
            'hard_iron_uT': [1.0, 2.0, 3.0],
            'soft_iron': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        }
        invalid = {
            'missing': None, 'hash_invalid': {**valid, 'calibration_hash': 'bad'},
            'mac_mismatch': {**valid, 'device_id': 'esp32:112233445566'},
            'axis_invalid': {**valid, 'axis_convention': 'zyx'},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'calibration.json'
            path.write_text(json.dumps(valid), encoding='utf-8')
            loaded = loader(str(path), expected_device_id=self.DEVICE_ID)
            self.assertEqual(loaded[self.DEVICE_ID]['calibration_hash'], valid['calibration_hash'])
            for name, artifact in invalid.items():
                with self.subTest(name=name):
                    if artifact is None:
                        self.assertEqual(loader('', expected_device_id=self.DEVICE_ID), {})
                        continue
                    path.write_text(json.dumps(artifact), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        loader(str(path), expected_device_id=self.DEVICE_ID)


class FleetAppliedMappingProvenanceTest(unittest.TestCase):
    DEVICE_ID = 'esp32:aabbccddeeff'
    MODEL_HASH = 'sha256:' + 'b' * 64

    def _document(self, *, draft_frame='draft_frame', applied_frame='femur_r_imu'):
        return {
            'schema_version': 'map.v1',
            'revision': 9,
            'assignments': {
                self.DEVICE_ID: {
                    'state': 'assigned', 'segment': 'draft_segment', 'frame': draft_frame,
                },
            },
            'applied_revision': 3,
            'applied_assignments': {
                self.DEVICE_ID: {
                    'state': 'assigned', 'segment': 'femur_r', 'frame': applied_frame,
                },
            },
            'model_hash': self.MODEL_HASH,
        }

    def test_applied_provenance_ignores_draft_and_snapshots_authoritative_fields(self):
        cache = fleet.AppliedMappingCache()
        self.assertTrue(cache.update(self._document()))
        first = cache.snapshot(self.DEVICE_ID)
        self.assertEqual(first['revision'], 3)
        self.assertEqual(first['segment'], 'femur_r')
        self.assertEqual(first['frame'], 'femur_r_imu')
        self.assertEqual(first['model_hash'], self.MODEL_HASH)
        self.assertEqual(cache.epoch, 1)

        draft_only = self._document(draft_frame='another_draft')
        draft_only['revision'] = 10
        self.assertFalse(cache.update(draft_only))
        self.assertEqual(cache.epoch, 1)
        self.assertEqual(cache.snapshot(self.DEVICE_ID), first)

    def test_applied_provenance_apply_changes_only_subsequent_immutable_snapshot(self):
        cache = fleet.AppliedMappingCache()
        cache.update(self._document())
        before = cache.snapshot(self.DEVICE_ID)
        applied = self._document(applied_frame='tibia_r_imu')
        applied['applied_revision'] = 10
        self.assertTrue(cache.update(applied))
        after = cache.snapshot(self.DEVICE_ID)
        self.assertEqual(before['frame'], 'femur_r_imu')
        self.assertEqual(after['frame'], 'tibia_r_imu')
        self.assertEqual(cache.epoch, 2)

    def test_applied_provenance_unassigned_and_reconnect_epochs_are_independent(self):
        cache = fleet.AppliedMappingCache()
        unassigned = self._document()
        unassigned['applied_revision'] = 0
        unassigned['applied_assignments'] = {}
        cache.update(unassigned)
        snapshot = cache.snapshot(self.DEVICE_ID)
        self.assertEqual(snapshot['revision'], 0)
        self.assertIsNone(snapshot['segment'])
        self.assertIsNone(snapshot['frame'])

        store = fleet.FleetRegistryStore()
        store.upsert_connected(
            device_id=self.DEVICE_ID, role='master', host='127.0.0.1', esp_port=5000,
            listen_port=5002, configured_hz=100, observed_hz=100, last_seen_us=1,
        )
        mapping_epoch = cache.epoch
        store.mark_reconnecting(self.DEVICE_ID, last_seen_us=2)
        store.upsert_connected(
            device_id=self.DEVICE_ID, role='master', host='127.0.0.1', esp_port=5000,
            listen_port=5002, configured_hz=100, observed_hz=100, last_seen_us=3,
        )
        self.assertEqual(cache.epoch, mapping_epoch)
        self.assertEqual(store._devices[self.DEVICE_ID].reconnect_generation, 2)


class FleetCanonicalTopicContractsTest(unittest.TestCase):
    def test_device_topic_token_maps_to_canonical_raw_and_status_topics(self):
        device_id = 'esp32:aabbccddeeff'
        token = bridge.device_topic_token(device_id)
        self.assertEqual(token, 'mac_aabbccddeeff')
        raw, status = fleet.canonical_topic_paths(device_id)
        self.assertEqual(raw, '/esp/raw/mac_aabbccddeeff')
        self.assertEqual(status, '/esp/status/mac_aabbccddeeff')
        self.assertEqual(raw, f'/esp/raw/{token}')
        self.assertEqual(status, f'/esp/status/{token}')

    def test_low32_colliding_macs_get_distinct_topic_tokens(self):
        first = 'esp32:aabbccddeeff'
        second = 'esp32:1111ccddeeff'
        self.assertEqual(first[10:], second[10:])
        self.assertNotEqual(
            bridge.device_topic_token(first),
            bridge.device_topic_token(second),
        )
        raw_a, status_a = fleet.canonical_topic_paths(first)
        raw_b, status_b = fleet.canonical_topic_paths(second)
        self.assertNotEqual(raw_a, raw_b)
        self.assertNotEqual(status_a, status_b)
        self.assertTrue(raw_a.startswith('/esp/raw/mac_'))
        self.assertTrue(raw_b.startswith('/esp/raw/mac_'))


class FleetRegistryBuilderTest(unittest.TestCase):
    def test_registry_schema_and_layered_fields_on_every_row(self):
        rows = [
            fleet.FleetDeviceState(
                device_id='esp32:aabbccddeeff',
                role='master',
                host='192.168.4.1',
                esp_port=5000,
                listen_port=5002,
                discovery='present',
                command='ready',
                route='connected',
                orientation_freshness='fresh',
                synchronization='unknown',
                configured_hz=100,
                observed_hz=99.5,
                last_seen_us=1_000_000,
            ),
            fleet.FleetDeviceState(
                device_id='esp32:1111ccddeeff',
                role='slave',
                host='192.168.4.3',
                esp_port=5000,
                listen_port=5003,
                discovery='present',
                command='ready',
                route='connected',
                orientation_freshness='fresh',
                synchronization='unknown',
                configured_hz=100,
                observed_hz=98.0,
                last_seen_us=1_000_100,
            ),
        ]
        doc = fleet.build_fleet_registry(rows, revision=3, timestamp_us=42)
        self.assertEqual(doc['schema'], 'oe_esp32.fleet_registry.v1')
        self.assertEqual(doc['revision'], 3)
        self.assertEqual(doc['timestamp_us'], 42)
        self.assertEqual(len(doc['devices']), 2)
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertEqual(set(by_id), {
            'esp32:aabbccddeeff',
            'esp32:1111ccddeeff',
        })
        for device_id, row in by_id.items():
            self.assertEqual(row['topic_token'], bridge.device_topic_token(device_id))
            self.assertEqual(row['display_mac'], bridge.display_mac(device_id))
            for field in LAYERED_FIELDS:
                self.assertIn(field, row)
            self.assertIn('endpoint', row)
            self.assertIn('host', row['endpoint'])
            # Role/IP are metadata — never redefine topic_token.
            self.assertEqual(row['topic_token'], f"mac_{device_id[6:]}")

    def test_offline_devices_retained_with_last_seen(self):
        store = fleet.FleetRegistryStore()
        store.upsert_connected(
            device_id='esp32:aabbccddeeff',
            role='master',
            host='192.168.4.1',
            esp_port=5000,
            listen_port=5002,
            configured_hz=100,
            observed_hz=100.0,
            last_seen_us=5_000,
        )
        store.mark_offline('esp32:aabbccddeeff', last_seen_us=5_000)
        doc = store.build(revision=1, timestamp_us=9_000)
        self.assertEqual(len(doc['devices']), 1)
        row = doc['devices'][0]
        self.assertEqual(row['device_id'], 'esp32:aabbccddeeff')
        self.assertIn(row['route'], ('offline', 'stale'))
        self.assertEqual(row['last_seen_us'], 5_000)

    def test_identity_change_retains_prior_mac_offline_and_registers_new(self):
        store = fleet.FleetRegistryStore()
        store.upsert_connected(
            device_id='esp32:aabbccddeeff',
            role='slave',
            host='192.168.4.3',
            esp_port=5000,
            listen_port=5003,
            configured_hz=100,
            observed_hz=50.0,
            last_seen_us=10,
        )
        store.replace_session_identity(
            prior_device_id='esp32:aabbccddeeff',
            new_device_id='esp32:2222ccddeeff',
            role='slave',
            host='192.168.4.3',
            esp_port=5000,
            listen_port=5003,
            configured_hz=100,
            observed_hz=50.0,
            last_seen_us=20,
        )
        doc = store.build(revision=2, timestamp_us=30)
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertIn('esp32:aabbccddeeff', by_id)
        self.assertIn('esp32:2222ccddeeff', by_id)
        self.assertIn(by_id['esp32:aabbccddeeff']['route'], ('offline', 'stale'))
        self.assertEqual(by_id['esp32:2222ccddeeff']['route'], 'connected')
        self.assertEqual(
            by_id['esp32:aabbccddeeff']['topic_token'],
            'mac_aabbccddeeff',
        )
        self.assertEqual(
            by_id['esp32:2222ccddeeff']['topic_token'],
            'mac_2222ccddeeff',
        )


class FleetRoutesAndEntryPointTest(unittest.TestCase):
    def test_parse_routes_json_lists_host_port_expected_device_id(self):
        payload = json.dumps([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
        ])
        routes = fleet.parse_routes_json(payload)
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[0]['host'], '192.168.4.1')
        self.assertEqual(routes[0]['port'], 5002)
        self.assertEqual(routes[0]['expected_device_id'], 'esp32:aabbccddeeff')
        self.assertEqual(routes[1]['expected_device_id'], 'esp32:1111ccddeeff')

    def test_fleet_manager_owns_sessions_and_emits_registry_topic_name(self):
        self.assertTrue(hasattr(fleet, 'FleetBridgeNode'))
        self.assertTrue(hasattr(fleet, 'main'))
        self.assertEqual(fleet.FLEET_REGISTRY_TOPIC, '/esp/fleet/registry')
        self.assertEqual(fleet.FLEET_REGISTRY_SCHEMA, 'oe_esp32.fleet_registry.v1')

    def test_stub_session_publishes_canonical_topics_after_bind(self):
        published: list[tuple[str, str]] = []

        class StubPublisher:
            def __init__(self, topic: str) -> None:
                self.topic = topic

            def publish(self, message) -> None:
                published.append((self.topic, getattr(message, 'data', message)))

        session = fleet.FleetDeviceSession(
            host='192.168.4.1',
            port=5002,
            expected_device_id='esp32:aabbccddeeff',
            role='master',
            create_publisher=lambda msg_type, topic, qos: StubPublisher(topic),
            string_message_type=type('String', (), {'__init__': lambda self: setattr(self, 'data', '')}),
        )
        session.bind_verified_self('esp32:aabbccddeeff')
        self.assertEqual(
            sorted(session.canonical_topics()),
            [
                '/esp/raw/mac_aabbccddeeff',
                '/esp/status/mac_aabbccddeeff',
            ],
        )
        session.publish_raw_json('{"sample":1}')
        session.publish_health_json('{"connection_state":"connected"}')
        topics = {topic for topic, _ in published}
        self.assertEqual(
            topics,
            {'/esp/raw/mac_aabbccddeeff', '/esp/status/mac_aabbccddeeff'},
        )

    def test_session_manager_owns_multiple_routes_and_emits_registry_on_bind(self):
        emitted: list[dict] = []
        created_topics: list[str] = []

        class StubPublisher:
            def __init__(self, topic: str) -> None:
                self.topic = topic

            def publish(self, message) -> None:
                return None

        routes = fleet.parse_routes_json(json.dumps([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
        ]))

        def create_publisher(msg_type, topic, qos):
            created_topics.append(topic)
            return StubPublisher(topic)

        manager = fleet.FleetSessionManager(
            routes,
            create_publisher=create_publisher,
            string_message_type=type('String', (), {'__init__': lambda self: setattr(self, 'data', '')}),
            on_registry_change=emitted.append,
        )
        self.assertEqual(len(manager.sessions), 2)
        seed = manager.build_registry()
        self.assertEqual(len(seed['devices']), 2)
        self.assertTrue(all(row['route'] in ('offline', 'stale') for row in seed['devices']))

        doc = manager.on_session_bound(
            manager.sessions[0],
            'esp32:aabbccddeeff',
            configured_hz=100,
            observed_hz=99.0,
            last_seen_us=11,
        )
        self.assertEqual(doc['revision'], 1)
        self.assertEqual(len(emitted), 1)
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertEqual(by_id['esp32:aabbccddeeff']['route'], 'connected')
        self.assertIn(by_id['esp32:1111ccddeeff']['route'], ('offline', 'stale'))
        self.assertIn('/esp/raw/mac_aabbccddeeff', created_topics)
        self.assertIn('/esp/status/mac_aabbccddeeff', created_topics)

        # Different self on the same session retains prior MAC offline.
        manager.on_session_bound(
            manager.sessions[1],
            'esp32:1111ccddeeff',
            last_seen_us=12,
        )
        doc2 = manager.on_session_bound(
            manager.sessions[1],
            'esp32:2222ccddeeff',
            last_seen_us=13,
        )
        by_id = {row['device_id']: row for row in doc2['devices']}
        self.assertIn('esp32:1111ccddeeff', by_id)
        self.assertIn('esp32:2222ccddeeff', by_id)
        self.assertIn(by_id['esp32:1111ccddeeff']['route'], ('offline', 'stale'))
        self.assertEqual(by_id['esp32:2222ccddeeff']['route'], 'connected')
        self.assertIn('/esp/raw/mac_2222ccddeeff', created_topics)
    def test_setup_py_registers_fleet_bridge_console_script(self):
        setup_text = (
            Path(__file__).parents[1] / 'setup.py'
        ).read_text(encoding='utf-8')
        self.assertIn(
            'fleet_bridge_node = rehab_robotics_bridge.fleet_bridge_node:main',
            setup_text,
        )

    def test_esp32_bridge_node_remains_single_session_entry(self):
        setup_text = (
            Path(__file__).parents[1] / 'setup.py'
        ).read_text(encoding='utf-8')
        self.assertIn(
            'esp32_bridge_node = rehab_robotics_bridge.esp32_bridge_node:main',
            setup_text,
        )
        self.assertTrue(callable(bridge.main))
        # Single-session constructor still declares role-based node_id.
        source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'esp32_bridge_node.py'
        ).read_text(encoding='utf-8')
        self.assertIn("self.declare_parameter('node_id', 'master')", source)
        self.assertIn("f'/esp/raw/{self._node_id}'", source)


class Phase21ControlsGuardUpdateTest(unittest.TestCase):
    def test_esp32_bridge_forbids_esp32_mac_prefix_but_allows_token_helper(self):
        source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'esp32_bridge_node.py'
        ).read_text(encoding='utf-8')
        self.assertNotIn('/esp32/mac_', source)
        self.assertIn('def device_topic_token(', source)
        fleet_source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'fleet_bridge_node.py'
        ).read_text(encoding='utf-8')
        self.assertIn('device_topic_token', fleet_source)
        self.assertIn('/esp/raw/', fleet_source)
        self.assertIn('/esp/status/', fleet_source)
        self.assertNotIn('/esp32/mac_', fleet_source)


class FleetAliasBindingTest(unittest.TestCase):
    """D-21-06/07/16: identity-bound Master/Slave aliases + pair health."""

    def _routes(self, entries):
        return fleet.parse_routes_json(json.dumps(entries))

    def _string_type(self):
        return type('String', (), {'__init__': lambda self: setattr(self, 'data', '')})

    def _manager(self, routes, *, alias_master='', alias_slave='', published=None):
        published = published if published is not None else []

        class StubPublisher:
            def __init__(self, topic: str) -> None:
                self.topic = topic

            def publish(self, message) -> None:
                published.append((self.topic, getattr(message, 'data', message)))

        def create_publisher(msg_type, topic, qos):
            return StubPublisher(topic)

        return fleet.FleetSessionManager(
            routes,
            create_publisher=create_publisher,
            string_message_type=self._string_type(),
            alias_master_device_id=alias_master,
            alias_slave_device_id=alias_slave,
        ), published

    def test_alias_master_mirrors_canonical_raw_and_status_payloads(self):
        routes = self._routes([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
        ])
        manager, published = self._manager(
            routes,
            alias_master='esp32:aabbccddeeff',
            alias_slave='esp32:1111ccddeeff',
        )
        manager.on_session_bound(manager.sessions[0], 'esp32:aabbccddeeff', last_seen_us=1)
        manager.on_session_bound(manager.sessions[1], 'esp32:1111ccddeeff', last_seen_us=2)
        manager.publish_session_raw(manager.sessions[0], '{"sample":42}')
        manager.publish_session_health(
            manager.sessions[0],
            '{"connection_state":"connected"}',
        )
        by_topic = {topic: payload for topic, payload in published}
        self.assertEqual(by_topic['/esp/raw/mac_aabbccddeeff'], '{"sample":42}')
        self.assertEqual(by_topic['/esp/raw/master'], '{"sample":42}')
        self.assertEqual(
            by_topic['/esp/status/mac_aabbccddeeff'],
            '{"connection_state":"connected"}',
        )
        self.assertEqual(
            by_topic['/esp/status/master'],
            '{"connection_state":"connected"}',
        )

    def test_alias_slave_mirrors_canonical_payloads(self):
        routes = self._routes([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
        ])
        manager, published = self._manager(
            routes,
            alias_master='esp32:aabbccddeeff',
            alias_slave='esp32:1111ccddeeff',
        )
        manager.on_session_bound(manager.sessions[0], 'esp32:aabbccddeeff', last_seen_us=1)
        manager.on_session_bound(manager.sessions[1], 'esp32:1111ccddeeff', last_seen_us=2)
        manager.publish_session_raw(manager.sessions[1], '{"slave":1}')
        manager.publish_session_health(
            manager.sessions[1],
            '{"connection_state":"connected"}',
        )
        by_topic = {topic: payload for topic, payload in published}
        self.assertEqual(by_topic['/esp/raw/mac_1111ccddeeff'], '{"slave":1}')
        self.assertEqual(by_topic['/esp/raw/slave'], '{"slave":1}')
        self.assertEqual(by_topic['/esp/status/slave'], '{"connection_state":"connected"}')

    def test_empty_alias_params_bind_first_verified_role_not_connect_order(self):
        # Slave route listed first so TCP connect order alone would pick wrong alias.
        routes = self._routes([
            {
                'host': '192.168.4.5',
                'port': 5004,
                'expected_device_id': 'esp32:2222ccddeeff',
                'role': 'slave',
            },
            {
                'host': '192.168.4.4',
                'port': 5003,
                'expected_device_id': 'esp32:3333ccddeeff',
                'role': 'slave',
            },
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
        ])
        manager, published = self._manager(routes)
        manager.on_session_bound(manager.sessions[0], 'esp32:2222ccddeeff', last_seen_us=1)
        manager.on_session_bound(manager.sessions[1], 'esp32:3333ccddeeff', last_seen_us=2)
        manager.on_session_bound(manager.sessions[2], 'esp32:aabbccddeeff', last_seen_us=3)
        doc = manager.build_registry()
        self.assertEqual(doc['alias_master_device_id'], 'esp32:aabbccddeeff')
        self.assertEqual(doc['alias_slave_device_id'], 'esp32:2222ccddeeff')
        manager.publish_session_raw(manager.sessions[2], '{"m":1}')
        manager.publish_session_raw(manager.sessions[0], '{"s":1}')
        by_topic = {topic: payload for topic, payload in published}
        self.assertEqual(by_topic['/esp/raw/master'], '{"m":1}')
        self.assertEqual(by_topic['/esp/raw/slave'], '{"s":1}')

    def test_offline_alias_target_leaves_other_devices_publishing(self):
        routes = self._routes([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
            {
                'host': '192.168.4.4',
                'port': 5004,
                'expected_device_id': 'esp32:4444ccddeeff',
                'role': 'slave',
            },
        ])
        manager, published = self._manager(
            routes,
            alias_master='esp32:aabbccddeeff',
            alias_slave='esp32:1111ccddeeff',
        )
        for session, device_id, ts in (
            (manager.sessions[0], 'esp32:aabbccddeeff', 1),
            (manager.sessions[1], 'esp32:1111ccddeeff', 2),
            (manager.sessions[2], 'esp32:4444ccddeeff', 3),
        ):
            manager.on_session_bound(session, device_id, last_seen_us=ts)
        manager.on_session_offline(manager.sessions[1], last_seen_us=4)
        published.clear()
        manager.publish_session_raw(manager.sessions[0], '{"master_alive":1}')
        manager.publish_session_raw(manager.sessions[2], '{"other_slave":1}')
        by_topic = {topic: payload for topic, payload in published}
        self.assertEqual(by_topic['/esp/raw/master'], '{"master_alive":1}')
        self.assertEqual(by_topic['/esp/raw/mac_4444ccddeeff'], '{"other_slave":1}')
        self.assertNotIn('/esp/raw/slave', by_topic)

    def test_pair_health_publishes_when_both_aliases_bound(self):
        routes = self._routes([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
        ])
        manager, published = self._manager(
            routes,
            alias_master='esp32:aabbccddeeff',
            alias_slave='esp32:1111ccddeeff',
        )
        manager.on_session_bound(manager.sessions[0], 'esp32:aabbccddeeff', last_seen_us=1)
        manager.on_session_bound(manager.sessions[1], 'esp32:1111ccddeeff', last_seen_us=2)
        master_health = {
            'schema': 'oe_esp32.health.v1',
            'node_id': 'master',
            'connection_state': 'connected',
            'timestamp_us': 99,
        }
        slave_health = {
            'schema': 'oe_esp32.health.v1',
            'node_id': 'slave',
            'connection_state': 'connected',
            'timestamp_us': 100,
        }
        pair = manager.publish_pair_health(master_health, slave_health)
        self.assertIsNotNone(pair)
        self.assertEqual(pair['schema'], 'oe_esp32.pair_health.v1')
        self.assertTrue(pair['pair_available'])
        pair_payloads = [payload for topic, payload in published if topic == '/esp/status/pair']
        self.assertEqual(len(pair_payloads), 1)
        decoded = json.loads(pair_payloads[0])
        self.assertEqual(decoded['schema'], 'oe_esp32.pair_health.v1')
        self.assertEqual(decoded['master']['connection_state'], 'connected')
        self.assertEqual(decoded['slave']['connection_state'], 'connected')

    def test_pair_health_omitted_until_both_aliases_bound(self):
        routes = self._routes([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
        ])
        manager, published = self._manager(routes, alias_master='esp32:aabbccddeeff')
        manager.on_session_bound(manager.sessions[0], 'esp32:aabbccddeeff', last_seen_us=1)
        pair = manager.publish_pair_health(
            {'schema': 'oe_esp32.health.v1', 'connection_state': 'connected'},
            None,
        )
        self.assertIsNone(pair)
        self.assertFalse(any(topic == '/esp/status/pair' for topic, _ in published))

    def test_registry_includes_resolved_alias_device_ids(self):
        routes = self._routes([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
        ])
        manager, _published = self._manager(
            routes,
            alias_master='esp32:aabbccddeeff',
            alias_slave='esp32:1111ccddeeff',
        )
        manager.on_session_bound(manager.sessions[0], 'esp32:aabbccddeeff', last_seen_us=1)
        manager.on_session_bound(manager.sessions[1], 'esp32:1111ccddeeff', last_seen_us=2)
        doc = manager.build_registry()
        self.assertEqual(doc['alias_master_device_id'], 'esp32:aabbccddeeff')
        self.assertEqual(doc['alias_slave_device_id'], 'esp32:1111ccddeeff')

    def test_alias_topic_constants_and_no_typed_imu_mirror_in_fleet(self):
        self.assertEqual(fleet.ALIAS_RAW_MASTER_TOPIC, '/esp/raw/master')
        self.assertEqual(fleet.ALIAS_RAW_SLAVE_TOPIC, '/esp/raw/slave')
        self.assertEqual(fleet.ALIAS_STATUS_MASTER_TOPIC, '/esp/status/master')
        self.assertEqual(fleet.ALIAS_STATUS_SLAVE_TOPIC, '/esp/status/slave')
        self.assertEqual(fleet.PAIR_HEALTH_TOPIC, '/esp/status/pair')
        source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'fleet_bridge_node.py'
        ).read_text(encoding='utf-8')
        # Typed OpenSim IMU topics remain /esp32/{master,slave}/imu consumers;
        # fleet String aliases do not invent /esp32/mac_ or mirror IMU frames here.
        self.assertNotIn('/esp32/mac_', source)
        self.assertIn('ALIAS_RAW_MASTER_TOPIC', source)


class FleetDropReconnectDiagnosticsTest(unittest.TestCase):
    """D-21-10/11/14: drop_count + reconnect diagnostics on registry/health."""

    def test_registry_rows_include_drop_and_reconnect_fields(self):
        store = fleet.FleetRegistryStore()
        store.upsert_connected(
            device_id='esp32:aabbccddeeff',
            role='master',
            host='192.168.4.1',
            esp_port=5000,
            listen_port=5002,
            configured_hz=100,
            observed_hz=99.0,
            last_seen_us=1,
        )
        doc = store.build(revision=1, timestamp_us=2)
        row = doc['devices'][0]
        self.assertIn('drops', row)
        self.assertEqual(row['drops']['udp_drop_count'], 0)
        self.assertEqual(row['drops']['queue_maxsize'], 256)
        self.assertIn('reconnects', row)
        self.assertEqual(row['reconnects']['count'], 0)
        self.assertGreaterEqual(row['reconnects']['generation'], 1)

    def test_record_udp_drops_affects_only_target_device(self):
        store = fleet.FleetRegistryStore()
        for device_id, host, port in (
            ('esp32:aabbccddeeff', '192.168.4.1', 5002),
            ('esp32:1111ccddeeff', '192.168.4.3', 5003),
        ):
            store.upsert_connected(
                device_id=device_id,
                role='master' if 'aa' in device_id else 'slave',
                host=host,
                esp_port=5000,
                listen_port=port,
                configured_hz=100,
                observed_hz=100.0,
                last_seen_us=1,
            )
        store.record_udp_drops('esp32:1111ccddeeff', 7)
        doc = store.build(revision=2, timestamp_us=3)
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertEqual(by_id['esp32:1111ccddeeff']['drops']['udp_drop_count'], 7)
        self.assertEqual(by_id['esp32:aabbccddeeff']['drops']['udp_drop_count'], 0)

    def test_mark_reconnecting_retains_row_and_increments_on_reconnect(self):
        store = fleet.FleetRegistryStore()
        store.upsert_connected(
            device_id='esp32:1111ccddeeff',
            role='slave',
            host='192.168.4.3',
            esp_port=5000,
            listen_port=5003,
            configured_hz=100,
            observed_hz=50.0,
            last_seen_us=10,
        )
        store.mark_reconnecting('esp32:1111ccddeeff', last_seen_us=11)
        mid = store.build(revision=2, timestamp_us=12)
        row = mid['devices'][0]
        self.assertEqual(row['device_id'], 'esp32:1111ccddeeff')
        self.assertEqual(row['route'], 'reconnecting')
        self.assertEqual(row['last_seen_us'], 11)
        self.assertEqual(row['reconnects']['count'], 0)

        store.note_reconnect('esp32:1111ccddeeff')
        store.upsert_connected(
            device_id='esp32:1111ccddeeff',
            role='slave',
            host='192.168.4.9',
            esp_port=5000,
            listen_port=5003,
            configured_hz=100,
            observed_hz=50.0,
            last_seen_us=20,
        )
        after = store.build(revision=3, timestamp_us=21)
        row = after['devices'][0]
        self.assertEqual(row['route'], 'connected')
        self.assertEqual(row['endpoint']['host'], '192.168.4.9')
        self.assertEqual(row['reconnects']['count'], 1)
        self.assertGreaterEqual(row['reconnects']['generation'], 2)

    def test_health_snapshot_includes_drop_count_and_reconnect_count(self):
        from backend.test import test_esp32_controls as controls

        node = controls._make_health_stub()
        node._drop_count = 3
        node._reconnect_count = 2
        snapshot = bridge.Esp32BridgeNode._health_snapshot(node)
        self.assertEqual(snapshot['schema'], 'oe_esp32.health.v1')
        self.assertEqual(snapshot['drop_count'], 3)
        self.assertEqual(snapshot['reconnect_count'], 2)
        self.assertEqual(snapshot['drops']['udp_drop_count'], 3)
        self.assertEqual(snapshot['drops']['queue_maxsize'], 256)


class FleetFailureIsolationTest(unittest.TestCase):
    """D-21-09/11/12: sibling failure must not stop healthy routes (no STEP_ESP32)."""

    def _routes(self):
        return fleet.parse_routes_json(json.dumps([
            {
                'host': '192.168.4.1',
                'port': 5002,
                'expected_device_id': 'esp32:aabbccddeeff',
                'role': 'master',
            },
            {
                'host': '192.168.4.3',
                'port': 5003,
                'expected_device_id': 'esp32:1111ccddeeff',
                'role': 'slave',
            },
            {
                'host': '192.168.4.5',
                'port': 5004,
                'expected_device_id': 'esp32:2222ccddeeff',
                'role': 'slave',
            },
        ]))

    def _manager(self, published=None):
        published = published if published is not None else []

        class StubPublisher:
            def __init__(self, topic: str) -> None:
                self.topic = topic

            def publish(self, message) -> None:
                published.append((self.topic, getattr(message, 'data', message)))

        def create_publisher(msg_type, topic, qos):
            return StubPublisher(topic)

        string_type = type('String', (), {'__init__': lambda self: setattr(self, 'data', '')})
        return fleet.FleetSessionManager(
            self._routes(),
            create_publisher=create_publisher,
            string_message_type=string_type,
            alias_master_device_id='esp32:aabbccddeeff',
            alias_slave_device_id='esp32:1111ccddeeff',
        ), published

    def test_slave_b_reconnect_does_not_stop_master_or_slave_a_publish(self):
        manager, published = self._manager()
        master, slave_a, slave_b = manager.sessions
        manager.on_session_bound(master, 'esp32:aabbccddeeff', last_seen_us=1)
        manager.on_session_bound(slave_a, 'esp32:1111ccddeeff', last_seen_us=2)
        manager.on_session_bound(slave_b, 'esp32:2222ccddeeff', last_seen_us=3)

        manager.publish_session_raw(master, '{"frame":"m1"}')
        manager.publish_session_health(master, '{"connection_state":"connected"}')
        manager.publish_session_raw(slave_a, '{"frame":"a1"}')

        manager.on_session_reconnecting(slave_b, last_seen_us=4)
        doc = manager.build_registry()
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertEqual(by_id['esp32:2222ccddeeff']['route'], 'reconnecting')
        self.assertEqual(by_id['esp32:aabbccddeeff']['route'], 'connected')
        self.assertEqual(by_id['esp32:1111ccddeeff']['route'], 'connected')

        published.clear()
        manager.publish_session_raw(master, '{"frame":"m2"}')
        manager.publish_session_health(master, '{"connection_state":"connected","ok":1}')
        manager.publish_session_raw(slave_a, '{"frame":"a2"}')
        manager.publish_session_health(slave_a, '{"connection_state":"connected","ok":1}')
        by_topic = {topic: payload for topic, payload in published}
        self.assertEqual(by_topic['/esp/raw/mac_aabbccddeeff'], '{"frame":"m2"}')
        self.assertEqual(by_topic['/esp/raw/master'], '{"frame":"m2"}')
        self.assertEqual(by_topic['/esp/raw/mac_1111ccddeeff'], '{"frame":"a2"}')
        self.assertEqual(by_topic['/esp/status/mac_aabbccddeeff'], '{"connection_state":"connected","ok":1}')
        self.assertEqual(by_topic['/esp/status/mac_1111ccddeeff'], '{"connection_state":"connected","ok":1}')
        # Failed slave B must not appear in post-failure publishes.
        self.assertNotIn('/esp/raw/mac_2222ccddeeff', by_topic)

    def test_dhcp_ip_remap_keeps_canonical_mac_topic_names(self):
        manager, published = self._manager()
        master = manager.sessions[0]
        manager.on_session_bound(master, 'esp32:aabbccddeeff', last_seen_us=1)
        before = list(master.canonical_topics())
        self.assertEqual(before, [
            '/esp/raw/mac_aabbccddeeff',
            '/esp/status/mac_aabbccddeeff',
        ])
        # DHCP refresh: endpoint host changes, identity/topic token stay.
        master.host = '192.168.4.17'
        manager.registry._devices['esp32:aabbccddeeff'].host = '192.168.4.17'
        manager.publish_session_raw(master, '{"after_dhcp":1}')
        self.assertEqual(master.canonical_topics(), before)
        by_topic = {topic: payload for topic, payload in published}
        self.assertEqual(by_topic['/esp/raw/mac_aabbccddeeff'], '{"after_dhcp":1}')
        self.assertEqual(by_topic['/esp/raw/master'], '{"after_dhcp":1}')
        by_id = {row['device_id']: row for row in manager.build_registry()['devices']}
        row = by_id['esp32:aabbccddeeff']
        self.assertEqual(row['topic_token'], 'mac_aabbccddeeff')
        self.assertEqual(row['endpoint']['host'], '192.168.4.17')

    def test_tcp_death_retains_offline_mac_with_last_seen(self):
        manager, _published = self._manager()
        slave_b = manager.sessions[2]
        manager.on_session_bound(slave_b, 'esp32:2222ccddeeff', last_seen_us=10)
        manager.on_session_offline(slave_b, last_seen_us=99)
        doc = manager.build_registry()
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertIn('esp32:2222ccddeeff', by_id)
        self.assertIn(by_id['esp32:2222ccddeeff']['route'], ('offline', 'stale'))
        self.assertEqual(by_id['esp32:2222ccddeeff']['last_seen_us'], 99)
        # Configured siblings remain present even if never bound this cycle.
        self.assertIn('esp32:aabbccddeeff', by_id)
        self.assertIn('esp32:1111ccddeeff', by_id)

    def test_isolated_supervisor_keeps_healthy_task_after_sibling_error(self):
        import asyncio

        events: list[str] = []

        async def healthy() -> None:
            events.append('healthy-start')
            await asyncio.sleep(0.05)
            events.append('healthy-done')

        async def failing() -> None:
            events.append('fail-start')
            raise RuntimeError('simulated slave B TCP death')

        async def run() -> None:
            await fleet.run_isolated_session_tasks([failing, healthy])

        asyncio.run(run())
        self.assertIn('fail-start', events)
        self.assertIn('healthy-start', events)
        self.assertIn('healthy-done', events)

    def test_supervisor_source_avoids_global_gather_cancel(self):
        source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'fleet_bridge_node.py'
        ).read_text(encoding='utf-8')
        self.assertIn('run_isolated_session_tasks', source)
        self.assertIn('return_exceptions=True', source)
        # Recording/acquisition must not share a fatal sibling cancel path.
        self.assertIn('CancelledError', source)


class FleetLiveSessionContractTest(unittest.TestCase):
    """Live-session contract tests for plan 21-06 (no STEP_ESP32 required)."""

    # --- wire format constants (from 21-06-PLAN.md) ---
    IDENTITY_OK = (
        b'IDENTITY_OK protocol=id-v1 record=self device_id=esp32:aabbccddeeff '
        b'display_mac=AA:BB:CC:DD:EE:FF base_mac=AA:BB:CC:DD:EE:FF '
        b'sta_mac=AA:BB:CC:DD:EE:FE ap_mac=AA:BB:CC:DD:EE:FF '
        b'espnow_mac=AA:BB:CC:DD:EE:FF role=master schema_version=1 verified=1 '
        b'identify_supported=1 peer_count=0 route_ip=192.168.4.1 board_revision=3\n'
    )
    IDENTITY_END = b'IDENTITY_END protocol=id-v1 peer_count=0\n'
    STARTED_TCP = b'STARTED BIN:esp32s3_arduino transport=tcp\n'

    def _make_stub_manager(self, routes=None):
        """Build a FleetSessionManager with stub publishers."""
        import json as _json
        if routes is None:
            routes = fleet.parse_routes_json(_json.dumps([
                {
                    'host': '127.0.0.1',
                    'port': 5002,
                    'expected_device_id': 'esp32:aabbccddeeff',
                    'role': 'master',
                },
            ]))

        class _StubPub:
            def __init__(self, topic):
                self.topic = topic
            def publish(self, message):
                pass

        def _create_pub(msg_type, topic, qos):
            return _StubPub(topic)

        string_type = type('String', (), {'__init__': lambda self: setattr(self, 'data', '')})
        return fleet.FleetSessionManager(
            routes,
            create_publisher=_create_pub,
            string_message_type=string_type,
        )

    def _make_stub_node(self, routes=None):
        """Build a minimal FleetBridgeNode stub bypassing ROS init."""
        import json as _json
        if routes is None:
            routes = fleet.parse_routes_json(_json.dumps([
                {
                    'host': '127.0.0.1',
                    'port': 5002,
                    'expected_device_id': 'esp32:aabbccddeeff',
                    'role': 'master',
                },
            ]))

        manager = self._make_stub_manager(routes)

        class _NullLogger:
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def debug(self, *a, **k): pass
            def error(self, *a, **k): pass

        node = object.__new__(fleet.FleetBridgeNode)
        node._reconnect_delay_s = 5.0
        node._handshake_timeout_s = 15.0
        node._identify_timeout_s = 3.0
        node._routes = routes
        node._body_segments = {}
        node._manager = manager
        node._sessions = manager.sessions
        node._registry = manager.registry
        n = len(manager.sessions)
        import asyncio
        node._active_writers = [None] * n
        node._session_locks = [None] * n
        node._identify_queues = [None] * n
        node._imu_pubs = {'master': None, 'slave': None}
        node._loop = asyncio.new_event_loop()
        node.get_logger = lambda: _NullLogger()
        return node

    # --- test 1 ---
    def test_fleet_handshake_binds_session_on_valid_identity(self):
        """_fleet_handshake with valid IDENTITY_OK bytes binds device_id and marks registry connected."""
        import asyncio

        # Wire format: IDENTITY_OK (self record) + IDENTITY_END (peer count=0, so 1 extra line)
        # + OK response to REDPITAYA handshake + STARTED response to START command.
        identity_bytes = self.IDENTITY_OK + self.IDENTITY_END

        node = self._make_stub_node()
        session = node._sessions[0]

        # Minimal mock writer (write/drain/is_closing stubs)
        class _MockWriter:
            def __init__(self):
                self.sent = bytearray()
            def write(self, data):
                self.sent.extend(data)
            async def drain(self):
                pass
            def is_closing(self):
                return False

        async def _run():
            # Build mock reader inside the event loop to avoid DeprecationWarning
            # Protocol sequence:
            #   [recv] IDENTITY_OK ...   → records[0] (IDENTITY_OK self line)
            #   [recv] IDENTITY_END ...  → records[1] (peer_count=0 → 0+1=1 extra line)
            #   [send] SIGNAL_STATUS? then identity-bound capability response
            #   [send] REDPITAYA\n
            #   [recv] OK\n              → discarded REDPITAYA acknowledgement
            #   [send] START\n
            #   [recv] STARTED BIN:...  → StartedOK
            reader = asyncio.StreamReader()
            # Feed: identity, capability, REDPITAYA ack, then STARTED line.
            status = FleetSignalStatusProtocolTest.VALID_STATUS.encode('ascii') + b'\n'
            reader.feed_data(identity_bytes + status + b'OK\n' + self.STARTED_TCP)
            reader.feed_eof()
            writer = _MockWriter()
            transport = await node._fleet_handshake(0, session, reader, writer)
            return transport, bytes(writer.sent)

        loop = asyncio.new_event_loop()
        try:
            transport_type, sent = loop.run_until_complete(_run())
        finally:
            loop.close()

        self.assertEqual(session._bound_device_id, 'esp32:aabbccddeeff')
        doc = node._manager.build_registry()
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertEqual(by_id['esp32:aabbccddeeff']['route'], 'connected')
        self.assertIn(transport_type, ('tcp', 'udp'))
        self.assertIn(b'SIGNAL_STATUS?\n', sent)
        self.assertIn(b'FILTER ON\n', sent)

    # --- test 2 ---
    def test_session_reconnecting_does_not_cancel_siblings(self):
        """run_isolated_session_tasks with one failing route leaves sibling's registry row connected."""
        import asyncio
        import json as _json

        routes = fleet.parse_routes_json(_json.dumps([
            {'host': '127.0.0.1', 'port': 5002,
             'expected_device_id': 'esp32:aabbccddeeff', 'role': 'master'},
            {'host': '127.0.0.1', 'port': 5003,
             'expected_device_id': 'esp32:1111ccddeeff', 'role': 'slave'},
        ]))
        manager = self._make_stub_manager(routes)
        events: list[str] = []

        async def failing_factory():
            events.append('failing-start')
            raise RuntimeError('simulated TCP disconnect')

        async def healthy_factory():
            events.append('healthy-start')
            # Simulate a brief connected run
            await asyncio.sleep(0.05)
            events.append('healthy-done')

        # Bind the healthy session first so its registry row starts 'connected'
        manager.on_session_bound(manager.sessions[1], 'esp32:1111ccddeeff', last_seen_us=1)
        # Mark the failing session reconnecting (simulating what _connect_and_stream_route does)
        manager.on_session_reconnecting(manager.sessions[0], last_seen_us=2)

        # run_isolated_session_tasks must not cancel the healthy factory
        async def run():
            await fleet.run_isolated_session_tasks([failing_factory, healthy_factory])

        asyncio.run(run())

        self.assertIn('failing-start', events)
        self.assertIn('healthy-start', events)
        self.assertIn('healthy-done', events)

        doc = manager.build_registry()
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertEqual(by_id['esp32:aabbccddeeff']['route'], 'reconnecting')
        self.assertEqual(by_id['esp32:1111ccddeeff']['route'], 'connected')

    # --- test 3 ---
    def test_identify_fleet_device_returns_offline_when_no_writer(self):
        """_identify_fleet_device returns 'offline' when _active_writers[index] is None."""
        node = self._make_stub_node()
        # Ensure the session is known but has no active writer
        self.assertIsNone(node._active_writers[0])

        class _StubRequest:
            command_id = 'test-cmd-001'
            target_device_id = 'esp32:aabbccddeeff'
            duration_ms = 1500

        class _StubResponse:
            command_id = ''
            target_device_id = ''
            outcome = ''
            applied_duration_ms = 0
            detail = ''

        response = node._identify_fleet_device(_StubRequest(), _StubResponse())
        self.assertEqual(response.outcome, 'offline')

    # --- test 4 ---
    def test_imu_publishers_created_for_master_and_slave_roles(self):
        """fleet_bridge_node.py source contains /esp32/master/imu and /esp32/slave/imu publisher topics."""
        from pathlib import Path
        source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'fleet_bridge_node.py'
        ).read_text(encoding='utf-8')
        self.assertIn('/esp32/master/imu', source)
        self.assertIn('/esp32/slave/imu', source)
        # Both should appear in the __init__ section (within the first 1000 lines)
        lines = source.splitlines()
        imu_lines = [i for i, line in enumerate(lines, 1)
                     if '/esp32/master/imu' in line or '/esp32/slave/imu' in line]
        self.assertGreaterEqual(len(imu_lines), 2,
            'Expected at least two lines referencing imu publisher topics')

    # --- test 5 ---
    def test_fleet_frame_publish_calls_session_raw_publish(self):
        """_publish_fleet_frame with 14-channel all-zeros OE payload calls publish_session_raw."""
        import json as _json
        import struct

        published_raw: list[str] = []

        class _StubPub:
            def __init__(self, topic):
                self.topic = topic
            def publish(self, message):
                published_raw.append(getattr(message, 'data', ''))

        routes = fleet.parse_routes_json(_json.dumps([
            {'host': '127.0.0.1', 'port': 5002,
             'expected_device_id': 'esp32:aabbccddeeff', 'role': 'master'},
        ]))
        string_type = type('String', (), {'__init__': lambda self: setattr(self, 'data', '')})

        def _create_pub(msg_type, topic, qos):
            return _StubPub(topic)

        manager = fleet.FleetSessionManager(
            routes,
            create_publisher=_create_pub,
            string_message_type=string_type,
        )

        # Override publish_session_raw to capture calls
        session_raw_calls: list[str] = []
        def _spy_raw(session, payload):
            session_raw_calls.append(payload)
        manager.publish_session_raw = _spy_raw
        session_health_calls: list[str] = []
        manager.publish_session_health = lambda _session, payload: session_health_calls.append(payload)
        pair_health_calls: list[tuple[object, object]] = []
        manager.publish_pair_health = lambda master, slave: pair_health_calls.append((master, slave))

        manager.on_session_bound(manager.sessions[0], 'esp32:aabbccddeeff', last_seen_us=1)

        node = object.__new__(fleet.FleetBridgeNode)
        node._manager = manager
        node._sessions = manager.sessions
        node._imu_pubs = {'master': None, 'slave': None}
        node._mac_imu_pubs = {}
        node._body_segments = {}
        node._health_snapshots = {}
        node._frame_times_by_device = {}
        node._signal_calibrations = {}
        node._mapping_cache = fleet.AppliedMappingCache()
        node._mapping_cache.update({
            'applied_revision': 0,
            'applied_assignments': {},
            'model_hash': 'unavailable',
        })
        manager.sessions[0].signal_status = fleet.parse_signal_status(
            FleetSignalStatusProtocolTest.VALID_STATUS,
            'esp32:aabbccddeeff',
        )

        # 14-channel, 1 sample/period, 2 bytes/sample → 28 bytes all zeros
        n_ch = 14
        n_per = 1
        payload = bytes(n_ch * n_per * 2)

        node._publish_fleet_frame(0, manager.sessions[0], payload, n_ch, n_per, 1)

        self.assertEqual(len(session_raw_calls), 1)
        data = _json.loads(session_raw_calls[0])
        self.assertIn('device_id', data)
        self.assertIn('node_role', data)
        self.assertIn('quat', data)
        self.assertIn('imu', data)
        self.assertEqual(data['sensor_config']['accel_range_g'], 2)
        self.assertEqual(data['sensor_config']['gyro_range_dps'], 250)
        self.assertEqual(data['device_id'], 'esp32:aabbccddeeff')
        self.assertEqual(data['node_role'], 'master')
        self.assertEqual(data['topic_schema'], 'oe_esp32.raw.v1')
        canonical = data['sample_contract']
        self.assertEqual(canonical['schema'], 'rehab.signal_sample.1')
        self.assertEqual(canonical['sequence_origin'], 'bridge_session')
        self.assertIsNone(canonical['acquisition_time_us'])
        self.assertIsNone(canonical['acquisition_clock'])
        self.assertEqual(canonical['applied_mapping']['revision'], 0)
        self.assertEqual(len(session_health_calls), 1)
        health = _json.loads(session_health_calls[0])
        self.assertEqual(health['connection_state'], 'connected')
        self.assertEqual(health['frames_received'], 1)
        self.assertGreater(health['observed_stream_rate_hz'], 0)
        self.assertEqual(len(pair_health_calls), 1)

    def test_fleet_mode_exposes_the_gui_recording_service(self):
        source = (
            Path(__file__).parents[1]
            / 'rehab_robotics_bridge'
            / 'fleet_bridge_node.py'
        ).read_text(encoding='utf-8')
        self.assertIn("'/esp/recording/set'", source)
        self.assertIn('def _set_recording', source)

    # --- test 6 ---
    def test_apply_udp_drop_count_called_on_reconnect(self):
        """FleetRegistryStore.record_udp_drops + apply_udp_drop_count propagates to registry row."""
        store = fleet.FleetRegistryStore()
        store.upsert_connected(
            device_id='esp32:aabbccddeeff',
            role='master',
            host='192.168.4.1',
            esp_port=5000,
            listen_port=5002,
            configured_hz=100,
            observed_hz=99.0,
            last_seen_us=1,
        )
        store.record_udp_drops('esp32:aabbccddeeff', 42)

        import json as _json
        routes = fleet.parse_routes_json(_json.dumps([
            {'host': '192.168.4.1', 'port': 5002,
             'expected_device_id': 'esp32:aabbccddeeff', 'role': 'master'},
        ]))
        string_type = type('String', (), {'__init__': lambda self: setattr(self, 'data', '')})

        class _StubPub:
            def __init__(self, topic): pass
            def publish(self, message): pass

        manager = fleet.FleetSessionManager(
            routes,
            create_publisher=lambda t, topic, q: _StubPub(topic),
            string_message_type=string_type,
        )
        manager.on_session_bound(manager.sessions[0], 'esp32:aabbccddeeff', last_seen_us=1)

        # Simulate what _connect_and_stream_route does on reconnect:
        # propagate relay-visible drop_count into the registry
        manager.apply_udp_drop_count('esp32:aabbccddeeff', 42)

        doc = manager.build_registry()
        by_id = {row['device_id']: row for row in doc['devices']}
        self.assertEqual(by_id['esp32:aabbccddeeff']['drops']['udp_drop_count'], 42)


if __name__ == '__main__':
    unittest.main()
class AppliedMappingCacheConcurrencyTest(unittest.TestCase):
    def test_snapshot_epoch_and_labels_are_one_atomic_state(self):
        cache = fleet.AppliedMappingCache()
        device_id = 'esp32:aabbccddeeff'
        states = [
            {
                'applied_revision': revision,
                'model_hash': f'model-{revision}',
                'applied_assignments': {
                    device_id: {'state': 'assigned', 'segment': f's{revision}', 'frame': f'f{revision}'},
                },
            }
            for revision in range(1, 100)
        ]
        failures: list[tuple[int, dict[str, object]]] = []

        def writer() -> None:
            for state in states:
                cache.update(state)

        thread = threading.Thread(target=writer)
        thread.start()
        while thread.is_alive():
            epoch, snapshot = cache.snapshot_with_epoch(device_id)
            revision = snapshot['revision']
            if revision != 0 and (
                epoch != revision
                or snapshot['model_hash'] != f'model-{revision}'
                or snapshot['segment'] != f's{revision}'
                or snapshot['frame'] != f'f{revision}'
            ):
                failures.append((epoch, snapshot))
        thread.join()
        self.assertEqual(failures, [])
