# Phase 16 Verification: Retire Custom Angle + IK Contracts

**Verified:** 2026-07-28
**Status:** PASSED
**Requirement:** IK-00

## Scope Checked

| Plan | Objective | Result |
|------|-----------|--------|
| 16-01 | Backend default-OFF custom `/opensim/joint_angle` | PASS |
| 16-02 | Studio default graph / HealthPanel / rosbridge retirement | PASS |
| 16-03 | Locked `/opensim/joint_states` + CALIBRATED gate contracts | PASS |

## Must-Have Truths

| Truth | Evidence |
|-------|----------|
| Default opensim_bridge does not publish product `/opensim/joint_angle` | `test_default_path_never_publishes_custom_joint_angle_as_product` |
| Status does not present custom deg as product IK when flag off | `joint_angle_deg` is `None` when `publish_joint_angle_enabled=false` |
| Default graph does not use `opensim_ik_live` as product IK | B8 = `opensim_ik_waiting`; productKneeReadout tests |
| Rosbridge does not attach `/opensim/joint_angle` by default | `does not attach /opensim/joint_angle to emitted frames by default` |
| HealthPanel shows waiting/calibration-required | "Waiting (requires calibration)" copy |
| `/opensim/joint_states` + CALIBRATED gate locked | `ik_contracts.py` + `test_ik_contracts` + `docs/opensim-ik-contracts.md` |

## Automated Results

### Backend

```
$env:PYTHONPATH='backend'; python -m unittest \
  backend.test.test_opensim_node \
  backend.test.test_opensim_launch \
  backend.test.test_opensim_adapter \
  backend.test.test_ik_contracts -v
```

- **Result:** Ran 55 tests — OK (3 skipped: OpenSim bindings / visualizer not installed on host)
- **ik_contracts:** 5/5 OK

### Studio

```
npm test --prefix rehab-robotics-studio
npm run typecheck --prefix rehab-robotics-studio
```

- **Result:** 22/22 tests pass; `tsc --noEmit` clean
- Includes `productKneeReadout.test.ts` fail-closed suite

### Contract doc assert

```
python -c "... assert docs/opensim-ik-contracts.md contains locked names ..."
```

- **Result:** DOC_OK; `JOINT_STATES_TOPIC == '/opensim/joint_states'`

## Key Commits

| Hash | Message |
|------|---------|
| `8b475c9` | test(16-01): failing retired joint-angle tests |
| `cb363b0` | feat(16-01): demote joint_angle behind default-OFF flag |
| `615f0fe` | docs(16-01): complete plan |
| `71e77f1` | test(16-02): product knee readout contract tests |
| `6747003` | feat(16-02): retire Studio custom angle product path |
| `258f0be` | docs(16-02): complete plan |
| `6cc0da6` | test(16-03): IK contract constant assertions |
| `3dc9325` | feat(16-03): lock IK ROS contracts and calibration gate |

## Self-Check

| Artifact | Status |
|----------|--------|
| `16-01-SUMMARY.md` | FOUND |
| `16-02-SUMMARY.md` | FOUND |
| `16-03-SUMMARY.md` | FOUND |
| `docs/opensim-ik-contracts.md` | FOUND |
| `backend/.../opensim/ik_contracts.py` | FOUND |
| Commits above on `master` | FOUND |

## Self-Check: PASSED

## Gaps / Out of Scope (intentional)

- No OpenSim IK solver (Phase 18)
- No Calibrate toolbar / services implementation (Phase 17)
- No `/opensim/joint_states` runtime publisher (Phase 18)
- Phase 17 not started (per execution directive)

## Verdict

**Phase 16 is complete.** Custom relative-quat angle is retired as product OpenSim IK on backend and Studio; contracts for calibrated JointState output are locked.
