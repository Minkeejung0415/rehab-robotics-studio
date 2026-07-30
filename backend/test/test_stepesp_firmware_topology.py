"""Regression checks for the STEP_ESP32 master/slave network contract."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]
MASTER_SOURCE = REPO_ROOT / 'firmware' / 'step_node' / 'step_node.ino'
SLAVE_SOURCE = REPO_ROOT / 'firmware' / 'step_node_slave' / 'step_node_slave.ino'

# Shared by the firmware, relay, and bridge suites so every adjacent layer is
# checked against one named protocol matrix instead of drifting fixture copies.
CROSS_LAYER_SELF_ID = 'esp32:aabbccddeeff'
CROSS_LAYER_PEER_IDS = (
    'esp32:112233445566',
    'esp32:77bbccddeeff',
)
CROSS_LAYER_LOW32_COLLISION_IDS = (
    'esp32:1111ccddeeff',
    'esp32:2222ccddeeff',
)
CROSS_LAYER_IDENTITY_REJECTION_CASES = (
    'missing_self',
    'duplicate_self',
    'peer_before_self',
    'peer_reuses_self',
    'duplicate_peer',
    'count_mismatch',
    'missing_terminator',
    'mismatched_terminator',
)
CROSS_LAYER_BINDING_ATTACKS = ('peer_matches_expected',)
CROSS_LAYER_IDENTIFY_OUTCOMES = (
    'confirmed',
    'sent_unconfirmed',
    'timeout',
    'offline',
    'unsupported',
    'rejected',
    'invalid_target',
)
CROSS_LAYER_FALSE_CONFIRM_CASES = (
    'wrong_command',
    'wrong_target',
    'duplicate_unmatched',
    'late',
    'lost',
    'sent_unconfirmed',
    'timeout',
    'offline',
    'unsupported',
    'rejected',
    'invalid_target',
)


def define(source: str, name: str) -> str:
    match = re.search(rf'^#define\s+{re.escape(name)}\s+(.+?)\s*(?://.*)?$', source, re.MULTILINE)
    if match is None:
        raise AssertionError(f'missing firmware define: {name}')
    return match.group(1).strip().strip('"')


def xiao_identify_led_branches(source: str) -> tuple[str, str]:
    match = re.search(
        r'^#if defined\(ARDUINO_XIAO_ESP32S3\)\s*$'
        r'(?P<supported>.*?)'
        r'^#else\s*$'
        r'(?P<unsupported>.*?)'
        r'^#endif\s*$',
        source,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(
            'missing exact ARDUINO_XIAO_ESP32S3 Identify LED guard'
        )
    return match.group('supported'), match.group('unsupported')


def struct_body(source: str, name: str) -> str:
    match = re.search(
        rf'struct\s+{re.escape(name)}\s*\{{(?P<body>.*?)\}}\s*;',
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f'missing firmware struct: {name}')
    return match.group('body')


def function_body(source: str, name: str) -> str:
    signature = re.search(
        rf'(?:static\s+)?[\w:*&<>\s]+\b{re.escape(name)}\s*\([^;]*?\)\s*\{{',
        source,
    )
    if signature is None:
        raise AssertionError(f'missing firmware function: {name}')
    depth = 1
    cursor = signature.end()
    while cursor < len(source) and depth:
        if source[cursor] == '{':
            depth += 1
        elif source[cursor] == '}':
            depth -= 1
        cursor += 1
    if depth:
        raise AssertionError(f'unbalanced firmware function: {name}')
    return source[signature.end():cursor - 1]


def canonical_device_id(mac: bytes) -> str:
    if len(mac) != 6:
        raise ValueError('full MAC must contain exactly six bytes')
    return f'esp32:{mac.hex()}'


class StepEspFirmwareTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = MASTER_SOURCE.read_text(encoding='utf-8')
        cls.slave = SLAVE_SOURCE.read_text(encoding='utf-8')

    def test_master_is_the_only_soft_ap_owner(self):
        self.assertEqual(define(self.master, 'WIFI_FORCE_SOFT_AP'), 'true')
        self.assertEqual(define(self.slave, 'WIFI_FORCE_SOFT_AP'), 'false')
        self.assertEqual(define(self.slave, 'WIFI_ALLOW_SOFT_AP_FALLBACK'), 'false')

    def test_slave_sta_credentials_match_master_ap(self):
        self.assertEqual(define(self.slave, 'WIFI_SSID'), define(self.master, 'WIFI_AP_SSID'))
        self.assertEqual(define(self.slave, 'WIFI_PASS'), define(self.master, 'WIFI_AP_PASS'))

    def test_slave_uses_dhcp_instead_of_a_conflicting_fixed_address(self):
        self.assertEqual(define(self.slave, 'SLAVE_STATIC_IP_OCTET'), '0')

    def test_espnow_channel_matches_master_ap_channel(self):
        ap_channel = define(self.master, 'WIFI_AP_CHANNEL')
        self.assertEqual(define(self.master, 'ESPNOW_WIFI_CHANNEL'), ap_channel)
        self.assertEqual(define(self.slave, 'ESPNOW_WIFI_CHANNEL'), ap_channel)

    def test_live_stream_uses_shared_udp_router_port(self):
        self.assertEqual(define(self.master, 'WIFI_STREAM_OVER_TCP'), 'false')
        self.assertEqual(define(self.slave, 'WIFI_STREAM_OVER_TCP'), 'false')
        self.assertEqual(define(self.master, 'UDP_STREAM_PORT'), '55001')
        self.assertEqual(define(self.slave, 'UDP_STREAM_PORT'), '55001')

        for source in (self.master, self.slave):
            self.assertNotIn('STREAM_TCP_BATCH_MAX_FRAMES', source)
            self.assertNotIn('STREAM_TCP_BATCH_WAIT_MS', source)
            self.assertIn(
                'stream_udp.beginPacket(target, UDP_STREAM_PORT)',
                source,
            )
            self.assertIn(
                'stream_udp.write((const uint8_t *)&rec.header, sizeof(rec.header))',
                source,
            )
            self.assertIn(
                'stream_udp.write((const uint8_t *)rec.ch, sizeof(rec.ch))',
                source,
            )
            self.assertIn('stream_udp.endPacket()', source)
            self.assertIn('transport=udp port=55001', source)
            self.assertIn('g_stream_sent++;', source)
            self.assertIn('g_stream_send_errors++;', source)

    def test_start_handshake_precedes_binary_streaming(self):
        for source in (self.master, self.slave):
            start_branch = source[source.index('} else if (line.startsWith("START")) {'):]
            sensors = start_branch.index('replyToHost("SENSORS:0,ICM20948\\n");')
            streaming = start_branch.index('streaming = true;')
            self.assertLess(sensors, streaming)

    def test_slave_direct_tcp_start_is_not_preempted_by_espnow(self):
        relay_case = self.slave[
            self.slave.index('case CMD_START_STREAM:'):
            self.slave.index('case CMD_STOP_STREAM:')
        ]
        self.assertIn('#if ENABLE_TCP', relay_case)
        self.assertIn('#else', relay_case)
        self.assertIn('streaming = true;', relay_case)

    def test_identity_packet_schema_matches_and_carries_full_interface_identity(self):
        expected_fields = (
            'uint8_t magic;',
            'uint8_t type;',
            'uint8_t version;',
            'uint16_t packet_size;',
            'uint8_t base_mac[6];',
            'uint8_t sta_mac[6];',
            'uint8_t ap_mac[6];',
            'uint8_t espnow_mac[6];',
            'uint8_t role;',
            'uint16_t capabilities;',
            'uint8_t verified;',
        )
        master_body = struct_body(self.master, 'IdentityPacket')
        slave_body = struct_body(self.slave, 'IdentityPacket')
        self.assertEqual(
            re.sub(r'\s+', ' ', master_body).strip(),
            re.sub(r'\s+', ' ', slave_body).strip(),
        )
        for field in expected_fields:
            self.assertIn(field, master_body)
        for name in (
            'IDENTITY_PACKET_MAGIC',
            'IDENTITY_PACKET_TYPE',
            'IDENTITY_PACKET_VERSION',
            'IDENTITY_CAP_IDENTIFY',
        ):
            self.assertEqual(define(self.master, name), define(self.slave, name))

    def test_identity_receive_paths_reject_unknown_or_wrong_sized_packets(self):
        for source in (self.master, self.slave):
            receive = function_body(source, 'onEspNowRecv')
            self.assertRegex(
                receive,
                r'len\s*==\s*\(int\)sizeof\(IdentityPacket\)',
            )
            self.assertIn(
                'identity->packet_size == sizeof(IdentityPacket)',
                receive,
            )
            self.assertIn(
                'identity->version == IDENTITY_PACKET_VERSION',
                receive,
            )
            self.assertIn(
                'identity->type == IDENTITY_PACKET_TYPE',
                receive,
            )

    def test_full_mac_collision_does_not_collapse_identity(self):
        first = bytes.fromhex(CROSS_LAYER_LOW32_COLLISION_IDS[0][6:])
        second = bytes.fromhex(CROSS_LAYER_LOW32_COLLISION_IDS[1][6:])
        self.assertEqual(first[-4:], second[-4:])
        self.assertNotEqual(canonical_device_id(first), canonical_device_id(second))
        for source in (self.master, self.slave):
            self.assertIn('formatCanonicalDeviceId', source)
            self.assertIn('formatDisplayMac', source)
            identity_regions = '\n'.join(
                function_body(source, name)
                for name in ('formatCanonicalDeviceId', 'formatDisplayMac')
            )
            self.assertNotIn('slave_id', identity_regions)

    def test_identity_inventory_has_one_self_then_counted_peers_and_terminator(self):
        master_inventory = function_body(self.master, 'printIdentityInventory')
        slave_inventory = function_body(self.slave, 'printIdentityInventory')
        self.assertIn(
            'IDENTITY_OK protocol=id-v1 record=self peer_count=%d',
            master_inventory,
        )
        self.assertIn(
            'IDENTITY_PEER protocol=id-v1 record=peer',
            master_inventory,
        )
        self.assertIn(
            'IDENTITY_END protocol=id-v1 peer_count=%d',
            master_inventory,
        )
        self.assertLess(
            master_inventory.index('IDENTITY_OK protocol=id-v1 record=self'),
            master_inventory.index('IDENTITY_PEER protocol=id-v1 record=peer'),
        )
        self.assertLess(
            master_inventory.index('IDENTITY_PEER protocol=id-v1 record=peer'),
            master_inventory.index('IDENTITY_END protocol=id-v1'),
        )
        self.assertNotIn(
            'IDENTITY_OK protocol=id-v1 record=peer',
            master_inventory,
        )
        self.assertIn('peer_count=0', slave_inventory)
        self.assertNotIn('IDENTITY_PEER', slave_inventory)
        self.assertIn('IDENTITY_END protocol=id-v1 peer_count=0', slave_inventory)
        for source in (self.master, self.slave):
            command = function_body(source, 'handleLine')
            self.assertIn('line.equalsIgnoreCase("IDENTITY?")', command)
            self.assertIn('printIdentityInventory();', command)

    def test_cross_layer_matrix_pins_exact_firmware_producer_and_identify_contract(self):
        master_inventory = function_body(self.master, 'printIdentityInventory')
        slave_inventory = function_body(self.slave, 'printIdentityInventory')
        self.assertEqual(
            master_inventory.count(
                'IDENTITY_OK protocol=id-v1 record=self peer_count=%d'
            ),
            1,
        )
        self.assertEqual(
            master_inventory.count(
                'IDENTITY_PEER protocol=id-v1 record=peer'
            ),
            2,
        )
        self.assertEqual(
            master_inventory.count(
                'IDENTITY_END protocol=id-v1 peer_count=%d'
            ),
            1,
        )
        self.assertEqual(
            slave_inventory.count(
                'IDENTITY_OK protocol=id-v1 record=self peer_count=0'
            ),
            1,
        )
        self.assertEqual(slave_inventory.count('IDENTITY_PEER'), 0)
        self.assertEqual(
            slave_inventory.count(
                'IDENTITY_END protocol=id-v1 peer_count=0'
            ),
            1,
        )

        dispatch = function_body(self.master, 'dispatchIdentifyRequest')
        self.assertIn('memcmp(self.base_mac, target_mac, 6)', dispatch)
        self.assertRegex(
            dispatch,
            r'memcmp\(slot\.identity\.base_mac,\s*target_mac,\s*6\)',
        )
        self.assertNotIn('slave_id', dispatch)
        host_output = function_body(self.master, 'emitIdentifyHostResult')
        for outcome in CROSS_LAYER_IDENTIFY_OUTCOMES:
            self.assertIn(f'"{outcome}"', self.master)
        self.assertIn('command_id=%s target=%s outcome=%s', host_output)

    def test_legacy_status_remains_unverified_and_not_an_identity_key(self):
        master_inventory = function_body(self.master, 'printIdentityInventory')
        self.assertIn('verified=0', master_inventory)
        self.assertIn('identify_supported=0', master_inventory)
        self.assertIn('slave_id_deprecated=', master_inventory)
        self.assertRegex(
            self.master,
            r'memcmp\(g_slave_status\[i\]\.mac,\s*info->src_addr,\s*'
            r'sizeof\(g_slave_status\[i\]\.mac\)\)',
        )
        self.assertNotRegex(
            self.master,
            r'(?:identity|target)[^\n]*(?:==|memcmp)[^\n]*slave_id|'
            r'slave_id[^\n]*(?:==|memcmp)[^\n]*(?:identity|target)',
        )

    def test_xiao_led_capability_is_exactly_guarded_and_fail_closed(self):
        master_supported, master_unsupported = xiao_identify_led_branches(
            self.master
        )
        slave_supported, slave_unsupported = xiao_identify_led_branches(
            self.slave
        )
        self.assertEqual(master_supported, slave_supported)
        self.assertEqual(master_unsupported, slave_unsupported)

        self.assertEqual(
            define(master_supported, 'STEPESP_IDENTIFY_LED_VERIFIED'),
            '1',
        )
        self.assertEqual(
            define(master_supported, 'STEPESP_IDENTIFY_LED_PIN'),
            'GPIO_NUM_21',
        )
        self.assertEqual(
            define(master_supported, 'STEPESP_IDENTIFY_LED_ACTIVE_LEVEL'),
            'LOW',
        )
        self.assertEqual(
            define(master_supported, 'STEPESP_IDENTIFY_LED_BOARD_REVISION'),
            'seeed-xiao-esp32s3',
        )

        self.assertEqual(
            define(master_unsupported, 'STEPESP_IDENTIFY_LED_VERIFIED'),
            '0',
        )
        self.assertEqual(
            define(master_unsupported, 'STEPESP_IDENTIFY_LED_BOARD_REVISION'),
            'unsupported',
        )
        self.assertNotIn('STEPESP_IDENTIFY_LED_PIN', master_unsupported)
        self.assertNotIn(
            'STEPESP_IDENTIFY_LED_ACTIVE_LEVEL',
            master_unsupported,
        )
        self.assertNotIn('GPIO_NUM_21', master_unsupported)

    def test_identify_packet_schemas_match_and_require_exact_validation(self):
        request_fields = (
            'uint8_t magic;',
            'uint8_t type;',
            'uint8_t version;',
            'uint16_t packet_size;',
            'char command_id[IDENTIFY_COMMAND_ID_MAX + 1];',
            'uint8_t target_mac[6];',
            'uint32_t requested_duration_ms;',
        )
        ack_fields = (
            'uint8_t magic;',
            'uint8_t type;',
            'uint8_t version;',
            'uint16_t packet_size;',
            'char command_id[IDENTIFY_COMMAND_ID_MAX + 1];',
            'uint8_t target_mac[6];',
            'uint32_t requested_duration_ms;',
            'uint32_t applied_duration_ms;',
            'uint8_t outcome;',
        )
        for struct_name, expected_fields in (
            ('IdentifyRequestPacket', request_fields),
            ('IdentifyAckPacket', ack_fields),
        ):
            master_body = struct_body(self.master, struct_name)
            slave_body = struct_body(self.slave, struct_name)
            self.assertEqual(
                re.sub(r'\s+', ' ', master_body).strip(),
                re.sub(r'\s+', ' ', slave_body).strip(),
            )
            for field in expected_fields:
                self.assertIn(field, master_body)

        for name in (
            'IDENTIFY_PACKET_MAGIC',
            'IDENTIFY_REQUEST_TYPE',
            'IDENTIFY_ACK_TYPE',
            'IDENTIFY_PACKET_VERSION',
            'IDENTIFY_COMMAND_ID_MAX',
            'IDENTIFY_DURATION_MIN_MS',
            'IDENTIFY_DURATION_MAX_MS',
            'IDENTIFY_DURATION_DEFAULT_MS',
        ):
            self.assertEqual(define(self.master, name), define(self.slave, name))

        master_receive = function_body(self.master, 'onEspNowRecv')
        slave_receive = function_body(self.slave, 'onEspNowRecv')
        self.assertIn(
            'len == (int)sizeof(IdentifyAckPacket)',
            master_receive,
        )
        self.assertIn(
            'ack->packet_size == sizeof(IdentifyAckPacket)',
            master_receive,
        )
        self.assertIn(
            'ack->version == IDENTIFY_PACKET_VERSION',
            master_receive,
        )
        self.assertIn(
            'len == (int)sizeof(IdentifyRequestPacket)',
            slave_receive,
        )
        self.assertIn(
            'request->packet_size == sizeof(IdentifyRequestPacket)',
            slave_receive,
        )
        self.assertIn(
            'request->version == IDENTIFY_PACKET_VERSION',
            slave_receive,
        )

    def test_identify_outcomes_and_duration_contract_match(self):
        outcome_names = (
            'IDENTIFY_OUTCOME_CONFIRMED',
            'IDENTIFY_OUTCOME_SENT_UNCONFIRMED',
            'IDENTIFY_OUTCOME_TIMEOUT',
            'IDENTIFY_OUTCOME_OFFLINE',
            'IDENTIFY_OUTCOME_UNSUPPORTED',
            'IDENTIFY_OUTCOME_REJECTED',
            'IDENTIFY_OUTCOME_INVALID_TARGET',
        )
        for name in outcome_names:
            self.assertEqual(define(self.master, name), define(self.slave, name))
        self.assertEqual(define(self.master, 'IDENTIFY_DURATION_MIN_MS'), '1000UL')
        self.assertEqual(define(self.master, 'IDENTIFY_DURATION_MAX_MS'), '5000UL')
        self.assertEqual(define(self.master, 'IDENTIFY_DURATION_DEFAULT_MS'), '3000UL')

        host_output = function_body(self.master, 'emitIdentifyHostResult')
        self.assertIn('IDENTIFY_ACK protocol=identify-v1', host_output)
        self.assertIn('IDENTIFY_ERR protocol=identify-v1', host_output)
        self.assertIn('command_id=%s target=%s outcome=%s', host_output)
        self.assertIn('applied_duration_ms=%lu detail=%s', host_output)
        for outcome in CROSS_LAYER_IDENTIFY_OUTCOMES:
            self.assertIn(f'"{outcome}"', self.master)

    def test_master_identify_parser_targets_self_or_one_full_mac_peer(self):
        parser = function_body(self.master, 'handleIdentifyLine')
        dispatch = function_body(self.master, 'dispatchIdentifyRequest')
        self.assertIn('protocol=identify-v1', parser)
        self.assertIn('command_id=', parser)
        self.assertIn('target=esp32:', parser)
        self.assertIn('duration_ms=', parser)
        self.assertIn('IDENTIFY_DURATION_DEFAULT_MS', parser)
        self.assertIn('parseCanonicalDeviceId', parser)
        self.assertIn('isSafeIdentifyCommandId', parser)
        self.assertIn('memcmp(self.base_mac, target_mac, 6)', dispatch)
        self.assertRegex(
            dispatch,
            r'memcmp\(slot\.identity\.base_mac,\s*target_mac,\s*6\)',
        )
        self.assertIn(
            'esp_now_send(slot.mac, (uint8_t *)&request, sizeof(request))',
            dispatch,
        )
        self.assertNotIn('espNowSendToSlaves', dispatch)
        self.assertNotIn('slave_id', dispatch)

    def test_identify_callbacks_defer_application_work_to_loop(self):
        master_receive = function_body(self.master, 'onEspNowRecv')
        slave_receive = function_body(self.slave, 'onEspNowRecv')
        self.assertIn('g_identify_ack_pending = true;', master_receive)
        self.assertIn(
            'g_identify_pending_ack = *ack;',
            master_receive,
        )
        self.assertIn('g_identify_request_pending = true;', slave_receive)
        self.assertIn(
            'g_identify_pending_request = *request;',
            slave_receive,
        )
        callbacks = (
            master_receive,
            slave_receive,
            function_body(self.master, 'onEspNowSent'),
            function_body(self.slave, 'onEspNowSent'),
        )
        for callback in callbacks:
            self.assertNotIn('digitalWrite(', callback)
            self.assertNotIn('pinMode(', callback)
            self.assertNotIn('delay(', callback)

        for send_callback in callbacks[2:]:
            self.assertNotIn('IDENTIFY_OUTCOME_CONFIRMED', send_callback)
            self.assertNotIn('confirmed', send_callback)

    def test_identify_tick_is_non_blocking_idempotent_and_restores_led(self):
        forbidden_assignment = re.compile(
            r'\b(?:streaming|g_stream_target_ip|g_sd_recording|'
            r'g_relay_only_recording|g_sample_hz|g_sample_last_us|'
            r'g_generated_samples|g_filter_on|g_rec_state|g_rec_armed|'
            r'g_rec_start_at_us|g_rec_stop_at_us|g_rec_grace_deadline_ms|'
            r'g_sd_ready|g_sd_saved_samples|g_sd_write_errors|'
            r'g_sd_queue_drops)\s*=(?!=)'
        )
        for source in (self.master, self.slave):
            tick = function_body(source, 'identifyTick')
            self.assertNotIn('delay(', tick)
            self.assertIsNone(forbidden_assignment.search(tick))
            self.assertIn('g_identify_request_pending', tick)
            self.assertIn('g_identify_last_ack_valid', tick)
            self.assertIn('g_identify_active_command_id', tick)
            self.assertIn('g_identify_deadline_ms', tick)
            self.assertIn('g_identify_prior_led_level', tick)
            self.assertRegex(
                tick,
                r'g_identify_prior_led_level\s*=\s*'
                r'digitalRead\(STEPESP_IDENTIFY_LED_PIN\)',
            )
            self.assertRegex(
                tick,
                r'g_identify_deadline_ms\s*=\s*'
                r'now_ms\s*\+\s*request\.requested_duration_ms',
            )
            self.assertIn(
                'digitalWrite(STEPESP_IDENTIFY_LED_PIN, '
                'g_identify_prior_led_level)',
                tick,
            )
            self.assertIn(
                'strcmp(request.command_id, g_identify_active_command_id) == 0',
                tick,
            )
            self.assertIn('identifyTick();', function_body(source, 'loop'))

    def test_identify_unsupported_path_never_touches_unknown_pin(self):
        for source in (self.master, self.slave):
            tick = function_body(source, 'identifyTick')
            unsupported = tick[
                tick.index('#if !STEPESP_IDENTIFY_LED_VERIFIED'):
                tick.index('#else', tick.index('#if !STEPESP_IDENTIFY_LED_VERIFIED'))
            ]
            self.assertIn('IDENTIFY_OUTCOME_UNSUPPORTED', unsupported)
            self.assertNotIn('digitalWrite(', unsupported)
            self.assertNotIn('pinMode(', unsupported)


if __name__ == '__main__':
    unittest.main()
