# Hardware Acceptance Report — Rehab Robotics Multi-Device Workflow

**Phase:** 25 — Multi-Device Compatibility and Promotion Gate
**Requirement:** COMP-03
**Purpose:** Documents hardware evidence that the dynamic N-sensor fleet workflow (`use_fleet_bridge=true`) is safe to set as the default launch configuration.

**Promotion Gate:** Run `python scripts/acceptance_gate.py` — exits 0 only when all sections are STATUS: PASS.

> **Note on rollback mode:** The legacy two-sensor workflow remains available at any time by launching with `use_fleet_bridge:=false`. This is the current default and will remain so until this gate closes.

---

## 1. Fleet Configuration Tested

Document the devices under test: device IDs, roles, firmware version, and fleet size.

| Field | Value |
|-------|-------|
| Fleet size (Master + Slaves) | PENDING HARDWARE TEST |
| Master device ID | PENDING HARDWARE TEST |
| Slave device IDs | PENDING HARDWARE TEST |
| Firmware version | PENDING HARDWARE TEST |
| Test date | PENDING HARDWARE TEST |
| Tested by / Date: | PENDING |

STATUS: PENDING

---

## 2. Identify Safety

Confirm that the LED Identify action works for each device individually without disrupting acquisition or other devices.

**Procedure:** Issue Identify to Master; confirm LED blinks; confirm Slave IMU data continues to publish at target rate. Repeat for each Slave.

| Device | Outcome | Acquisition unaffected | Notes |
|--------|---------|----------------------|-------|
| Master | PENDING | PENDING | |
| Slave 1 | PENDING | PENDING | |

Tested by / Date: PENDING

STATUS: PENDING

---

## 3. Acquisition Continuity

Master plus N-1 Slave acquisition at target Hz with no data loss during continuous operation.

**Target rate:** ≥100 Hz per device. **Duration:** ≥60 seconds.

| Device | Measured rate (Hz) | Dropped frames | Notes |
|--------|--------------------|---------------|-------|
| Master | PENDING | PENDING | |
| Slave 1 | PENDING | PENDING | |

Tested by / Date: PENDING

STATUS: PENDING

---

## 4. Recording Continuity

Full record/stop cycle with N sensors. Verify no dropped frames at device reconnect during recording.

**Procedure:** Start recording, power-cycle one Slave mid-recording, stop recording, verify file integrity.

| Metric | Result | Notes |
|--------|--------|-------|
| Recording start/stop without error | PENDING | |
| Frame count consistent after reconnect | PENDING | |
| SD file playback valid | PENDING | |

Tested by / Date: PENDING

STATUS: PENDING

---

## 5. Reconnect Under Load

Physically power-cycle one Slave during active acquisition; confirm recovery and re-attachment.

**Procedure:** All devices streaming → power-cycle Slave → wait for reconnect → confirm IMU data resumes on canonical MAC topic → confirm assignment re-attaches automatically.

| Metric | Result | Notes |
|--------|--------|-------|
| Reconnect time (seconds) | PENDING | |
| Assignment re-attaches automatically | PENDING | |
| Other devices unaffected during reconnect | PENDING | |

Tested by / Date: PENDING

STATUS: PENDING

---

## 6. Radio/Relay Load

Measured throughput at full fleet size; compare to single-device baseline.

**Procedure:** Single device → measure UDP rate. Full fleet → measure per-device UDP rate. Record ratio.

| Configuration | Measured rate (Hz) | Packet loss (%) | Notes |
|---------------|--------------------|-----------------|-------|
| Single device baseline | PENDING | PENDING | |
| Full fleet per-device | PENDING | PENDING | |
| Rate ratio (fleet/baseline) | PENDING | PENDING | |

Tested by / Date: PENDING

STATUS: PENDING

---

## 7. OpenSim Solve Latency

Wall-clock latency from IMU frame arrival to `/rehab/opensim/joint_states` publication for N sensors.

**Procedure:** Timestamp IMU frame on arrival; timestamp JointState publish. Compute delta over 1000 samples. Report mean and 99th percentile.

| Metric | Value | Notes |
|--------|-------|-------|
| Mean latency (ms) | PENDING | |
| 99th percentile latency (ms) | PENDING | |
| Sensor count (N) | PENDING | |

Tested by / Date: PENDING

STATUS: PENDING

---

## 8. Compatibility Aliases

Confirm `/esp32/master/imu` and `/esp32/slave/imu` still publish matching data when fleet_bridge is active with alias bindings configured.

**Procedure:** Launch with `use_fleet_bridge:=true alias_master_device_id:=<ID> alias_slave_device_id:=<ID>`. Subscribe to both alias topics. Confirm data matches canonical MAC topics.

**Rollback verification:** Launch with `use_fleet_bridge:=false`; confirm legacy esp32_bridge_node starts and publishes on both alias topics without fleet_bridge.

| Topic | Publishes | Matches canonical | Notes |
|-------|-----------|------------------|-------|
| /esp32/master/imu (fleet mode) | PENDING | PENDING | |
| /esp32/slave/imu (fleet mode) | PENDING | PENDING | |
| /esp32/master/imu (legacy mode) | PENDING | N/A (native) | |
| /esp32/slave/imu (legacy mode) | PENDING | N/A (native) | |

Tested by / Date: PENDING

STATUS: PENDING

---

## Gate Summary

All 8 sections must show `STATUS: PASS` before dynamic mode is promoted to the default.

Run: `python scripts/acceptance_gate.py`

Current gate status: OPEN — hardware evidence pending.
