"""Multi-session fleet bridge: canonical mac_ topics + layered registry."""
from __future__ import annotations

import asyncio
import json
import math
import socket
import struct
import threading
import time
from collections import deque
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Header, String
from rehab_robotics_interfaces.srv import IdentifyDevice

from rehab_robotics_bridge.esp32_bridge_node import (
    device_topic_token,
    display_mac,
    normalize_device_id,
    OE_HEADER,
    OE_HEADER_SIZE,
    NUM_CHANNELS,
    HANDSHAKE_CONNECT,
    HANDSHAKE_START,
    IDENTITY_QUERY,
    IDENTITY_PROTOCOL,
    IDENTIFY_PROTOCOL,
    MAX_CONTROL_LINE_BYTES,
    CONTROL_RESPONSE_PREFIXES,
    IDENTIFY_DURATION_MIN_MS,
    IDENTIFY_DURATION_MAX_MS,
    QUAT_SCALE,
    is_valid_oe_header,
    find_next_oe_header,
    parse_identity_self,
    parse_identity_peer,
    parse_identity_inventory,
    validate_identify_request,
    parse_identify_reply,
)

# ICM20948 scale factors (same values as esp32_bridge_node — defined locally to avoid
# circular import concerns if esp32_bridge_node ever imports from fleet_bridge_node).
ACC_SCALE = 9.80665 / 16384.0       # m/s² per LSB at ±2g
GYR_SCALE = (math.pi / 180.0) / 131.072  # rad/s per LSB at ±250 dps

FLEET_REGISTRY_TOPIC = '/esp/fleet/registry'
FLEET_REGISTRY_SCHEMA = 'oe_esp32.fleet_registry.v1'

# Compatibility aliases (COMP-01 / FLEET-02): same String payload as canonical mac_ topics.
# Typed OpenSim IMU (/esp32/{master,slave}/imu) is NOT mirrored here — those stay on
# stream publishers / OpenSim launch consumers; fleet owns JSON raw/status aliases only.
ALIAS_RAW_MASTER_TOPIC = '/esp/raw/master'
ALIAS_RAW_SLAVE_TOPIC = '/esp/raw/slave'
ALIAS_STATUS_MASTER_TOPIC = '/esp/status/master'
ALIAS_STATUS_SLAVE_TOPIC = '/esp/status/slave'
PAIR_HEALTH_TOPIC = '/esp/status/pair'
PAIR_HEALTH_SCHEMA = 'oe_esp32.pair_health.v1'


async def run_isolated_session_tasks(
    session_factories: list[Callable[[], Awaitable[Any]]],
    *,
    on_session_error: Callable[[int, BaseException], None] | None = None,
) -> list[BaseException | None]:
    """Run one supervised task per session; sibling failures never cancel peers.

    Recording/acquisition paths must call this (or equivalent per-task
    supervision) instead of a fatal ``asyncio.gather`` that cancels siblings
    on the first exception. ``CancelledError`` is re-raised so shutdown still
    propagates; other errors are reported and swallowed per index.
    """

    async def _guard(index: int, factory: Callable[[], Awaitable[Any]]) -> BaseException | None:
        try:
            await factory()
            return None
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — isolation boundary
            if on_session_error is not None:
                on_session_error(index, exc)
            return exc

    tasks = [
        asyncio.create_task(_guard(index, factory), name=f'fleet-session-{index}')
        for index, factory in enumerate(session_factories)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors: list[BaseException | None] = []
    for result in results:
        if isinstance(result, asyncio.CancelledError):
            raise result
        if isinstance(result, BaseException):
            errors.append(result)
        else:
            errors.append(result)
    return errors


def build_pair_health(
    master_snapshot: dict[str, Any] | None,
    slave_snapshot: dict[str, Any] | None,
    *,
    timestamp_us: int | None = None,
) -> dict[str, Any]:
    """Build oe_esp32.pair_health.v1 from alias-bound master/slave health snapshots."""
    if timestamp_us is None:
        if isinstance(master_snapshot, dict) and isinstance(
            master_snapshot.get('timestamp_us'), int
        ):
            timestamp_us = master_snapshot['timestamp_us']
        else:
            timestamp_us = time.monotonic_ns() // 1000
    master_ok = (
        isinstance(master_snapshot, dict)
        and master_snapshot.get('connection_state') == 'connected'
    )
    slave_ok = (
        isinstance(slave_snapshot, dict)
        and slave_snapshot.get('connection_state') == 'connected'
    )
    return {
        'schema': PAIR_HEALTH_SCHEMA,
        'timestamp_us': timestamp_us,
        'master': master_snapshot,
        'slave': slave_snapshot,
        'pair_available': bool(master_ok and slave_ok),
    }


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

    def mark_reconnecting(self, device_id: str, *, last_seen_us: int) -> None:
        """Mark one route reconnecting without removing the registry row."""
        device_id = normalize_device_id(device_id)
        state = self._devices.get(device_id)
        if state is None:
            self._devices[device_id] = FleetDeviceState(
                device_id=device_id,
                route='reconnecting',
                discovery='known',
                command='unavailable',
                orientation_freshness='stale',
                last_seen_us=last_seen_us,
            )
            return
        state.route = 'reconnecting'
        state.command = 'unavailable'
        state.orientation_freshness = 'stale'
        state.last_seen_us = last_seen_us

    def record_udp_drops(self, device_id: str, drop_count: int) -> None:
        """Set absolute per-device UDP drop-oldest counter (relay-visible)."""
        device_id = normalize_device_id(device_id)
        state = self._devices.get(device_id)
        if state is None:
            self._devices[device_id] = FleetDeviceState(
                device_id=device_id,
                route='offline',
                discovery='known',
                udp_drop_count=int(drop_count),
            )
            return
        state.udp_drop_count = int(drop_count)

    def note_reconnect(self, device_id: str) -> None:
        """Increment reconnect_count for the affected device only."""
        device_id = normalize_device_id(device_id)
        state = self._devices.get(device_id)
        if state is None:
            self._devices[device_id] = FleetDeviceState(
                device_id=device_id,
                route='reconnecting',
                discovery='known',
                reconnect_count=1,
            )
            return
        state.reconnect_count += 1

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
    """Owns N identity sessions, registry, and explicit Master/Slave aliases."""

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
        self._create_publisher = create_publisher
        self._string_type = string_message_type
        self._alias_master_param = (
            normalize_device_id(alias_master_device_id) if alias_master_device_id else ''
        )
        self._alias_slave_param = (
            normalize_device_id(alias_slave_device_id) if alias_slave_device_id else ''
        )
        self._alias_master = self._alias_master_param
        self._alias_slave = self._alias_slave_param
        self._on_registry_change = on_registry_change
        self._online_devices: set[str] = set()
        self._alias_raw_master_pub: Any = None
        self._alias_raw_slave_pub: Any = None
        self._alias_status_master_pub: Any = None
        self._alias_status_slave_pub: Any = None
        self._pair_health_pub: Any = None
        if create_publisher is not None:
            self._alias_raw_master_pub = create_publisher(
                string_message_type, ALIAS_RAW_MASTER_TOPIC, 10
            )
            self._alias_raw_slave_pub = create_publisher(
                string_message_type, ALIAS_RAW_SLAVE_TOPIC, 10
            )
            self._alias_status_master_pub = create_publisher(
                string_message_type, ALIAS_STATUS_MASTER_TOPIC, 10
            )
            self._alias_status_slave_pub = create_publisher(
                string_message_type, ALIAS_STATUS_SLAVE_TOPIC, 10
            )
            self._pair_health_pub = create_publisher(
                string_message_type, PAIR_HEALTH_TOPIC, 10
            )
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

    def aliases_bound(self) -> bool:
        return bool(self._alias_master and self._alias_slave)

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

    def _publish_string(self, publisher: Any, payload: str) -> None:
        if publisher is None:
            return
        message = self._string_type()
        message.data = payload
        publisher.publish(message)

    def _device_online(self, device_id: str) -> bool:
        if not device_id:
            return False
        return device_id in self._online_devices

    def _resolve_role_aliases(self) -> None:
        """Bind empty alias params to first verified master/slave roles (not TCP order)."""
        if not self._alias_master_param:
            for session in self.sessions:
                if session._bound_device_id and session.role == 'master':
                    self._alias_master = session._bound_device_id
                    break
        else:
            self._alias_master = self._alias_master_param
        if not self._alias_slave_param:
            for session in self.sessions:
                if session._bound_device_id and session.role == 'slave':
                    self._alias_slave = session._bound_device_id
                    break
        else:
            self._alias_slave = self._alias_slave_param

    def _mirror_alias_payload(
        self,
        device_id: str,
        *,
        raw_payload: str | None = None,
        status_payload: str | None = None,
    ) -> None:
        if not device_id or not self._device_online(device_id):
            return
        if device_id == self._alias_master:
            if raw_payload is not None:
                self._publish_string(self._alias_raw_master_pub, raw_payload)
            if status_payload is not None:
                self._publish_string(self._alias_status_master_pub, status_payload)
        if device_id == self._alias_slave:
            if raw_payload is not None:
                self._publish_string(self._alias_raw_slave_pub, raw_payload)
            if status_payload is not None:
                self._publish_string(self._alias_status_slave_pub, status_payload)

    def publish_session_raw(self, session: FleetDeviceSession, payload: str) -> None:
        session.publish_raw_json(payload)
        device_id = session._bound_device_id or ''
        self._mirror_alias_payload(device_id, raw_payload=payload)

    def publish_session_health(self, session: FleetDeviceSession, payload: str) -> None:
        session.publish_health_json(payload)
        device_id = session._bound_device_id or ''
        self._mirror_alias_payload(device_id, status_payload=payload)

    def publish_pair_health(
        self,
        master_snapshot: dict[str, Any] | None,
        slave_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Publish /esp/status/pair only when both Master and Slave aliases are bound."""
        if not self.aliases_bound():
            return None
        pair = build_pair_health(master_snapshot, slave_snapshot)
        self._publish_string(
            self._pair_health_pub,
            json.dumps(pair, sort_keys=True, separators=(',', ':')),
        )
        return pair

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
        device_id = normalize_device_id(device_id)
        prior_state = self.registry._devices.get(device_id)
        # Count reconnect only after a prior connected generation (not initial configure).
        if (
            prior_state is not None
            and prior_state.route in ('offline', 'reconnecting', 'stale')
            and prior_state.reconnect_generation >= 1
        ):
            self.registry.note_reconnect(device_id)
        if prior is not None and prior != device_id:
            self._online_devices.discard(prior)
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
        self._online_devices.add(normalize_device_id(device_id))
        self._resolve_role_aliases()
        self.revision += 1
        return self._emit_registry()

    def on_session_reconnecting(
        self,
        session: FleetDeviceSession,
        *,
        last_seen_us: int | None = None,
    ) -> dict[str, Any]:
        """Mark only this session reconnecting; siblings keep publishing."""
        if last_seen_us is None:
            last_seen_us = time.monotonic_ns() // 1000
        device_id = session._bound_device_id or session.expected_device_id
        self._online_devices.discard(normalize_device_id(device_id))
        self.registry.mark_reconnecting(device_id, last_seen_us=last_seen_us)
        self.revision += 1
        return self._emit_registry()

    def apply_udp_drop_count(self, device_id: str, drop_count: int) -> dict[str, Any]:
        """Propagate relay-visible per-route drop_count into the registry row."""
        self.registry.record_udp_drops(device_id, drop_count)
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
        self._online_devices.discard(normalize_device_id(device_id))
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
        self.declare_parameter('reconnect_delay_s', 5.0)
        self.declare_parameter('handshake_timeout_s', 15.0)
        self.declare_parameter('identify_timeout_s', 3.0)
        self._reconnect_delay_s = float(self.get_parameter('reconnect_delay_s').value)
        self._handshake_timeout_s = float(self.get_parameter('handshake_timeout_s').value)
        self._identify_timeout_s = float(self.get_parameter('identify_timeout_s').value)

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

        # Per-session live state (indexed to match self._sessions).
        n = len(self._sessions)
        self._active_writers: list[asyncio.StreamWriter | None] = [None] * n
        self._session_locks: list[asyncio.Lock | None] = [None] * n
        self._identify_queues: list[asyncio.Queue | None] = [None] * n
        self._imu_pubs: dict[str, Any] = {}

        # Typed Imu publishers for alias-bound roles (exist even if no alias is bound yet;
        # they publish only when a session with matching alias role streams frames).
        self._imu_pubs['master'] = self.create_publisher(Imu, '/esp32/master/imu', 10)
        self._imu_pubs['slave'] = self.create_publisher(Imu, '/esp32/slave/imu', 10)

        # IdentifyDevice service routed to the correct per-session writer.
        self.create_service(IdentifyDevice, '/esp32/fleet/identify', self._identify_fleet_device)

        self.get_logger().info(
            f'fleet_bridge_node routes={len(self._sessions)} '
            f'registry={FLEET_REGISTRY_TOPIC} '
            f'alias_master={alias_master or "(role-resolved)"} '
            f'alias_slave={alias_slave or "(role-resolved)"}'
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
        """Supervise one isolated TCP session task per configured route."""
        if not self._sessions:
            while rclpy.ok():
                await asyncio.sleep(1.0)
            return

        await run_isolated_session_tasks(
            [lambda i=index: self._connect_and_stream_route(i)
             for index in range(len(self._sessions))],
            on_session_error=lambda index, exc: self.get_logger().warning(
                f'isolated session[{index}] exited with {exc!r}'
            ),
        )

    async def _fleet_handshake(
        self,
        index: int,
        session: 'FleetDeviceSession',
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> str:
        """Perform IDENTITY?/REDPITAYA/START handshake; return 'tcp' or 'udp'."""
        writer.write(IDENTITY_QUERY)
        await writer.drain()
        deadline = asyncio.get_running_loop().time() + self._handshake_timeout_s

        async def _read_line() -> str:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError('identity timeout')
            raw = await asyncio.wait_for(reader.readline(), timeout=remaining)
            if not raw:
                raise EOFError('stream closed during identity')
            return raw.decode('ascii', errors='replace').rstrip('\r\n')

        records = [await _read_line()]
        self_id = parse_identity_self(records[0])
        peer_count = int(self_id['peer_count'])
        for _ in range(peer_count + 1):
            records.append(await _read_line())
        inventory = parse_identity_inventory(records)
        reported = str(inventory['self']['device_id'])
        if reported != session.expected_device_id:
            raise RuntimeError(
                f'[fleet:{index}] expected {session.expected_device_id}, got {reported}'
            )
        self.on_session_bound(
            session,
            reported,
            configured_hz=100.0,
            observed_hz=0.0,
        )
        self.get_logger().info(
            f'[fleet:{index}] identity bound: {reported} role={session.role}'
        )

        # REDPITAYA handshake
        writer.write(HANDSHAKE_CONNECT)
        await writer.drain()
        remaining = max(0.1, deadline - asyncio.get_running_loop().time())
        await asyncio.wait_for(reader.readline(), timeout=remaining)

        # START streaming
        writer.write(HANDSHAKE_START)
        await writer.drain()
        started = b''
        for _ in range(3):
            remaining = max(0.1, deadline - asyncio.get_running_loop().time())
            line = await asyncio.wait_for(reader.readline(), timeout=remaining)
            if b'STARTED' in line:
                started = line
                break
        if not started:
            raise RuntimeError(f'[fleet:{index}] ESP32 did not acknowledge START')

        # Consume SENSORS line if present (non-blocking peek)
        for _ in range(5):
            await asyncio.sleep(0.02)
            if reader._buffer.startswith(b'SENSORS:'):  # type: ignore[attr-defined]
                await reader.readline()
                break

        return 'udp' if b'transport=udp' in started else 'tcp'

    async def _read_fleet_frames(
        self,
        index: int,
        session: 'FleetDeviceSession',
        reader: asyncio.StreamReader,
    ) -> None:
        """Read OE binary frames and publish via the fleet manager."""
        buf = bytearray()
        n_frames = 0
        frame_times: deque[float] = deque()

        while rclpy.ok():
            # Control text scanner
            control_offsets = [
                offset for prefix in CONTROL_RESPONSE_PREFIXES
                if (offset := buf.find(prefix)) >= 0
            ]
            if control_offsets:
                control_offset = min(control_offsets)
                if control_offset:
                    del buf[:control_offset]
                while b'\n' not in buf:
                    chunk = await reader.read(4096)
                    if not chunk:
                        raise EOFError('stream closed while reading control line')
                    buf.extend(chunk)
                    if len(buf) > MAX_CONTROL_LINE_BYTES:
                        raise RuntimeError('control line exceeds bound')
                line, _, remainder = buf.partition(b'\n')
                buf[:] = remainder
                text = line.decode(errors='replace').strip()
                queue = self._identify_queues[index]
                if queue is not None and text.startswith(('IDENTIFY_ACK ', 'IDENTIFY_ERR ')):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(text)
                continue

            # Accumulate header
            while len(buf) < OE_HEADER_SIZE:
                chunk = await reader.read(4096)
                if not chunk:
                    raise EOFError('stream closed')
                buf.extend(chunk)

            if any(buf.find(prefix) >= 0 for prefix in CONTROL_RESPONSE_PREFIXES):
                continue

            if not is_valid_oe_header(buf):
                sync_offset = find_next_oe_header(buf, 1)
                if sync_offset is not None:
                    del buf[:sync_offset]
                    continue
                chunk = await reader.read(4096)
                if not chunk:
                    raise EOFError('stream closed while resyncing')
                buf.extend(chunk)
                if len(buf) > 8192:
                    del buf[:-(OE_HEADER_SIZE - 1)]
                continue

            _off, num_bytes, _bd, elem, n_ch, n_per = OE_HEADER.unpack_from(buf, 0)
            total = OE_HEADER_SIZE + num_bytes
            while len(buf) < total:
                chunk = await reader.read(4096)
                if not chunk:
                    raise EOFError('stream closed during payload')
                buf.extend(chunk)

            payload = bytes(buf[OE_HEADER_SIZE:total])
            del buf[:total]

            if elem != 2 or n_ch < NUM_CHANNELS:
                continue

            n_frames += 1
            frame_time = time.monotonic()
            frame_times.append(frame_time)
            now = frame_time
            while frame_times and now - frame_times[0] > 5.0:
                frame_times.popleft()

            self._publish_fleet_frame(index, session, payload, n_ch, n_per, n_frames)

            if n_frames % 500 == 0:
                self.get_logger().debug(
                    f'[fleet:{index}] {n_frames} frames published'
                )

    def _publish_fleet_frame(
        self,
        index: int,
        session: 'FleetDeviceSession',
        payload: bytes,
        n_ch: int,
        n_per: int,
        frame_index: int,
    ) -> None:
        """Decode OE payload and publish canonical + typed Imu messages."""
        def s16(ch: int) -> int:
            i = ch * n_per * 2
            return int.from_bytes(payload[i:i + 2], 'little', signed=True)

        device_id = session._bound_device_id or session.expected_device_id
        now_us = time.monotonic_ns() // 1000

        raw_json = json.dumps({
            'sample_index': frame_index,
            'seq': frame_index,
            'time_us': now_us,
            'node_role': session.role,
            'device_id': device_id,
            'topic_schema': 'oe_esp32.raw.v1',
            'imu': {
                'ax': s16(0), 'ay': s16(1), 'az': s16(2),
                'gx': s16(3), 'gy': s16(4), 'gz': s16(5),
                'mx': s16(6), 'my': s16(7), 'mz': s16(8),
            },
            'quat': {
                'qw': s16(9), 'qx': s16(10), 'qy': s16(11), 'qz': s16(12),
            },
            'dio': s16(13),
        }, sort_keys=True, separators=(',', ':'))

        self._manager.publish_session_raw(session, raw_json)

        # Publish typed Imu when this session's role maps to an alias
        role = session.role
        imu_pub = self._imu_pubs.get(role)
        alias_id = (
            self._manager._alias_master if role == 'master'
            else self._manager._alias_slave if role == 'slave'
            else ''
        )
        if imu_pub is not None and alias_id and device_id == alias_id:
            imu_msg = Imu()
            imu_msg.header = Header()
            imu_msg.header.stamp = self.get_clock().now().to_msg()
            imu_msg.header.frame_id = f'esp32_{role}'
            imu_msg.orientation.w = s16(9) * QUAT_SCALE
            imu_msg.orientation.x = s16(10) * QUAT_SCALE
            imu_msg.orientation.y = s16(11) * QUAT_SCALE
            imu_msg.orientation.z = s16(12) * QUAT_SCALE
            imu_msg.linear_acceleration.x = s16(0) * ACC_SCALE
            imu_msg.linear_acceleration.y = s16(1) * ACC_SCALE
            imu_msg.linear_acceleration.z = s16(2) * ACC_SCALE
            imu_msg.angular_velocity.x = s16(3) * GYR_SCALE
            imu_msg.angular_velocity.y = s16(4) * GYR_SCALE
            imu_msg.angular_velocity.z = s16(5) * GYR_SCALE
            imu_msg.orientation_covariance[0] = -1.0
            imu_msg.linear_acceleration_covariance[0] = -1.0
            imu_msg.angular_velocity_covariance[0] = -1.0
            imu_pub.publish(imu_msg)

    async def _connect_and_stream_route(self, index: int) -> None:
        """Per-session reconnect loop with exponential backoff and drop_count propagation."""
        session = self._sessions[index]
        retry_delay = self._reconnect_delay_s
        while rclpy.ok():
            try:
                reader, writer = await asyncio.open_connection(session.host, session.port)
                self.get_logger().info(
                    f'[fleet:{index}] connected to {session.host}:{session.port}'
                )
                try:
                    self._active_writers[index] = writer
                    self._session_locks[index] = asyncio.Lock()
                    self._identify_queues[index] = asyncio.Queue(maxsize=256)
                    await self._fleet_handshake(index, session, reader, writer)
                    retry_delay = self._reconnect_delay_s
                    await self._read_fleet_frames(index, session, reader)
                finally:
                    self._active_writers[index] = None
                    self._session_locks[index] = None
                    self._identify_queues[index] = None
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                    self.get_logger().info(f'[fleet:{index}] disconnected')
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Fetch latest relay drop counts and propagate to registry
                device_id = session._bound_device_id or session.expected_device_id
                relay_state = self._manager.registry._devices.get(device_id)
                if relay_state is not None:
                    self._manager.apply_udp_drop_count(device_id, relay_state.udp_drop_count)
                self._manager.on_session_reconnecting(
                    session,
                    last_seen_us=time.monotonic_ns() // 1000,
                )
                self.get_logger().warning(
                    f'[fleet:{index}] {session.expected_device_id} '
                    f'error={exc!r}; retry in {retry_delay:.0f}s'
                )

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2.0, 30.0)

    def _identify_fleet_device(self, request, response):
        """Route an IdentifyDevice request to the correct per-session asyncio writer."""
        command_id = str(getattr(request, 'command_id', ''))
        raw_target = str(getattr(request, 'target_device_id', ''))
        duration_ms = int(getattr(request, 'duration_ms', 0))

        def _fail(outcome, detail):
            response.command_id = command_id
            response.target_device_id = raw_target
            response.outcome = outcome
            response.applied_duration_ms = 0
            response.detail = detail
            return response

        try:
            target = normalize_device_id(raw_target)
            if target != raw_target:
                raise ValueError('target_device_id must be canonical')
        except ValueError as exc:
            return _fail('invalid_target', str(exc))

        try:
            command_id, target, duration_ms = validate_identify_request(
                command_id, target, duration_ms
            )
        except ValueError as exc:
            return _fail('rejected', str(exc))

        # Find the session that owns this target MAC
        session_index: int | None = None
        for idx, session in enumerate(self._sessions):
            bound = session._bound_device_id
            if (bound == target) or (bound is None and session.expected_device_id == target):
                session_index = idx
                break

        if session_index is None:
            return _fail('offline', 'target device_id not in fleet routes')

        writer = self._active_writers[session_index]
        lock = self._session_locks[session_index]
        id_queue = self._identify_queues[session_index]

        if writer is None or lock is None or id_queue is None or writer.is_closing():
            return _fail('offline', 'session is not connected')

        try:
            result = asyncio.run_coroutine_threadsafe(
                self._send_fleet_identify_command(
                    session_index, writer, lock, id_queue,
                    command_id, target, duration_ms,
                ),
                self._loop,
            ).result(timeout=self._identify_timeout_s + 1.0)
        except (TimeoutError, FutureTimeoutError):
            result = {'outcome': 'timeout', 'applied_duration_ms': 0,
                      'detail': 'host wait timed out'}
        except Exception as exc:
            result = {'outcome': 'offline', 'applied_duration_ms': 0, 'detail': str(exc)}

        response.command_id = command_id
        response.target_device_id = target
        response.outcome = str(result.get('outcome', 'rejected'))
        response.applied_duration_ms = int(result.get('applied_duration_ms', 0))
        response.detail = str(result.get('detail', ''))
        return response

    async def _send_fleet_identify_command(
        self,
        index: int,
        writer: asyncio.StreamWriter,
        lock: asyncio.Lock,
        id_queue: asyncio.Queue,
        command_id: str,
        target: str,
        duration_ms: int,
    ) -> dict:
        """Send IDENTIFY command and drain identify_queue for a correlated reply."""
        async with lock:
            writer.write(
                (
                    f'IDENTIFY protocol={IDENTIFY_PROTOCOL} '
                    f'command_id={command_id} target={target} '
                    f'duration_ms={duration_ms}\n'
                ).encode('ascii')
            )
            await writer.drain()
            deadline = asyncio.get_running_loop().time() + self._identify_timeout_s
            sent_unconfirmed = None
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return sent_unconfirmed or {
                        'outcome': 'timeout', 'applied_duration_ms': 0,
                        'detail': 'timed out waiting for correlated reply',
                    }
                try:
                    line = await asyncio.wait_for(id_queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    return sent_unconfirmed or {
                        'outcome': 'timeout', 'applied_duration_ms': 0,
                        'detail': 'timed out waiting for correlated reply',
                    }
                try:
                    parsed = parse_identify_reply(
                        line,
                        expected_command_id=command_id,
                        expected_target=target,
                    )
                except ValueError:
                    continue
                if parsed['outcome'] == 'sent_unconfirmed':
                    sent_unconfirmed = parsed
                    continue
                return parsed


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
