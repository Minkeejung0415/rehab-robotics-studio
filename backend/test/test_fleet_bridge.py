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


if __name__ == '__main__':
    unittest.main()
