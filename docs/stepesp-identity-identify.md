# STEP_ESP32 Identity and Confirmed Identify

This runbook defines the Phase 20 operator contract for discovering a device's
stable full identity and asking exactly one selected device to identify itself.
It separates locally repeatable software evidence from the physical
`HUMAN-UAT` that still requires a deployed board.

## Identity forms and ownership

The stable identity is the complete six-byte eFuse/base MAC:

- Canonical form used by launch parameters, protocol requests, services, and
  internal keys: `esp32:aabbccddeeff`
- Display form shown to operators: `AA:BB:CC:DD:EE:FF`
- Collision-safe topic token reserved for Phase 21: `mac_aabbccddeeff`

Never use a role (`master` or `slave`), DHCP IP, route, discovery slot,
interface MAC, or deprecated low-32-bit `slave_id` as the stable identity.
Two devices such as `esp32:1111ccddeeff` and `esp32:2222ccddeeff` share the
same low 32 bits and must remain distinct.

The following are separate metadata, not aliases for the stable identity:

| Field | Meaning | Mutable or contextual |
| --- | --- | --- |
| `base_mac` | Display form of the eFuse/base identity | Stable identity source |
| `sta_mac` | Wi-Fi station interface MAC | Interface metadata |
| `ap_mac` | Wi-Fi access-point interface MAC | Interface metadata |
| `espnow_mac` | Current ESP-NOW interface MAC | Transport metadata |
| `transport_mac` | MAC observed for a peer route | Route metadata |
| `role` | Current Master/Slave compatibility role | Operational metadata |
| `route_ip` | Current IP endpoint | Mutable route metadata |
| `slave_id_deprecated` | Legacy low-32 diagnostic value | Never an identity key |

A changed base identity on a known route represents a different device. Keep
the old identity offline and register the new identity separately; do not
mutate one device into the other.

## Exact `IDENTITY?` inventory contract

Send this line on the firmware control connection:

```text
IDENTITY?
```

A complete two-peer example is exactly one `IDENTITY_OK` `record=self` row,
exactly the advertised number of `IDENTITY_PEER` `record=peer` rows, and one
matching `IDENTITY_END` terminator:

```text
IDENTITY_OK protocol=id-v1 record=self peer_count=2 device_id=esp32:aabbccddeeff display_mac=AA:BB:CC:DD:EE:FF base_mac=AA:BB:CC:DD:EE:FF sta_mac=AA:BB:CC:DD:EE:F0 ap_mac=AA:BB:CC:DD:EE:F1 espnow_mac=AA:BB:CC:DD:EE:F2 role=master route_ip=192.168.4.1 schema_version=1 verified=1 identify_supported=1 board_revision=xiao_esp32s3
IDENTITY_PEER protocol=id-v1 record=peer device_id=esp32:112233445566 display_mac=11:22:33:44:55:66 base_mac=11:22:33:44:55:66 sta_mac=11:22:33:44:55:66 ap_mac=11:22:33:44:55:66 espnow_mac=11:22:33:44:55:66 transport_mac=10:20:30:40:50:60 role=slave schema_version=1 verified=1 identify_supported=1 slave_id_deprecated=33445566
IDENTITY_PEER protocol=id-v1 record=peer device_id=esp32:77bbccddeeff display_mac=77:BB:CC:DD:EE:FF base_mac=77:BB:CC:DD:EE:FF sta_mac=77:BB:CC:DD:EE:FF ap_mac=77:BB:CC:DD:EE:FF espnow_mac=77:BB:CC:DD:EE:FF transport_mac=10:20:30:40:50:61 role=slave schema_version=1 verified=1 identify_supported=1 slave_id_deprecated=ccddeeff
IDENTITY_END protocol=id-v1 peer_count=2
```

For a Slave directly connected to the host, the valid sequence is one self row
with `peer_count=0`, followed immediately by
`IDENTITY_END protocol=id-v1 peer_count=0`.

Relay and bridge session binding is fail-closed:

1. The first record must be the one verified `record=self` row.
2. Exactly `peer_count` distinct `record=peer` rows must follow.
3. The final `IDENTITY_END` count must equal the self row's `peer_count`.
4. Only the self row can satisfy `--expected-device-id`,
   `--slave-expected-device-id`, or ROS `expected_device_id`.
5. Peer inventory never binds the connected session, even if a peer reports
   the expected ID.

Missing or duplicate self rows, peer-before-self order, a peer repeating self,
duplicate peers, count mismatch, and a missing or mismatched terminator all
reject the inventory. Do not continue streaming under a guessed identity.

The wireless launcher performs these checks automatically when exact identities
are supplied:

```powershell
.\scripts\start_stepesp_wireless.ps1 `
  -ExpectedMasterDeviceId esp32:aabbccddeeff `
  -ExpectedSlaveDeviceId esp32:112233445566
```

Ping and DHCP results discover candidate routes only. They never select
physical identity.

## Exact-target Identify contract

The terminal command is versioned, correlated by a bounded command ID, targets
the full canonical identity, and carries a bounded duration:

```text
IDENTIFY protocol=identify-v1 command_id=operator-blink-001 target=esp32:aabbccddeeff duration_ms=3000
```

The accepted duration range is 1-5 seconds (`1000` through `5000` ms), with a
3-second (`3000` ms) default. The firmware clamps or rejects values according
to this contract; operators should send an explicit in-range value.

The typed ROS surface preserves the same fields:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc 'source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 service call /esp32/master/identify rehab_robotics_interfaces/srv/IdentifyDevice "{command_id: operator-blink-001, target_device_id: esp32:aabbccddeeff, duration_ms: 3000}"'
```

The response contains `command_id`, `target_device_id`, `outcome`,
`applied_duration_ms`, and `detail`. A result confirms this request only when
both command ID and exact full target match.

The corresponding terminal lines retain the requested and applied durations:

```text
IDENTIFY_ACK protocol=identify-v1 command_id=operator-blink-001 target=esp32:aabbccddeeff outcome=confirmed requested_duration_ms=3000 applied_duration_ms=3000 detail=started
IDENTIFY_ERR protocol=identify-v1 command_id=operator-blink-001 target=esp32:aabbccddeeff outcome=timeout requested_duration_ms=3000 applied_duration_ms=0 detail=application_ack
```

## Outcome meanings

| Outcome | Operator meaning | Success? |
| --- | --- | --- |
| `confirmed` | The exact target validated the request, started its loop-owned LED action, and returned a correlated application ACK. | Yes |
| `sent_unconfirmed` | Transport accepted/sent the request, but no target application confirmation has arrived. | No |
| `timeout` | The target application ACK did not arrive within the bounded wait. A late ACK remains unmatched. | No |
| `offline` | The exact target is not in verified connected inventory, or the bridge connection is unavailable. | No |
| `unsupported` | The target or mixed/older firmware does not advertise safe Identify support. | No |
| `rejected` | The target received the request but rejected it; inspect `detail`. | No |
| `invalid_target` | The target syntax, identity, or exact-target resolution is invalid. | No |

ESP-NOW send completion is never physical confirmation. A wrong-command,
wrong-target, duplicate-unmatched, late, or lost reply cannot update the
last-confirmed state. Duplicate delivery of the same command ID and target is
idempotent and must not extend the active deadline indefinitely.

## LED safety and mixed firmware

Phase 20 enables Identify only for the official Seeed Studio XIAO ESP32S3
compile target guarded by `ARDUINO_XIAO_ESP32S3`. The selected onboard user LED
is `GPIO 21` with `active-low` semantics. Unknown board targets are pinless and
return `unsupported`; never guess a fallback pin or polarity.

Identify is owned by the normal firmware loop. It must not call `delay()`, block
an ESP-NOW callback, change acquisition rate/filter state, start or stop
streaming, or mutate SD recording/finalization state. When the deadline expires,
the firmware restores the exact prior application-owned LED level.

Mixed old/new firmware must continue the existing acquisition and recording
path. An older device may appear as unverified legacy inventory and returns
`unsupported` for Identify. It must not be promoted to verified self from a
role, IP, peer row, route MAC, or `slave_id_deprecated`.

## Existing Phase 20 ROS inspection

Phase 20 retains the compatibility role publishers and role Identify services on
the single-session `esp32_bridge_node` (USB/legacy). Phase 21 wireless fleet mode
binds the same compatibility topics as **explicit aliases** on `fleet_bridge_node`
via `alias_master_device_id` / `alias_slave_device_id` (or first verified
master/slave roles when those params are empty). Canonical streams use
`/esp/raw|status/mac_<12hex>`; `/esp/fleet/registry` is authoritative for N>2.
`/esp/status/pair` publishes when both aliases are bound (COMP-01).

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic echo /esp/status/master --once --field data"
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic echo /esp/status/slave --once --field data"
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic echo /esp/fleet/registry --once --field data"
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 service list | grep -E '^/esp32/(master|slave)/identify$'"
```

Inspect `identity.self` for the bound session and `identity.peers` only as
inventory. Phase 20 defines and tests the pure `mac_<12hex>` normalization
contract. Phase 21 owns canonical per-MAC publisher lifecycle, identity-bound
aliases, N-route fleet routing, and the registry snapshot.

## Evidence boundary

Automated local evidence can prove:

- firmware source/configuration guards and official-board compilation;
- exact self/peer/count/end parsing and self-only binding;
- full-MAC collision resistance and exact-target correlation;
- all seven reason-coded outcomes and non-confirmation behavior;
- loop/callback isolation, prior-level restoration code, queue bounds, and
  preservation of existing acquisition/recording contracts; and
- absence of Phase 20 per-MAC publisher lifecycle.

Automated evidence does **not** prove that a deployed board's LED is electrically
active-low, only the chosen board blinks, observed timing matches the requested
duration, the prior physical level is restored, or streaming/recording remain
unaffected on real hardware. Those observations remain pending `HUMAN-UAT`.

The execute-phase verifier must record this physical worksheet as `HUMAN-UAT`;
it must not auto-approve it from fixtures, source inspection, compilation, or
this document. Phase 25 remains the final multi-device capacity, supported
fleet-size/rate, and compatibility-mode promotion gate.

## Pending one-selected-target physical UAT

Use one selected XIAO ESP32S3 target with at least one other device powered,
visible, and close enough to observe. Record actual identities, firmware
revisions, board markings, route/interface MACs, timestamps, and results. Do
not fill this worksheet from expected behavior.

| Check | Requested/expected observation | Actual observation | Result |
| --- | --- | --- | --- |
| Identity relationship | Record selected board base, STA, AP, and ESP-NOW MACs separately; verify which is the stable eFuse/base identity. | HUMAN NEEDED | Pending |
| Non-target isolation | Select one exact canonical target; the other visible device must not blink. | HUMAN NEEDED | Pending |
| 1-second bound | Send a new command ID with `duration_ms=1000`; observe only the selected target. | HUMAN NEEDED | Pending |
| 3-second default | Send a new command ID with `duration_ms=3000`; observe only the selected target. | HUMAN NEEDED | Pending |
| 5-second bound | Send a new command ID with `duration_ms=5000`; observe only the selected target. | HUMAN NEEDED | Pending |
| Active-low behavior | Verify the deployed board revision's GPIO 21 LED electrical/visible active-low behavior. | HUMAN NEEDED | Pending |
| Exact restoration | Capture the prior application-owned LED level, run Identify, and verify that exact level returns afterward. | HUMAN NEEDED | Pending |
| Streaming isolation | Run Identify while live acquisition is streaming; record continuity, sample rate, and any drops/errors. | HUMAN NEEDED | Pending |
| SD recording isolation | Run Identify during active SD recording and finalization; verify session state, saved samples, file size, and checksum/status remain valid. | HUMAN NEEDED | Pending |
| Outcome correlation | Record command ID, exact target, terminal outcome, applied duration, and detail; only matching `confirmed` may be marked successful. | HUMAN NEEDED | Pending |

If any non-target blinks, physical timing is out of bounds, state restoration is
not exact, or acquisition/recording changes, mark `HUMAN-UAT` failed and retain
the Phase 20 compatibility mode. Do not infer Phase 25 fleet capacity or
promotion from this one-target worksheet.
