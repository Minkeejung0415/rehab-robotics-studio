"""Offline deterministic tests for mapping_node.py (MAP-01 through MAP-06).

No live ROS, no hardware, no OpenSim. All tests run via:
  python -m unittest backend.test.test_mapping_node -v
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Stub infrastructure (defined BEFORE installing stubs and loading module)
# ---------------------------------------------------------------------------

_FAKE_MODEL_HASH = "a" * 64
_FAKE_CATALOG_JSON = json.dumps({
    "schema_version": "rehab.model_catalog.1",
    "model_hash": _FAKE_MODEL_HASH,
    "model_path": "/fake/model.osim",
    "frame_list": [
        {"segment": "femur_r", "frame": "femur_r_imu"},
        {"segment": "tibia_r", "frame": "tibia_r_imu"},
    ],
    "error_reason": "",
})

DEVICE_A = "esp32:aabbccddeeff"
DEVICE_B = "esp32:112233445566"
DEVICE_C = "esp32:ffeeddccbbaa"


class _Parameter:
    def __init__(self, value):
        self.value = value


class _Publisher:
    def __init__(self):
        self.messages: list = []

    def publish(self, msg):
        self.messages.append(msg)


class _Logger:
    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass

    def debug(self, msg):
        pass


class _StubNode:
    """Test-double for rclpy.node.Node — supports declare_parameter, publishers, services, subs.

    Must be defined before _install_ros_stubs() so it can be set as Node in the ROS stub.
    MappingNode inherits from this at class-definition time (when the module is exec'd).
    """
    parameter_overrides: dict = {}

    def __init__(self, name: str):
        self.node_name = name
        self.parameters: dict = {}
        self.publishers_list: list[_Publisher] = []
        self.subscriptions_list: list = []
        self.services_list: list = []
        self.timers_list: list = []
        self._logger = _Logger()

    def declare_parameter(self, name: str, default):
        value = self.parameter_overrides.get(name, default)
        self.parameters[name] = value
        return _Parameter(value)

    def get_parameter(self, name: str):
        return _Parameter(self.parameters[name])

    def create_publisher(self, msg_type, topic: str, qos):
        pub = _Publisher()
        pub.message_type = msg_type  # type: ignore[attr-defined]
        pub.topic = topic  # type: ignore[attr-defined]
        self.publishers_list.append(pub)
        return pub

    def create_subscription(self, msg_type, topic: str, callback, qos):
        sub = types.SimpleNamespace(
            message_type=msg_type, topic=topic, callback=callback
        )
        self.subscriptions_list.append(sub)
        return sub

    def create_service(self, srv_type, name: str, callback):
        svc = types.SimpleNamespace(srv_type=srv_type, name=name, callback=callback)
        self.services_list.append(svc)
        return svc

    def create_timer(self, period, callback):
        timer = types.SimpleNamespace(period=period, callback=callback)
        self.timers_list.append(timer)
        return timer

    def get_logger(self):
        return self._logger


class _String:
    """Stub for std_msgs.msg.String."""
    def __init__(self, **kw):
        self.data = ""


class _QoSProfile:
    def __init__(self, **kw):
        pass


# ---------------------------------------------------------------------------
# ROS stub installation (must happen before loading mapping_node module)
# ---------------------------------------------------------------------------

def _install_ros_stubs() -> None:
    """Install minimal ROS stubs so mapping_node.py can be imported offline.

    Critically, rclpy.node.Node is set to _StubNode so that MappingNode
    inherits from _StubNode (not object) when the module is exec'd.
    Use sys.modules[] assignment (not setdefault) to ensure the correct
    stub is always active when the module is loaded.
    """
    _backend_root = str(Path(__file__).parents[1])
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

    # rclpy.qos
    rclpy_qos = types.ModuleType("rclpy.qos")
    rclpy_qos.HistoryPolicy = types.SimpleNamespace(KEEP_LAST="KEEP_LAST", KEEP_ALL="KEEP_ALL")
    rclpy_qos.QoSProfile = _QoSProfile
    sys.modules["rclpy.qos"] = rclpy_qos

    # rclpy.node
    rclpy_node = types.ModuleType("rclpy.node")
    rclpy_node.Node = _StubNode
    sys.modules["rclpy.node"] = rclpy_node

    # rclpy (top-level)
    rclpy = types.ModuleType("rclpy")
    rclpy.node = rclpy_node
    rclpy.qos = rclpy_qos
    rclpy.ok = lambda: True
    rclpy.init = lambda *a, **k: None
    rclpy.spin = lambda *a, **k: None
    rclpy.try_shutdown = lambda *a, **k: None
    sys.modules["rclpy"] = rclpy

    # std_msgs
    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.String = _String
    std_msgs.msg = std_msgs_msg
    sys.modules["std_msgs"] = std_msgs
    sys.modules["std_msgs.msg"] = std_msgs_msg

    # rehab_robotics_interfaces.srv
    rehab_interfaces = types.ModuleType("rehab_robotics_interfaces")
    rehab_srv = types.ModuleType("rehab_robotics_interfaces.srv")
    for svc_name in ("SetAssignment", "ApplyMapping", "GetMappingState", "ResetMapping"):
        svc_cls = type(svc_name, (), {
            "Request": type(svc_name + ".Request", (), {}),
            "Response": type(svc_name + ".Response", (), {}),
        })
        setattr(rehab_srv, svc_name, svc_cls)
    rehab_interfaces.srv = rehab_srv
    sys.modules["rehab_robotics_interfaces"] = rehab_interfaces
    sys.modules["rehab_robotics_interfaces.srv"] = rehab_srv


def _load_mapping_module():
    """Load mapping_node.py as an isolated module (with stubs installed).

    Stubs are installed via sys.modules[] assignment before exec so that
    MappingNode inherits _StubNode as its Node base class.
    """
    _install_ros_stubs()
    path = Path(__file__).parents[1] / "rehab_robotics_bridge" / "mapping_node.py"
    spec = importlib.util.spec_from_file_location("mapping_node_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Module-level load (shared across all test classes in this file)
mapping = _load_mapping_module()


# ---------------------------------------------------------------------------
# Request / response factory helpers
# ---------------------------------------------------------------------------

def _req(**kwargs):
    return types.SimpleNamespace(**kwargs)


def _set_assign_req(device_id: str, segment: str, frame: str, state: str):
    return _req(device_id=device_id, segment=segment, frame=frame, state=state)


def _set_assign_resp():
    return _req(outcome="", detail="")


def _apply_req(expected_revision: int):
    return _req(expected_revision=expected_revision)


def _apply_resp():
    return _req(outcome="", applied_revision=0, detail="")


def _get_state_resp():
    return _req(state_json="")


def _reset_req(model_hash: str = ""):
    return _req(model_hash=model_hash)


def _reset_resp():
    return _req(outcome="")


def _str_msg(data: str):
    """Create a fake String message."""
    return types.SimpleNamespace(data=data)


def _make_node(tmp_dir: str) -> mapping.MappingNode:
    """Instantiate MappingNode with a temp store_path.

    MappingNode inherits _StubNode (set at module-load time), so no
    patching is needed here — just set parameter_overrides before init.
    """
    store_path = str(Path(tmp_dir) / "mapping_store.json")
    _StubNode.parameter_overrides = {"store_path": store_path}
    try:
        node = mapping.MappingNode()
    finally:
        _StubNode.parameter_overrides = {}
    return node


# ---------------------------------------------------------------------------
# MappingStoreTest — pure persistence layer, no ROS
# ---------------------------------------------------------------------------

class MappingStoreTest(unittest.TestCase):
    """MAP-01 through MAP-04: store invariants, persistence, corruption recovery."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp.name) / "mapping_store.json"
        self.store = mapping.MappingStore(self.store_path)
        # All assigned-state tests need a model_hash loaded
        self.store.set_model_hash("deadbeef01234567" * 4)

    def tearDown(self):
        self.tmp.cleanup()

    # MAP-01: initial state
    def test_initial_state_is_empty(self):
        """MAP-01: fresh MappingStore has revision=0, applied_revision=0, assignments={}."""
        fresh_store = mapping.MappingStore(self.store_path.parent / "fresh.json")
        self.assertEqual(fresh_store.revision, 0)
        self.assertEqual(fresh_store.applied_revision, 0)
        self.assertEqual(fresh_store.assignments, {})

    # MAP-01: set_assignment states
    def test_set_assignment_assigned_ok(self):
        """MAP-01: set_assignment with state=assigned succeeds when frame is valid."""
        self.store.set_frame_list([{"segment": "femur_r", "frame": "femur_r_imu"}])
        outcome, detail = self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(outcome, "ok")
        self.assertIn(DEVICE_A, self.store.assignments)
        self.assertEqual(self.store.assignments[DEVICE_A]["state"], "assigned")

    def test_set_assignment_not_used_ok(self):
        """MAP-01: set_assignment with state=not_used does not require a frame."""
        outcome, _ = self.store.set_assignment(DEVICE_A, "", "", "not_used")
        self.assertEqual(outcome, "ok")

    def test_set_assignment_unassigned_ok(self):
        """MAP-01: set_assignment with state=unassigned is valid (draft only)."""
        outcome, _ = self.store.set_assignment(DEVICE_A, "", "", "unassigned")
        self.assertEqual(outcome, "ok")

    # MAP-01: invalid state rejection
    def test_set_assignment_invalid_state_rejected(self):
        """MAP-01: set_assignment rejects unknown state values."""
        outcome, _ = self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "active")
        self.assertEqual(outcome, "invalid_state")

    # MAP-01: device_id validation
    def test_set_assignment_invalid_device_id_rejected_bare_string(self):
        """MAP-01: bare non-esp32 device_id is rejected."""
        outcome, _ = self.store.set_assignment("invalidid", "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(outcome, "invalid_device_id")

    def test_set_assignment_invalid_device_id_rejected_too_short(self):
        """MAP-01: esp32: prefix with fewer than 12 hex chars is rejected."""
        outcome, _ = self.store.set_assignment("esp32:tooshort", "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(outcome, "invalid_device_id")

    def test_set_assignment_invalid_device_id_rejected_uppercase(self):
        """MAP-01: uppercase hex in device_id is rejected (canonical form is lowercase)."""
        outcome, _ = self.store.set_assignment("esp32:AABBCCDDEEFF", "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(outcome, "invalid_device_id")

    def test_set_assignment_invalid_device_id_rejected_wrong_prefix(self):
        """MAP-01: wrong prefix (not 'esp32:') is rejected."""
        outcome, _ = self.store.set_assignment("notanesp32:aabbccddeeff", "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(outcome, "invalid_device_id")

    # MAP-01: duplicate frame rejection
    def test_set_assignment_duplicate_frame_rejected(self):
        """MAP-01: assigning two devices to the same (segment, frame) pair is rejected."""
        self.store.set_frame_list([{"segment": "femur_r", "frame": "femur_r_imu"}])
        outcome_a, _ = self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(outcome_a, "ok")
        outcome_b, _ = self.store.set_assignment(DEVICE_B, "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(outcome_b, "duplicate_frame")
        # DEVICE_B should NOT have been added
        self.assertNotIn(DEVICE_B, self.store.assignments)

    # MAP-02: revision tracking
    def test_revision_increments_on_each_set_assignment(self):
        """MAP-02: each successful set_assignment increments revision by 1."""
        self.assertEqual(self.store.revision, 0)
        self.store.set_assignment(DEVICE_A, "", "", "unassigned")
        self.assertEqual(self.store.revision, 1)
        self.store.set_assignment(DEVICE_B, "", "", "not_used")
        self.assertEqual(self.store.revision, 2)

    # MAP-03: persistence
    def test_persistence_across_instantiation(self):
        """MAP-03: assignments survive MappingStore re-instantiation from same path."""
        self.store.set_frame_list([{"segment": "femur_r", "frame": "femur_r_imu"}])
        self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        # Reload from disk
        new_store = mapping.MappingStore(self.store_path)
        self.assertIn(DEVICE_A, new_store.assignments)
        self.assertEqual(new_store.assignments[DEVICE_A]["state"], "assigned")

    def test_backup_on_save(self):
        """MAP-03: atomic write produces a .bak file after the first save."""
        self.store.set_assignment(DEVICE_A, "", "", "unassigned")
        # The backup is written on the SECOND save (first save has no prior file to back up)
        self.store.set_assignment(DEVICE_B, "", "", "unassigned")
        bak = self.store_path.with_suffix(".bak")
        self.assertTrue(
            bak.exists(),
            msg=f"Expected .bak file at {bak} but it was not found.",
        )

    # MAP-03: corruption recovery
    def test_corruption_recovery_fresh_start(self):
        """MAP-03: both main and .bak corrupt triggers fresh start (revision=0, assignments={})."""
        # Write garbage to both paths
        self.store_path.write_text("not valid json {{{", encoding="utf-8")
        bak = self.store_path.with_suffix(".bak")
        bak.write_text("also garbage", encoding="utf-8")
        # Load fresh store
        recovered = mapping.MappingStore(self.store_path)
        self.assertEqual(recovered.revision, 0)
        self.assertEqual(recovered.assignments, {})

    # MAP-03: reset
    def test_reset_clears_assignments(self):
        """MAP-03: reset() clears assignments and sets revision back to 0."""
        self.store.set_frame_list([{"segment": "femur_r", "frame": "femur_r_imu"}])
        self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        self.assertEqual(self.store.revision, 1)
        outcome = self.store.reset("")
        self.assertEqual(outcome, "ok")
        self.assertEqual(self.store.assignments, {})
        self.assertEqual(self.store.revision, 0)

    # MAP-04: apply_candidate — revision mismatch
    def test_apply_fails_on_revision_mismatch(self):
        """MAP-04: apply_candidate with wrong expected_revision returns revision_mismatch."""
        result = self.store.apply_candidate(
            expected_revision=999,
            frame_list=[],
            interlock_active=False,
        )
        self.assertEqual(result["outcome"], "revision_mismatch")

    # MAP-04: apply_candidate — interlock (blocked)
    def test_apply_blocked_when_interlock_active(self):
        """MAP-04: apply_candidate is blocked when interlock_active=True."""
        result = self.store.apply_candidate(
            expected_revision=0,
            frame_list=[],
            interlock_active=True,
            interlock_reason="recording_active",
        )
        self.assertEqual(result["outcome"], "blocked")

    # MAP-04: apply_candidate — incomplete mapping
    def test_apply_fails_incomplete_mapping(self):
        """MAP-04: apply returns 'incomplete' when any device has state=unassigned."""
        self.store.set_assignment(DEVICE_A, "", "", "unassigned")
        result = self.store.apply_candidate(
            expected_revision=1,
            frame_list=[{"segment": "femur_r", "frame": "femur_r_imu"}],
            interlock_active=False,
        )
        self.assertEqual(result["outcome"], "incomplete")
        # applied_revision must not be touched
        self.assertEqual(result["applied_revision"], 0)

    # MAP-04: apply_candidate — success path
    def test_apply_passes_with_valid_candidate(self):
        """MAP-04: apply_candidate succeeds and persists applied_revision when all checks pass."""
        self.store.set_frame_list([{"segment": "femur_r", "frame": "femur_r_imu"}])
        self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        result = self.store.apply_candidate(
            expected_revision=1,
            frame_list=[{"segment": "femur_r", "frame": "femur_r_imu"}],
            interlock_active=False,
        )
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(result["applied_revision"], 1)
        self.assertEqual(self.store.applied_revision, 1)

    # MAP-04: apply_candidate — invalid_frame
    def test_apply_fails_invalid_frame(self):
        """MAP-04: apply returns 'invalid_frame' when assigned frame not in frame_list."""
        self.store.set_frame_list([{"segment": "femur_r", "frame": "femur_r_imu"}])
        self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        # Apply with an empty frame_list (frame no longer valid)
        result = self.store.apply_candidate(
            expected_revision=1,
            frame_list=[],
            interlock_active=False,
        )
        self.assertEqual(result["outcome"], "invalid_frame")

    # MAP-04: applied_revision is preserved on failure
    def test_apply_preserves_applied_revision_on_failure(self):
        """MAP-04: failed apply does not overwrite a previously applied_revision."""
        self.store.set_frame_list([{"segment": "femur_r", "frame": "femur_r_imu"}])
        self.store.set_assignment(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        # First apply — succeeds
        first = self.store.apply_candidate(
            expected_revision=1,
            frame_list=[{"segment": "femur_r", "frame": "femur_r_imu"}],
            interlock_active=False,
        )
        self.assertEqual(first["outcome"], "applied")
        self.assertEqual(self.store.applied_revision, 1)
        # Add an unassigned device (bumps revision to 2)
        self.store.set_assignment(DEVICE_B, "", "", "unassigned")
        # Second apply — should fail incomplete
        second = self.store.apply_candidate(
            expected_revision=2,
            frame_list=[{"segment": "femur_r", "frame": "femur_r_imu"}],
            interlock_active=False,
        )
        self.assertEqual(second["outcome"], "incomplete")
        # applied_revision must still be 1
        self.assertEqual(self.store.applied_revision, 1)


# ---------------------------------------------------------------------------
# MappingNodeApplyTest — ROS service handler contracts (MAP-04, MAP-05)
# ---------------------------------------------------------------------------

class MappingNodeApplyTest(unittest.TestCase):
    """Tests for MappingNode service handlers via _StubNode."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_node(self.tmp.name)
        # Load catalog (sets model_hash + frame_list)
        self.node._on_catalog(_str_msg(_FAKE_CATALOG_JSON))
        # Assign DEVICE_A to femur_r frame
        req = _set_assign_req(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        resp = _set_assign_resp()
        self.node._on_set_assignment(req, resp)
        self.assertEqual(resp.outcome, "ok", "setUp: set_assignment must succeed")

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_ok(self):
        """MAP-04: successful apply returns outcome=applied, applied_revision=1."""
        req = _apply_req(expected_revision=1)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "applied")
        self.assertEqual(result.applied_revision, 1)

    def test_apply_revision_mismatch(self):
        """MAP-04: apply with wrong expected_revision returns revision_mismatch."""
        req = _apply_req(expected_revision=99)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "revision_mismatch")

    def test_apply_blocked_recording(self):
        """MAP-05: apply is blocked when recording_active=True; detail says 'recording'."""
        self.node._recording_active = True
        req = _apply_req(expected_revision=1)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "blocked")
        self.assertIn("recording", result.detail)

    def test_apply_blocked_calibration(self):
        """MAP-05: apply is blocked when calibration_active=True; detail says 'calibration'."""
        self.node._calibration_active = True
        req = _apply_req(expected_revision=1)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "blocked")
        self.assertIn("calibration", result.detail)

    def test_apply_incomplete_unassigned_device(self):
        """MAP-04: apply fails with 'incomplete' when a device has state=unassigned."""
        # Add DEVICE_B as unassigned (revision becomes 2)
        req2 = _set_assign_req(DEVICE_B, "", "", "unassigned")
        resp2 = _set_assign_resp()
        self.node._on_set_assignment(req2, resp2)
        req = _apply_req(expected_revision=2)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "incomplete")

    def test_apply_invalid_frame(self):
        """MAP-04: apply fails with 'invalid_frame' when assigned frame is not in frame_list."""
        # Assign DEVICE_B to an unknown frame (revision becomes 2)
        # We do this directly on the store to bypass set_assignment frame validation
        self.node._store._data["assignments"][DEVICE_B] = {
            "segment": "femur_r",
            "frame": "unknown_frame",
            "state": "assigned",
        }
        self.node._store._data["revision"] = 2
        req = _apply_req(expected_revision=2)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "invalid_frame")

    def test_apply_preserves_applied_revision_on_failure(self):
        """MAP-04: failed apply does not overwrite previously applied_revision."""
        # First apply — OK at revision=1
        req1 = _apply_req(expected_revision=1)
        resp1 = _apply_resp()
        self.node._on_apply_mapping(req1, resp1)
        self.assertEqual(self.node._store.applied_revision, 1)
        # Add DEVICE_B as unassigned (revision becomes 2)
        req2 = _set_assign_req(DEVICE_B, "", "", "unassigned")
        resp2 = _set_assign_resp()
        self.node._on_set_assignment(req2, resp2)
        # Second apply fails — incomplete
        req3 = _apply_req(expected_revision=2)
        resp3 = _apply_resp()
        result = self.node._on_apply_mapping(req3, resp3)
        self.assertEqual(result.outcome, "incomplete")
        self.assertEqual(self.node._store.applied_revision, 1)


# ---------------------------------------------------------------------------
# MappingNodeReconnectTest — reconnect re-attach and new device (MAP-06)
# ---------------------------------------------------------------------------

class MappingNodeReconnectTest(unittest.TestCase):
    """MAP-06: fleet registry reconnect re-attach contracts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_node(self.tmp.name)
        # Load catalog
        self.node._on_catalog(_str_msg(_FAKE_CATALOG_JSON))
        # Assign DEVICE_A to femur_r_imu
        req = _set_assign_req(DEVICE_A, "femur_r", "femur_r_imu", "assigned")
        resp = _set_assign_resp()
        self.node._on_set_assignment(req, resp)
        # Apply successfully (applied_revision=1)
        apply_req = _apply_req(expected_revision=1)
        apply_resp = _apply_resp()
        self.node._on_apply_mapping(apply_req, apply_resp)

    def tearDown(self):
        self.tmp.cleanup()

    def _fleet_msg(self, device_ids: list[str]) -> object:
        """Build a fake /esp/fleet/registry message with given devices connected."""
        devices = [
            {
                "device_id": did,
                "route_state": "connected",
                "route": "connected",
            }
            for did in device_ids
        ]
        return _str_msg(json.dumps({"devices": devices}))

    def test_reconnect_reattach_stays_assigned(self):
        """MAP-06: device already in mapping stays 'assigned' after fleet registry update."""
        msg = self._fleet_msg([DEVICE_A])
        self.node._on_fleet_registry(msg)
        self.assertIn(DEVICE_A, self.node._store.assignments)
        self.assertEqual(self.node._store.assignments[DEVICE_A]["state"], "assigned")

    def test_new_device_from_fleet_registry_gets_unassigned(self):
        """MAP-06: new device appearing in fleet registry is registered as 'unassigned'."""
        self.assertNotIn(DEVICE_C, self.node._store.assignments)
        msg = self._fleet_msg([DEVICE_C])
        self.node._on_fleet_registry(msg)
        self.assertIn(DEVICE_C, self.node._store.assignments)
        self.assertEqual(self.node._store.assignments[DEVICE_C]["state"], "unassigned")


# ---------------------------------------------------------------------------
# MappingNodePublishTest — publish-on-change and get_mapping_state (MAP-04)
# ---------------------------------------------------------------------------

class MappingNodePublishTest(unittest.TestCase):
    """Tests for publish-on-change and GetMappingState service."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_node(self.tmp.name)
        self.node._on_catalog(_str_msg(_FAKE_CATALOG_JSON))

    def tearDown(self):
        self.tmp.cleanup()

    def test_publish_on_set_assignment(self):
        """MAP-04: _on_set_assignment triggers a publish to /rehab/mapping/current."""
        pub = self.node._current_publisher
        before = len(pub.messages)
        req = _set_assign_req(DEVICE_A, "", "", "unassigned")
        resp = _set_assign_resp()
        self.node._on_set_assignment(req, resp)
        self.assertGreater(len(pub.messages), before, "Expected at least one new published message")

    def test_get_mapping_state_returns_valid_json(self):
        """MAP-04: GetMappingState returns valid JSON with schema fields present."""
        req = _req()
        resp = _get_state_resp()
        result = self.node._on_get_mapping_state(req, resp)
        self.assertTrue(result.state_json, "state_json must be non-empty")
        parsed = json.loads(result.state_json)
        self.assertIn("model_hash", parsed)
        self.assertIn("revision", parsed)
        self.assertIn("applied_revision", parsed)
        self.assertIn("assignments", parsed)

    def test_recording_status_sets_interlock(self):
        """MAP-05: _on_recording_status parses 'active' field correctly."""
        self.node._on_recording_status(_str_msg(json.dumps({"active": True})))
        self.assertTrue(self.node._recording_active)
        self.node._on_recording_status(_str_msg(json.dumps({"active": False})))
        self.assertFalse(self.node._recording_active)

    def test_calibration_status_sets_interlock(self):
        """MAP-05: _on_calibration_status parses 'active' field correctly."""
        self.node._on_calibration_status(_str_msg(json.dumps({"active": True})))
        self.assertTrue(self.node._calibration_active)
        self.node._on_calibration_status(_str_msg(json.dumps({"active": False})))
        self.assertFalse(self.node._calibration_active)

    def test_recording_status_state_field_sets_interlock(self):
        """MAP-05: 'state=recording' in status message activates interlock."""
        self.node._on_recording_status(_str_msg(json.dumps({"active": False, "state": "recording"})))
        self.assertTrue(self.node._recording_active)

    def test_calibration_status_state_field_sets_interlock(self):
        """MAP-05: 'state=capturing' in calibration status activates interlock."""
        self.node._on_calibration_status(_str_msg(json.dumps({"active": False, "state": "capturing"})))
        self.assertTrue(self.node._calibration_active)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
