---
phase: 20-full-identity-and-confirmed-identify
verified: 2026-07-30T21:38:55Z
status: human_needed
score: 2/3 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Exact-target LED, polarity, timing, and restoration"
    expected: "On official XIAO ESP32S3 hardware, only the selected full-MAC target blinks for bounded 1 s, 3 s, and 5 s requests; the non-target remains still, GPIO 21 is physically active-low, and the exact prior LED level returns."
    why_human: "Compilation and source tests prove configuration and control flow, but cannot observe electrical polarity, the physical LED, elapsed wall-clock timing, or the non-target board."
  - test: "Identify during live acquisition"
    expected: "Repeating Identify while streaming does not stop or alter acquisition; sample rate, continuity, drops, and errors remain acceptable before, during, and after the action."
    why_human: "The source contract proves no direct acquisition-state mutation, but deployed scheduling, radio, and hardware timing require observation."
  - test: "Identify during SD recording and finalization"
    expected: "Repeating Identify during active SD recording and finalization does not alter session state, saved samples, file size, checksum/status, or continuity."
    why_human: "Static isolation assertions cannot establish storage and recording continuity on deployed hardware."
  - test: "Physical identity and outcome correlation"
    expected: "Recorded base, STA, AP, and ESP-NOW MACs match the selected board relationship, and only a matching command ID plus exact target with outcome=confirmed is paired with a successful physical observation."
    why_human: "The deployed board/interface-MAC relationship and correspondence between the reply and the observed board cannot be established without hardware access."
---

# Phase 20: Full Identity and Confirmed Identify Verification Report

**Phase Goal:** Operators can reliably distinguish and physically identify every Master and Slave without disrupting live work.
**Verified:** 2026-07-30T21:38:55Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Operator can see a verified, normalized full 48-bit identity for the Master and every discovered Slave, with role, IP address, and transport MAC shown as separate metadata. | ✓ VERIFIED | Firmware derives canonical identity from all six eFuse/base-MAC bytes and emits a counted self/peer inventory (`step_node.ino:847-880`, `2713-2787`; Slave equivalent at `835-853`, `2427-2451`). Self rows carry `role`, `route_ip`, and interface/ESP-NOW MACs; peer rows carry distinct role and observed `transport_mac`. Relay session identity keeps `current_endpoint` separate (`stepesp_tcp_udp_relay.py:45-77`, `193-274`), and bridge health exposes verified self plus peer inventory (`esp32_bridge_node.py:938-994`). Directly discovered DHCP candidates are identity-probed before selection, with host/IP retained separately by the launcher (`start_stepesp_wireless.ps1:82-229`, `405-445`). |
| 2 | A physical device retains the same canonical identity across DHCP changes, reconnects, and discovery-order changes, while canonical data-topic instantiation remains owned by Phase 21. | ✓ VERIFIED | Relay registry keys by canonical full MAC, updates the same identity's endpoint, and detaches a displaced identity rather than mutating it (`stepesp_tcp_udp_relay.py:368-404`). Launcher selection probes identity instead of trusting ping/discovery order (`start_stepesp_wireless.ps1:405-445`). Bridge reconnect accepts the same self identity with refreshed route metadata and rejects a changed self before mutation (`esp32_bridge_node.py:938-969`, `1288-1302`). Tests cover DHCP endpoint changes, old-endpoint replacement, arbitrary discovery order, and low-32 collisions. The bridge contains only fixed role publishers; `device_topic_token()` is a pure helper and per-MAC publisher lifecycle is absent, correctly leaving ID-02 and publisher lifecycle to Phase 21. |
| 3 | Operator can target exactly one device with a bounded, non-blocking LED Identify action and see whether it was confirmed, timed out, offline, unsupported, or rejected without interrupting acquisition or recording. | ? UNCERTAIN | Automated evidence verifies exact six-byte lookup and one-peer `esp_now_send`, 1000–5000 ms bounds, loop-owned `millis()` timing, prior-level save/restore code, all seven outcomes, application-level command/target correlation, and no direct acquisition/recording mutation (`step_node.ino:2424-2708`; Slave `2282-2425`; bridge `669-735`, `1131-1228`). Physical target isolation, GPIO polarity, observed timing/restoration, and deployed stream/SD continuity remain intentionally unobserved and require the Phase 20 HUMAN-UAT worksheet. |

**Score:** 2/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `firmware/step_node/step_node.ino` | Master full identity, inventory, exact-target routing, self Identify, ACK forwarding | ✓ VERIFIED | 3,599 lines; versioned exact-size packets, six-byte identity, self/peer/end producer, one-slot unicast, loop-owned LED state machine, and correlated ACK handling are substantive and invoked by command/loop paths. |
| `firmware/step_node_slave/step_node_slave.ino` | Slave full identity and loop-owned idempotent Identify | ✓ VERIFIED | 3,321 lines; matching schemas, exact self target validation, callback-to-loop deferral, ACK after LED start, and deadline restoration are wired into receive, command, setup, and loop paths. |
| `scripts/stepesp_tcp_udp_relay.py` | Identity-confirmed session routing and transparent Identify forwarding | ✓ VERIFIED | 801 lines; strict counted inventory parser, canonical registry, changed-identity quarantine, separate endpoint metadata, and independent relay tasks are substantive and used by relay sessions. |
| `scripts/start_stepesp_wireless.ps1` | Identity-probed DHCP-safe fixed-role launch | ✓ VERIFIED | 522 lines; probes complete inventories, fails closed on ambiguity, passes exact expected IDs separately from endpoints, and launches relay/bridge with those values. |
| `rehab_robotics_interfaces/srv/IdentifyDevice.srv` | Typed exact-target Identify contract | ✓ VERIFIED | Primitive request/response fields include command ID, target, duration, discriminated outcome, applied duration, and detail. |
| `rehab_robotics_interfaces/CMakeLists.txt` | Build registration for Identify service | ✓ VERIFIED | `srv/IdentifyDevice.srv` is registered alongside the existing message in `rosidl_generate_interfaces`. |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | Strict identity binding, health exposure, and typed Identify service | ✓ VERIFIED | 1,700 lines; complete self/peer/end handshake gates the legacy stream, health publishes real bound identity data, and service requests flow through the connected writer to correlated terminal replies. |
| `backend/test/test_stepesp_firmware_topology.py` | Firmware source-contract coverage | ✓ VERIFIED | 588 lines; covers schema parity, collision safety, exact-target unicast, board guard, callback deferral, timing/restoration, and state-isolation invariants. |
| `backend/test/test_stepesp_udp_relay.py` | Relay/reconnect/failure-isolation coverage | ✓ VERIFIED | 555 lines; covers canonical normalization, complete inventory, self-only binding, endpoint replacement, ordering, and independent routes. |
| `backend/test/test_esp32_controls.py` | Bridge/service/parser/outcome coverage | ✓ VERIFIED | 1,016 lines; covers strict inventory, expected-self binding, health snapshot, all outcomes, false-confirmation resistance, and the Phase 21 publisher boundary. |
| `docs/stepesp-identity-identify.md` | Operator contract and physical UAT worksheet | ✓ VERIFIED | 213 lines; documents identity ownership, exact protocols, outcomes, ROS inspection, evidence boundary, and ten pending hardware observations. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| Slave firmware | Master firmware | Matching packed identity/request/ACK schemas | ✓ WIRED | Both sketches define the same versions, exact packet sizes, six-byte MAC fields, duration bounds, and outcome codes; both official FQBN builds pass. |
| Master Identify parser | One peer | Full six-byte comparison then `esp_now_send(slot.mac, ...)` | ✓ WIRED | `step_node.ino:2519-2569` selects one verified slot by base MAC and unicasts only to its observed transport MAC. |
| Launcher | Relay and bridge | Exact canonical expected identity plus separately resolved endpoint | ✓ WIRED | `start_stepesp_wireless.ps1:405-459` rejects ambiguous identity selection and passes both expected ID and host independently. |
| Relay | Firmware text protocol | Complete strict handshake plus byte-transparent forwarding | ✓ WIRED | `stepesp_tcp_udp_relay.py:277-329`, `439-467`, and `615-650` parse/bind identity then forward control bytes without reinterpreting Identify outcomes. |
| Bridge | Firmware inventory and Identify | Full counted handshake, connected writer, bounded response queue | ✓ WIRED | `esp32_bridge_node.py:1264-1302` binds identity before streaming; `1131-1228` sends exact target and accepts only command/target-correlated terminal replies. |
| Bridge | `IdentifyDevice.srv` | Registered ROS service callback | ✓ WIRED | Interface import, service creation, validation, I/O, and response population are present at `esp32_bridge_node.py:59`, `621-625`, and `653-735`. |
| XIAO board macro | Identify GPIO configuration | Exact compile-time guard | ✓ WIRED | Both sketches enable GPIO 21 active-low only under `ARDUINO_XIAO_ESP32S3`; the unsupported branch has no pin or active-level macro. |
| Canonical token helper | Phase 21 boundary | Pure normalization without publisher construction | ✓ WIRED | `device_topic_token()` exists only as a pure helper; no `/esp32/mac_*` publisher, cache, creation, publication, or destruction exists in Phase 20. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| Master/Slave identity inventory | `IdentityPacket` / `device_id` | `ESP.getEfuseMac()`, `esp_read_mac()`, current Wi-Fi IP, and ESP-NOW receive metadata | Yes — hardware-derived values populate emitted self/peer records; no hardcoded identity fixture is used in runtime code. | ✓ FLOWING |
| Relay identity session | `SessionIdentity`, `IdentityInventory` | Live `IDENTITY?` socket response plus actual endpoint | Yes — strict parsing precedes registry binding and stores endpoint separately from the MAC key. | ✓ FLOWING |
| Bridge health identity | `_bound_identity`, `_peer_inventory` | Live complete inventory read from active stream | Yes — bound records flow into `/esp/status/{node_id}` health JSON; empty startup state is replaced only after verified handshake. | ✓ FLOWING |
| Identify response | service request/result | ROS request → active TCP writer → firmware exact-target dispatch → target loop ACK → bounded bridge queue | Yes — only a correlated runtime reply can set `_last_confirmed_identify`; static link-layer completion cannot confirm. | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Cross-layer identity and Identify regression | `python -m unittest backend.test.test_stepesp_firmware_topology backend.test.test_stepesp_udp_relay backend.test.test_esp32_controls -v` | 73 tests ran in 1.054 s; all passed. | ✓ PASS |
| Official Master firmware build | `arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node` | 1,009,968 bytes flash (30%); 49,052 bytes RAM (14%); exit 0. | ✓ PASS |
| Official Slave firmware build | `arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node_slave` | 1,010,772 bytes flash (30%); 48,068 bytes RAM (14%); exit 0. | ✓ PASS |

### Probe Execution

No Phase 20 plan declares a probe script and no conventional `scripts/**/tests/probe-*.sh` exists. Step 7c is **SKIPPED (no applicable probes)**.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ID-01 | 20-01, 20-02, 20-03, 20-05, 20-06 | Operator can see a verified, normalized full 48-bit hardware identity for the Master and every discovered Slave. | ✓ SATISFIED | Six-byte eFuse/base identities flow through firmware inventory, strict relay/bridge binding, health metadata, launcher inspection, and collision tests. |
| ID-03 | 20-01, 20-02, 20-03, 20-04, 20-05, 20-06 | Exact one-device bounded non-blocking Identify with application acknowledgement and discriminated outcomes. | ? NEEDS HUMAN | Software contract, wiring, outcomes, and builds pass. Physical blink/target isolation/timing/restoration and deployed acquisition/recording continuity remain unobserved. |

`ID-02` is not orphaned Phase 20 work. REQUIREMENTS.md and ROADMAP.md assign the canonical per-MAC data-topic and fleet publisher lifecycle to Phase 21. Phase 20 correctly supplies stable identity and the collision-safe token foundation without instantiating that lifecycle.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| Scoped Phase 20 files | — | No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, placeholder, empty implementation, or console-only handler matched. | ℹ️ Info | No blocker anti-pattern found. |
| `docs/stepesp-identity-identify.md` | 180-207 | Explicit `HUMAN NEEDED` / `Pending` worksheet | ℹ️ Info | Deliberate evidence gate, not a product stub. |

### Disconfirmation Pass

- **Partial requirement:** ID-03 is only software-verified; its physical LED and continuity claims are not yet established.
- **Potentially misleading passing test:** the topology suite inspects firmware source structure. It proves the checked-in state machine and guards, but cannot prove deployed GPIO polarity, actual blink timing, or hardware scheduling behavior.
- **Uncovered deployed error path:** a board-specific LED mapping/polarity mismatch or radio/storage timing interaction can occur despite compilation and source-contract success; the pending hardware worksheet is required to close this path.

### Human Verification Required

#### 1. Exact-target LED, polarity, timing, and restoration

**Test:** With at least two official XIAO ESP32S3 devices powered, record the selected and witness identities, issue fresh exact-target Identify commands for 1000, 3000, and 5000 ms, and observe the LEDs and prior level.

**Expected:** Only the selected device blinks; the witness stays still; GPIO 21 behaves active-low; each duration is bounded to the request; and the exact prior application-owned LED level returns.

**Why human:** Software can prove selection and timing logic but cannot observe board electrical/visible behavior.

#### 2. Identify during live acquisition

**Test:** Repeat Identify while acquisition is streaming and record sample rate, continuity, drops, and errors before, during, and after.

**Expected:** Streaming remains active with no Identify-induced interruption or material change.

**Why human:** Deployed scheduler, network, radio, and sensor behavior cannot be established by static source checks.

#### 3. Identify during SD recording and finalization

**Test:** Repeat Identify during active SD recording and finalization; capture session state, saved samples, file size, checksum/status, and any discontinuity.

**Expected:** Recording/finalization remains valid and unchanged by Identify.

**Why human:** Storage and recording continuity require the physical device and SD path.

#### 4. Physical identity and outcome correlation

**Test:** Record the target's base, STA, AP, and ESP-NOW MACs, firmware hash, command ID, exact target, terminal outcome, applied duration, detail, timestamps, and observed board.

**Expected:** The full-MAC relationship is attributable to the physical target, and only the matching exact-target `confirmed` reply is paired with a successful observation.

**Why human:** Code cannot establish that the responding identity is the board the operator physically observed.

### Gaps Summary

No automated implementation gap was found. The identity, reconnect, exact-target, correlation, outcome, fail-closed board guard, and Phase 21 boundary contracts are implemented and independently pass their test/build gates.

The phase cannot be marked `passed` because its goal explicitly includes physical identification without live-work disruption. The required STEP_ESP observations have not been performed. Complete the runbook's **Pending one-selected-target physical UAT** worksheet; a non-target blink, out-of-bound duration, incorrect restoration, or acquisition/recording change is a failed UAT result and must not be auto-approved.

---

_Verified: 2026-07-30T21:38:55Z_
_Verifier: the agent (gsd-verifier)_
