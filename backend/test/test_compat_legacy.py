"""Offline compatibility tests for the legacy two-sensor workflow (COMP-01).

Proves use_fleet_bridge=false contracts remain intact after Phases 20-24.
Run: python -m pytest backend/test/test_compat_legacy.py -v
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
# Stub infrastructure — verbatim copy from test_opensim_node.py
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
    parameter_overrides = {}

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
    def __init__(
        self,
        x=0.0,
        y=0.0,
        z=0.0,
        w=1.0,
        *,
        stamp_sec=None,
        stamp_nanosec=0,
    ):
        self.orientation = types.SimpleNamespace(x=x, y=y, z=z, w=w)
        if stamp_sec is not None:
            self.header = types.SimpleNamespace(
                stamp=types.SimpleNamespace(
                    sec=stamp_sec,
                    nanosec=stamp_nanosec,
                ),
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

    class QoSProfile:
        def __init__(self, *, history, depth):
            self.history = history
            self.depth = depth

    rclpy.qos.QoSProfile = QoSProfile
    rclpy.init = lambda args=None: None
    rclpy.spin = lambda node: None
    rclpy.try_shutdown = lambda: None
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

from rehab_robotics_bridge import opensim_node  # noqa: E402
from rehab_robotics_bridge.opensim.orientation_ik import FakeOrientationIkSolver  # noqa: E402


# ---------------------------------------------------------------------------
# Load mapping_node via importlib (avoids double-import conflicts)
# ---------------------------------------------------------------------------

def _load_mapping_module():
    path = Path(__file__).parents[1] / "rehab_robotics_bridge" / "mapping_node.py"
    spec = importlib.util.spec_from_file_location("mapping_node_legacy_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Register before exec so circular-import lookups find it
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_mapping = _load_mapping_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeAdapter:
    """Minimal VisualizerAdapter test double for legacy tests."""

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


def _make_opensim_node():
    """Instantiate OpenSimBridgeNode with legacy (use_fleet_bridge=false) constructor args."""
    _StubNode.parameter_overrides = {
        "master_imu_topic": "/esp32/master/imu",
        "slave_imu_topic": "/esp32/slave/imu",
        "master_frame": "femur_r_imu",
        "slave_frame": "tibia_r_imu",
        "stale_timeout_s": 1.0,
        "model_path": "",
    }
    try:
        node = opensim_node.OpenSimBridgeNode(
            adapter=_FakeAdapter(),
            ik_solver=FakeOrientationIkSolver(),
        )
    finally:
        _StubNode.parameter_overrides = {}
    return node


def _make_mapping_node(tmp_dir: str) -> object:
    """Instantiate MappingNode with a temp store_path."""
    store_path = str(Path(tmp_dir) / "mapping_store.json")
    _StubNode.parameter_overrides = {"store_path": store_path}
    try:
        node = _mapping.MappingNode()
    finally:
        _StubNode.parameter_overrides = {}
    return node


def _imu(*, w=1.0, stamp_sec=None):
    """Create a stub _Imu with the given orientation."""
    return _Imu(x=0.0, y=0.0, z=0.0, w=w, stamp_sec=stamp_sec)


def _req(**kwargs):
    return types.SimpleNamespace(**kwargs)


def _apply_req(expected_revision: int):
    return _req(expected_revision=expected_revision)


def _apply_resp():
    return _req(outcome="", applied_revision=0, detail="")


# ---------------------------------------------------------------------------
# LegacyStartupTest
# ---------------------------------------------------------------------------

class LegacyStartupTest(unittest.TestCase):
    """COMP-01: node initialises correctly with legacy fixed topics."""

    def setUp(self):
        self.node = _make_opensim_node()

    def test_node_creates_master_slave_subscriptions(self):
        """Legacy startup: both master and slave IMU topics are subscribed."""
        topics = {s.topic for s in self.node.subscriptions}
        self.assertIn("/esp32/master/imu", topics,
                      "Master IMU topic must be subscribed in legacy mode")
        self.assertIn("/esp32/slave/imu", topics,
                      "Slave IMU topic must be subscribed in legacy mode")

    def test_mac_inputs_empty_in_legacy_mode(self):
        """_mac_inputs starts empty — no dynamic mapping in legacy mode."""
        self.assertEqual(
            len(self.node._mac_inputs),
            0,
            "_mac_inputs must be empty in legacy mode (no fleet mapping)",
        )


# ---------------------------------------------------------------------------
# LegacyJointStateTest
# ---------------------------------------------------------------------------

class LegacyJointStateTest(unittest.TestCase):
    """COMP-01: IMU callbacks activate sensor states in the legacy solve path."""

    def setUp(self):
        self.node = _make_opensim_node()

    def test_valid_imu_pair_activates_sensor_states(self):
        """Valid master + slave Imu transitions both sensors to 'live'."""
        self.node._on_master_imu(_imu(w=1.0, stamp_sec=1000))
        self.node._on_slave_imu(_imu(w=1.0, stamp_sec=1000))
        self.assertEqual(
            self.node._sensor_states["master"].state,
            "live",
            "Master sensor must be 'live' after valid IMU injection",
        )
        self.assertEqual(
            self.node._sensor_states["slave"].state,
            "live",
            "Slave sensor must be 'live' after valid IMU injection",
        )
        self.assertIsNotNone(
            self.node._sensor_states["master"].last_xyzw,
            "master last_xyzw must be set after valid IMU",
        )

    def test_stale_master_suppresses_dual_imu_solve(self):
        """Stale master sensor must suppress the dual-IMU solve path."""
        # Inject slave into live state
        self.node._on_slave_imu(_imu(w=1.0, stamp_sec=1000))
        self.node._sensor_states["slave"].state = "live"
        # Force master into stale state
        self.node._sensor_states["master"].state = "stale"
        # Record the current joint_states publisher message count
        js_pub = next(
            (p for p in self.node.publishers if "joint_states" in p.topic),
            None,
        )
        before = len(js_pub.messages) if js_pub else 0
        # Trigger solve
        self.node._solve_and_publish_ik()
        after = len(js_pub.messages) if js_pub else 0
        self.assertEqual(
            before, after,
            "Stale master sensor must suppress joint state publication",
        )


# ---------------------------------------------------------------------------
# LegacyCalibrationTest
# ---------------------------------------------------------------------------

class LegacyCalibrationTest(unittest.TestCase):
    """COMP-01: calibration service callbacks behave safely in legacy mode."""

    def setUp(self):
        self.node = _make_opensim_node()

    def test_calibrate_trigger_does_not_raise(self):
        """Calling the legacy calibration capture callback must not raise."""
        self.node._on_master_imu(_imu(w=1.0, stamp_sec=1000))
        self.node._on_slave_imu(_imu(w=1.0, stamp_sec=1000))
        req = _TriggerRequest()
        resp = _TriggerResponse()
        try:
            result = self.node._on_calibration_capture(req, resp)
            self.assertIsNotNone(result)
            self.assertIsInstance(result.success, bool)
        except Exception as exc:
            self.fail(f"_on_calibration_capture raised unexpectedly: {exc}")

    def test_n_sensor_capture_returns_no_mapping_in_legacy_mode(self):
        """N-sensor calibration capture must return 'no_mapping' when _mac_inputs is empty."""
        req = _TriggerRequest()
        resp = _TriggerResponse()
        result = self.node._on_calibration_capture_n(req, resp)
        self.assertFalse(result.success)
        self.assertIn(
            "no_mapping",
            result.message,
            "N-sensor capture must indicate no_mapping when _mac_inputs is empty",
        )


# ---------------------------------------------------------------------------
# LegacyRecordingInterlockTest
# ---------------------------------------------------------------------------

class LegacyRecordingInterlockTest(unittest.TestCase):
    """COMP-01: MappingNode apply interlock during recording is intact."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = _make_mapping_node(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_blocked_during_recording(self):
        """ApplyMapping returns 'blocked' with 'recording' in detail when recording is active."""
        self.node._recording_active = True
        req = _apply_req(expected_revision=0)
        resp = _apply_resp()
        result = self.node._on_apply_mapping(req, resp)
        self.assertEqual(result.outcome, "blocked",
                         "Apply must be blocked during recording")
        self.assertIn("recording", result.detail,
                      "blocked detail must mention 'recording'")

    def test_recording_not_stopped_by_blocked_apply(self):
        """A blocked apply must leave _recording_active unchanged (True)."""
        self.node._recording_active = True
        req = _apply_req(expected_revision=0)
        resp = _apply_resp()
        self.node._on_apply_mapping(req, resp)
        self.assertTrue(self.node._recording_active,
                        "Recording must still be active after a blocked apply")


# ---------------------------------------------------------------------------
# LegacyAliasTopicTest
# ---------------------------------------------------------------------------

class LegacyAliasTopicTest(unittest.TestCase):
    """COMP-01: legacy alias topics (/esp32/master/imu, /esp32/slave/imu) are subscribed."""

    def setUp(self):
        self.node = _make_opensim_node()

    def test_master_alias_topic_is_slash_esp32_master_imu(self):
        """Master alias topic must be '/esp32/master/imu' in legacy mode."""
        topics = {s.topic for s in self.node.subscriptions}
        self.assertIn("/esp32/master/imu", topics)

    def test_slave_alias_topic_is_slash_esp32_slave_imu(self):
        """Slave alias topic must be '/esp32/slave/imu' in legacy mode."""
        topics = {s.topic for s in self.node.subscriptions}
        self.assertIn("/esp32/slave/imu", topics)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
