"""Fleet registry and canonical mac_ topic contracts (no live ROS / STEP_ESP32)."""
from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

from backend.test.test_esp32_controls import _load_bridge_module


def _install_ros_stubs() -> None:
    _backend_root = str(Path(__file__).parents[1])
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

    rclpy = types.ModuleType('rclpy')
    rclpy.node = types.ModuleType('rclpy.node')
    rclpy.node.Node = type('Node', (), {})
    rclpy.ok = lambda: True
    rclpy.init = lambda *a, **k: None
    rclpy.spin = lambda *a, **k: None
    rclpy.try_shutdown = lambda *a, **k: None
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
        setattr(std_msgs.msg, name, type(name, (), {'__init__': lambda self, **kw: None}))
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


def _load_fleet_module():
    _install_ros_stubs()
    path = Path(__file__).parents[1] / 'rehab_robotics_bridge' / 'fleet_bridge_node.py'
    spec = importlib.util.spec_from_file_location('fleet_bridge_node_test', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


if __name__ == '__main__':
    unittest.main()
