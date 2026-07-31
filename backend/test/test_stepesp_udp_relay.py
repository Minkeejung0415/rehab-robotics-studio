"""Contract tests for routing STEP_ESP32 UDP frames into WSL streams."""
from __future__ import annotations

import asyncio
import importlib.util
import socket
import sys
import unittest
from pathlib import Path

from backend.test.test_stepesp_firmware_topology import (
    CROSS_LAYER_BINDING_ATTACKS,
    CROSS_LAYER_IDENTITY_REJECTION_CASES,
    CROSS_LAYER_IDENTIFY_OUTCOMES,
    CROSS_LAYER_LOW32_COLLISION_IDS,
)


REPO_ROOT = Path(__file__).parents[2]
RELAY_PATH = REPO_ROOT / 'scripts' / 'stepesp_tcp_udp_relay.py'
LAUNCHER_PATH = REPO_ROOT / 'scripts' / 'start_stepesp_wireless.ps1'
SPEC = importlib.util.spec_from_file_location('stepesp_tcp_udp_relay', RELAY_PATH)
assert SPEC is not None and SPEC.loader is not None
relay_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = relay_module
SPEC.loader.exec_module(relay_module)

SELF_ID = 'esp32:aabbccddeeff'
PEER_ONE_ID = 'esp32:112233445566'
PEER_TWO_ID = 'esp32:77bbccddeeff'


def _self_line(
    device_id: str = SELF_ID,
    *,
    peer_count: int = 2,
    role: str = 'master',
) -> bytes:
    compact = device_id.removeprefix('esp32:')
    display = ':'.join(compact[index:index + 2] for index in range(0, 12, 2)).upper()
    return (
        'IDENTITY_OK protocol=id-v1 record=self '
        f'peer_count={peer_count} device_id={device_id} display_mac={display} '
        f'base_mac={display} sta_mac={display} ap_mac={display} '
        f'espnow_mac={display} role={role} capabilities=identify '
        'verification=verified\n'
    ).encode('ascii')


def _peer_line(device_id: str, slot: int) -> bytes:
    compact = device_id.removeprefix('esp32:')
    display = ':'.join(compact[index:index + 2] for index in range(0, 12, 2)).upper()
    return (
        'IDENTITY_PEER protocol=id-v1 record=peer '
        f'slot={slot} device_id={device_id} display_mac={display} '
        f'base_mac={display} sta_mac={display} ap_mac={display} '
        f'espnow_mac={display} role=slave capabilities=identify '
        'verification=verified\n'
    ).encode('ascii')


def _end_line(peer_count: int = 2) -> bytes:
    return f'IDENTITY_END protocol=id-v1 peer_count={peer_count}\n'.encode('ascii')


def _complete_inventory(
    device_id: str = SELF_ID,
    *,
    endpoint: str = '192.168.4.1',
):
    peer_ids = [
        peer_id for peer_id in (PEER_ONE_ID, PEER_TWO_ID)
        if peer_id != device_id
    ]
    return relay_module.parse_identity_inventory(
        [
            _self_line(device_id, peer_count=len(peer_ids)),
            *[
                _peer_line(peer_id, slot)
                for slot, peer_id in enumerate(peer_ids)
            ],
            _end_line(len(peer_ids)),
        ],
        endpoint=endpoint,
    )


class _Writer:
    def __init__(self) -> None:
        self.data = bytearray()

    def is_closing(self) -> bool:
        return False

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        return None


class _Socket:
    def __init__(self, chunks: list[bytes | BaseException]) -> None:
        self.chunks = list(chunks)
        self.sent = bytearray()

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def recv(self, _size: int) -> bytes:
        if not self.chunks:
            return b''
        chunk = self.chunks.pop(0)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk


class IdentityContractTests(unittest.TestCase):
    def test_full_mac_normalizes_to_canonical_and_display_forms(self):
        for raw in (
            'aabbccddeeff',
            'esp32:aabbccddeeff',
            'AA:BB:CC:DD:EE:FF',
        ):
            self.assertEqual(relay_module.normalize_device_id(raw), SELF_ID)
        self.assertEqual(
            relay_module.display_mac(SELF_ID),
            'AA:BB:CC:DD:EE:FF',
        )

    def test_partial_malformed_and_unknown_identity_values_are_rejected(self):
        for raw in (
            '',
            'esp32:aabbccdd',
            'esp32:aabbccddeeff00',
            'esp32:aabbccddeefg',
            'device:aabbccddeeff',
            'aabb-ccdd-eeff',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    relay_module.normalize_device_id(raw)

    def test_complete_inventory_binds_only_the_self_record(self):
        inventory = _complete_inventory()
        self.assertEqual(inventory.session.device_id, SELF_ID)
        self.assertEqual(inventory.session.role, 'master')
        self.assertEqual(inventory.session.current_endpoint, '192.168.4.1')
        self.assertTrue(inventory.session.verified)
        self.assertEqual(set(inventory.peers), {PEER_ONE_ID, PEER_TWO_ID})
        self.assertNotIn(inventory.session.device_id, inventory.peers)

    def test_expected_identity_must_match_the_self_record_not_a_peer(self):
        with self.assertRaises(relay_module.IdentityProtocolError):
            relay_module.parse_identity_inventory(
                [
                    _self_line(),
                    _peer_line(PEER_ONE_ID, 0),
                    _peer_line(PEER_TWO_ID, 1),
                    _end_line(),
                ],
                endpoint='192.168.4.1',
                expected_device_id=PEER_ONE_ID,
            )

    def test_incomplete_or_reordered_inventory_fails_closed(self):
        cases = {
            'peer before self': [
                _peer_line(PEER_ONE_ID, 0),
                _self_line(peer_count=1),
                _end_line(1),
            ],
            'duplicate self': [
                _self_line(peer_count=0),
                _self_line(peer_count=0),
                _end_line(0),
            ],
            'missing peer': [
                _self_line(peer_count=2),
                _peer_line(PEER_ONE_ID, 0),
                _end_line(2),
            ],
            'extra peer': [
                _self_line(peer_count=1),
                _peer_line(PEER_ONE_ID, 0),
                _peer_line(PEER_TWO_ID, 1),
                _end_line(1),
            ],
            'duplicate peer': [
                _self_line(peer_count=2),
                _peer_line(PEER_ONE_ID, 0),
                _peer_line(PEER_ONE_ID, 1),
                _end_line(2),
            ],
            'mismatched terminator': [
                _self_line(peer_count=1),
                _peer_line(PEER_ONE_ID, 0),
                _end_line(2),
            ],
            'missing terminator': [
                _self_line(peer_count=1),
                _peer_line(PEER_ONE_ID, 0),
            ],
        }
        for label, lines in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(relay_module.IdentityProtocolError):
                    relay_module.parse_identity_inventory(
                        lines,
                        endpoint='192.168.4.1',
                    )

    def test_cross_layer_identity_matrix_rejects_every_binding_attack(self):
        cases = {
            'missing_self': [
                _peer_line(PEER_ONE_ID, 0),
                _end_line(1),
            ],
            'duplicate_self': [
                _self_line(peer_count=0),
                _self_line(peer_count=0),
                _end_line(0),
            ],
            'peer_before_self': [
                _peer_line(PEER_ONE_ID, 0),
                _self_line(peer_count=1),
                _end_line(1),
            ],
            'peer_reuses_self': [
                _self_line(peer_count=1),
                _peer_line(SELF_ID, 0),
                _end_line(1),
            ],
            'duplicate_peer': [
                _self_line(peer_count=2),
                _peer_line(PEER_ONE_ID, 0),
                _peer_line(PEER_ONE_ID, 1),
                _end_line(2),
            ],
            'count_mismatch': [
                _self_line(peer_count=2),
                _peer_line(PEER_ONE_ID, 0),
                _end_line(2),
            ],
            'missing_terminator': [
                _self_line(peer_count=1),
                _peer_line(PEER_ONE_ID, 0),
            ],
            'mismatched_terminator': [
                _self_line(peer_count=1),
                _peer_line(PEER_ONE_ID, 0),
                _end_line(2),
            ],
        }
        self.assertEqual(set(cases), set(CROSS_LAYER_IDENTITY_REJECTION_CASES))
        for label, lines in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(relay_module.IdentityProtocolError):
                    relay_module.parse_identity_inventory(
                        lines,
                        endpoint='192.168.4.1',
                    )

        self.assertEqual(CROSS_LAYER_BINDING_ATTACKS, ('peer_matches_expected',))
        with self.assertRaises(relay_module.IdentityProtocolError):
            relay_module.parse_identity_inventory(
                [
                    _self_line(peer_count=1),
                    _peer_line(PEER_ONE_ID, 0),
                    _end_line(1),
                ],
                endpoint='192.168.4.1',
                expected_device_id=PEER_ONE_ID,
            )

    def test_reconnect_updates_endpoint_metadata_for_the_same_full_mac(self):
        registry = relay_module.SessionIdentityRegistry()
        first = registry.bind(_complete_inventory(endpoint='192.168.4.3').session)
        rebound = registry.bind(_complete_inventory(endpoint='192.168.4.7').session)
        self.assertIs(first, rebound)
        self.assertEqual(first.current_endpoint, '192.168.4.7')
        self.assertEqual(list(registry.identities), [SELF_ID])

    def test_new_full_mac_at_an_old_endpoint_is_a_distinct_identity(self):
        registry = relay_module.SessionIdentityRegistry()
        old = registry.bind(_complete_inventory(endpoint='192.168.4.3').session)
        new_id = 'esp32:010203040506'
        new = registry.bind(
            _complete_inventory(new_id, endpoint='192.168.4.3').session
        )
        self.assertIsNot(old, new)
        self.assertIsNone(old.current_endpoint)
        self.assertEqual(new.current_endpoint, '192.168.4.3')
        self.assertEqual(set(registry.identities), {SELF_ID, new_id})

    def test_low_32_bit_collision_does_not_merge_devices(self):
        registry = relay_module.SessionIdentityRegistry()
        first_id, second_id = CROSS_LAYER_LOW32_COLLISION_IDS
        first = registry.bind(_complete_inventory(first_id).session)
        second = registry.bind(
            _complete_inventory(second_id, endpoint='192.168.4.8').session
        )
        self.assertEqual(first_id[-8:], second_id[-8:])
        self.assertNotEqual(first.device_id, second.device_id)
        self.assertEqual(len(registry.identities), 2)

    def test_changed_identity_line_is_quarantined(self):
        session = _complete_inventory().session
        with self.assertRaises(relay_module.IdentityChangedError):
            relay_module.validate_session_identity_line(
                session,
                _self_line('esp32:010203040506', peer_count=0),
            )
        self.assertEqual(session.device_id, SELF_ID)
        self.assertEqual(session.verification_state, 'quarantined')

    def test_old_firmware_is_explicitly_unverified_and_unsupported(self):
        legacy = relay_module.legacy_session_identity(
            role='slave',
            endpoint='192.168.4.3',
        )
        self.assertIsNone(legacy.device_id)
        self.assertFalse(legacy.verified)
        self.assertEqual(legacy.verification_state, 'unsupported')


class LauncherIdentityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = LAUNCHER_PATH.read_text(encoding='utf-8')

    def test_expected_master_and_slave_ids_are_strict_canonical_parameters(self):
        self.assertIn('[string]$ExpectedMasterDeviceId', self.launcher)
        self.assertIn('[string]$ExpectedSlaveDeviceId', self.launcher)
        self.assertIn('[string[]]$ExpectedSlaveDeviceIds', self.launcher)
        self.assertRegex(
            self.launcher,
            r"\^esp32:\[0-9a-fA-F\]\{12\}\$",
        )
        self.assertIn('ConvertTo-StepEspCanonicalId', self.launcher)

    def test_every_candidate_is_probed_with_complete_id_v1_inventory(self):
        for contract in (
            'Get-StepEspIdentity',
            "IDENTITY?`n",
            'IDENTITY_OK',
            'record=self',
            'IDENTITY_PEER',
            'record=peer',
            'IDENTITY_END',
            'protocol=id-v1',
            'peer_count',
            'verified=1',
            'foreach ($candidateHost in $candidateSlaveHosts)',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.launcher)

    def test_ping_order_cannot_select_the_slave(self):
        self.assertNotIn('$responsiveStations[0]', self.launcher)
        self.assertIn(
            '$verifiedSlaveCandidates = @($slaveIdentityProbes',
            self.launcher,
        )
        self.assertIn('MAX_SLAVE_ROUTES = 6', self.launcher)
        self.assertIn('firmware peer slot limit', self.launcher)
        self.assertNotIn(
            'Slave route selection is ambiguous',
            self.launcher,
        )
        self.assertIn(
            'Discovered verified self identities:',
            self.launcher,
        )

    def test_launcher_routes_all_verified_slaves_with_contiguous_ports(self):
        for contract in (
            '--slave-route',
            '$SlaveRelayPort + $index',
            'ExpectedSlaveDeviceIds',
            'duplicate slave identity',
            'exceeds the firmware peer slot limit',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.launcher)

    def test_role_alias_endpoint_and_verified_identity_are_separate_launch_values(self):
        for contract in (
            '--esp-host $MasterHost',
            '--expected-device-id $verifiedMasterDeviceId',
            '--slave-route',
            'node_id:=master',
            'node_id:=slave',
            'expected_device_id:=$verifiedMasterDeviceId',
            'expected_device_id:=$verifiedSlaveDeviceId',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.launcher)

    def test_existing_two_route_and_operator_stack_contracts_remain(self):
        for preserved in (
            '[int]$UdpPort = 55001',
            '[int]$RelayPort = 5002',
            '[int]$SlaveRelayPort = 5003',
            'rosbridge_websocket',
            'processing_block_observer',
            'opensim_bridge',
            'npm.cmd run build',
        ):
            with self.subTest(preserved=preserved):
                self.assertIn(preserved, self.launcher)


class MultiSlaveRouteContractTests(unittest.TestCase):
    def test_slave_route_cli_accepts_up_to_six_distinct_routes(self):
        parser = relay_module.build_arg_parser()
        route_args = []
        for index in range(6):
            route_args.extend([
                '--slave-route',
                f'192.168.4.{index + 3}:{5003 + index}:esp32:{index:012x}',
            ])
        args = parser.parse_args([
            '--esp-host', '192.168.4.1',
            '--listen-port', '5002',
            *route_args,
        ])
        routes = relay_module.parse_slave_routes(args)
        self.assertEqual(len(routes), 6)
        self.assertEqual(routes[0].host, '192.168.4.3')
        self.assertEqual(routes[0].listen_port, 5003)
        self.assertEqual(routes[0].expected_device_id, 'esp32:000000000000')
        self.assertEqual(routes[5].listen_port, 5008)

    def test_slave_route_cli_rejects_overflow_duplicates_and_bad_shapes(self):
        parser = relay_module.build_arg_parser()
        seven = [
            item
            for index in range(7)
            for item in (
                '--slave-route',
                f'192.168.4.{index + 3}:{5003 + index}:esp32:{index:012x}',
            )
        ]
        with self.assertRaises(ValueError):
            relay_module.parse_slave_routes(parser.parse_args(seven))

        duplicate_host = parser.parse_args([
            '--slave-route', '192.168.4.3:5003:esp32:aaaaaaaaaaaa',
            '--slave-route', '192.168.4.3:5004:esp32:bbbbbbbbbbbb',
        ])
        with self.assertRaises(ValueError):
            relay_module.parse_slave_routes(duplicate_host)

        duplicate_port = parser.parse_args([
            '--slave-route', '192.168.4.3:5003:esp32:aaaaaaaaaaaa',
            '--slave-route', '192.168.4.4:5003:esp32:bbbbbbbbbbbb',
        ])
        with self.assertRaises(ValueError):
            relay_module.parse_slave_routes(duplicate_port)

        duplicate_id = parser.parse_args([
            '--slave-route', '192.168.4.3:5003:esp32:aaaaaaaaaaaa',
            '--slave-route', '192.168.4.4:5004:esp32:aaaaaaaaaaaa',
        ])
        with self.assertRaises(ValueError):
            relay_module.parse_slave_routes(duplicate_id)

        clashes_master = parser.parse_args([
            '--esp-host', '192.168.4.1',
            '--listen-port', '5002',
            '--slave-route', '192.168.4.1:5003:esp32:aaaaaaaaaaaa',
        ])
        with self.assertRaises(ValueError):
            relay_module.parse_slave_routes(clashes_master)

    def test_singular_slave_host_compatibility_still_parses_one_route(self):
        parser = relay_module.build_arg_parser()
        args = parser.parse_args([
            '--slave-host', '192.168.4.3',
            '--slave-listen-port', '5003',
            '--slave-expected-device-id', 'esp32:112233445566',
        ])
        routes = relay_module.parse_slave_routes(args)
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].host, '192.168.4.3')
        self.assertEqual(routes[0].listen_port, 5003)
        self.assertEqual(routes[0].expected_device_id, PEER_ONE_ID)

    def test_endpoint_refresh_keeps_device_id_and_remaps_udp_host(self):
        registry = relay_module.SessionIdentityRegistry()
        relay = relay_module.StepEspRelay(
            'slave',
            '192.168.4.3',
            5000,
            expected_device_id=SELF_ID,
            identity_registry=registry,
        )
        session = registry.bind(_complete_inventory(endpoint='192.168.4.3').session)
        relay.session_identity = session
        router = relay_module.UdpRouter(
            55001,
            {'192.168.4.3': relay},
        )
        remapped = relay_module.remap_relay_endpoint(
            router,
            relay,
            registry,
            new_endpoint='192.168.4.9',
        )
        self.assertIs(remapped, session)
        self.assertEqual(session.device_id, SELF_ID)
        self.assertEqual(session.current_endpoint, '192.168.4.9')
        self.assertEqual(relay.esp_host, '192.168.4.9')
        self.assertIn('192.168.4.9', router.routes)
        self.assertNotIn('192.168.4.3', router.routes)
        self.assertIn('192.168.4.9', router.queues)
        self.assertNotIn('192.168.4.3', router.queues)
        self.assertTrue(router.route_datagram('192.168.4.9', b'ok'))
        self.assertFalse(router.route_datagram('192.168.4.3', b'stale'))

    def test_new_identity_at_old_endpoint_marks_prior_mac_offline(self):
        registry = relay_module.SessionIdentityRegistry()
        old_relay = relay_module.StepEspRelay(
            'slave',
            '192.168.4.3',
            5000,
            expected_device_id=SELF_ID,
            identity_registry=registry,
        )
        old = registry.bind(_complete_inventory(endpoint='192.168.4.3').session)
        old_relay.session_identity = old
        router = relay_module.UdpRouter(55001, {'192.168.4.3': old_relay})
        new_id = 'esp32:010203040506'
        new_relay = relay_module.StepEspRelay(
            'slave',
            '192.168.4.3',
            5000,
            expected_device_id=new_id,
            identity_registry=registry,
        )
        new = registry.bind(
            _complete_inventory(new_id, endpoint='192.168.4.3').session
        )
        new_relay.session_identity = new
        relay_module.remap_relay_endpoint(
            router,
            new_relay,
            registry,
            new_endpoint='192.168.4.3',
        )
        self.assertIsNone(old.current_endpoint)
        self.assertEqual(new.current_endpoint, '192.168.4.3')
        self.assertEqual(router.routes['192.168.4.3'], new_relay)
        self.assertEqual(set(registry.identities), {SELF_ID, new_id})


class StepEspUdpRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_source_ips_demux_independently(self):
        hosts = ('192.168.4.1', '192.168.4.3', '192.168.4.5')
        relays = {
            hosts[0]: relay_module.StepEspRelay('master', hosts[0], 5000),
            hosts[1]: relay_module.StepEspRelay('slave', hosts[1], 5000),
            hosts[2]: relay_module.StepEspRelay('slave', hosts[2], 5000),
        }
        writers = {host: _Writer() for host in hosts}
        for host, relay in relays.items():
            relay._downstream_writer = writers[host]
            relay._udp_enabled.set()
        router = relay_module.UdpRouter(55001, relays)
        workers = [
            asyncio.create_task(router._forward_route(host)) for host in hosts
        ]
        frames = {
            hosts[0]: bytes([0xA1]) * 40,
            hosts[1]: bytes([0xB2]) * 40,
            hosts[2]: bytes([0xC3]) * 40,
        }
        try:
            for host, frame in frames.items():
                self.assertTrue(router.route_datagram(host, frame))
            await asyncio.wait_for(
                asyncio.gather(*(router.queues[host].join() for host in hosts)),
                timeout=0.5,
            )
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        for host, frame in frames.items():
            self.assertEqual(bytes(writers[host].data), frame)

    async def test_source_ip_routes_master_and_slave_frames_independently(self):
        master = relay_module.StepEspRelay('master', '192.168.4.1', 5000)
        slave = relay_module.StepEspRelay('slave', '192.168.4.3', 5000)
        master_writer = _Writer()
        slave_writer = _Writer()
        master._downstream_writer = master_writer
        slave._downstream_writer = slave_writer
        master._udp_enabled.set()
        slave._udp_enabled.set()
        router = relay_module.UdpRouter(
            55001,
            {
                '192.168.4.1': master,
                '192.168.4.3': slave,
            },
        )
        workers = [
            asyncio.create_task(router._forward_route('192.168.4.1')),
            asyncio.create_task(router._forward_route('192.168.4.3')),
        ]
        try:
            master_frame = bytes([0xA1]) * 50
            slave_frame = bytes([0xB2]) * 50
            self.assertTrue(router.route_datagram('192.168.4.1', master_frame))
            self.assertTrue(router.route_datagram('192.168.4.3', slave_frame))
            self.assertFalse(router.route_datagram('192.168.4.99', b'unknown'))
            await asyncio.wait_for(
                asyncio.gather(
                    router.queues['192.168.4.1'].join(),
                    router.queues['192.168.4.3'].join(),
                ),
                timeout=0.5,
            )
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

        self.assertEqual(bytes(master_writer.data), master_frame)
        self.assertEqual(bytes(slave_writer.data), slave_frame)

    async def test_identify_outcome_matrix_and_binary_traffic_are_forwarded_byte_identically(self):
        relay = relay_module.StepEspRelay(
            'master',
            '192.168.4.1',
            5000,
            expected_device_id=SELF_ID,
        )
        writer = _Writer()
        relay._downstream_writer = writer
        replies = b''.join(
            (
                b'IDENTIFY_ACK'
                if outcome in {'confirmed', 'sent_unconfirmed'}
                else b'IDENTIFY_ERR'
            )
            + b' protocol=identify-v1 command_id=blink-1 '
            + b'target=esp32:aabbccddeeff outcome='
            + outcome.encode('ascii')
            + b' duration_ms=3000 detail=fixture\n'
            for outcome in CROSS_LAYER_IDENTIFY_OUTCOMES
        )
        mixed = (b'\xa1' * 50) + replies + (b'\xb2' * 50)
        await relay._forward_esp_control(_Socket([mixed, b'']))
        self.assertEqual(bytes(writer.data), mixed)

    async def test_malformed_inventory_cannot_poison_an_unrelated_live_route(self):
        with self.assertRaises(relay_module.IdentityProtocolError):
            relay_module.parse_identity_inventory(
                [
                    _peer_line(PEER_ONE_ID, 0),
                    _self_line(peer_count=1),
                    _end_line(1),
                ],
                endpoint='192.168.4.1',
            )

        malformed = relay_module.StepEspRelay('master', '192.168.4.1', 5000)
        live = relay_module.StepEspRelay('slave', '192.168.4.3', 5000)
        live_writer = _Writer()
        live._downstream_writer = live_writer
        live._udp_enabled.set()
        router = relay_module.UdpRouter(
            55001,
            {
                '192.168.4.1': malformed,
                '192.168.4.3': live,
            },
        )
        worker = asyncio.create_task(router._forward_route('192.168.4.3'))
        try:
            self.assertTrue(router.route_datagram('192.168.4.3', b'live-frame'))
            await asyncio.wait_for(
                router.queues['192.168.4.3'].join(),
                timeout=0.5,
            )
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        self.assertEqual(bytes(live_writer.data), b'live-frame')

    async def test_split_identity_change_after_binary_is_quarantined(self):
        relay = relay_module.StepEspRelay('master', '192.168.4.1', 5000)
        relay.session_identity = _complete_inventory().session
        relay._downstream_writer = _Writer()
        changed = _self_line('esp32:010203040506', peer_count=0)
        with self.assertRaises(relay_module.IdentityChangedError):
            await relay._forward_esp_control(
                _Socket([
                    b'\xa1' * 50 + changed[:9],
                    changed[9:],
                ])
            )
        self.assertEqual(
            relay.session_identity.verification_state,
            'quarantined',
        )

    async def test_stalled_route_does_not_block_another_route(self):
        stalled = relay_module.StepEspRelay('master', '192.168.4.1', 5000)
        live = relay_module.StepEspRelay('slave', '192.168.4.3', 5000)
        stalled._downstream_writer = _Writer()
        live_writer = _Writer()
        live._downstream_writer = live_writer
        live._udp_enabled.set()
        router = relay_module.UdpRouter(
            55001,
            {
                '192.168.4.1': stalled,
                '192.168.4.3': live,
            },
        )
        workers = [
            asyncio.create_task(router._forward_route('192.168.4.1')),
            asyncio.create_task(router._forward_route('192.168.4.3')),
        ]
        try:
            self.assertTrue(router.route_datagram('192.168.4.1', b'stalled'))
            self.assertTrue(router.route_datagram('192.168.4.3', b'live'))
            await asyncio.wait_for(
                router.queues['192.168.4.3'].join(),
                timeout=0.5,
            )
            self.assertEqual(bytes(live_writer.data), b'live')
            self.assertEqual(bytes(stalled._downstream_writer.data), b'')
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
