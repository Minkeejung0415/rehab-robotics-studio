"""Relay STEP_ESP32 master/slave control and samples from Windows into WSL ROS.

The ESPs send UDP samples to the source IP of their TCP control clients. WSL2
has a private NAT address that the ESP Soft AP cannot route to. This process
therefore owns both ESP TCP connections on Windows, binds shared UDP port 55001
once, and routes datagrams by source IP to separate WSL bridge clients.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
from dataclasses import dataclass, field
import re
import socket
import time
from typing import Iterable, Sequence


IDENTITY_PROTOCOL = 'id-v1'
MAX_IDENTITY_LINE_BYTES = 768
MAX_IDENTITY_HANDSHAKE_BYTES = 16_384
MAX_IDENTITY_PEERS = 64
MAX_SLAVE_ROUTES = 6
CONTROL_LOG_PREFIXES = (
    b'REC ', b'SLAVE_STATUS ', b'SD_STATUS ', b'SD_FINAL ',
    b'STOPPED', b'OK FREQ:', b'ERROR FREQ:',
    b'OK FILTER ', b'ERROR FILTER:', b'OK CFG ', b'ERROR CFG:',
    b'IDENTITY_OK ', b'IDENTITY_PEER ', b'IDENTITY_END ',
    b'IDENTIFY_ACK ', b'IDENTIFY_ERR ',
)
_COMPACT_MAC_RE = re.compile(r'^[0-9A-Fa-f]{12}$')
_DISPLAY_MAC_RE = re.compile(r'^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
_TOKEN_VALUE_RE = re.compile(r'^[A-Za-z0-9_.:,/@+-]+$')


class IdentityProtocolError(ValueError):
    """The endpoint returned an invalid or incomplete identity inventory."""


class IdentityChangedError(IdentityProtocolError):
    """A verified connection reported a different stable identity."""


@dataclass
class SessionIdentity:
    device_id: str | None
    display_mac: str | None
    base_mac: str | None
    sta_mac: str | None
    ap_mac: str | None
    espnow_mac: str | None
    role: str
    capabilities: tuple[str, ...] = ()
    verification_state: str = 'unsupported'
    current_endpoint: str | None = None
    schema_version: int = 0

    @property
    def verified(self) -> bool:
        return self.verification_state == 'verified' and self.device_id is not None


@dataclass(frozen=True)
class PeerIdentity:
    device_id: str | None
    display_mac: str | None
    base_mac: str | None
    sta_mac: str | None
    ap_mac: str | None
    espnow_mac: str | None
    transport_mac: str | None
    role: str
    capabilities: tuple[str, ...] = ()
    verification_state: str = 'unsupported'
    schema_version: int = 0
    slot: int | None = None

    @property
    def verified(self) -> bool:
        return self.verification_state == 'verified' and self.device_id is not None


@dataclass(frozen=True)
class IdentityInventory:
    session: SessionIdentity
    peers: dict[str, PeerIdentity] = field(default_factory=dict)


def normalize_device_id(value: str) -> str:
    """Normalize one complete 48-bit MAC without inferring missing bits."""
    if _COMPACT_MAC_RE.fullmatch(value):
        compact = value
    elif value.startswith('esp32:') and _COMPACT_MAC_RE.fullmatch(value[6:]):
        compact = value[6:]
    elif _DISPLAY_MAC_RE.fullmatch(value):
        compact = value.replace(':', '')
    else:
        raise ValueError('device identity must contain exactly 12 hexadecimal digits')
    return f'esp32:{compact.lower()}'


def display_mac(device_id: str) -> str:
    compact = normalize_device_id(device_id)[6:]
    return ':'.join(compact[index:index + 2] for index in range(0, 12, 2)).upper()


def _decode_identity_line(line: bytes | str) -> tuple[str, dict[str, str]]:
    if isinstance(line, bytes):
        if len(line) > MAX_IDENTITY_LINE_BYTES:
            raise IdentityProtocolError('identity line exceeds the bounded limit')
        try:
            text = line.decode('ascii')
        except UnicodeDecodeError as exc:
            raise IdentityProtocolError('identity line is not ASCII') from exc
    else:
        text = line
        if len(text.encode('utf-8')) > MAX_IDENTITY_LINE_BYTES:
            raise IdentityProtocolError('identity line exceeds the bounded limit')
    parts = text.strip().split()
    if not parts:
        raise IdentityProtocolError('empty identity line')
    fields: dict[str, str] = {}
    for token in parts[1:]:
        if token.count('=') != 1:
            raise IdentityProtocolError('identity field is not key=value')
        key, value = token.split('=', 1)
        if not key or key in fields or not value or not _TOKEN_VALUE_RE.fullmatch(value):
            raise IdentityProtocolError('identity field is malformed or duplicated')
        fields[key] = value
    return parts[0], fields


def _required(fields: dict[str, str], key: str) -> str:
    try:
        return fields[key]
    except KeyError as exc:
        raise IdentityProtocolError(f'missing identity field: {key}') from exc


def _parse_count(value: str, field_name: str) -> int:
    if not value.isascii() or not value.isdecimal():
        raise IdentityProtocolError(f'{field_name} must be a decimal count')
    count = int(value)
    if count < 0 or count > MAX_IDENTITY_PEERS:
        raise IdentityProtocolError(f'{field_name} exceeds the supported bound')
    return count


def _parse_schema_version(fields: dict[str, str]) -> int:
    value = fields.get('schema_version', '1')
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise IdentityProtocolError('schema_version must be a positive integer')
    return int(value)


def _verification_state(fields: dict[str, str]) -> str:
    if fields.get('verified') == '1' or fields.get('verification') == 'verified':
        return 'verified'
    if fields.get('verified') == '0':
        return 'unsupported'
    raise IdentityProtocolError('identity verification state is invalid')


def _capabilities(fields: dict[str, str]) -> tuple[str, ...]:
    named = fields.get('capabilities')
    if named is not None:
        values = tuple(item for item in named.split(',') if item)
        if not values:
            raise IdentityProtocolError('capabilities must not be empty')
        return values
    supported = fields.get('identify_supported')
    if supported not in (None, '0', '1'):
        raise IdentityProtocolError('identify_supported must be 0 or 1')
    return ('identify',) if supported == '1' else ()


def _normalized_mac_field(
    fields: dict[str, str],
    key: str,
    *,
    allow_unknown: bool = False,
) -> str | None:
    value = _required(fields, key)
    if allow_unknown and value == 'unknown':
        return None
    try:
        return display_mac(value)
    except ValueError as exc:
        raise IdentityProtocolError(f'{key} is not a complete MAC') from exc


def _parse_self(fields: dict[str, str], endpoint: str) -> SessionIdentity:
    if fields.get('protocol') != IDENTITY_PROTOCOL or fields.get('record') != 'self':
        raise IdentityProtocolError('self record must use protocol=id-v1 record=self')
    try:
        device_id = normalize_device_id(_required(fields, 'device_id'))
    except ValueError as exc:
        raise IdentityProtocolError('self device_id is not canonical full identity') from exc
    base_mac = _normalized_mac_field(fields, 'base_mac')
    if base_mac != display_mac(device_id):
        raise IdentityProtocolError('self base_mac does not match device_id')
    display_value = _normalized_mac_field(fields, 'display_mac')
    if display_value != display_mac(device_id):
        raise IdentityProtocolError('self display_mac does not match device_id')
    state = _verification_state(fields)
    if state != 'verified':
        raise IdentityProtocolError('session self identity is not verified')
    role = _required(fields, 'role')
    if role not in ('master', 'slave'):
        raise IdentityProtocolError('self role must be master or slave')
    return SessionIdentity(
        device_id=device_id,
        display_mac=display_value,
        base_mac=base_mac,
        sta_mac=_normalized_mac_field(fields, 'sta_mac'),
        ap_mac=_normalized_mac_field(fields, 'ap_mac'),
        espnow_mac=_normalized_mac_field(fields, 'espnow_mac'),
        role=role,
        capabilities=_capabilities(fields),
        verification_state=state,
        current_endpoint=endpoint,
        schema_version=_parse_schema_version(fields),
    )


def _parse_peer(fields: dict[str, str]) -> PeerIdentity:
    if fields.get('protocol') != IDENTITY_PROTOCOL or fields.get('record') != 'peer':
        raise IdentityProtocolError('peer record must use protocol=id-v1 record=peer')
    state = _verification_state(fields)
    raw_device_id = _required(fields, 'device_id')
    if raw_device_id == 'unknown':
        if state == 'verified':
            raise IdentityProtocolError('unknown peer cannot be verified')
        device_id = None
        display_value = _normalized_mac_field(
            fields, 'display_mac', allow_unknown=True)
        base_mac = _normalized_mac_field(fields, 'base_mac', allow_unknown=True)
    else:
        try:
            device_id = normalize_device_id(raw_device_id)
        except ValueError as exc:
            raise IdentityProtocolError('peer device_id is malformed') from exc
        display_value = _normalized_mac_field(fields, 'display_mac')
        base_mac = _normalized_mac_field(fields, 'base_mac')
        expected_display = display_mac(device_id)
        if display_value != expected_display or base_mac != expected_display:
            raise IdentityProtocolError('peer MAC fields do not match device_id')
    role = _required(fields, 'role')
    if role not in ('master', 'slave'):
        raise IdentityProtocolError('peer role must be master or slave')
    slot_value = fields.get('slot')
    slot = _parse_count(slot_value, 'slot') if slot_value is not None else None
    transport = fields.get('transport_mac')
    transport_mac = (
        display_mac(transport)
        if transport is not None and transport != 'unknown'
        else None
    )
    return PeerIdentity(
        device_id=device_id,
        display_mac=display_value,
        base_mac=base_mac,
        sta_mac=_normalized_mac_field(fields, 'sta_mac', allow_unknown=True),
        ap_mac=_normalized_mac_field(fields, 'ap_mac', allow_unknown=True),
        espnow_mac=_normalized_mac_field(
            fields, 'espnow_mac', allow_unknown=True),
        transport_mac=transport_mac,
        role=role,
        capabilities=_capabilities(fields),
        verification_state=state,
        schema_version=_parse_schema_version(fields) if state == 'verified' else 0,
        slot=slot,
    )


def parse_identity_inventory(
    lines: Iterable[bytes | str],
    *,
    endpoint: str,
    expected_device_id: str | None = None,
) -> IdentityInventory:
    """Parse exactly self, its counted peer rows, and a matching terminator."""
    records = list(lines)
    if not records:
        raise IdentityProtocolError('identity inventory is empty')
    prefix, self_fields = _decode_identity_line(records[0])
    if prefix != 'IDENTITY_OK':
        raise IdentityProtocolError('identity inventory must start with self')
    session = _parse_self(self_fields, endpoint)
    advertised_count = _parse_count(
        _required(self_fields, 'peer_count'), 'peer_count')
    if expected_device_id is not None:
        try:
            expected = normalize_device_id(expected_device_id)
        except ValueError as exc:
            raise IdentityProtocolError('expected device identity is invalid') from exc
        if session.device_id != expected:
            raise IdentityProtocolError(
                f'endpoint self identity {session.device_id} does not match expected {expected}'
            )
    if len(records) != advertised_count + 2:
        raise IdentityProtocolError('identity row count does not match peer_count')
    peers: dict[str, PeerIdentity] = {}
    for record in records[1:advertised_count + 1]:
        peer_prefix, peer_fields = _decode_identity_line(record)
        if peer_prefix != 'IDENTITY_PEER':
            raise IdentityProtocolError('expected counted peer inventory row')
        peer = _parse_peer(peer_fields)
        if peer.device_id == session.device_id:
            raise IdentityProtocolError('self identity is duplicated as a peer')
        key = peer.device_id or (
            f'transport:{peer.transport_mac}'
            if peer.transport_mac is not None
            else f'unverified:{len(peers)}'
        )
        if key in peers:
            raise IdentityProtocolError('duplicate peer identity')
        peers[key] = peer
    end_prefix, end_fields = _decode_identity_line(records[-1])
    if (
        end_prefix != 'IDENTITY_END'
        or end_fields.get('protocol') != IDENTITY_PROTOCOL
        or set(end_fields) != {'protocol', 'peer_count'}
        or _parse_count(_required(end_fields, 'peer_count'), 'peer_count')
        != advertised_count
    ):
        raise IdentityProtocolError('identity terminator does not match inventory')
    return IdentityInventory(session=session, peers=peers)


def legacy_session_identity(*, role: str, endpoint: str) -> SessionIdentity:
    if role not in ('master', 'slave'):
        raise ValueError('legacy role must be master or slave')
    return SessionIdentity(
        device_id=None,
        display_mac=None,
        base_mac=None,
        sta_mac=None,
        ap_mac=None,
        espnow_mac=None,
        role=role,
        verification_state='unsupported',
        current_endpoint=endpoint,
    )


def validate_session_identity_line(
    session: SessionIdentity,
    line: bytes | str,
) -> None:
    prefix, fields = _decode_identity_line(line)
    if prefix != 'IDENTITY_OK' or fields.get('record') != 'self':
        return
    try:
        reported = normalize_device_id(_required(fields, 'device_id'))
    except ValueError as exc:
        session.verification_state = 'quarantined'
        raise IdentityChangedError('session reported malformed replacement identity') from exc
    if not session.verified or reported != session.device_id:
        previous = session.device_id
        session.verification_state = 'quarantined'
        raise IdentityChangedError(
            f'session identity changed from {previous} to {reported}'
        )


class SessionIdentityRegistry:
    """Keep stable full-MAC keys separate from mutable endpoint ownership."""

    def __init__(self) -> None:
        self.identities: dict[str, SessionIdentity] = {}
        self._endpoint_keys: dict[str, str] = {}

    def bind(self, session: SessionIdentity) -> SessionIdentity:
        if not session.verified or session.device_id is None:
            raise IdentityProtocolError('only verified self identity can be bound')
        endpoint = session.current_endpoint
        if endpoint is None:
            raise IdentityProtocolError('verified identity requires an endpoint')
        displaced_key = self._endpoint_keys.get(endpoint)
        if displaced_key is not None and displaced_key != session.device_id:
            displaced = self.identities[displaced_key]
            displaced.current_endpoint = None
        existing = self.identities.get(session.device_id)
        if existing is None:
            existing = session
            self.identities[session.device_id] = existing
        else:
            old_endpoint = existing.current_endpoint
            if old_endpoint is not None and old_endpoint != endpoint:
                self._endpoint_keys.pop(old_endpoint, None)
            existing.display_mac = session.display_mac
            existing.base_mac = session.base_mac
            existing.sta_mac = session.sta_mac
            existing.ap_mac = session.ap_mac
            existing.espnow_mac = session.espnow_mac
            existing.role = session.role
            existing.capabilities = session.capabilities
            existing.verification_state = session.verification_state
            existing.current_endpoint = endpoint
            existing.schema_version = session.schema_version
        self._endpoint_keys[endpoint] = session.device_id
        return existing


def _identity_records_from_buffer(buffer: bytes) -> tuple[list[bytes], int] | None:
    lines = buffer.splitlines(keepends=True)
    offset = 0
    records: list[bytes] = []
    started = False
    for line in lines:
        complete = line.endswith((b'\n', b'\r'))
        if not complete:
            return None
        stripped = line.rstrip(b'\r\n')
        if stripped.startswith(b'IDENTITY_PEER ') and not started:
            raise IdentityProtocolError('peer inventory arrived before self')
        if stripped.startswith(b'IDENTITY_END ') and not started:
            raise IdentityProtocolError('identity terminator arrived before self')
        if stripped.startswith(b'IDENTITY_OK '):
            if started:
                raise IdentityProtocolError('duplicate self identity record')
            started = True
            records.append(stripped)
        elif started:
            if stripped.startswith(b'IDENTITY_PEER '):
                records.append(stripped)
            elif stripped.startswith(b'IDENTITY_END '):
                records.append(stripped)
                return records, offset + len(line)
            else:
                raise IdentityProtocolError(
                    'non-identity data interrupted identity inventory')
        offset += len(line)
    return None


def probe_identity_socket(
    esp_sock: socket.socket,
    *,
    endpoint: str,
    expected_device_id: str | None = None,
    timeout_seconds: float = 3.0,
) -> tuple[IdentityInventory | None, bytes]:
    """Request and synchronously validate one bounded identity inventory."""
    esp_sock.sendall(b'IDENTITY?\n')
    received = bytearray()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            chunk = esp_sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        if not chunk:
            break
        received.extend(chunk)
        if len(received) > MAX_IDENTITY_HANDSHAKE_BYTES:
            raise IdentityProtocolError('identity handshake exceeds bounded limit')
        found = _identity_records_from_buffer(bytes(received))
        if found is not None:
            records, _end_offset = found
            return (
                parse_identity_inventory(
                    records,
                    endpoint=endpoint,
                    expected_device_id=expected_device_id,
                ),
                bytes(received),
            )
    if b'IDENTITY_' in received:
        raise IdentityProtocolError('identity handshake was incomplete')
    return None, bytes(received)


class StepEspRelay:
    """One ESP TCP session and one corresponding WSL bridge listener."""

    def __init__(
        self,
        name: str,
        esp_host: str,
        esp_port: int,
        *,
        expected_device_id: str | None = None,
        identity_registry: SessionIdentityRegistry | None = None,
    ) -> None:
        if name not in ('master', 'slave'):
            raise ValueError('relay name is a role label, not a device identity')
        self.name = name
        self.esp_host = esp_host
        self.esp_port = esp_port
        self.expected_device_id = (
            normalize_device_id(expected_device_id)
            if expected_device_id is not None
            else None
        )
        self.identity_registry = identity_registry or SessionIdentityRegistry()
        self.session_identity = legacy_session_identity(
            role=name,
            endpoint=esp_host,
        )
        self.peer_inventory: dict[str, PeerIdentity] = {}
        self._downstream_writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()
        self._session_lock = asyncio.Lock()
        self._udp_enabled = asyncio.Event()
        self._stream_bytes = 0
        self._identity_scan_tail = b''

    def _log(self, message: str) -> None:
        print(f'[relay:{self.name}] {message}', flush=True)

    async def serve(self, listen_host: str, listen_port: int) -> None:
        server = await asyncio.start_server(self._handle_client, listen_host, listen_port)
        addresses = ', '.join(str(sock.getsockname()) for sock in server.sockets or [])
        self._log(f'listening for WSL bridge on {addresses}')
        async with server:
            await server.serve_forever()

    async def _write_downstream(self, data: bytes) -> None:
        writer = self._downstream_writer
        if writer is None or writer.is_closing():
            return
        async with self._write_lock:
            writer.write(data)
            await writer.drain()

    async def _handle_client(
        self,
        downstream_reader: asyncio.StreamReader,
        downstream_writer: asyncio.StreamWriter,
    ) -> None:
        async with self._session_lock:
            await self._handle_client_locked(downstream_reader, downstream_writer)

    async def _handle_client_locked(
        self,
        downstream_reader: asyncio.StreamReader,
        downstream_writer: asyncio.StreamWriter,
    ) -> None:
        if self._downstream_writer is not None and not self._downstream_writer.is_closing():
            downstream_writer.close()
            await downstream_writer.wait_closed()
            return

        self._downstream_writer = downstream_writer
        self._udp_enabled.clear()
        peer = downstream_writer.get_extra_info('peername')
        self._log(f'WSL bridge connected from {peer}; connecting to ESP')
        try:
            esp_sock = await asyncio.to_thread(
                socket.create_connection, (self.esp_host, self.esp_port), 15.0
            )
            esp_sock.settimeout(1.0)
            self._log(f'ESP control connected to {self.esp_host}:{self.esp_port}')
            inventory, handshake_bytes = await asyncio.to_thread(
                probe_identity_socket,
                esp_sock,
                endpoint=self.esp_host,
                expected_device_id=self.expected_device_id,
            )
            if inventory is None:
                self.session_identity = legacy_session_identity(
                    role=self.name,
                    endpoint=self.esp_host,
                )
                if self.expected_device_id is not None:
                    raise IdentityProtocolError(
                        f'{self.esp_host} does not support verified {IDENTITY_PROTOCOL}'
                    )
                self._log('identity unsupported; continuing as unverified legacy route')
            else:
                if inventory.session.role != self.name:
                    raise IdentityProtocolError(
                        f'endpoint role {inventory.session.role} does not match route {self.name}'
                    )
                self.session_identity = self.identity_registry.bind(inventory.session)
                self.peer_inventory = inventory.peers
                self._log(
                    f'identity verified device_id={self.session_identity.device_id} '
                    f'endpoint={self.esp_host} role={self.name} '
                    f'peer_count={len(self.peer_inventory)}'
                )
            if handshake_bytes:
                await self._write_downstream(handshake_bytes)
                if b'SENSORS:' in handshake_bytes:
                    self._udp_enabled.set()
            tasks = [
                asyncio.create_task(
                    self._forward_downstream_control(downstream_reader, esp_sock)
                ),
                asyncio.create_task(self._forward_esp_control(esp_sock)),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in pending:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            for task in done:
                task.result()
        except Exception as exc:
            self._log(f'connection error: {exc}')
        finally:
            if 'esp_sock' in locals():
                esp_sock.close()
            if self._downstream_writer is downstream_writer:
                self._downstream_writer = None
            downstream_writer.close()
            with contextlib.suppress(Exception):
                await downstream_writer.wait_closed()
            self._log('bridge session closed')

    async def _forward_downstream_control(
        self, reader: asyncio.StreamReader, esp_sock: socket.socket
    ) -> None:
        while data := await reader.read(4096):
            self._log(f'WSL -> ESP control: {data!r}')
            await asyncio.to_thread(esp_sock.sendall, data)

    def _validate_identity_control_bytes(self, data: bytes) -> None:
        prefix = b'IDENTITY_OK '
        scan = self._identity_scan_tail + data
        position = 0
        while True:
            start = scan.find(prefix, position)
            if start < 0:
                self._identity_scan_tail = scan[-(len(prefix) - 1):]
                return
            end = scan.find(b'\n', start)
            if end < 0:
                pending = scan[start:]
                if len(pending) > MAX_IDENTITY_LINE_BYTES:
                    self.session_identity.verification_state = 'quarantined'
                    raise IdentityChangedError(
                        'session identity line exceeds the bounded limit')
                self._identity_scan_tail = pending
                return
            validate_session_identity_line(
                self.session_identity,
                scan[start:end],
            )
            position = end + 1

    async def _forward_esp_control(self, esp_sock: socket.socket) -> None:
        while True:
            try:
                data = await asyncio.to_thread(esp_sock.recv, 4096)
            except TimeoutError:
                continue
            if not data:
                return
            self._validate_identity_control_bytes(data)
            if not self._udp_enabled.is_set():
                bounded = data[:MAX_IDENTITY_LINE_BYTES]
                self._log(f'ESP -> WSL handshake: {bounded!r}')
            else:
                self._stream_bytes += len(data)
                for prefix in CONTROL_LOG_PREFIXES:
                    start = data.find(prefix)
                    if start < 0:
                        continue
                    end = data.find(b'\n', start)
                    if end >= 0:
                        line = data[start:end].decode('ascii', errors='replace')
                        self._log(f'ESP -> WSL control: {line}')
                    break
                if self._stream_bytes >= 1_000_000:
                    self._log('forwarded 1 MB of TCP stream data')
                    self._stream_bytes = 0

            downstream_data = data
            if b'STARTED' in data and b'transport=udp' in data:
                downstream_data = data.replace(
                    b'transport=udp port=55001', b'transport=tcp'
                )
                if downstream_data == data:
                    downstream_data = data.replace(b'transport=udp', b'transport=tcp')
                self._log('translated downstream transport udp -> tcp')
            await self._write_downstream(downstream_data)
            if b'SENSORS:' in data:
                # The WSL bridge must see the complete text handshake before
                # binary UDP frames are appended to its relayed TCP stream.
                self._udp_enabled.set()

    async def forward_udp(self, data: bytes) -> None:
        """Forward one datagram already selected by its ESP source address."""
        await self._udp_enabled.wait()
        await self._write_downstream(data)


class UdpRouter:
    """Own the shared firmware UDP port and demultiplex by ESP source IP."""

    def __init__(self, udp_port: int, routes: dict[str, StepEspRelay]) -> None:
        self.udp_port = udp_port
        self.routes = dict(routes)
        self.queues = {
            host: asyncio.Queue[bytes](maxsize=256) for host in routes
        }
        self._unknown_sources: set[str] = set()

    def remap_host(self, old_host: str, new_host: str, relay: StepEspRelay) -> None:
        """Move one route/queue to a refreshed ESP source IP without dropping identity."""
        if old_host == new_host:
            self.routes[new_host] = relay
            if new_host not in self.queues:
                self.queues[new_host] = asyncio.Queue[bytes](maxsize=256)
            return
        if new_host in self.routes and self.routes[new_host] is not relay:
            raise ValueError(
                f'cannot remap {old_host} onto occupied UDP host {new_host}'
            )
        queue = self.queues.pop(old_host, None)
        self.routes.pop(old_host, None)
        if queue is None:
            queue = asyncio.Queue[bytes](maxsize=256)
        self.routes[new_host] = relay
        self.queues[new_host] = queue

    async def _forward_route(self, host: str) -> None:
        relay = self.routes[host]
        queue = self.queues[host]
        while True:
            data = await queue.get()
            try:
                active_host = next(
                    (
                        candidate
                        for candidate, mapped in self.routes.items()
                        if mapped is relay
                    ),
                    host,
                )
                if active_host != host:
                    queue = self.queues[active_host]
                    host = active_host
                await relay.forward_udp(data)
            finally:
                queue.task_done()

    def route_datagram(self, source_host: str, data: bytes) -> bool:
        """Queue a datagram for the ESP route selected by its source address."""
        queue = self.queues.get(source_host)
        if queue is None:
            return False
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(data)
        return True

    async def serve(self) -> None:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setblocking(False)
        udp_sock.bind(('0.0.0.0', self.udp_port))
        print(
            f'[relay:udp] listening on 0.0.0.0:{self.udp_port}; '
            f'routes={sorted(self.routes)}',
            flush=True,
        )
        loop = asyncio.get_running_loop()
        workers = [
            asyncio.create_task(self._forward_route(host)) for host in list(self.routes)
        ]
        try:
            while True:
                data, source = await loop.sock_recvfrom(udp_sock, 4096)
                if self.route_datagram(source[0], data):
                    continue
                if source[0] not in self._unknown_sources:
                    self._unknown_sources.add(source[0])
                    print(f'[relay:udp] ignoring unknown source {source[0]}', flush=True)
        finally:
            for worker in workers:
                worker.cancel()
            for worker in workers:
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
            udp_sock.close()


@dataclass(frozen=True)
class SlaveRouteConfig:
    host: str
    listen_port: int
    expected_device_id: str | None
    esp_port: int = 5000


def _parse_slave_route_spec(spec: str, *, esp_port: int) -> SlaveRouteConfig:
    parts = spec.split(':')
    if len(parts) < 3:
        raise ValueError(
            'slave route must be HOST:LISTEN_PORT:EXPECTED_DEVICE_ID'
        )
    host = parts[0]
    listen_port_text = parts[1]
    device_raw = ':'.join(parts[2:])
    if not host:
        raise ValueError('slave route host must not be empty')
    if not listen_port_text.isascii() or not listen_port_text.isdecimal():
        raise ValueError('slave route listen port must be an integer')
    listen_port = int(listen_port_text)
    if listen_port <= 0 or listen_port > 65535:
        raise ValueError('slave route listen port is out of range')
    expected = normalize_device_id(device_raw) if device_raw else None
    return SlaveRouteConfig(
        host=host,
        listen_port=listen_port,
        expected_device_id=expected,
        esp_port=esp_port,
    )


def parse_slave_routes(args: argparse.Namespace) -> list[SlaveRouteConfig]:
    """Normalize repeatable --slave-route and singular --slave-host forms."""
    routes: list[SlaveRouteConfig] = []
    route_specs: Sequence[str] = getattr(args, 'slave_route', None) or []
    for spec in route_specs:
        routes.append(
            _parse_slave_route_spec(spec, esp_port=args.slave_esp_port)
        )
    if args.slave_host:
        routes.append(
            SlaveRouteConfig(
                host=args.slave_host,
                listen_port=args.slave_listen_port,
                expected_device_id=(
                    normalize_device_id(args.slave_expected_device_id)
                    if args.slave_expected_device_id
                    else None
                ),
                esp_port=args.slave_esp_port,
            )
        )
    if len(routes) > MAX_SLAVE_ROUTES:
        raise ValueError(
            f'slave route count {len(routes)} exceeds firmware peer slot cap '
            f'{MAX_SLAVE_ROUTES}'
        )
    hosts = [route.host for route in routes]
    ports = [route.listen_port for route in routes]
    device_ids = [
        route.expected_device_id
        for route in routes
        if route.expected_device_id is not None
    ]
    if len(set(hosts)) != len(hosts):
        raise ValueError('slave route hosts must be unique')
    if len(set(ports)) != len(ports):
        raise ValueError('slave listen ports must be unique')
    if len(set(device_ids)) != len(device_ids):
        raise ValueError('slave expected device identities must be unique')
    if args.esp_host in hosts:
        raise ValueError('master and slave ESP hosts must be different')
    if args.listen_port in ports:
        raise ValueError('master and slave WSL listen ports must be different')
    return routes


def remap_relay_endpoint(
    router: UdpRouter,
    relay: StepEspRelay,
    registry: SessionIdentityRegistry,
    *,
    new_endpoint: str,
) -> SessionIdentity:
    """Refresh ESP host/IP while keeping the canonical device_id binding."""
    if not new_endpoint:
        raise ValueError('new endpoint must not be empty')
    old_endpoint = relay.esp_host
    session = relay.session_identity
    if session.verified and session.device_id is not None:
        session.current_endpoint = new_endpoint
        rebound = registry.bind(session)
        relay.session_identity = rebound
        session = rebound
    else:
        session.current_endpoint = new_endpoint
    relay.esp_host = new_endpoint
    router.remap_host(old_endpoint, new_endpoint, relay)
    return session


async def run_relays(args: argparse.Namespace) -> None:
    registry = SessionIdentityRegistry()
    master = StepEspRelay(
        'master',
        args.esp_host,
        args.esp_port,
        expected_device_id=args.expected_device_id,
        identity_registry=registry,
    )
    routes: dict[str, StepEspRelay] = {args.esp_host: master}
    tasks = [master.serve(args.listen_host, args.listen_port)]

    for index, slave_route in enumerate(parse_slave_routes(args)):
        slave = StepEspRelay(
            'slave',
            slave_route.host,
            slave_route.esp_port,
            expected_device_id=slave_route.expected_device_id,
            identity_registry=registry,
        )
        routes[slave_route.host] = slave
        tasks.append(
            slave.serve(args.listen_host, slave_route.listen_port)
        )
        print(
            f'[relay:config] slave[{index}] host={slave_route.host} '
            f'listen={slave_route.listen_port} '
            f'expected={slave_route.expected_device_id}',
            flush=True,
        )

    router = UdpRouter(args.udp_port, routes)
    await asyncio.gather(router.serve(), *tasks)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Relay STEP_ESP32 master plus up to '
            f'{MAX_SLAVE_ROUTES} identity-bound slave TCP/UDP routes.'
        )
    )
    parser.add_argument('--esp-host', default='192.168.4.1')
    parser.add_argument('--esp-port', type=int, default=5000)
    parser.add_argument('--udp-port', type=int, default=55001)
    parser.add_argument('--listen-host', default='0.0.0.0')
    parser.add_argument('--listen-port', type=int, default=5002)
    parser.add_argument('--expected-device-id')
    parser.add_argument(
        '--slave-route',
        action='append',
        default=[],
        metavar='HOST:LISTEN_PORT:EXPECTED_DEVICE_ID',
        help=(
            'Repeatable slave route (max '
            f'{MAX_SLAVE_ROUTES}). Prefer this form for N slaves.'
        ),
    )
    parser.add_argument(
        '--slave-host',
        help='Singular one-slave compatibility host (optional with --slave-route).',
    )
    parser.add_argument('--slave-esp-port', type=int, default=5000)
    parser.add_argument('--slave-listen-port', type=int, default=5003)
    parser.add_argument('--slave-expected-device-id')
    return parser


def main() -> None:
    asyncio.run(run_relays(build_arg_parser().parse_args()))


if __name__ == '__main__':
    main()
