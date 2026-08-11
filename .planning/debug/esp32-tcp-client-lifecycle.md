---
status: verifying
trigger: "서버 재시작이 아닌 클라이언트 수명 관리와 연결 큐 처리를 직접 계측해서 수정"
created: "2026-08-11"
updated: "2026-08-11T17:00:00-07:00"
---

# ESP32 TCP Client Lifecycle

## Symptoms

- expected: Master and slave accept repeated IDENTITY/control connections, then stream UDP data and support the complete GUI workflow without manual reset.
- actual: Both nodes join the iPhone 2.4 GHz hotspot and the first post-reset IDENTITY request can succeed, but subsequent TCP connections time out or close with an empty response.
- errors: Python TimeoutError, ConnectionResetError/WinError 10054, empty recv; firmware previously retained half-open control clients.
- timeline: Worked intermittently after reset; failures persist after moving from STEP_ESP32 AP and Shaw to iPhone hotspot infrastructure mode.
- reproduction: Reset node, connect to TCP 5000, send IDENTITY?, close, reconnect and repeat; second or later request fails. Full direct test stalls before UDP verification.

## Current Focus

- reasoning_checkpoint:
    hypothesis: "Both nodes close valid newly accepted control sockets because TCP_IDLE_CLIENT_TIMEOUT_MS equals the host's normal 500 ms pre-command delay; the host then observes empty recv/reset. The existing fresh-client replacement logic is separately required to prevent queued probes behind an old UDP-mode control socket."
    confirming_evidence:
      - "Live delay matrix passed all 12 immediate/250 ms probes across both boards."
      - "At 500/750 ms, 11 of 12 probes failed with empty recv/reset/abort, and serial logged 'TCP client idle before command; closing'."
      - "scripts/test_stepesp_shaw.py deliberately sleeps 500 ms after connect, exactly matching the shortened firmware timeout."
    falsification_test: "After setting a 5000 ms grace and reflashing, any 1000 ms delayed probe that still produces the idle-close serial log or empty response would falsify the timeout diagnosis."
    fix_rationale: "A 5000 ms timeout safely exceeds observed 0.5-1.0 s host handshake delays while retaining stale-client cleanup. NetworkServer::available() returns only a newly accepted socket, so every accepted socket can replace an old control client in UDP mode without checking the old client's buffered data. Prefix-matching IDENTITY_END lets the smoke test stop on the actual protocol line."
    blind_spots: "The full UDP workflow and long-lived old-socket replacement have not yet been repeated after both boards run the same rebuilt image."
- hypothesis: The full WSL/ROS/GUI startup legitimately takes about 5.5 seconds between the relay's identity work and the next control command, so the former 5000 ms idle grace still closes a valid socket at the production boundary. A 30000 ms grace preserves stale cleanup while covering startup scheduling variance.
- test: Re-run the complete launcher after the freshly flashed 30000 ms images, then verify stable master/slave ROS rates, fleet registry, OpenSim ready/fresh state, and the live GUI.
- expecting: Both routes progress through IDENTITY, REDPITAYA, START, and SENSORS without reconnect; UDP frames remain continuous through the Windows relay into ROS and the GUI.
- next_action: Run `scripts/start_stepesp_wireless.ps1` with the verified hotspot routes and inspect relay/fleet/OpenSim logs plus both ROS IMU topic rates and GUI rendering.

## Evidence

- timestamp: 2026-08-11; Both nodes joined iPhone hotspot channel 6 at 172.20.10.3 and 172.20.10.2.
- timestamp: 2026-08-11; A reset-and-probe captured TCP CMD IDENTITY? and returned IDENTITY_OK once; subsequent reconnect timed out.
- timestamp: 2026-08-11; checked project inventory and git status; found both firmware/step_node/step_node.ino and firmware/step_node_slave/step_node_slave.ino are modified and each defines a global WiFiServer on TCP 5000 plus one global WiFiClient, with accept/replacement logic in loop(). No project-defined .codex/skills or .agents/skills directory exists.
- timestamp: 2026-08-11; checked firmware diff and host probes; found TCP_IDLE_CLIENT_TIMEOUT_MS was changed from 2000 ms to 500 ms in both sketches while scripts/test_stepesp_shaw.py sleeps exactly 500 ms after connect before sending IDENTITY?, producing a direct boundary race. The simple probe sends immediately. Knowledge base had no lifecycle keyword match.
- timestamp: 2026-08-11; ran 24 live probes with simultaneous COM3/COM4 serial capture. All 12 probes sent at 0 or 250 ms succeeded. Eleven of 12 probes sent at 500 or 750 ms failed with empty recv, reset, or abort; every failure correlated with firmware logging 'TCP client idle before command; closing'. This confirms the 500 ms boundary race.
- timestamp: 2026-08-11; shared-workspace investigator reported the fresh UDP-mode control-client replacement was compiled in both sketches, COM3 was flashed, and COM4 previously failed upload due port ownership. Current port inventory shows COM3 and COM4 present with no serial consumer process.
- timestamp: 2026-08-11; master compilation reached a clean 1,014,860-byte image with 49,076 bytes global RAM, but Arduino CLI's --output-dir copy hook failed parsing the apostrophe in the workspace path. This is a tooling export-path error after compilation, not a firmware compile error; retrying with --build-path.
- timestamp: 2026-08-11; ESP32 core NetworkServer::available() was verified to call accept() and return only a newly accepted socket, not the current client. Therefore the old-client current_has_data guard can incorrectly leave a genuinely new connection queued/unhandled; replacement is safe whenever UDP mode permits it.
- timestamp: 2026-08-11; both sketches compiled successfully using apostrophe-free temporary build paths: master 1,014,832 bytes program/49,076 bytes globals; slave 1,011,824 bytes program/48,068 bytes globals.
- timestamp: 2026-08-11; flashed COM3 master and COM4 slave successfully with esptool hash verification and hard reset; COM4 port ownership was no longer blocked.
- timestamp: 2026-08-11; post-flash lifecycle matrix passed 40/40 repeated IDENTITY probes across both nodes (10 immediate and 10 with 1000 ms delay per node). Every response contained complete IDENTITY_OK through IDENTITY_END inventory; no empty/reset/timeout occurred.
- timestamp: 2026-08-11; deliberate stale-client replacement passed on both nodes: an old socket received identity, remained held open, a second new socket received complete identity, and the old socket was observably closed. This directly verifies new-accept replacement.
- timestamp: 2026-08-11; full smoke test completed master IDENTITY, REDPITAYA, START, and SENSORS handshakes but timed out awaiting the UDP frame; its subsequent slave identity phase timed out. This is not yet attributed to the TCP lifecycle fix and requires a scoped retry/state check.
- timestamp: 2026-08-11; discovered a second direct lifecycle cause in temporary instrumentation: the 40/40 matrix passed while COM3/COM4 were continuously drained, but commands later stalled with no serial reader. Upon reopening the COM ports, queued 'TCP CMD' lines flushed and firmware then attempted replies after host sockets had timed out (TCP WRITE FAIL connected=0). The per-command Serial.printf executes before handleLine and can block USB CDC, directly delaying TCP responses.
- timestamp: 2026-08-11; changed the relay to answer downstream IDENTITY? from its already validated, bounded inventory rather than forwarding a second query to the ESP. `backend/test/test_stepesp_udp_relay.py` passes 32 tests and 51 subtests. This removes duplicate/interleaved identity inventories between the relay and fleet bridge.
- timestamp: 2026-08-11; a clean full-stack run bound both verified identities but measured roughly 5.5 seconds from fleet connection to identity bind; with the 5000 ms firmware limit, both sockets closed at REDPITAYA and the fleet retried. A relay-only handshake outside WSL scheduling completed REDPITAYA, STARTED, and SENSORS, isolating the remaining failure to the production startup timing boundary.
- timestamp: 2026-08-11; raised TCP_IDLE_CLIENT_TIMEOUT_MS from 5000 ms to 30000 ms in both sketches, compiled both XIAO ESP32-S3 images, and flashed COM3 master and COM4 slave successfully with esptool hash verification and hard reset.
- timestamp: 2026-08-11; post-flash physical matrix returned JSON `ok: true`: all 12 delayed identity reconnects passed, master and slave each completed REDPITAYA/START/SENSORS, emitted a valid 50-byte UDP frame with 14-channel/28-byte payload header, and acknowledged STOP. The process exit was nonzero only because a Windows serial-reader thread raised ClearCommError during port teardown after the successful result was printed; this is a test-harness shutdown issue, not a device/protocol failure.

## Eliminated

- hypothesis: ESP32 cannot see the hotspot; reason: both nodes joined the iPhone 2.4 GHz hotspot with strong RSSI.

## Resolution

- root_cause: Three lifecycle defects combined: (1) a 500 ms idle timeout matched normal 0.5-1.0 s handshake delays and closed valid sockets before commands; (2) newly accepted sockets could be ignored based on stale old-client buffered state even though NetworkServer::available() returns only a new accept; (3) temporary per-command Serial.printf instrumentation ran before handleLine and blocked TCP processing when USB CDC was not drained, so replies occurred only after host timeout.
- fix: Set TCP_IDLE_CLIENT_TIMEOUT_MS to 30000 ms; always replace the old control client for a newly accepted socket when not protecting a TCP data stream (UDP streaming remains replaceable); remove blocking hot-path TCP serial diagnostics; update smoke test to recognize the field-bearing IDENTITY_END line; make the Windows relay own the physical identity exchange and serve its bounded verified inventory to the fleet client.
- verification: Physical firmware lifecycle and UDP matrix passes on both flashed boards. Final post-change ROS/OpenSim/GUI end-to-end rerun remains pending by explicit wrap-up request.
- files_changed: [firmware/step_node/step_node.ino, firmware/step_node_slave/step_node_slave.ino, scripts/test_stepesp_shaw.py, scripts/stepesp_tcp_udp_relay.py, scripts/start_stepesp_wireless.ps1, backend/rehab_robotics_bridge/fleet_bridge_node.py, backend/test/test_stepesp_udp_relay.py]
