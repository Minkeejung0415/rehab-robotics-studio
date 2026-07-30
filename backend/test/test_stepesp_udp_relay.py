"""Contract tests for routing STEP_ESP32 UDP frames into WSL streams."""
from __future__ import annotations

import asyncio
import importlib.util
import socket
import sys
import unittest
from pathlib import Path


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
        first = registry.bind(_complete_inventory(SELF_ID).session)
        second = registry.bind(
            _complete_inventory(PEER_TWO_ID, endpoint='192.168.4.8').session
        )
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
        self.assertIn(
            '$_.DeviceId -eq $expectedSlaveCanonical',
            self.launcher,
        )
        self.assertIn(
            'Discovered verified self identities:',
            self.launcher,
        )

    def test_role_alias_endpoint_and_verified_identity_are_separate_launch_values(self):
        for contract in (
            '--esp-host $MasterHost',
            '--expected-device-id $verifiedMasterDeviceId',
            '--slave-host $resolvedSlaveHost',
            '--slave-expected-device-id $verifiedSlaveDeviceId',
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


class StepEspUdpRelayTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_identify_terminal_reply_is_forwarded_byte_identically(self):
        relay = relay_module.StepEspRelay(
            'master',
            '192.168.4.1',
            5000,
            expected_device_id=SELF_ID,
        )
        writer = _Writer()
        relay._downstream_writer = writer
        reply = (
            b'IDENTIFY_ACK protocol=identify-v1 command_id=blink-1 '
            b'target=esp32:aabbccddeeff outcome=confirmed duration_ms=3000 '
            b'detail=started\n'
        )
        await relay._forward_esp_control(_Socket([reply, b'']))
        self.assertEqual(bytes(writer.data), reply)

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
