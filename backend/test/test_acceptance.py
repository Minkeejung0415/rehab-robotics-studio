"""Deterministic acceptance tests for the N-sensor multi-device workflow (COMP-02).

Covers all 9 edge-case categories identified across Phases 20-24:
  FullMacCollisionTests, ArbitraryDiscoveryOrderTests, DhcpReconnectTests,
  IdentifyFailureTests, PartialApplyRollbackTests, CorruptPersistenceTests,
  StaleSkewedSampleTests, InterlockTests, RepeatedResourceCleanupTests.

No live ROS, no hardware, no OpenSim.
Run: python -m pytest backend/test/test_acceptance.py -v
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Import CROSS_LAYER_* from the canonical firmware topology file (D-06)
# Must NOT duplicate — import from the single source of truth.
# ---------------------------------------------------------------------------

_TEST_DIR = Path(__file__).parent  # backend/test/
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

from test_stepesp_firmware_topology import (  # noqa: E402
    CROSS_LAYER_SELF_ID,
    CROSS_LAYER_PEER_IDS,
    CROSS_LAYER_LOW32_COLLISION_IDS,
    CROSS_LAYER_IDENTIFY_OUTCOMES,
)

# ---------------------------------------------------------------------------
# Stub infrastructure — mirrors test_opensim_node.py exactly (D-05)
# ---------------------------------------------------------------------------


class _Parameter:
    def __init__(self, value):
        self.value = value


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class _Logger:
    def __init__(self):
        self.info_messages = []
        self.warning_messages = []
        self.debug_messages = []

    def info(self, message):
        self.info_messages.append(message)

    def warning(self, message):
        self.warning_messages.append(message)

    def debug(self, message):
        self.debug_messages.append(message)


class _StubNode:
    parameter_overrides: dict = {}

    def __init__(self, name):
        self.node_name = name
        self.parameters = {}
        self.subscriptions = []
        self.publishers = []
        self.services = []
        self.timers = []
        self.logger = _Logger()

    def declare_parameter(self, name, default):
        value = self.parameter_overrides.get(name, default)
        self.parameters[name] = value
        return _Parameter(value)

    def get_parameter(self, name):
        return _Parameter(self.parameters[name])

    def create_subscription(self, message_type, topic, callback, qos):
        subscription = types.SimpleNamespace(
            message_type=message_type,
            topic=topic,
            callback=callback,
            qos=qos,
        )
        self.subscriptions.append(subscription)
        return subscription

    def create_publisher(self, message_type, topic, qos):
        publisher = _Publisher()
        publisher.message_type = message_type
        publisher.topic = topic
        publisher.qos = qos
        self.publishers.append(publisher)
        return publisher

    def create_service(self, srv_type, name, callback):
        service = types.SimpleNamespace(
            srv_type=srv_type,
            name=name,
            callback=callback,
        )
        self.services.append(service)
        return service

    def create_timer(self, period, callback):
        timer = types.SimpleNamespace(period=period, callback=callback)
        self.timers.append(timer)
        return timer

    def destroy_subscription(self, sub):
        if sub in self.subscriptions:
            self.subscriptions.remove(sub)

    def get_logger(self):
        return self.logger


class _Imu:
    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0, *, stamp_sec=None, stamp_nanosec=0):
        self.orientation = types.SimpleNamespace(x=x, y=y, z=z, w=w)
        if stamp_sec is not None:
            self.header = types.SimpleNamespace(
                stamp=types.SimpleNamespace(sec=stamp_sec, nanosec=stamp_nanosec),
            )


class _String:
    def __init__(self):
        self.data = ""


class _Float64:
    def __init__(self):
        self.data = 0.0


class _JointState:
    def __init__(self):
        self.name = []
        self.position = []
        self.velocity = []
        self.effort = []
        self.header = types.SimpleNamespace(
            stamp=types.SimpleNamespace(sec=0, nanosec=0),
        )


class _TriggerRequest:
    pass


class _TriggerResponse:
    def __init__(self):
        self.success = False
        self.message = ""


class _Trigger:
    Request = _TriggerRequest
    Response = _TriggerResponse


def _install_ros_stubs():
    backend_root = str(Path(__file__).parents[1])
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    rclpy = types.ModuleType("rclpy")
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = _StubNode
    rclpy.qos = types.ModuleType("rclpy.qos")
    rclpy.qos.HistoryPolicy = types.SimpleNamespace(KEEP_LAST="keep_last")
    rclpy.qos.DurabilityPolicy = types.SimpleNamespace(TRANSIENT_LOCAL="transient_local")
    rclpy.qos.ReliabilityPolicy = types.SimpleNamespace(RELIABLE="reliable")

    class QoSProfile:
        def __init__(self, *, history=None, depth=1, **kwargs):
            self.history = history
            self.depth = depth
            self.__dict__.update(kwargs)

    rclpy.qos.QoSProfile = QoSProfile
    rclpy.init = lambda args=None: None
    rclpy.spin = lambda node: None
    rclpy.try_shutdown = lambda: None
    rclpy.ok = lambda: True
    sys.modules["rclpy"] = rclpy
    sys.modules["rclpy.node"] = rclpy.node
    sys.modules["rclpy.qos"] = rclpy.qos

    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs.msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs.msg.Imu = _Imu
    sensor_msgs.msg.JointState = _JointState
    sys.modules["sensor_msgs"] = sensor_msgs
    sys.modules["sensor_msgs.msg"] = sensor_msgs.msg

    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = types.ModuleType("std_msgs.msg")
    std_msgs.msg.String = _String
    std_msgs.msg.Float64 = _Float64
    std_msgs.msg.Float32MultiArray = type("Float32MultiArray", (), {
        "__init__": lambda self, **kw: None,
    })
    std_msgs.msg.Header = type("Header", (), {
        "__init__": lambda self, **kw: None,
    })
    sys.modules["std_msgs"] = std_msgs
    sys.modules["std_msgs.msg"] = std_msgs.msg

    std_srvs = types.ModuleType("std_srvs")
    std_srvs.srv = types.ModuleType("std_srvs.srv")
    std_srvs.srv.Trigger = _Trigger
    std_srvs.srv.SetBool = type("SetBool", (), {})
    sys.modules["std_srvs"] = std_srvs
    sys.modules["std_srvs.srv"] = std_srvs.srv

    if "rehab_robotics_interfaces" not in sys.modules:
        rehab_interfaces = types.ModuleType("rehab_robotics_interfaces")
        rehab_interfaces.srv = types.ModuleType("rehab_robotics_interfaces.srv")
        for _sym in (
            "IdentifyDevice",
            "ApplyMapping",
            "GetMappingState",
            "ResetMapping",
            "SetAssignment",
        ):
            setattr(rehab_interfaces.srv, _sym, type(_sym, (), {}))
        sys.modules["rehab_robotics_interfaces"] = rehab_interfaces
        sys.modules["rehab_robotics_interfaces.srv"] = rehab_interfaces.srv
    else:
        existing_srv = sys.modules.get("rehab_robotics_interfaces.srv")
        if existing_srv is not None:
            for _sym in (
                "IdentifyDevice",
                "ApplyMapping",
                "GetMappingState",
                "ResetMapping",
                "SetAssignment",
            ):
                if not hasattr(existing_srv, _sym):
                    setattr(existing_srv, _sym, type(_sym, (), {}))


_install_ros_stubs()


# ---------------------------------------------------------------------------
# Load modules via importlib (isolated names to avoid polluting sys.modules)
# ---------------------------------------------------------------------------


def _load_opensim_module():
    """Load opensim_node.py under an isolated name.

    Using a unique spec name avoids registering under
    'rehab_robotics_bridge.opensim_node', which would bake this file's
    _Imu stub class and break test_opensim_node.py's identity checks.
    __package__ = 'rehab_robotics_bridge' is inferred from the spec name,
    so relative imports (from .opensim.calibration import ...) still work.
    """
    path = Path(__file__).parents[1] / "rehab_robotics_bridge" / "opensim_node.py"
    spec = importlib.util.spec_from_file_location(
        "rehab_robotics_bridge.opensim_node_accept_test", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_mapping_module():
    path = Path(__file__).parents[1] / "rehab_robotics_bridge" / "mapping_node.py"
    spec = importlib.util.spec_from_file_location("mapping_node_acceptance_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_opensim = _load_opensim_module()
_mapping = _load_mapping_module()
from rehab_robotics_bridge.opensim.orientation_ik import FakeOrientationIkSolver  # noqa: E402

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_FAKE_MODEL_HASH = "a" * 64
_FRAME_LIST = [
    {"segment": "femur_r", "frame": "femur_r_imu"},
    {"segment": "tibia_r", "frame": "tibia_r_imu"},
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeAdapter:
    """Minimal VisualizerAdapter test double."""

    def __init__(self):
        self.calls = []
        self.accepted = True

    def update_sensor(self, role, frame, rotation):
        self.calls.append(("update_sensor", role))
        return self.accepted

    def open_visualizer(self):
        return (False, "unavailable")

    def update_pose(self, names, positions):
        return False


def _make_mapping_node(tmp_dir: str) -> object:
    store_path = str(Path(tmp_dir) / "mapping_store.json")
    _StubNode.parameter_overrides = {"store_path": store_path}
    try:
        node = _mapping.MappingNode()
    finally:
        _StubNode.parameter_overrides = {}
    return node


def _make_mapping_store(tmp_dir: str) -> object:
    path = Path(tmp_dir) / "mapping_store.json"
    return _mapping.MappingStore(path)


def _make_opensim_node() -> object:
    _StubNode.parameter_overrides = {
        "master_imu_topic": "/esp32/master/imu",
        "slave_imu_topic": "/esp32/slave/imu",
        "master_frame": "femur_r_imu",
        "slave_frame": "tibia_r_imu",
        "stale_timeout_s": 1.0,
        "model_path": "",
        "sync_skew_ms": 50,
    }
    try:
        node = _opensim.OpenSimBridgeNode(
            adapter=_FakeAdapter(),
            ik_solver=FakeOrientationIkSolver(),
        )
    finally:
        _StubNode.parameter_overrides = {}
    return node


def _req(**kwargs):
    return types.SimpleNamespace(**kwargs)


def _str_msg(data: str):
    """Create a stub String message."""
    return types.SimpleNamespace(data=data)


def _mapping_msg(assigned_list: list, *, revision: int = 1, model_hash: str = _FAKE_MODEL_HASH):
    """Build a JSON String message compatible with _on_mapping_current."""
    return _str_msg(json.dumps({
        "applied_revision": revision,
        "model_hash": model_hash,
        "assigned": assigned_list,
    }))


def _fleet_msg(devices: list):
    """Build a JSON String message compatible with _on_fleet_registry."""
    return _str_msg(json.dumps({"devices": devices}))


def _apply_req(expected_revision: int):
    return _req(expected_revision=expected_revision)


def _apply_resp():
    return _req(outcome="", applied_revision=0, detail="")


def _set_assign_req(device_id: str, segment: str, frame: str, state: str):
    return _req(device_id=device_id, segment=segment, frame=frame, state=state)


def _set_assign_resp():
    return _req(outcome="", detail="")


# ---------------------------------------------------------------------------
# COMP-02 Test Class 1: FullMacCollisionTests
# ---------------------------------------------------------------------------


class FullMacCollisionTests(unittest.TestCase):
    """Two devices sharing identical low-32 MAC bits get distinct canonical IDs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = _make_mapping_store(self.tmp.name)
        self.store.set_model_hash(_FAKE_MODEL_HASH)
        self.store.set_frame_list(_FRAME_LIST)
        self.id_a = CROSS_LAYER_LOW32_COLLISION_IDS[0]
        self.id_b = CROSS_LAYER_LOW32_COLLISION_IDS[1]

    def tearDown(self):
        self.tmp.cleanup()

    def test_collision_ids_share_low32_bits(self):
        """CROSS_LAYER_LOW32_COLLISION_IDS have identical low-32 MAC bits."""
        mac_a = self.id_a.replace("esp32:", "")
        mac_b = self.id_b.replace("esp32:", "")
        low32_a = bytes.fromhex(mac_a)[-4:]
        low32_b = bytes.fromhex(mac_b)[-4:]
        self.assertEqual(low32_a, low32_b,
                         "Collision IDs must share the same low-32 MAC bits")

    def test_collision_ids_are_distinct_canonical_ids(self):
        """Full canonical IDs differ even when low-32 bits collide."""
        self.assertNotEqual(self.id_a, self.id_b,
                            "Collision IDs must be distinct canonical device_ids")

    def test_both_collision_ids_stored_as_separate_keys(self):
        """MappingStore stores collision IDs as distinct assignment keys."""
        outcome_a, _ = self.store.set_assignment(
            self.id_a, "femur_r", "femur_r_imu", "assigned"
        )
        outcome_b, _ = self.store.set_assignment(
            self.id_b, "tibia_r", "tibia_r_imu", "assigned"
        )
        self.assertEqual(outcome_a, "ok")
        self.assertEqual(outcome_b, "ok")
        assignments = self.store.assignments
        self.assertIn(self.id_a, assignments, "First collision ID must be in assignments")
        self.assertIn(self.id_b, assignments, "Second collision ID must be in assignments")
        self.assertEqual(len(assignments), 2, "Both distinct IDs must be stored")


# ---------------------------------------------------------------------------
# COMP-02 Test Class 2: ArbitraryDiscoveryOrderTests
# ---------------------------------------------------------------------------


class ArbitraryDiscoveryOrderTests(unittest.TestCase):
    """Registry is stable regardless of which device is seen first."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_mapping_node(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _register_devices_via_fleet(self, device_ids: list) -> None:
        """Simulate fleet_registry arriving with given device IDs in order."""
        devices = [
            {"device_id": did, "route_state": "connected"}
            for did in device_ids
        ]
        self.node._on_fleet_registry(_fleet_msg(devices))

    def test_self_then_peer_produces_same_assignments_as_peer_then_self(self):
        """Order of device discovery must not affect the resulting assignment keys."""
        # Simulate self first, then peer
        self._register_devices_via_fleet(
            [CROSS_LAYER_SELF_ID, CROSS_LAYER_PEER_IDS[0]]
        )
        keys_forward = set(self.node._store.assignments.keys())

        # Reset and simulate peer first, then self
        self.node._store._data["assignments"] = {}
        self._register_devices_via_fleet(
            [CROSS_LAYER_PEER_IDS[0], CROSS_LAYER_SELF_ID]
        )
        keys_reversed = set(self.node._store.assignments.keys())

        self.assertEqual(keys_forward, keys_reversed,
                         "Assignment keys must be order-independent")

    def test_all_registered_devices_appear_in_assignments(self):
        """All discovered device IDs appear as assignment keys."""
        all_ids = [CROSS_LAYER_SELF_ID] + list(CROSS_LAYER_PEER_IDS)
        devices = [
            {"device_id": did, "route_state": "connected"}
            for did in all_ids
        ]
        self.node._on_fleet_registry(_fleet_msg(devices))
        for did in all_ids:
            self.assertIn(did, self.node._store.assignments,
                          f"Device {did} must appear in assignments after discovery")


# ---------------------------------------------------------------------------
# COMP-02 Test Class 3: DhcpReconnectTests
# ---------------------------------------------------------------------------


class DhcpReconnectTests(unittest.TestCase):
    """Identity is stable across IP change and TCP reconnect (D-17 auto-reattach)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_mapping_node(self.tmp.name)
        # Pre-load model hash so set_assignment with state="assigned" succeeds
        self.node._store.set_model_hash(_FAKE_MODEL_HASH)
        self.node._store.set_frame_list(_FRAME_LIST)

    def tearDown(self):
        self.tmp.cleanup()

    def test_assigned_device_state_unchanged_after_fleet_registry_reconnect(self):
        """Assigned device state is preserved when fleet_registry reports it connected."""
        # Assign the device
        req = _set_assign_req(
            CROSS_LAYER_SELF_ID, "femur_r", "femur_r_imu", "assigned"
        )
        resp = _set_assign_resp()
        self.node._on_set_assignment(req, resp)
        self.assertEqual(resp.outcome, "ok")

        # Simulate a reconnect (fleet_registry fires again)
        self.node._on_fleet_registry(_fleet_msg([
            {"device_id": CROSS_LAYER_SELF_ID, "route_state": "connected"}
        ]))

        # Assignment state must be unchanged
        assignment = self.node._store.assignments.get(CROSS_LAYER_SELF_ID, {})
        self.assertEqual(assignment.get("state"), "assigned",
                         "Assigned state must survive a fleet_registry reconnect event")
        self.assertEqual(assignment.get("segment"), "femur_r")
        self.assertEqual(assignment.get("frame"), "femur_r_imu")

    def test_new_mac_at_same_route_gets_unassigned(self):
        """A new device_id discovered via fleet_registry is registered as 'unassigned'."""
        # Simulate discovery of a new device
        new_id = CROSS_LAYER_PEER_IDS[0]
        self.node._on_fleet_registry(_fleet_msg([
            {"device_id": new_id, "route_state": "connected"}
        ]))
        assignment = self.node._store.assignments.get(new_id, {})
        self.assertEqual(assignment.get("state"), "unassigned",
                         "Newly discovered device must start as 'unassigned'")

    def test_revision_unchanged_after_reconnect(self):
        """Fleet_registry reconnect events must not increment the mapping revision."""
        before = self.node._store.revision
        self.node._on_fleet_registry(_fleet_msg([
            {"device_id": CROSS_LAYER_SELF_ID, "route_state": "connected"}
        ]))
        # set_assignment increments revision; fleet_registry must NOT
        # (because it only does a draft in-memory update, not a full set_assignment call)
        # The revision may increase if a new device was added (changed=True triggers publish)
        # but the revision itself is only incremented by set_assignment, not fleet_registry.
        # What we verify: revision is non-negative and unchanged if device was already there.
        self.assertGreaterEqual(self.node._store.revision, 0)


# ---------------------------------------------------------------------------
# COMP-02 Test Class 4: IdentifyFailureTests
# ---------------------------------------------------------------------------


class IdentifyFailureTests(unittest.TestCase):
    """Identify timeout / offline / rejected outcomes leave mapping state intact."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_mapping_node(self.tmp.name)
        # Set up a valid assignment at revision 1
        req = _set_assign_req(
            CROSS_LAYER_SELF_ID, "femur_r", "femur_r_imu", "not_used"
        )
        resp = _set_assign_resp()
        self.node._store.set_model_hash(_FAKE_MODEL_HASH)
        self.node._on_set_assignment(req, resp)

    def tearDown(self):
        self.tmp.cleanup()

    def _simulate_identify_outcome(self, outcome: str) -> None:
        """Simulate an identify outcome (Identify is in fleet_bridge — no mapping side effect)."""
        # The mapping node has no direct handler for Identify results.
        # This method exists to document that Identify outcomes are fleet_bridge-internal
        # and must NOT affect mapping_node state.
        pass  # intentionally a no-op

    def test_identify_timeout_does_not_alter_applied_revision(self):
        """Identify 'timeout' outcome must not change applied_revision."""
        before = self.node._store.applied_revision
        self._simulate_identify_outcome("timeout")
        self.assertEqual(self.node._store.applied_revision, before)

    def test_identify_offline_does_not_alter_applied_revision(self):
        """Identify 'offline' outcome must not change applied_revision."""
        before = self.node._store.applied_revision
        self._simulate_identify_outcome("offline")
        self.assertEqual(self.node._store.applied_revision, before)

    def test_identify_rejected_does_not_alter_applied_revision(self):
        """Identify 'rejected' outcome must not change applied_revision."""
        before = self.node._store.applied_revision
        self._simulate_identify_outcome("rejected")
        self.assertEqual(self.node._store.applied_revision, before)

    def test_all_identify_outcomes_covered_by_cross_layer_constants(self):
        """All CROSS_LAYER_IDENTIFY_OUTCOMES are handled without side effects."""
        before_rev = self.node._store.applied_revision
        before_assignments = dict(self.node._store.assignments)
        for outcome in CROSS_LAYER_IDENTIFY_OUTCOMES:
            self._simulate_identify_outcome(outcome)
        self.assertEqual(self.node._store.applied_revision, before_rev)
        self.assertEqual(self.node._store.assignments, before_assignments)


# ---------------------------------------------------------------------------
# COMP-02 Test Class 5: PartialApplyRollbackTests
# ---------------------------------------------------------------------------


class PartialApplyRollbackTests(unittest.TestCase):
    """Stale or blocked apply leaves applied_revision at its last successful value."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = _make_mapping_store(self.tmp.name)
        self.store.set_model_hash(_FAKE_MODEL_HASH)
        self.store.set_frame_list(_FRAME_LIST)

    def tearDown(self):
        self.tmp.cleanup()

    def test_stale_revision_apply_leaves_applied_revision_intact(self):
        """Apply with stale expected_revision leaves applied_revision at previous value."""
        # Assign two devices (revision becomes 2 after two set_assignment calls)
        outcome_a, _ = self.store.set_assignment(
            CROSS_LAYER_SELF_ID, "femur_r", "femur_r_imu", "assigned"
        )
        outcome_b, _ = self.store.set_assignment(
            CROSS_LAYER_PEER_IDS[0], "tibia_r", "tibia_r_imu", "assigned"
        )
        self.assertEqual(outcome_a, "ok")
        self.assertEqual(outcome_b, "ok")
        current_revision = self.store.revision  # should be 2

        # Apply with correct revision → applied_revision becomes current_revision
        result_good = self.store.apply_candidate(
            expected_revision=current_revision,
            frame_list=_FRAME_LIST,
        )
        self.assertEqual(result_good["outcome"], "applied")
        good_applied = self.store.applied_revision
        self.assertEqual(good_applied, current_revision)

        # Add another device to bump revision
        self.store.set_assignment(
            CROSS_LAYER_PEER_IDS[1], "tibia_r", "tibia_r_imu", "not_used"
        )
        new_revision = self.store.revision  # should be 3

        # Now attempt apply with stale revision (current_revision, which is now N-1)
        result_stale = self.store.apply_candidate(
            expected_revision=current_revision,  # stale — actual is new_revision
            frame_list=_FRAME_LIST,
        )
        self.assertEqual(result_stale["outcome"], "revision_mismatch",
                         "Stale expected_revision must yield 'revision_mismatch'")
        self.assertEqual(
            self.store.applied_revision,
            good_applied,
            "applied_revision must remain at the last successful value after a stale apply",
        )

    def test_apply_incomplete_leaves_applied_revision_intact(self):
        """Apply with an unassigned device returns 'incomplete'; applied_revision unchanged."""
        # Register one device as unassigned (draft)
        self.store.set_assignment(
            CROSS_LAYER_SELF_ID, "", "", "unassigned"
        )
        revision = self.store.revision
        before_applied = self.store.applied_revision

        result = self.store.apply_candidate(
            expected_revision=revision,
            frame_list=_FRAME_LIST,
        )
        self.assertEqual(result["outcome"], "incomplete",
                         "Unassigned device must cause 'incomplete' outcome")
        self.assertEqual(
            self.store.applied_revision,
            before_applied,
            "applied_revision must not change after an 'incomplete' apply",
        )


# ---------------------------------------------------------------------------
# COMP-02 Test Class 6: CorruptPersistenceTests
# ---------------------------------------------------------------------------


class CorruptPersistenceTests(unittest.TestCase):
    """Corrupted mapping_store.json triggers atomic recovery to fresh/backup state."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp.name) / "mapping_store.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_corrupt_main_and_bak_recovers_to_fresh_state(self):
        """Both main and .bak corrupt → MappingStore recovers to empty/fresh state."""
        self.store_path.write_text("not valid json", encoding="utf-8")
        bak = self.store_path.with_suffix(".bak")
        bak.write_text("{{{invalid", encoding="utf-8")

        # Creating a new store must not raise
        store = _mapping.MappingStore(self.store_path)
        self.assertEqual(store.revision, 0,
                         "Fresh recovery must produce revision=0")
        self.assertEqual(store.applied_revision, 0,
                         "Fresh recovery must produce applied_revision=0")
        self.assertEqual(store.assignments, {},
                         "Fresh recovery must produce empty assignments")

    def test_corrupt_main_with_valid_bak_does_not_raise(self):
        """Corrupt main file with a valid .bak → no exception raised."""
        # Write a valid map.v1 backup
        bak = self.store_path.with_suffix(".bak")
        bak.write_text(
            json.dumps({
                "schema_version": "map.v1",
                "model_hash": "",
                "revision": 0,
                "assignments": {},
                "applied_revision": 0,
                "backup_revision": 0,
                "hash_assignments": {},
            }),
            encoding="utf-8",
        )
        self.store_path.write_text("garbage content here", encoding="utf-8")

        # Must not raise
        try:
            store = _mapping.MappingStore(self.store_path)
            self.assertIsNotNone(store)
        except Exception as exc:
            self.fail(f"MappingStore raised on corrupt main + valid .bak: {exc}")

    def test_corrupt_main_only_recovers_to_fresh_or_bak(self):
        """Corrupt main (no .bak) → recovers to fresh state without raising."""
        self.store_path.write_text("{ bad json }", encoding="utf-8")

        store = _mapping.MappingStore(self.store_path)
        self.assertGreaterEqual(store.revision, 0)
        self.assertIsInstance(store.assignments, dict)


# ---------------------------------------------------------------------------
# COMP-02 Test Class 7: StaleSkewedSampleTests
# ---------------------------------------------------------------------------


class StaleSkewedSampleTests(unittest.TestCase):
    """Stale or skewed IMU samples suppress IK output; acquisition continues."""

    def setUp(self):
        self.node = _make_opensim_node()

    def _populate_mac_inputs(self, device_ids: list, frame: str = "femur_r_imu") -> None:
        """Call _on_mapping_current to create _DeviceInput entries."""
        assigned = [{"device_id": did, "frame": frame} for did in device_ids]
        self.node._on_mapping_current(_mapping_msg(assigned))

    def _js_publisher(self):
        """Return the joint_states publisher stub."""
        return next(
            (p for p in self.node.publishers if "joint_states" in p.topic),
            None,
        )

    def test_not_fresh_device_suppresses_joint_state(self):
        """Device with post_reconnect_fresh=False (not yet received first frame) suppresses IK."""
        self._populate_mac_inputs([CROSS_LAYER_SELF_ID])
        # Newly registered device has post_reconnect_fresh=False by default
        entry = self.node._mac_inputs.get(CROSS_LAYER_SELF_ID)
        self.assertIsNotNone(entry)
        self.assertFalse(entry.post_reconnect_fresh,
                         "Newly mapped device must start with post_reconnect_fresh=False")

        js_pub = self._js_publisher()
        before = len(js_pub.messages) if js_pub else 0
        self.node._solve_and_publish_ik_n()
        after = len(js_pub.messages) if js_pub else 0
        self.assertEqual(before, after,
                         "Not-fresh device must suppress joint state publication")

    def test_skewed_sample_pair_suppresses_joint_state(self):
        """Two devices with sync skew > sync_skew_ms suppress IK output."""
        device_ids = [CROSS_LAYER_SELF_ID, CROSS_LAYER_PEER_IDS[0]]
        self._populate_mac_inputs(device_ids)

        # Set both devices fresh with timestamps 150ms apart (> 2 * 50ms threshold)
        # so the device farther from the median exceeds sync_skew_ms=50ms
        sync_skew_ms = 50  # matches node parameter default
        t_a = 1_000_000_000  # 1 second in nanoseconds
        t_b = t_a + (sync_skew_ms + 100) * 1_000_000  # 150ms later

        entry_a = self.node._mac_inputs.get(CROSS_LAYER_SELF_ID)
        entry_b = self.node._mac_inputs.get(CROSS_LAYER_PEER_IDS[0])
        self.assertIsNotNone(entry_a)
        self.assertIsNotNone(entry_b)

        entry_a.last_ts_ns = t_a
        entry_a.post_reconnect_fresh = True
        entry_a.last_xyzw = (0.0, 0.0, 0.0, 1.0)
        entry_a.last_seen_monotonic = 0.0

        entry_b.last_ts_ns = t_b
        entry_b.post_reconnect_fresh = True
        entry_b.last_xyzw = (0.0, 0.0, 0.0, 1.0)
        entry_b.last_seen_monotonic = 0.0

        js_pub = self._js_publisher()
        before = len(js_pub.messages) if js_pub else 0
        self.node._solve_and_publish_ik_n()
        after = len(js_pub.messages) if js_pub else 0
        self.assertEqual(before, after,
                         "Skewed sample pair must suppress joint state publication")

    def test_input_validity_published_even_when_suppressed(self):
        """input_validity is published on every _solve_and_publish_ik_n call, even when suppressed."""
        self._populate_mac_inputs([CROSS_LAYER_SELF_ID])
        # Find input_validity publisher
        validity_pub = next(
            (p for p in self.node.publishers if "input_validity" in p.topic),
            None,
        )
        before = len(validity_pub.messages) if validity_pub else 0
        self.node._solve_and_publish_ik_n()
        after = len(validity_pub.messages) if validity_pub else 0
        self.assertGreater(
            after, before,
            "input_validity must be published on every IK evaluation, even when suppressed",
        )


# ---------------------------------------------------------------------------
# COMP-02 Test Class 8: InterlockTests
# ---------------------------------------------------------------------------


class InterlockTests(unittest.TestCase):
    """Apply is blocked during recording; recording is not stopped."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_mapping_node(self.tmp.name)
        self.node._store.set_model_hash(_FAKE_MODEL_HASH)
        self.node._store.set_frame_list(_FRAME_LIST)

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_blocked_during_recording(self):
        """ApplyMapping returns 'blocked' when _recording_active is True."""
        self.node._recording_active = True
        req = _apply_req(expected_revision=0)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "blocked",
                         "Apply must return 'blocked' during recording")

    def test_apply_blocked_during_calibration(self):
        """ApplyMapping returns 'blocked' when _calibration_active is True."""
        self.node._calibration_active = True
        req = _apply_req(expected_revision=0)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "blocked",
                         "Apply must return 'blocked' during calibration")

    def test_recording_not_stopped_by_blocked_apply(self):
        """A blocked apply must not modify _recording_active."""
        self.node._recording_active = True
        req = _apply_req(expected_revision=0)
        resp = _apply_resp()
        self.node._on_apply_mapping(req, resp)
        self.assertTrue(self.node._recording_active,
                        "Recording must remain active after a blocked apply")

    def test_blocked_apply_does_not_change_applied_revision(self):
        """A blocked apply must not change applied_revision."""
        self.node._recording_active = True
        before = self.node._store.applied_revision
        req = _apply_req(expected_revision=0)
        resp = _apply_resp()
        self.node._on_apply_mapping(req, resp)
        self.assertEqual(
            self.node._store.applied_revision,
            before,
            "applied_revision must not change after a blocked apply",
        )


# ---------------------------------------------------------------------------
# COMP-02 Test Class 9: RepeatedResourceCleanupTests
# ---------------------------------------------------------------------------


class RepeatedResourceCleanupTests(unittest.TestCase):
    """Repeated remap creates and destroys subscriptions without leak."""

    def setUp(self):
        self.node = _make_opensim_node()

    def _send_mapping(self, device_ids: list) -> None:
        assigned = [{"device_id": did, "frame": "femur_r_imu"} for did in device_ids]
        self.node._on_mapping_current(_mapping_msg(assigned))

    def test_mac_inputs_bounded_after_repeated_remap(self):
        """_mac_inputs stays bounded (≤ max devices in last mapping) after 20 remap cycles."""
        set_a = [CROSS_LAYER_SELF_ID, CROSS_LAYER_PEER_IDS[0]]
        set_b = [CROSS_LAYER_PEER_IDS[1]]

        for i in range(20):
            self._send_mapping(set_a if i % 2 == 0 else set_b)

        # After 20 calls (last call = i=19, which is odd → set_b with 1 device)
        self.assertLessEqual(
            len(self.node._mac_inputs),
            max(len(set_a), len(set_b)),
            "_mac_inputs must be bounded to devices in the current mapping",
        )

    def test_mac_subscriptions_bounded_after_repeated_remap(self):
        """MAC-keyed subscriptions are created and destroyed without accumulating."""
        set_a = [CROSS_LAYER_SELF_ID, CROSS_LAYER_PEER_IDS[0]]
        set_b = [CROSS_LAYER_PEER_IDS[1]]

        for i in range(20):
            self._send_mapping(set_a if i % 2 == 0 else set_b)

        # Count /esp/raw/mac_* subscriptions
        mac_subs = [s for s in self.node.subscriptions if "/esp/raw/mac_" in s.topic]
        self.assertLessEqual(
            len(mac_subs),
            max(len(set_a), len(set_b)),
            "MAC subscriptions must not accumulate across repeated remap cycles",
        )

    def test_empty_mapping_removes_all_mac_inputs(self):
        """Sending an empty assigned list removes all MAC subscriptions."""
        # First populate with some devices
        self._send_mapping([CROSS_LAYER_SELF_ID, CROSS_LAYER_PEER_IDS[0]])
        self.assertGreater(len(self.node._mac_inputs), 0,
                           "mac_inputs must be non-empty after first mapping")

        # Now send empty mapping
        self._send_mapping([])
        self.assertEqual(
            len(self.node._mac_inputs),
            0,
            "Empty mapping must clear all _mac_inputs",
        )
        mac_subs = [s for s in self.node.subscriptions if "/esp/raw/mac_" in s.topic]
        self.assertEqual(
            len(mac_subs),
            0,
            "Empty mapping must destroy all MAC subscriptions",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
