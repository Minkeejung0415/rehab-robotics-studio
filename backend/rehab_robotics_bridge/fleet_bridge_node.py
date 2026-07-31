"""Multi-session fleet bridge: canonical mac_ topics + layered registry."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from rehab_robotics_bridge.esp32_bridge_node import (
    device_topic_token,
    display_mac,
    normalize_device_id,
)

FLEET_REGISTRY_TOPIC = '/esp/fleet/registry'
FLEET_REGISTRY_SCHEMA = 'oe_esp32.fleet_registry.v1'


def canonical_topic_paths(device_id: str) -> tuple[str, str]:
    """Return identity-stable raw and status topic paths for a device."""
    token = device_topic_token(device_id)
    return f'/esp/raw/{token}', f'/esp/status/{token}'


def parse_routes_json(raw: str) -> list[dict[str, Any]]:
    """Parse the operator route table (JSON list of host/port/expected_device_id)."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('routes_json must be a non-empty JSON string')
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError('routes_json must be valid JSON') from exc
    if not isinstance(payload, list):
        raise ValueError('routes_json must be a JSON list')
    routes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ValueError(f'routes_json[{index}] must be an object')
        host = entry.get('host')
        port = entry.get('port', entry.get('listen_port'))
        expected = entry.get('expected_device_id', '')
        role = str(entry.get('role', '') or '')
        if not isinstance(host, str) or not host:
            raise ValueError(f'routes_json[{index}].host is required')
        if not isinstance(port, int) or isinstance(port, bool) or port <= 0:
            raise ValueError(f'routes_json[{index}].port must be a positive int')
        if not isinstance(expected, str) or not expected:
            raise ValueError(f'routes_json[{index}].expected_device_id is required')
        device_id = normalize_device_id(expected)
        if device_id != expected:
            raise ValueError(
                f'routes_json[{index}].expected_device_id must be canonical'
            )
        if device_id in seen_ids:
            raise ValueError(f'duplicate expected_device_id: {device_id}')
        seen_ids.add(device_id)
        routes.append({
            'host': host,
            'port': int(port),
            'expected_device_id': device_id,
            'role': role,
            'esp_port': int(entry.get('esp_port', 5000)),
            'body_segment': str(entry.get('body_segment', '') or ''),
        })
    return routes


@dataclass
class FleetDeviceState:
    """Layered readiness row for one known MAC (retained across TCP loss)."""

    device_id: str
    role: str = ''
    host: str = ''
    esp_port: int = 5000
    listen_port: int = 0
    discovery: str = 'unknown'
    command: str = 'unknown'
    route: str = 'offline'
    orientation_freshness: str = 'stale'
    synchronization: str = 'unknown'
    configured_hz: float = 0.0
    observed_hz: float = 0.0
    last_seen_us: int = 0
    udp_drop_count: int = 0
    queue_maxsize: int = 256
    reconnect_count: int = 0
    reconnect_generation: int = 0


def build_fleet_registry(
    devices: list[FleetDeviceState],
    *,
    revision: int = 1,
    timestamp_us: int | None = None,
    alias_master_device_id: str = '',
    alias_slave_device_id: str = '',
) -> dict[str, Any]:
    """Serialize devices into oe_esp32.fleet_registry.v1."""
    if timestamp_us is None:
        timestamp_us = time.monotonic_ns() // 1000
    rows: list[dict[str, Any]] = []
    for state in devices:
        device_id = normalize_device_id(state.device_id)
        rows.append({
            'device_id': device_id,
            'display_mac': display_mac(device_id),
            'topic_token': device_topic_token(device_id),
            'role': state.role,
            'endpoint': {
                'host': state.host,
                'esp_port': state.esp_port,
                'listen_port': state.listen_port,
            },
            'discovery': state.discovery,
            'command': state.command,
            'route': state.route,
            'orientation_freshness': state.orientation_freshness,
            'synchronization': state.synchronization,
            'rate': {
                'configured_hz': state.configured_hz,
                'observed_hz': state.observed_hz,
            },
            'drops': {
                'udp_drop_count': state.udp_drop_count,
                'queue_maxsize': state.queue_maxsize,
            },
            'reconnects': {
                'count': state.reconnect_count,
                'generation': state.reconnect_generation,
            },
            'last_seen_us': state.last_seen_us,
        })
    rows.sort(key=lambda row: row['device_id'])
    return {
        'schema': FLEET_REGISTRY_SCHEMA,
        'revision': revision,
        'timestamp_us': timestamp_us,
        'alias_master_device_id': alias_master_device_id or None,
        'alias_slave_device_id': alias_slave_device_id or None,
        'devices': rows,
    }


class FleetRegistryStore:
    """In-memory MAC-keyed registry that retains offline/stale rows."""

    def __init__(self) -> None:
        self._devices: dict[str, FleetDeviceState] = {}

    def upsert_connected(
        self,
        *,
        device_id: str,
        role: str,
        host: str,
        esp_port: int,
        listen_port: int,
        configured_hz: float,
        observed_hz: float,
        last_seen_us: int,
        discovery: str = 'present',
        command: str = 'ready',
        orientation_freshness: str = 'fresh',
        synchronization: str = 'unknown',
    ) -> None:
        device_id = normalize_device_id(device_id)
        prior = self._devices.get(device_id)
        generation = (prior.reconnect_generation + 1) if prior else 1
        reconnect_count = prior.reconnect_count if prior else 0
        self._devices[device_id] = FleetDeviceState(
            device_id=device_id,
            role=role,
            host=host,
            esp_port=esp_port,
            listen_port=listen_port,
            discovery=discovery,
            command=command,
            route='connected',
            orientation_freshness=orientation_freshness,
            synchronization=synchronization,
            configured_hz=configured_hz,
            observed_hz=observed_hz,
            last_seen_us=last_seen_us,
            udp_drop_count=prior.udp_drop_count if prior else 0,
            queue_maxsize=prior.queue_maxsize if prior else 256,
            reconnect_count=reconnect_count,
            reconnect_generation=generation,
        )

    def mark_offline(self, device_id: str, *, last_seen_us: int) -> None:
        device_id = normalize_device_id(device_id)
        state = self._devices.get(device_id)
        if state is None:
            self._devices[device_id] = FleetDeviceState(
                device_id=device_id,
                route='offline',
                discovery='known',
                command='unavailable',
                orientation_freshness='stale',
                last_seen_us=last_seen_us,
            )
            return
        state.route = 'offline'
        state.command = 'unavailable'
        state.orientation_freshness = 'stale'
        state.last_seen_us = last_seen_us

    def replace_session_identity(
        self,
        *,
        prior_device_id: str,
        new_device_id: str,
        role: str,
        host: str,
        esp_port: int,
        listen_port: int,
        configured_hz: float,
        observed_hz: float,
        last_seen_us: int,
    ) -> None:
        self.mark_offline(prior_device_id, last_seen_us=last_seen_us)
        self.upsert_connected(
            device_id=new_device_id,
            role=role,
            host=host,
            esp_port=esp_port,
            listen_port=listen_port,
            configured_hz=configured_hz,
            observed_hz=observed_hz,
            last_seen_us=last_seen_us,
        )

    def build(
        self,
        *,
        revision: int = 1,
        timestamp_us: int | None = None,
        alias_master_device_id: str = '',
        alias_slave_device_id: str = '',
    ) -> dict[str, Any]:
        return build_fleet_registry(
            list(self._devices.values()),
            revision=revision,
            timestamp_us=timestamp_us,
            alias_master_device_id=alias_master_device_id,
            alias_slave_device_id=alias_slave_device_id,
        )


class FleetDeviceSession:
    """One identity-bound publish session (canonical mac_ topics only here)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        expected_device_id: str,
        role: str = '',
        esp_port: int = 5000,
        create_publisher: Callable[..., Any] | None = None,
        string_message_type: type = String,
    ) -> None:
        self.host = host
        self.port = port
        self.esp_port = esp_port
        self.expected_device_id = normalize_device_id(expected_device_id)
        self.role = role
        self._create_publisher = create_publisher
        self._string_type = string_message_type
        self._bound_device_id: str | None = None
        self._raw_pub: Any = None
        self._status_pub: Any = None
        self._publishers: dict[str, Any] = {}

    def bind_verified_self(self, device_id: str) -> None:
        device_id = normalize_device_id(device_id)
        if device_id != self.expected_device_id:
            raise ValueError(
                'verified self must match expected_device_id before publishers bind'
            )
        self._bound_device_id = device_id
        raw_topic, status_topic = canonical_topic_paths(device_id)
        if self._create_publisher is not None:
            self._raw_pub = self._create_publisher(self._string_type, raw_topic, 10)
            self._status_pub = self._create_publisher(self._string_type, status_topic, 10)
            self._publishers[raw_topic] = self._raw_pub
            self._publishers[status_topic] = self._status_pub

    def canonical_topics(self) -> list[str]:
        if self._bound_device_id is None:
            return []
        raw, status = canonical_topic_paths(self._bound_device_id)
        return [raw, status]

    def publish_raw_json(self, payload: str) -> None:
        if self._raw_pub is None:
            raise RuntimeError('canonical raw publisher requires verified bind')
        message = self._string_type()
        message.data = payload
        self._raw_pub.publish(message)

    def publish_health_json(self, payload: str) -> None:
        if self._status_pub is None:
            raise RuntimeError('canonical status publisher requires verified bind')
        message = self._string_type()
        message.data = payload
        self._status_pub.publish(message)


class FleetSessionManager:
    """Owns N identity sessions and the shared layered registry (ROS-free core)."""

    def __init__(
        self,
        routes: list[dict[str, Any]],
        *,
        create_publisher: Callable[..., Any] | None = None,
        string_message_type: type = String,
        alias_master_device_id: str = '',
        alias_slave_device_id: str = '',
        on_registry_change: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.registry = FleetRegistryStore()
        self.revision = 0
        self.sessions: list[FleetDeviceSession] = []
        self._alias_master = (
            normalize_device_id(alias_master_device_id) if alias_master_device_id else ''
        )
        self._alias_slave = (
            normalize_device_id(alias_slave_device_id) if alias_slave_device_id else ''
        )
        self._on_registry_change = on_registry_change
        for route in routes:
            session = FleetDeviceSession(
                host=route['host'],
                port=route['port'],
                expected_device_id=route['expected_device_id'],
                role=route.get('role', ''),
                esp_port=int(route.get('esp_port', 5000)),
                create_publisher=create_publisher,
                string_message_type=string_message_type,
            )
            self.registry.mark_offline(route['expected_device_id'], last_seen_us=0)
            row = self.registry._devices[route['expected_device_id']]
            row.role = route.get('role', '')
            row.host = route['host']
            row.listen_port = route['port']
            row.esp_port = int(route.get('esp_port', 5000))
            row.discovery = 'configured'
            self.sessions.append(session)

    def build_registry(self) -> dict[str, Any]:
        return self.registry.build(
            revision=self.revision,
            alias_master_device_id=self._alias_master,
            alias_slave_device_id=self._alias_slave,
        )

    def _emit_registry(self) -> dict[str, Any]:
        doc = self.build_registry()
        if self._on_registry_change is not None:
            self._on_registry_change(doc)
        return doc

    def on_session_bound(
        self,
        session: FleetDeviceSession,
        device_id: str,
        *,
        configured_hz: float = 100.0,
        observed_hz: float = 0.0,
        last_seen_us: int | None = None,
    ) -> dict[str, Any]:
        if last_seen_us is None:
            last_seen_us = time.monotonic_ns() // 1000
        prior = session._bound_device_id
        if prior is not None and prior != device_id:
            self.registry.replace_session_identity(
                prior_device_id=prior,
                new_device_id=device_id,
                role=session.role,
                host=session.host,
                esp_port=session.esp_port,
                listen_port=session.port,
                configured_hz=configured_hz,
                observed_hz=observed_hz,
                last_seen_us=last_seen_us,
            )
            session.expected_device_id = normalize_device_id(device_id)
            session._bound_device_id = None
            session._raw_pub = None
            session._status_pub = None
            session._publishers.clear()
            session.bind_verified_self(device_id)
        else:
            session.bind_verified_self(device_id)
            self.registry.upsert_connected(
                device_id=device_id,
                role=session.role,
                host=session.host,
                esp_port=session.esp_port,
                listen_port=session.port,
                configured_hz=configured_hz,
                observed_hz=observed_hz,
                last_seen_us=last_seen_us,
            )
        self.revision += 1
        return self._emit_registry()

    def on_session_offline(
        self,
        session: FleetDeviceSession,
        *,
        last_seen_us: int | None = None,
    ) -> dict[str, Any]:
        if last_seen_us is None:
            last_seen_us = time.monotonic_ns() // 1000
        device_id = session._bound_device_id or session.expected_device_id
        self.registry.mark_offline(device_id, last_seen_us=last_seen_us)
        self.revision += 1
        return self._emit_registry()


class FleetBridgeNode(Node):
    """Single process owning N identity sessions and /esp/fleet/registry."""

    def __init__(self) -> None:
        super().__init__('fleet_bridge_node')
        self.declare_parameter('routes_json', '[]')
        self.declare_parameter('body_segments_json', '{}')
        self.declare_parameter('registry_period_s', 0.5)
        self.declare_parameter('alias_master_device_id', '')
        self.declare_parameter('alias_slave_device_id', '')

        routes_raw = self.get_parameter('routes_json').value
        if not isinstance(routes_raw, str):
            raise ValueError('routes_json must be a string')
        self._routes = parse_routes_json(routes_raw) if routes_raw.strip() not in ('', '[]') else []
        body_raw = self.get_parameter('body_segments_json').value
        self._body_segments: dict[str, str] = {}
        if isinstance(body_raw, str) and body_raw.strip():
            parsed = json.loads(body_raw)
            if not isinstance(parsed, dict):
                raise ValueError('body_segments_json must be a JSON object')
            self._body_segments = {
                normalize_device_id(key): str(value)
                for key, value in parsed.items()
            }

        alias_master = str(self.get_parameter('alias_master_device_id').value or '')
        alias_slave = str(self.get_parameter('alias_slave_device_id').value or '')
        self._manager = FleetSessionManager(
            self._routes,
            create_publisher=self.create_publisher,
            string_message_type=String,
            alias_master_device_id=alias_master,
            alias_slave_device_id=alias_slave,
            on_registry_change=self._publish_registry_doc,
        )
        self._sessions = self._manager.sessions
        self._registry = self._manager.registry
        self._pub_registry = self.create_publisher(String, FLEET_REGISTRY_TOPIC, 10)
        period = float(self.get_parameter('registry_period_s').value)
        self._registry_timer = self.create_timer(max(0.1, period), self._publish_registry)

        self.get_logger().info(
            f'fleet_bridge_node routes={len(self._sessions)} '
            f'registry={FLEET_REGISTRY_TOPIC}'
        )

        self._loop = asyncio.new_event_loop()
        threading.Thread(
            target=self._loop.run_until_complete,
            args=(self._run_sessions(),),
            daemon=True,
        ).start()

    @property
    def _revision(self) -> int:
        return self._manager.revision

    @property
    def _alias_master(self) -> str:
        return self._manager._alias_master

    @property
    def _alias_slave(self) -> str:
        return self._manager._alias_slave

    def on_session_bound(
        self,
        session: FleetDeviceSession,
        device_id: str,
        *,
        configured_hz: float = 100.0,
        observed_hz: float = 0.0,
        last_seen_us: int | None = None,
    ) -> None:
        """Record a verified bind and ensure canonical publishers exist."""
        self._manager.on_session_bound(
            session,
            device_id,
            configured_hz=configured_hz,
            observed_hz=observed_hz,
            last_seen_us=last_seen_us,
        )

    def on_session_offline(
        self,
        session: FleetDeviceSession,
        *,
        last_seen_us: int | None = None,
    ) -> None:
        self._manager.on_session_offline(session, last_seen_us=last_seen_us)

    def _publish_registry_doc(self, doc: dict[str, Any]) -> None:
        message = String()
        message.data = json.dumps(doc, sort_keys=True, separators=(',', ':'))
        self._pub_registry.publish(message)

    def _publish_registry(self) -> None:
        self._publish_registry_doc(self._manager.build_registry())

    async def _run_sessions(self) -> None:
        """Supervisor placeholder: each session reconnects independently.

        Live TCP/UDP streaming continues to use Esp32BridgeNode / relay paths;
        this fleet node owns registry + canonical publisher lifecycle. Plan 04
        hardens per-session isolation against sibling failures.
        """
        while rclpy.ok():
            await asyncio.sleep(1.0)


def main(args=None):
    rclpy.init(args=args)
    node = FleetBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
