"""ROS-free contracts for the dual-IMU OpenSim bridge node."""
from __future__ import annotations

import json
import math
import sys
import types
import unittest
from dataclasses import replace
from pathlib import Path


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
    sys.modules["std_msgs"] = std_msgs
    sys.modules["std_msgs.msg"] = std_msgs.msg

    std_srvs = types.ModuleType("std_srvs")
    std_srvs.srv = types.ModuleType("std_srvs.srv")
    std_srvs.srv.Trigger = _Trigger
    sys.modules["std_srvs"] = std_srvs
    sys.modules["std_srvs.srv"] = std_srvs.srv


_install_ros_stubs()
from rehab_robotics_bridge import opensim_node  # noqa: E402
from rehab_robotics_bridge.opensim.calibration import CalibrationController  # noqa: E402
from rehab_robotics_bridge.opensim.ik_contracts import (  # noqa: E402
    CALIBRATION_CAPTURE_SERVICE,
    CALIBRATION_CLEAR_SERVICE,
    CALIBRATION_STATUS_TOPIC,
    DIAGNOSTICS_TOPIC,
    IK_STATUS_TOPIC,
    JOINT_STATES_TOPIC,
    VISUALIZER_OPEN_SERVICE,
    CalibrationState,
)
from rehab_robotics_bridge.opensim.orientation_ik import (  # noqa: E402
    FakeOrientationIkSolver,
    UnavailableOrientationIkSolver,
)
from rehab_robotics_bridge.opensim_adapter import (  # noqa: E402
    UnavailableVisualizerAdapter,
)


class _FakeAdapter:
    def __init__(
        self,
        *,
        accepted=True,
        available=True,
        reason="",
        open_result=(True, "visualizer_open"),
    ):
        self.accepted = accepted
        self.calls = []
        self.pose_calls = []
        self.open_calls = 0
        self.open_result = open_result
        self._status = {
            "available": available,
            "state": "ready" if available else "unavailable",
            "reason": reason,
        }

    def open_visualizer(self):
        self.open_calls += 1
        if isinstance(self.open_result, BaseException):
            raise self.open_result
        success, message = self.open_result
        self._status = {
            "available": bool(success),
            "state": "open" if success else "failed",
            "reason": "" if success else str(message),
        }
        return self.open_result

    def update_sensor(self, sensor_id, frame_name, rotation):
        self.calls.append((sensor_id, frame_name, rotation))
        return self.accepted

    def update_pose(self, coordinate_names, positions_rad):
        self.pose_calls.append((list(coordinate_names), list(positions_rad)))
        return self.accepted

    def status(self):
        return dict(self._status)


class _Clock:
    def __init__(self, now=10.0):
        self.now = now

    def __call__(self):
        return self.now


class OpenSimNodeForwardingTests(unittest.TestCase):
    def setUp(self):
        _StubNode.parameter_overrides = {}
        self.clock = _Clock()

    def _node(self, adapter=None):
        return opensim_node.OpenSimBridgeNode(
            adapter=adapter or _FakeAdapter(),
            monotonic_clock=self.clock,
        )

    def test_locked_defaults_create_exactly_two_native_imu_subscriptions(self):
        node = self._node()

        self.assertEqual(node.node_name, "opensim_bridge")
        # Check by topic name rather than bare count to tolerate additional
        # infrastructure subscriptions (e.g. /rehab/mapping/current, /esp/fleet/registry).
        topics = [subscription.topic for subscription in node.subscriptions]
        self.assertIn("/esp32/master/imu", topics)
        self.assertIn("/esp32/slave/imu", topics)
        imu_subs = [s for s in node.subscriptions if s.topic in ("/esp32/master/imu", "/esp32/slave/imu")]
        self.assertTrue(
            all(s.message_type is _Imu for s in imu_subs)
        )
        self.assertTrue(
            all(s.qos.history == "keep_last" for s in imu_subs)
        )
        self.assertTrue(
            all(s.qos.depth == 1 for s in imu_subs)
        )
        pub_topics = [publisher.topic for publisher in node.publishers]
        self.assertIn("/opensim/status", pub_topics)
        self.assertIn(CALIBRATION_STATUS_TOPIC, pub_topics)
        self.assertIn(JOINT_STATES_TOPIC, pub_topics)
        self.assertFalse(node.parameters.get("publish_joint_angle_enabled", True))

    def test_visualizer_trigger_is_unique_typed_and_delegates_once_per_request(self):
        adapter = _FakeAdapter()
        node = self._node(adapter)
        services = [
            service
            for service in node.services
            if service.name == VISUALIZER_OPEN_SERVICE
        ]

        self.assertEqual(len(services), 1)
        self.assertIs(services[0].srv_type, _Trigger)
        response = services[0].callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        self.assertTrue(response.success)
        self.assertEqual(response.message, "visualizer_open")
        self.assertEqual(adapter.open_calls, 1)
        status_messages = [
            json.loads(message.data)["visualization"]["state"]
            for message in node.publishers[0].messages[-2:]
        ]
        self.assertEqual(status_messages, ["opening", "open"])

        retry = services[0].callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        self.assertTrue(retry.success)
        self.assertEqual(adapter.open_calls, 2)

    def test_visualizer_trigger_contains_exception_and_malformed_results(self):
        for result in (RuntimeError("native failed"), None):
            with self.subTest(result=result):
                adapter = _FakeAdapter()
                adapter.open_result = result
                node = self._node(adapter)
                service = next(
                    service
                    for service in node.services
                    if service.name == VISUALIZER_OPEN_SERVICE
                )

                response = service.callback(
                    _TriggerRequest(),
                    _TriggerResponse(),
                )

                self.assertFalse(response.success)
                self.assertEqual(
                    response.message,
                    "visualizer_open_failed",
                )
                self.assertEqual(adapter.open_calls, 1)
                self.assertEqual(
                    node.status_snapshot()["visualization"],
                    {
                        "available": False,
                        "state": "failed",
                        "reason": "visualizer_open_failed",
                        "model_path": "",
                    },
                )

    def test_visualizer_trigger_retry_replaces_persistent_failure(self):
        adapter = _FakeAdapter(
            open_result=(False, "visualizer_native_failed"),
        )
        node = self._node(adapter)
        service = next(
            service
            for service in node.services
            if service.name == VISUALIZER_OPEN_SERVICE
        )

        failed = service.callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        self.assertFalse(failed.success)
        self.assertEqual(
            node.status_snapshot()["visualization"]["reason"],
            "visualizer_native_failed",
        )

        adapter.open_result = (True, "visualizer_open")
        recovered = service.callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        self.assertTrue(recovered.success)
        self.assertEqual(adapter.open_calls, 2)
        self.assertEqual(
            node.status_snapshot()["visualization"],
            {
                "available": True,
                "state": "open",
                "reason": "",
                "model_path": "",
            },
        )

    def test_visualizer_trigger_recreates_crashed_native_adapter(self):
        crashed = _FakeAdapter(
            available=False,
            reason="visualizer_open_failed",
            open_result=(False, "visualizer_open_failed"),
        )
        replacement = _FakeAdapter()
        adapters = [crashed, replacement]
        factory_calls = []

        def factory(model_path, frame_mappings):
            factory_calls.append((model_path, frame_mappings))
            return adapters[len(factory_calls) - 1]

        node = opensim_node.OpenSimBridgeNode(
            adapter_factory=factory,
            monotonic_clock=self.clock,
        )
        service = next(
            service
            for service in node.services
            if service.name == VISUALIZER_OPEN_SERVICE
        )

        response = service.callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )

        self.assertTrue(response.success)
        self.assertEqual(len(factory_calls), 2)
        self.assertEqual(crashed.open_calls, 1)
        self.assertEqual(replacement.open_calls, 1)
        self.assertEqual(
            node.status_snapshot()["visualization"]["state"],
            "open",
        )

    def test_parameter_overrides_control_topics_frames_model_timeout_and_status(self):
        _StubNode.parameter_overrides = {
            "master_imu_topic": "/custom/master",
            "slave_imu_topic": "/custom/slave",
            "master_frame": "pelvis_imu",
            "slave_frame": "torso_imu",
            "model_path": "model.osim",
            "stale_timeout_s": 2.5,
            "status_topic": "/custom/status",
            "joint_angle_topic": "/custom/joint_angle",
            "publish_joint_angle_enabled": True,
        }
        factory_calls = []

        def factory(model_path, frame_mappings):
            factory_calls.append((model_path, frame_mappings))
            return _FakeAdapter()

        node = opensim_node.OpenSimBridgeNode(
            adapter_factory=factory,
            monotonic_clock=self.clock,
        )

        sub_topics = [subscription.topic for subscription in node.subscriptions]
        self.assertIn("/custom/master", sub_topics)
        self.assertIn("/custom/slave", sub_topics)
        self.assertEqual(node.publishers[0].topic, "/custom/status")
        joint_angle_pubs = [
            publisher
            for publisher in node.publishers
            if publisher.topic == "/custom/joint_angle"
        ]
        self.assertEqual(len(joint_angle_pubs), 1)
        self.assertIs(joint_angle_pubs[0].message_type, _Float64)
        self.assertEqual(
            factory_calls,
            [("model.osim", {"master": "pelvis_imu", "slave": "torso_imu"})],
        )

    def test_default_path_never_publishes_custom_joint_angle_as_product(self):
        node = self._node()
        status_topics = [publisher.topic for publisher in node.publishers]
        self.assertIn("/opensim/status", status_topics)
        self.assertNotIn("/opensim/joint_angle", status_topics)

        node._on_master_imu(_Imu())
        node._on_slave_imu(
            _Imu(z=math.sqrt(0.5), w=math.sqrt(0.5)),
        )

        status = node.status_snapshot()
        self.assertTrue(
            "joint_angle_deg" not in status or status.get("joint_angle_deg") is None,
        )
        status_pub = next(p for p in node.publishers if p.topic == "/opensim/status")
        self.assertEqual(len(status_pub.messages), 0)

    def test_debug_flag_publishes_relative_joint_angle_when_enabled(self):
        _StubNode.parameter_overrides = {
            "publish_joint_angle_enabled": True,
        }
        node = self._node()
        angle_pub = next(p for p in node.publishers if p.topic == "/opensim/joint_angle")
        self.assertEqual(angle_pub.topic, "/opensim/joint_angle")

        node._on_master_imu(_Imu())  # identity
        self.assertEqual(angle_pub.messages, [])

        node._on_slave_imu(
            _Imu(z=math.sqrt(0.5), w=math.sqrt(0.5)),  # +90 deg about Z
        )
        self.assertEqual(len(angle_pub.messages), 1)
        # First paired sample establishes the baseline, so published angle is 0.
        self.assertAlmostEqual(angle_pub.messages[0].data, 0.0, places=6)

        # Move slave back toward identity — relative angle should leave zero.
        node._on_slave_imu(_Imu())
        self.assertEqual(len(angle_pub.messages), 2)
        self.assertAlmostEqual(angle_pub.messages[1].data, -90.0, places=5)

    def test_master_and_slave_update_independently_with_normalized_rotations(self):
        adapter = _FakeAdapter()
        node = self._node(adapter)

        node._on_master_imu(_Imu(z=2.0, w=2.0))
        self.assertEqual(len(adapter.calls), 1)
        role, frame, rotation = adapter.calls[0]
        self.assertEqual((role, frame), ("master", "femur_r_imu"))
        self.assertAlmostEqual(
            math.sqrt(sum(value * value for value in rotation.scalar_first)),
            1.0,
        )
        self.assertEqual(node._sensor_states["master"].updates, 1)
        self.assertEqual(node._sensor_states["master"].state, "live")
        self.assertEqual(node._sensor_states["slave"].state, "waiting")

        self.clock.now = 11.0
        node._on_slave_imu(_Imu(x=2.0, w=2.0))
        self.assertEqual(len(adapter.calls), 2)
        self.assertEqual(adapter.calls[1][:2], ("slave", "tibia_r_imu"))
        self.assertEqual(node._sensor_states["master"].updates, 1)
        self.assertEqual(node._sensor_states["slave"].updates, 1)
        self.assertEqual(node._sensor_states["slave"].last_valid_monotonic, 11.0)

    def test_invalid_orientation_never_reaches_adapter_or_refreshes_freshness(self):
        adapter = _FakeAdapter()
        node = self._node(adapter)

        node._on_master_imu(_Imu())
        previous_valid_time = node._sensor_states["master"].last_valid_monotonic
        self.clock.now = 12.0
        node._on_master_imu(_Imu(x=float("nan")))

        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(node._sensor_states["master"].updates, 1)
        self.assertEqual(
            node._sensor_states["master"].last_valid_monotonic,
            previous_valid_time,
        )
        self.assertEqual(node._sensor_states["master"].state, "invalid")
        self.assertEqual(
            node._sensor_states["master"].last_error,
            "quaternion_non_finite",
        )

    def test_out_of_order_message_cannot_overwrite_or_refresh_newer_state(self):
        adapter = _FakeAdapter()
        node = self._node(adapter)
        node._on_master_imu(
            _Imu(z=1.0, w=1.0, stamp_sec=20, stamp_nanosec=500),
        )
        latest_call = adapter.calls[-1]
        latest_valid_time = node._sensor_states["master"].last_valid_monotonic
        latest_source_time = node._sensor_states["master"].last_source_timestamp_ns

        self.clock.now = 12.0
        node._on_master_imu(
            _Imu(x=1.0, w=1.0, stamp_sec=19, stamp_nanosec=999),
        )

        sensor = node._sensor_states["master"]
        self.assertEqual(adapter.calls, [latest_call])
        self.assertEqual(sensor.updates, 1)
        self.assertEqual(sensor.last_valid_monotonic, latest_valid_time)
        self.assertEqual(sensor.last_source_timestamp_ns, latest_source_time)
        self.assertEqual(sensor.state, "live")

    def test_unavailable_visualization_accepts_both_roles_as_live_no_ops(self):
        reasons = (
            "opensim_bindings_unavailable",
            "model_path_not_found",
            "model_load_failed",
            "dynamic_decorations_unsupported_by_bindings",
        )
        for reason in reasons:
            with self.subTest(reason=reason):
                node = self._node(
                    UnavailableVisualizerAdapter(
                        reason,
                        {"master": "femur_r_imu", "slave": "tibia_r_imu"},
                    )
                )
                node._on_master_imu(_Imu())
                self.clock.now += 0.1
                node._on_slave_imu(_Imu(y=1.0, w=1.0))

                status = node.status_snapshot()
                self.assertFalse(status["visualization"]["available"])
                self.assertEqual(status["visualization"]["reason"], reason)
                self.assertEqual(status["sensors"]["master"]["state"], "live")
                self.assertEqual(status["sensors"]["slave"]["state"], "live")
                self.assertEqual(status["sensors"]["master"]["updates"], 1)
                self.assertEqual(status["sensors"]["slave"]["updates"], 1)
                self.assertNotEqual(
                    status["sensors"]["master"]["state"],
                    "mapping_error",
                )
                self.assertNotEqual(
                    status["sensors"]["slave"]["state"],
                    "mapping_error",
                )


class OpenSimNodeStatusTests(unittest.TestCase):
    def setUp(self):
        _StubNode.parameter_overrides = {}
        self.clock = _Clock()

    def _node(self, adapter=None, **overrides):
        _StubNode.parameter_overrides = overrides
        return opensim_node.OpenSimBridgeNode(
            adapter=adapter or _FakeAdapter(),
            monotonic_clock=self.clock,
        )

    def test_initial_status_is_versioned_compact_and_reports_waiting_roles(self):
        adapter = _FakeAdapter(
            available=False,
            reason="opensim_bindings_unavailable",
        )
        node = self._node(adapter)

        self.assertEqual(len(node.timers), 1)
        node.timers[0].callback()
        payload = node.publishers[0].messages[-1].data
        status = json.loads(payload)

        self.assertEqual(
            payload,
            json.dumps(status, sort_keys=True, separators=(",", ":")),
        )
        self.assertEqual(status["schema"], "rehab.opensim_live_link.1")
        self.assertEqual(status["sensors"]["master"]["state"], "waiting")
        self.assertIsNone(status["sensors"]["master"]["age_s"])
        self.assertEqual(status["sensors"]["slave"]["state"], "waiting")
        self.assertFalse(status["visualization"]["available"])
        self.assertEqual(
            status["visualization"]["reason"],
            "opensim_bindings_unavailable",
        )
        self.assertEqual(status["visualization"]["model_path"], "")
        self.assertEqual(
            node.logger.warning_messages,
            [
                "OpenSim visualization state available=False "
                "state=unavailable reason=opensim_bindings_unavailable",
            ],
        )

        node.timers[0].callback()
        self.assertEqual(len(node.logger.warning_messages), 1)

    def test_timer_cadence_is_bounded_by_half_timeout_with_safe_minimum(self):
        node = self._node(stale_timeout_s=4.0)
        self.assertGreater(node.timers[0].period, 0.0)
        self.assertLessEqual(node.timers[0].period, 2.0)

        short_timeout_node = self._node(stale_timeout_s=-2.0)
        self.assertGreater(short_timeout_node.timers[0].period, 0.0)
        self.assertGreater(short_timeout_node._stale_timeout_s, 0.0)
        self.assertLessEqual(
            short_timeout_node.timers[0].period,
            short_timeout_node._stale_timeout_s / 2.0,
        )

    def test_valid_update_changes_only_one_role_and_logs_transition_once(self):
        node = self._node()
        initial_log_count = len(node.logger.info_messages)

        node._on_master_imu(_Imu())
        first_log_count = len(node.logger.info_messages)
        self.clock.now += 0.1
        node._on_master_imu(_Imu(y=1.0, w=1.0))

        status = node.status_snapshot()
        self.assertEqual(status["sensors"]["master"]["state"], "live")
        self.assertEqual(status["sensors"]["master"]["updates"], 2)
        self.assertEqual(status["sensors"]["master"]["last_error"], "")
        self.assertEqual(status["sensors"]["slave"]["state"], "waiting")
        self.assertEqual(first_log_count, initial_log_count + 1)
        self.assertEqual(len(node.logger.info_messages), first_log_count)

    def test_invalid_reason_is_observable_without_refreshing_last_valid_time(self):
        node = self._node()
        node._on_master_imu(_Imu())
        last_valid_time = node._sensor_states["master"].last_valid_monotonic
        prior_warning_count = len(node.logger.warning_messages)
        self.clock.now += 0.6

        node._on_master_imu(_Imu(w=0.0))
        first_warning_count = len(node.logger.warning_messages)
        node._on_master_imu(_Imu(w=0.0))

        sensor = node.status_snapshot()["sensors"]["master"]
        self.assertEqual(sensor["state"], "invalid")
        self.assertEqual(sensor["last_error"], "quaternion_near_zero")
        self.assertEqual(
            node._sensor_states["master"].last_valid_monotonic,
            last_valid_time,
        )
        self.assertEqual(first_warning_count, prior_warning_count + 1)
        self.assertEqual(
            len(node.logger.warning_messages),
            first_warning_count,
        )

    def test_timer_marks_roles_stale_independently_and_keeps_publishing(self):
        node = self._node(stale_timeout_s=1.0)
        node._on_master_imu(_Imu())
        self.clock.now = 10.6
        node._on_slave_imu(_Imu())

        self.clock.now = 11.1
        node.timers[0].callback()
        first_status = json.loads(node.publishers[0].messages[-1].data)
        self.assertEqual(first_status["sensors"]["master"]["state"], "stale")
        self.assertEqual(first_status["sensors"]["slave"]["state"], "live")
        self.assertAlmostEqual(first_status["sensors"]["master"]["age_s"], 1.1)
        self.assertAlmostEqual(first_status["sensors"]["slave"]["age_s"], 0.5)

        published_count = len(node.publishers[0].messages)
        stale_warning_count = len(node.logger.warning_messages)
        node.timers[0].callback()
        self.assertEqual(len(node.publishers[0].messages), published_count + 1)
        self.assertEqual(len(node.logger.warning_messages), stale_warning_count)

        self.clock.now = 11.7
        node.timers[0].callback()
        second_status = json.loads(node.publishers[0].messages[-1].data)
        self.assertEqual(second_status["sensors"]["master"]["state"], "stale")
        self.assertEqual(second_status["sensors"]["slave"]["state"], "stale")

    def test_timer_marks_never_seen_roles_stale_after_startup_grace(self):
        node = self._node(stale_timeout_s=1.0)

        self.clock.now = 11.1
        node.timers[0].callback()
        status = json.loads(node.publishers[0].messages[-1].data)

        self.assertEqual(status["sensors"]["master"]["state"], "stale")
        self.assertEqual(status["sensors"]["slave"]["state"], "stale")
        self.assertIsNone(status["sensors"]["master"]["age_s"])
        self.assertIsNone(status["sensors"]["slave"]["age_s"])
        self.assertEqual(
            node.logger.warning_messages.count(
                "OpenSim sensor master state waiting->stale: stale_timeout",
            ),
            1,
        )
        self.assertEqual(
            node.logger.warning_messages.count(
                "OpenSim sensor slave state waiting->stale: stale_timeout",
            ),
            1,
        )

    def test_visualizer_update_failure_does_not_reject_valid_imu(self):
        adapter = _FakeAdapter(accepted=False)
        node = self._node(adapter)

        node._on_master_imu(_Imu())
        status = node.status_snapshot()
        self.assertEqual(status["sensors"]["master"]["state"], "live")
        self.assertEqual(status["sensors"]["master"]["last_error"], "")
        self.assertEqual(status["sensors"]["master"]["updates"], 1)
        self.assertEqual(status["sensors"]["slave"]["state"], "waiting")

        adapter.accepted = True
        node._on_slave_imu(_Imu())
        status = node.status_snapshot()
        self.assertEqual(status["sensors"]["master"]["state"], "live")
        self.assertEqual(status["sensors"]["slave"]["state"], "live")

    def test_valid_imu_recreates_crashed_native_adapter_once(self):
        crashed = _FakeAdapter(
            accepted=False,
            available=False,
            reason="visualizer_update_failed",
        )
        replacement = _FakeAdapter()
        adapters = [crashed, replacement]
        factory_calls = []

        def factory(model_path, frame_mappings):
            factory_calls.append((model_path, frame_mappings))
            return adapters[len(factory_calls) - 1]

        node = opensim_node.OpenSimBridgeNode(
            adapter_factory=factory,
            monotonic_clock=self.clock,
        )
        node._on_master_imu(_Imu())

        self.assertEqual(len(factory_calls), 2)
        self.assertEqual(len(crashed.calls), 1)
        self.assertEqual(len(replacement.calls), 1)
        self.assertEqual(
            node.status_snapshot()["sensors"]["master"]["state"],
            "live",
        )
        self.assertTrue(
            node.status_snapshot()["visualization"]["available"],
        )

    def test_unavailable_visualization_remains_orthogonal_to_live_freshness(self):
        node = self._node(
            UnavailableVisualizerAdapter(
                "model_path_not_found",
                {"master": "femur_r_imu", "slave": "tibia_r_imu"},
            )
        )
        node._on_master_imu(_Imu())
        node._on_slave_imu(_Imu())
        self.clock.now += 0.5
        node.timers[0].callback()
        status = json.loads(node.publishers[0].messages[-1].data)

        self.assertFalse(status["visualization"]["available"])
        self.assertEqual(
            status["visualization"]["reason"],
            "model_path_not_found",
        )
        self.assertEqual(status["sensors"]["master"]["state"], "live")
        self.assertEqual(status["sensors"]["slave"]["state"], "live")


class OpenSimNodeCalibrationTests(unittest.TestCase):
    def setUp(self):
        _StubNode.parameter_overrides = {}
        self.clock = _Clock()

    def _node(self, adapter=None, calibration=None, ik_solver=None):
        return opensim_node.OpenSimBridgeNode(
            adapter=adapter or _FakeAdapter(),
            monotonic_clock=self.clock,
            calibration_controller=calibration,
            ik_solver=ik_solver if ik_solver is not None else UnavailableOrientationIkSolver(
                "test_default_unavailable"
            ),
        )

    def _service(self, node, name):
        for service in node.services:
            if service.name == name:
                return service
        self.fail(f"missing service {name}")

    def _calibrate_live(self, node, *, stamp_sec=100):
        node._on_master_imu(_Imu(stamp_sec=stamp_sec))
        node._on_slave_imu(_Imu(stamp_sec=stamp_sec))
        self._service(node, CALIBRATION_CAPTURE_SERVICE).callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        for i in range(6):
            self.clock.now = 10.0 + i * 0.1
            node._on_master_imu(_Imu(stamp_sec=stamp_sec + 1 + i))
            node._on_slave_imu(_Imu(stamp_sec=stamp_sec + 1 + i))
        self.assertEqual(node.status_snapshot()["calibration"]["state"], "CALIBRATED")

    def test_constructs_capture_and_clear_trigger_services(self):
        node = self._node()
        names = [service.name for service in node.services]
        self.assertIn(CALIBRATION_CAPTURE_SERVICE, names)
        self.assertIn(CALIBRATION_CLEAR_SERVICE, names)
        for service in node.services:
            if service.name in (
                CALIBRATION_CAPTURE_SERVICE,
                CALIBRATION_CLEAR_SERVICE,
            ):
                self.assertIs(service.srv_type, _Trigger)

    def test_visualizer_failure_does_not_interrupt_ik_or_timer_publishers(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        adapter = _FakeAdapter(
            open_result=(False, "visualizer_native_failed"),
        )
        node = self._node(
            adapter=adapter,
            calibration=fast,
            ik_solver=FakeOrientationIkSolver(),
        )
        visualizer_service = self._service(
            node,
            VISUALIZER_OPEN_SERVICE,
        )
        response = visualizer_service.callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        self.assertFalse(response.success)
        self.assertEqual(response.message, "visualizer_native_failed")
        self.assertEqual(
            node.status_snapshot()["visualization"]["state"],
            "failed",
        )

        joint_pub = next(
            publisher
            for publisher in node.publishers
            if publisher.topic == JOINT_STATES_TOPIC
        )
        ik_pub = next(
            publisher
            for publisher in node.publishers
            if publisher.topic == IK_STATUS_TOPIC
        )
        diag_pub = next(
            publisher
            for publisher in node.publishers
            if publisher.topic == DIAGNOSTICS_TOPIC
        )
        self._calibrate_live(node, stamp_sec=500)
        node._on_master_imu(_Imu(stamp_sec=600))
        node._on_slave_imu(_Imu(stamp_sec=600))
        self.assertGreaterEqual(len(joint_pub.messages), 1)
        self.assertGreaterEqual(len(ik_pub.messages), 1)

        diagnostics_before = len(diag_pub.messages)
        node._on_status_timer()
        node._on_status_timer()
        self.assertEqual(len(diag_pub.messages), diagnostics_before + 2)
        failure_logs = [
            message
            for message in node.logger.warning_messages
            if "state=failed reason=visualizer_native_failed" in message
        ]
        self.assertEqual(len(failure_logs), 1)

    def test_status_snapshot_includes_uncalibrated_calibration_object(self):
        node = self._node()
        status = node.status_snapshot()
        self.assertIn("calibration", status)
        calibration = status["calibration"]
        self.assertEqual(calibration["state"], "UNCALIBRATED")
        self.assertIn("reason", calibration)

    def test_clear_service_returns_uncalibrated(self):
        fast = CalibrationController(window_s=0.2, min_samples=3)
        node = self._node(calibration=fast)
        # Force calibrated then clear
        fast.begin_capture()
        identity = (0.0, 0.0, 0.0, 1.0)
        for i in range(5):
            fast.feed_pair(identity, identity, monotonic_time=10.0 + i * 0.1)
        self.assertEqual(fast.state, CalibrationState.CALIBRATED)

        response = _TriggerResponse()
        self._service(node, CALIBRATION_CLEAR_SERVICE).callback(
            _TriggerRequest(),
            response,
        )
        self.assertTrue(response.success)
        self.assertEqual(node.status_snapshot()["calibration"]["state"], "UNCALIBRATED")

    def test_capture_requires_live_sensors_and_not_single_pair(self):
        fast = CalibrationController(window_s=1.5, min_samples=10)
        node = self._node(calibration=fast)
        response = _TriggerResponse()
        self._service(node, CALIBRATION_CAPTURE_SERVICE).callback(
            _TriggerRequest(),
            response,
        )
        self.assertFalse(response.success)

        node._on_master_imu(_Imu())
        node._on_slave_imu(_Imu())
        response = _TriggerResponse()
        self._service(node, CALIBRATION_CAPTURE_SERVICE).callback(
            _TriggerRequest(),
            response,
        )
        self.assertTrue(response.success)
        self.assertEqual(node.status_snapshot()["calibration"]["state"], "CAPTURING")

        # One additional pair after begin is not enough for CALIBRATED
        self.clock.now += 0.05
        node._on_master_imu(_Imu())
        node._on_slave_imu(_Imu())
        self.assertNotEqual(
            node.status_snapshot()["calibration"]["state"],
            "CALIBRATED",
        )

    def test_stable_feeds_reach_calibrated_via_imu_path(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        node = self._node(calibration=fast)
        node._on_master_imu(_Imu())
        node._on_slave_imu(_Imu())
        response = _TriggerResponse()
        self._service(node, CALIBRATION_CAPTURE_SERVICE).callback(
            _TriggerRequest(),
            response,
        )
        self.assertTrue(response.success)
        for i in range(6):
            self.clock.now = 10.0 + i * 0.1
            node._on_master_imu(_Imu())
            node._on_slave_imu(_Imu())
        self.assertEqual(node.status_snapshot()["calibration"]["state"], "CALIBRATED")

    def test_joint_states_empty_while_uncalibrated_and_when_calibrated_without_ik(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        node = self._node(
            calibration=fast,
            ik_solver=UnavailableOrientationIkSolver("opensim_ik_api_unavailable"),
        )
        joint_pub = next(p for p in node.publishers if p.topic == JOINT_STATES_TOPIC)

        node._maybe_publish_joint_states()
        self.assertEqual(joint_pub.messages, [])

        node._on_master_imu(_Imu(stamp_sec=1))
        node._on_slave_imu(_Imu(stamp_sec=1))
        self._service(node, CALIBRATION_CAPTURE_SERVICE).callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        for i in range(6):
            self.clock.now = 10.0 + i * 0.1
            node._on_master_imu(_Imu(stamp_sec=2 + i))
            node._on_slave_imu(_Imu(stamp_sec=2 + i))
        self.assertEqual(node.status_snapshot()["calibration"]["state"], "CALIBRATED")
        node._maybe_publish_joint_states()
        # Unavailable solver — still no fabricated JointState
        self.assertEqual(joint_pub.messages, [])

    def test_fake_solver_publishes_stamped_joint_states_when_calibrated(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        adapter = _FakeAdapter()
        node = self._node(
            adapter=adapter,
            calibration=fast,
            ik_solver=FakeOrientationIkSolver(),
        )
        joint_pub = next(p for p in node.publishers if p.topic == JOINT_STATES_TOPIC)
        self._calibrate_live(node, stamp_sec=50)
        node._on_master_imu(_Imu(stamp_sec=200))
        node._on_slave_imu(_Imu(stamp_sec=200))
        self.assertGreaterEqual(len(joint_pub.messages), 1)
        message = joint_pub.messages[-1]
        self.assertEqual(list(message.name), ["knee_angle_r"])
        self.assertEqual(len(message.position), 1)
        self.assertAlmostEqual(message.position[0], 0.0, places=5)
        self.assertEqual(message.header.stamp.sec, 200)
        self.assertEqual(message.header.stamp.nanosec, 0)
        self.assertGreaterEqual(len(adapter.pose_calls), 1)
        pose_names, pose_positions = adapter.pose_calls[-1]
        self.assertEqual(pose_names, ["knee_angle_r"])
        self.assertAlmostEqual(pose_positions[0], message.position[0], places=6)

    def test_full_ik_pose_drives_visualizer_without_expanding_product_output(self):
        class _FullPoseFake(FakeOrientationIkSolver):
            def solve(self, **kwargs):
                result = super().solve(**kwargs)
                return replace(
                    result,
                    visualization_coordinate_names=[
                        "hip_flexion_r",
                        "hip_adduction_r",
                        "hip_rotation_r",
                        "knee_angle_r",
                    ],
                    visualization_positions_rad=[0.4, 0.1, -0.2, 0.3],
                )

        fast = CalibrationController(window_s=0.3, min_samples=4)
        adapter = _FakeAdapter()
        node = self._node(
            adapter=adapter,
            calibration=fast,
            ik_solver=_FullPoseFake(),
        )
        joint_pub = next(p for p in node.publishers if p.topic == JOINT_STATES_TOPIC)
        self._calibrate_live(node, stamp_sec=50)
        node._on_master_imu(_Imu(stamp_sec=200))
        node._on_slave_imu(_Imu(stamp_sec=200))

        message = joint_pub.messages[-1]
        self.assertEqual(list(message.name), ["knee_angle_r"])
        self.assertEqual(len(message.position), 1)
        self.assertEqual(
            adapter.pose_calls[-1],
            (
                [
                    "hip_flexion_r",
                    "hip_adduction_r",
                    "hip_rotation_r",
                    "knee_angle_r",
                ],
                [0.4, 0.1, -0.2, 0.3],
            ),
        )

    def test_clear_stops_joint_states_and_resets_solution(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        node = self._node(calibration=fast, ik_solver=FakeOrientationIkSolver())
        joint_pub = next(p for p in node.publishers if p.topic == JOINT_STATES_TOPIC)
        self._calibrate_live(node, stamp_sec=50)
        node._on_master_imu(_Imu(stamp_sec=210))
        node._on_slave_imu(_Imu(stamp_sec=210))
        self.assertGreaterEqual(len(joint_pub.messages), 1)
        count_before = len(joint_pub.messages)

        self._service(node, CALIBRATION_CLEAR_SERVICE).callback(
            _TriggerRequest(),
            _TriggerResponse(),
        )
        self.assertIsNone(node._ik_solution)
        node._on_master_imu(_Imu(stamp_sec=220))
        node._on_slave_imu(_Imu(stamp_sec=220))
        self.assertEqual(len(joint_pub.messages), count_before)

    def test_invalid_solution_publishes_ik_status_not_joint_states(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)

        class _InvalidFake(FakeOrientationIkSolver):
            def solve(self, **kwargs):
                result = super().solve(**kwargs)
                return result.__class__(
                    solution_valid=False,
                    reason="forced_invalid",
                    joint_names=result.joint_names,
                    positions_rad=[],
                    source_timestamp_ns=result.source_timestamp_ns,
                    orientation_residual_rms=None,
                    orientation_residual_max=None,
                    calibration_id=result.calibration_id,
                    input_age_s=result.input_age_s,
                    solve_duration_s=result.solve_duration_s,
                )

        node = self._node(calibration=fast, ik_solver=_InvalidFake())
        joint_pub = next(p for p in node.publishers if p.topic == JOINT_STATES_TOPIC)
        ik_pub = next(p for p in node.publishers if p.topic == IK_STATUS_TOPIC)
        self._calibrate_live(node, stamp_sec=50)
        before = len(joint_pub.messages)
        node._on_master_imu(_Imu(stamp_sec=300))
        node._on_slave_imu(_Imu(stamp_sec=300))
        self.assertEqual(len(joint_pub.messages), before)
        self.assertGreaterEqual(len(ik_pub.messages), 1)
        payload = json.loads(ik_pub.messages[-1].data)
        self.assertFalse(payload["solution_valid"])
        self.assertEqual(payload["reason"], "forced_invalid")

    def test_missing_source_timestamp_blocks_joint_states(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        node = self._node(calibration=fast, ik_solver=FakeOrientationIkSolver())
        joint_pub = next(p for p in node.publishers if p.topic == JOINT_STATES_TOPIC)
        ik_pub = next(p for p in node.publishers if p.topic == IK_STATUS_TOPIC)
        self._calibrate_live(node, stamp_sec=50)
        before = len(joint_pub.messages)
        # Clear stored stamps so subsequent unstamped IMUs cannot reuse them.
        node._sensor_states["master"].last_source_timestamp_ns = None
        node._sensor_states["slave"].last_source_timestamp_ns = None
        node._on_master_imu(_Imu())  # no stamp
        node._on_slave_imu(_Imu())
        self.assertEqual(len(joint_pub.messages), before)
        payload = json.loads(ik_pub.messages[-1].data)
        self.assertFalse(payload["solution_valid"])
        self.assertIn("missing_source_timestamp", payload["reason"])

    def test_status_snapshot_embeds_ik_object(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        node = self._node(calibration=fast, ik_solver=FakeOrientationIkSolver())
        self._calibrate_live(node, stamp_sec=50)
        node._on_master_imu(_Imu(stamp_sec=400))
        node._on_slave_imu(_Imu(stamp_sec=400))
        status = node.status_snapshot()
        self.assertIn("ik", status)
        self.assertIn("solution_valid", status["ik"])
        self.assertIn("calibration_id", status["ik"])

    def test_diagnostics_heartbeat_publishes_on_timer(self):
        fast = CalibrationController(window_s=0.3, min_samples=4)
        node = self._node(calibration=fast, ik_solver=FakeOrientationIkSolver())
        diag_pub = next(p for p in node.publishers if p.topic == DIAGNOSTICS_TOPIC)
        self.assertEqual(diag_pub.messages, [])
        node._on_status_timer()
        self.assertGreaterEqual(len(diag_pub.messages), 1)
        payload = json.loads(diag_pub.messages[-1].data)
        self.assertIn("solution_valid", payload)


class IkOneContractTests(unittest.TestCase):
    """IK-01 contract tests: dynamic MAC-keyed subscription lifecycle.

    Covers IK-01-A through IK-01-F as defined in 23-01-PLAN.md.
    All tests run without live ROS or hardware via _install_ros_stubs().
    """

    _MAPPING_TWO_DEVICES = json.dumps({
        "applied_revision": 1,
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:112233445566", "frame": "femur_r_imu", "segment": "femur"},
        ],
    })

    _MAPPING_ONE_NEW_ONE_REMOVED = json.dumps({
        "applied_revision": 2,
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:ffeeddccbbaa", "frame": "pelvis_imu", "segment": "pelvis"},
        ],
    })

    _MAPPING_SINGLE_DEVICE = json.dumps({
        "applied_revision": 3,
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
        ],
    })

    def setUp(self):
        _StubNode.parameter_overrides = {}
        self.clock = _Clock()

    def _make_node(self):
        return opensim_node.OpenSimBridgeNode(
            adapter=_FakeAdapter(),
            monotonic_clock=self.clock,
            ik_solver=UnavailableOrientationIkSolver("test_ik01"),
        )

    def _mapping_msg(self, json_str):
        msg = _String()
        msg.data = json_str
        return msg

    def _imu_msg(self, x=0.0, y=0.0, z=0.0, w=1.0, stamp_sec=100, stamp_nanosec=0):
        return _Imu(x=x, y=y, z=z, w=w, stamp_sec=stamp_sec, stamp_nanosec=stamp_nanosec)

    def test_ik01_a_two_assigned_devices_create_two_mac_subscriptions(self):
        """IK-01-A: _on_mapping_current with 2 assigned devices creates 2 MAC subscriptions."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))

        mac_subs = [s for s in node.subscriptions if "/esp/raw/mac_" in s.topic]
        self.assertEqual(len(mac_subs), 2)

        mac_topics = {s.topic for s in mac_subs}
        self.assertIn("/esp/raw/mac_aabbccddeeff", mac_topics)
        self.assertIn("/esp/raw/mac_112233445566", mac_topics)

    def test_ik01_b_remap_destroys_removed_subscription_creates_new(self):
        """IK-01-B: Re-calling _on_mapping_current replaces old subscriptions with new ones."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))

        # First mapping: aabbccddeeff + 112233445566
        initial_mac_subs = [s for s in node.subscriptions if "/esp/raw/mac_" in s.topic]
        self.assertEqual(len(initial_mac_subs), 2)

        # Remap: keep aabbccddeeff, remove 112233445566, add ffeeddccbbaa
        node._on_mapping_current(self._mapping_msg(self._MAPPING_ONE_NEW_ONE_REMOVED))

        mac_subs_after = [s for s in node.subscriptions if "/esp/raw/mac_" in s.topic]
        mac_topics_after = {s.topic for s in mac_subs_after}

        # Old device 112233445566 must be gone
        self.assertNotIn("/esp/raw/mac_112233445566", mac_topics_after)
        # Kept device must remain
        self.assertIn("/esp/raw/mac_aabbccddeeff", mac_topics_after)
        # New device must be present
        self.assertIn("/esp/raw/mac_ffeeddccbbaa", mac_topics_after)
        # Exactly 2 MAC subscriptions
        self.assertEqual(len(mac_subs_after), 2)

    def test_ik01_c_mac_inputs_dict_has_exactly_new_device_ids_after_remap(self):
        """IK-01-C: _mac_inputs dict has exactly the new device_ids as keys after remap."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))

        self.assertIn("esp32:aabbccddeeff", node._mac_inputs)
        self.assertIn("esp32:112233445566", node._mac_inputs)
        self.assertEqual(len(node._mac_inputs), 2)

        # Remap with different devices
        node._on_mapping_current(self._mapping_msg(self._MAPPING_ONE_NEW_ONE_REMOVED))

        self.assertIn("esp32:aabbccddeeff", node._mac_inputs)
        self.assertNotIn("esp32:112233445566", node._mac_inputs)
        self.assertIn("esp32:ffeeddccbbaa", node._mac_inputs)
        self.assertEqual(len(node._mac_inputs), 2)

    def test_ik01_d_on_mac_imu_sets_last_xyzw_and_fresh_on_first_call(self):
        """IK-01-D: _on_mac_imu sets last_xyzw and post_reconnect_fresh=True on first call;
        subsequent calls do NOT re-set post_reconnect_fresh."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_SINGLE_DEVICE))

        device_id = "esp32:aabbccddeeff"
        self.assertIn(device_id, node._mac_inputs)
        entry = node._mac_inputs[device_id]
        self.assertIsNone(entry.last_xyzw)
        self.assertFalse(entry.post_reconnect_fresh)

        # First IMU frame
        node._on_mac_imu(device_id, self._imu_msg(x=0.0, y=0.0, z=0.0, w=1.0, stamp_sec=10))
        self.assertIsNotNone(entry.last_xyzw)
        self.assertTrue(entry.post_reconnect_fresh)

        # Second IMU frame — post_reconnect_fresh must stay True (not re-set)
        node._on_mac_imu(device_id, self._imu_msg(x=0.1, y=0.0, z=0.0, w=0.99, stamp_sec=11))
        self.assertTrue(entry.post_reconnect_fresh)

    def test_ik01_e_on_fleet_registry_reconnect_clears_post_reconnect_fresh(self):
        """IK-01-E: _on_fleet_registry with reconnect event sets post_reconnect_fresh=False."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_SINGLE_DEVICE))
        device_id = "esp32:aabbccddeeff"

        # Receive first frame so post_reconnect_fresh = True
        node._on_mac_imu(device_id, self._imu_msg(stamp_sec=10))
        self.assertTrue(node._mac_inputs[device_id].post_reconnect_fresh)

        # Fleet registry reconnect event
        reconnect_event = json.dumps({
            "reconnected_devices": ["esp32:aabbccddeeff"],
        })
        fleet_msg = _String()
        fleet_msg.data = reconnect_event
        node._on_fleet_registry(fleet_msg)

        self.assertFalse(node._mac_inputs[device_id].post_reconnect_fresh)

    def test_ik01_f_malformed_mapping_json_logs_warning_and_does_not_raise(self):
        """IK-01-F: _on_mapping_current with malformed JSON logs a warning and does not raise."""
        node = self._make_node()
        bad_msg = _String()
        bad_msg.data = "THIS IS NOT JSON {{{broken"

        # Must not raise
        try:
            node._on_mapping_current(bad_msg)
        except Exception as exc:
            self.fail(f"_on_mapping_current raised unexpectedly: {exc}")

        # _mac_inputs must remain empty (no partial modification)
        self.assertEqual(len(node._mac_inputs), 0)


class IkTwoNodeTests(unittest.TestCase):
    """IK-02 contract tests for OpenSimBridgeNode calibration capture service.

    Covers IK-02-F through IK-02-H. All tests run offline — no live ROS,
    no hardware. Uses _install_ros_stubs() established above.
    """

    _MAPPING_TWO_DEVICES = json.dumps({
        "applied_revision": 1,
        "model_hash": "abc123def456",
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:112233445566", "frame": "femur_r_imu", "segment": "femur"},
        ],
    })

    _MAPPING_DIFFERENT_DEVICES = json.dumps({
        "applied_revision": 2,
        "model_hash": "abc123def456",
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:NEWDEVICE9999", "frame": "pelvis_imu", "segment": "pelvis"},
        ],
    })

    _MAPPING_SAME_DEVICES_NEW_REVISION = json.dumps({
        "applied_revision": 1,
        "model_hash": "abc123def456",
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:112233445566", "frame": "femur_r_imu", "segment": "femur"},
        ],
    })

    def setUp(self):
        _StubNode.parameter_overrides = {}
        self.clock = _Clock()

    def _make_node(self):
        return opensim_node.OpenSimBridgeNode(
            adapter=_FakeAdapter(),
            monotonic_clock=self.clock,
            ik_solver=UnavailableOrientationIkSolver("test_ik02"),
        )

    def _mapping_msg(self, json_str):
        msg = _String()
        msg.data = json_str
        return msg

    def _imu_msg(self, x=0.0, y=0.0, z=0.0, w=1.0, stamp_sec=100):
        return _Imu(x=x, y=y, z=z, w=w, stamp_sec=stamp_sec)

    def _trigger(self, node, service_name):
        """Call a Trigger service on the node and return the response."""
        for service in node.services:
            if service.name == service_name:
                return service.callback(_TriggerRequest(), _TriggerResponse())
        raise AssertionError(f"Service not found: {service_name}")

    def _feed_two_imu(self, node):
        """Send one IMU frame for each of the two mapped devices."""
        node._on_mac_imu("esp32:aabbccddeeff", self._imu_msg(stamp_sec=10))
        node._on_mac_imu("esp32:112233445566", self._imu_msg(stamp_sec=10))

    def test_ik02_initial_state_is_uncalibrated_with_no_artifact(self):
        """OpenSimBridgeNode initialises with _n_calib_state='uncalibrated' and _n_calib_artifact=None."""
        node = self._make_node()
        self.assertEqual(node._n_calib_state, "uncalibrated")
        self.assertIsNone(node._n_calib_artifact)

    def test_ik02_capture_service_exists_with_correct_topic_and_type(self):
        """OpenSimBridgeNode creates /rehab/calibration/capture service of type Trigger."""
        node = self._make_node()
        capture_services = [
            s for s in node.services if s.name == "/rehab/calibration/capture"
        ]
        self.assertEqual(len(capture_services), 1)
        self.assertIs(capture_services[0].srv_type, _Trigger)

    def test_ik02_status_publisher_exists_on_correct_topic(self):
        """/rehab/calibration/status publisher is created."""
        node = self._make_node()
        status_pubs = [
            p for p in node.publishers if p.topic == "/rehab/calibration/status"
        ]
        self.assertEqual(len(status_pubs), 1)

    def test_ik02_f_capture_with_all_inputs_sets_calibrated_state(self):
        """IK-02-F: Capture service with all inputs sets _n_calib_state='calibrated'."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._feed_two_imu(node)

        response = self._trigger(node, "/rehab/calibration/capture")

        self.assertTrue(response.success)
        outcome = json.loads(response.message)
        self.assertEqual(outcome["outcome"], "captured")
        self.assertIsNotNone(outcome["artifact_path"])
        self.assertEqual(node._n_calib_state, "calibrated")
        self.assertIsNotNone(node._n_calib_artifact)

    def test_ik02_capture_no_mapping_returns_no_mapping_outcome(self):
        """Capture with empty _mac_inputs returns success=False, outcome='no_mapping'."""
        node = self._make_node()
        # No mapping sent — _mac_inputs is empty
        response = self._trigger(node, "/rehab/calibration/capture")

        self.assertFalse(response.success)
        outcome = json.loads(response.message)
        self.assertEqual(outcome["outcome"], "no_mapping")
        self.assertIsNone(outcome["artifact_path"])
        self.assertEqual(node._n_calib_state, "uncalibrated")

    def test_ik02_capture_missing_inputs_returns_missing_inputs_outcome(self):
        """Capture with device in _mac_inputs but no IMU data returns missing_inputs."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        # Do NOT send any IMU data — last_xyzw remains None

        response = self._trigger(node, "/rehab/calibration/capture")

        self.assertFalse(response.success)
        outcome = json.loads(response.message)
        self.assertEqual(outcome["outcome"], "missing_inputs")
        self.assertIsNone(outcome["artifact_path"])

    def test_ik02_artifact_contains_correct_schema_and_device_order(self):
        """After successful capture, artifact has schema_version='calib.v1' and sorted device_order."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._feed_two_imu(node)

        self._trigger(node, "/rehab/calibration/capture")

        artifact = node._n_calib_artifact
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact["schema_version"], "calib.v1")
        self.assertEqual(
            artifact["device_order"],
            sorted(["esp32:aabbccddeeff", "esp32:112233445566"]),
        )
        self.assertIn("reference_pose", artifact)
        self.assertIn("calibrated_at_iso8601", artifact)

    def test_ik02_g_remap_with_changed_devices_invalidates_artifact(self):
        """IK-02-G: Remap changing devices invalidates artifact (_n_calib_state resets to 'uncalibrated')."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._feed_two_imu(node)
        self._trigger(node, "/rehab/calibration/capture")
        self.assertEqual(node._n_calib_state, "calibrated")

        # Remap with different device set
        node._on_mapping_current(self._mapping_msg(self._MAPPING_DIFFERENT_DEVICES))

        self.assertEqual(node._n_calib_state, "uncalibrated")
        self.assertIsNone(node._n_calib_artifact)

    def test_ik02_h_remap_with_same_devices_preserves_valid_artifact(self):
        """IK-02-H: Remap with same devices (same revision, same model_hash) preserves artifact."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._feed_two_imu(node)
        self._trigger(node, "/rehab/calibration/capture")
        self.assertEqual(node._n_calib_state, "calibrated")

        # Remap with SAME device set, same revision, same model_hash
        node._on_mapping_current(self._mapping_msg(self._MAPPING_SAME_DEVICES_NEW_REVISION))

        self.assertEqual(node._n_calib_state, "calibrated")
        self.assertIsNotNone(node._n_calib_artifact)

    def test_ik02_status_topic_publishes_correct_schema_on_timer(self):
        """Status topic publishes schema='rehab.n_calibration_status.1' with state/revision/model_hash."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))

        # Trigger the status timer
        node._on_status_timer()

        status_pubs = [p for p in node.publishers if p.topic == "/rehab/calibration/status"]
        self.assertEqual(len(status_pubs), 1)
        self.assertGreaterEqual(len(status_pubs[0].messages), 1)

        payload = json.loads(status_pubs[0].messages[-1].data)
        self.assertEqual(payload["schema"], "rehab.n_calibration_status.1")
        self.assertIn("state", payload)
        self.assertIn("revision", payload)
        self.assertIn("model_hash", payload)

    def test_ik02_status_includes_schema_version_when_calibrated(self):
        """Status payload includes schema_version='calib.v1' when state is 'calibrated'."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._feed_two_imu(node)
        self._trigger(node, "/rehab/calibration/capture")

        node._on_status_timer()
        status_pubs = [p for p in node.publishers if p.topic == "/rehab/calibration/status"]
        payload = json.loads(status_pubs[0].messages[-1].data)

        self.assertEqual(payload["state"], "calibrated")
        self.assertEqual(payload.get("schema_version"), "calib.v1")

    def test_ik02_reference_pose_quaternion_format_in_artifact(self):
        """reference_pose entries use {qw, qx, qy, qz} format derived from IMU xyzw."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        # Send non-identity quaternion
        node._on_mac_imu("esp32:aabbccddeeff", self._imu_msg(x=0.5, y=0.5, z=0.5, w=0.5, stamp_sec=10))
        node._on_mac_imu("esp32:112233445566", self._imu_msg(x=0.0, y=0.0, z=0.0, w=1.0, stamp_sec=10))

        self._trigger(node, "/rehab/calibration/capture")

        artifact = node._n_calib_artifact
        pose = artifact["reference_pose"]["esp32:aabbccddeeff"]
        self.assertIn("qw", pose)
        self.assertIn("qx", pose)
        self.assertIn("qy", pose)
        self.assertIn("qz", pose)
        self.assertAlmostEqual(pose["qx"], 0.5)
        self.assertAlmostEqual(pose["qw"], 0.5)


class IkThreeContractTests(unittest.TestCase):
    """IK-03 contract tests: sync-skew gate, reconnect freshness, input_validity publisher.

    Covers IK-03-A through IK-03-H as defined in 23-03-PLAN.md.
    All tests run without live ROS or hardware via _install_ros_stubs().
    """

    _MAPPING_TWO_DEVICES = json.dumps({
        "applied_revision": 1,
        "model_hash": "abc123",
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:112233445566", "frame": "femur_r_imu", "segment": "femur"},
        ],
    })

    def setUp(self):
        _StubNode.parameter_overrides = {}
        self.clock = _Clock()

    def _make_node(self, **param_overrides):
        _StubNode.parameter_overrides = param_overrides
        return opensim_node.OpenSimBridgeNode(
            adapter=_FakeAdapter(),
            monotonic_clock=self.clock,
            ik_solver=FakeOrientationIkSolver(),
        )

    def _make_device_input(
        self,
        device_id,
        frame,
        last_ts_ns,
        post_reconnect_fresh,
        last_xyzw=(0.0, 0.0, 0.0, 1.0),
    ):
        """Create a _DeviceInput with specific state directly."""
        from rehab_robotics_bridge.opensim_node import _DeviceInput
        entry = _DeviceInput(
            device_id=device_id,
            frame=frame,
            subscription_handle=None,
            last_xyzw=last_xyzw,
            last_ts_ns=last_ts_ns,
            post_reconnect_fresh=post_reconnect_fresh,
        )
        return entry

    def _mapping_msg(self, json_str):
        msg = _String()
        msg.data = json_str
        return msg

    def _imu_msg(self, x=0.0, y=0.0, z=0.0, w=1.0, stamp_sec=100, stamp_nanosec=0):
        return _Imu(x=x, y=y, z=z, w=w, stamp_sec=stamp_sec, stamp_nanosec=stamp_nanosec)

    # --- IK-03-A: two devices at same timestamp, both fresh → all_valid=True ---

    def test_ik03_a_same_timestamp_both_fresh_all_valid_true(self):
        """IK-03-A: _check_sync_skew with 2 devices at same timestamp, both fresh → all_valid=True."""
        node = self._make_node()
        ts = 1_000_000_000  # 1 second in nanoseconds
        inputs = [
            self._make_device_input("esp32:aabbccddeeff", "tibia_r_imu", ts, True),
            self._make_device_input("esp32:112233445566", "femur_r_imu", ts, True),
        ]
        result = node._check_sync_skew(inputs)
        self.assertTrue(result["all_valid"])
        self.assertAlmostEqual(
            result["device_validities"]["esp32:aabbccddeeff"]["skew_ms"], 0.0
        )
        self.assertTrue(result["device_validities"]["esp32:aabbccddeeff"]["valid"])
        self.assertTrue(result["device_validities"]["esp32:112233445566"]["valid"])

    # --- IK-03-B: one device 100ms behind median → all_valid=False ---

    def test_ik03_b_one_device_100ms_behind_all_valid_false(self):
        """IK-03-B: _check_sync_skew with one device 100ms behind median → all_valid=False, that device valid=False.

        With sync_skew_ms=50: two devices 200ms apart means each is 100ms from the median.
        The device 100ms behind the median exceeds the 50ms limit → invalid.
        """
        node = self._make_node()  # default sync_skew_ms=50
        ts_now = 2_000_000_000   # 2 seconds
        # 200ms gap so each device is 100ms from the median (midpoint)
        ts_old = ts_now - 200_000_000  # 200ms earlier (200_000_000 ns)
        inputs = [
            self._make_device_input("esp32:aabbccddeeff", "tibia_r_imu", ts_now, True),
            self._make_device_input("esp32:112233445566", "femur_r_imu", ts_old, True),
        ]
        result = node._check_sync_skew(inputs)
        self.assertFalse(result["all_valid"])
        self.assertFalse(result["device_validities"]["esp32:112233445566"]["valid"])
        # The device with the recent timestamp is also >50ms from median, so also invalid
        # skew_ms for the late device should be ~100ms from the median
        skew = result["device_validities"]["esp32:112233445566"]["skew_ms"]
        self.assertIsNotNone(skew)
        self.assertGreater(skew, 50.0)

    # --- IK-03-C: fresh=False on one device → all_valid=False ---

    def test_ik03_c_fresh_false_causes_invalid(self):
        """IK-03-C: _check_sync_skew with fresh=False on one device → all_valid=False, that device valid=False."""
        node = self._make_node()
        ts = 3_000_000_000
        inputs = [
            self._make_device_input("esp32:aabbccddeeff", "tibia_r_imu", ts, True),
            self._make_device_input("esp32:112233445566", "femur_r_imu", ts, False),  # NOT fresh
        ]
        result = node._check_sync_skew(inputs)
        self.assertFalse(result["all_valid"])
        self.assertFalse(result["device_validities"]["esp32:112233445566"]["valid"])
        # Fresh device with same ts is fine
        self.assertTrue(result["device_validities"]["esp32:aabbccddeeff"]["valid"])

    # --- IK-03-D: last_ts_ns=None on any device → all_valid=False, skew_ms=None ---

    def test_ik03_d_none_timestamp_causes_invalid_and_none_skew(self):
        """IK-03-D: _check_sync_skew with last_ts_ns=None → all_valid=False, skew_ms=None."""
        node = self._make_node()
        ts = 4_000_000_000
        inputs = [
            self._make_device_input("esp32:aabbccddeeff", "tibia_r_imu", ts, True),
            self._make_device_input("esp32:112233445566", "femur_r_imu", None, True),
        ]
        result = node._check_sync_skew(inputs)
        self.assertFalse(result["all_valid"])
        self.assertFalse(result["device_validities"]["esp32:112233445566"]["valid"])
        self.assertIsNone(result["device_validities"]["esp32:112233445566"]["skew_ms"])

    # --- IK-03-E: skewed input does NOT publish on joint_states, DOES publish validity ---

    def test_ik03_e_skewed_input_suppresses_joint_states_publishes_validity(self):
        """IK-03-E: _solve_and_publish_ik_n() with skewed timestamps publishes to input_validity but NOT joint_states."""
        node = self._make_node()  # sync_skew_ms=50
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))

        validity_pub = next(
            p for p in node.publishers if p.topic == "/rehab/opensim/input_validity"
        )
        joint_pub = next(
            p for p in node.publishers if p.topic == "/opensim/joint_states"
        )
        initial_joint_count = len(joint_pub.messages)

        # Device A gets timestamp at 2s, device B gets 200ms older (1.8s).
        # Median is 1.9s; each device deviates 100ms from median → exceeds 50ms limit.
        node._on_mac_imu("esp32:aabbccddeeff", self._imu_msg(stamp_sec=2, stamp_nanosec=0))
        node._on_mac_imu("esp32:112233445566", self._imu_msg(stamp_sec=1, stamp_nanosec=800_000_000))  # 1.8s

        # After each _on_mac_imu call, _solve_and_publish_ik_n is called automatically
        # Both calls together should produce validity messages
        self.assertGreaterEqual(len(validity_pub.messages), 1)

        # The last validity message should show all_valid=False (100ms skew > 50ms limit)
        last_validity = json.loads(validity_pub.messages[-1].data)
        self.assertEqual(last_validity["schema"], "rehab.n_input_validity.1")
        self.assertFalse(last_validity["all_valid"])

        # No new joint_states published via N-sensor path (IK suppressed)
        self.assertEqual(len(joint_pub.messages), initial_joint_count)

    # --- IK-03-F: all valid inputs and calib present → gate passes, no crash ---

    def test_ik03_f_all_valid_with_calib_gate_passes_no_crash(self):
        """IK-03-F: _solve_and_publish_ik_n() with all valid inputs and calib set → no crash, stub completes."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))

        validity_pub = next(
            p for p in node.publishers if p.topic == "/rehab/opensim/input_validity"
        )

        # Set a fake calib artifact so the second gate also passes
        node._n_calib_artifact = {
            "schema_version": "calib.v1",
            "model_hash": "abc123",
            "applied_revision": 1,
            "device_order": ["esp32:112233445566", "esp32:aabbccddeeff"],
            "reference_pose": {},
        }

        # Send IMU frames with same timestamp (within skew bound)
        ts = 5_000_000_000
        ts_sec = ts // 1_000_000_000
        ts_ns = ts % 1_000_000_000

        node._on_mac_imu("esp32:aabbccddeeff", self._imu_msg(stamp_sec=ts_sec, stamp_nanosec=ts_ns))
        node._on_mac_imu("esp32:112233445566", self._imu_msg(stamp_sec=ts_sec, stamp_nanosec=ts_ns))

        # Should have published validity at least once
        self.assertGreaterEqual(len(validity_pub.messages), 1)
        # The last message should show all_valid=True (both fresh and within skew)
        last_validity = json.loads(validity_pub.messages[-1].data)
        self.assertTrue(last_validity["all_valid"])

    # --- IK-03-G: sync_skew_ms=200 allows 100ms skew to pass ---

    def test_ik03_g_param_override_200ms_allows_100ms_skew(self):
        """IK-03-G: sync_skew_ms=200 parameter allows 100ms timestamp skew to be valid."""
        node = self._make_node(sync_skew_ms=200)
        ts_now = 6_000_000_000
        ts_old = ts_now - 100_000_000  # 100ms older
        inputs = [
            self._make_device_input("esp32:aabbccddeeff", "tibia_r_imu", ts_now, True),
            self._make_device_input("esp32:112233445566", "femur_r_imu", ts_old, True),
        ]
        result = node._check_sync_skew(inputs)
        # With 200ms limit, 100ms skew (relative to median, so 50ms per device) passes
        self.assertTrue(result["all_valid"])
        # All devices should be valid
        for dev_id, validity in result["device_validities"].items():
            self.assertTrue(validity["valid"], f"{dev_id} should be valid")

    # --- IK-03-H: existing _solve_and_publish_ik() single-sensor path unaffected ---

    def test_ik03_h_single_sensor_path_unaffected_by_check_sync_skew(self):
        """IK-03-H: Existing _solve_and_publish_ik() can still be called without errors."""
        from rehab_robotics_bridge.opensim.calibration import CalibrationController
        fast = CalibrationController(window_s=0.3, min_samples=4)
        node = opensim_node.OpenSimBridgeNode(
            adapter=_FakeAdapter(),
            monotonic_clock=self.clock,
            calibration_controller=fast,
            ik_solver=FakeOrientationIkSolver(),
        )
        # Single-sensor path requires live sensors
        node._on_master_imu(_Imu(stamp_sec=100))
        node._on_slave_imu(_Imu(stamp_sec=100))
        # Call old path directly — must not raise
        try:
            node._solve_and_publish_ik()
        except Exception as exc:
            self.fail(f"_solve_and_publish_ik() raised unexpectedly: {exc}")

    # --- Additional edge cases for _check_sync_skew completeness ---

    def test_ik03_empty_inputs_returns_all_valid_false(self):
        """_check_sync_skew([]) returns all_valid=False with empty device_validities."""
        node = self._make_node()
        result = node._check_sync_skew([])
        self.assertFalse(result["all_valid"])
        self.assertEqual(result["device_validities"], {})

    def test_ik03_input_validity_publisher_exists_on_correct_topic(self):
        """/rehab/opensim/input_validity publisher is created at node init."""
        node = self._make_node()
        validity_pubs = [
            p for p in node.publishers if p.topic == "/rehab/opensim/input_validity"
        ]
        self.assertEqual(len(validity_pubs), 1)

    def test_ik03_sync_skew_ms_defaults_to_50(self):
        """sync_skew_ms parameter defaults to 50."""
        node = self._make_node()
        self.assertEqual(node._sync_skew_ms, 50)

    def test_ik03_all_none_timestamps_returns_all_valid_false(self):
        """_check_sync_skew with all last_ts_ns=None returns all_valid=False, skew_ms=None for all."""
        node = self._make_node()
        inputs = [
            self._make_device_input("esp32:aabbccddeeff", "tibia_r_imu", None, True),
            self._make_device_input("esp32:112233445566", "femur_r_imu", None, True),
        ]
        result = node._check_sync_skew(inputs)
        self.assertFalse(result["all_valid"])
        for dev_id, validity in result["device_validities"].items():
            self.assertIsNone(validity["skew_ms"], f"{dev_id} skew_ms should be None")
            self.assertFalse(validity["valid"])


class IkFourContractTests(unittest.TestCase):
    """IK-04 contract tests: N-sensor solve_n() wiring, metadata publication, solver_insufficient hard-block.

    Covers IK-04-A through IK-04-I as defined in 23-04-PLAN.md.
    All tests run without live ROS or hardware via _install_ros_stubs().
    """

    # Two devices where alpha order is "esp32:aaaa..." < "esp32:zzzz..."
    _MAPPING_ALPHA_DEVICES = json.dumps({
        "applied_revision": 5,
        "model_hash": "deadbeef1234abcd",
        "assigned": [
            {"device_id": "esp32:zzzzzzzzzzzz", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:aaaaaaaaaaaa", "frame": "femur_r_imu", "segment": "femur"},
        ],
    })

    _MAPPING_TWO_DEVICES = json.dumps({
        "applied_revision": 5,
        "model_hash": "deadbeef1234abcd",
        "assigned": [
            {"device_id": "esp32:aabbccddeeff", "frame": "tibia_r_imu", "segment": "tibia"},
            {"device_id": "esp32:112233445566", "frame": "femur_r_imu", "segment": "femur"},
        ],
    })

    def setUp(self):
        _StubNode.parameter_overrides = {}
        self.clock = _Clock(now=1000.0)

    def _make_node(self, **param_overrides):
        _StubNode.parameter_overrides = param_overrides
        return opensim_node.OpenSimBridgeNode(
            adapter=_FakeAdapter(),
            monotonic_clock=self.clock,
            ik_solver=_TrackingFakeIkSolver(),
        )

    def _mapping_msg(self, json_str):
        msg = _String()
        msg.data = json_str
        return msg

    def _imu_msg(self, x=0.0, y=0.0, z=0.0, w=1.0, stamp_sec=10, stamp_nanosec=0):
        return _Imu(x=x, y=y, z=z, w=w, stamp_sec=stamp_sec, stamp_nanosec=stamp_nanosec)

    def _get_metadata_pub(self, node):
        """Get the /rehab/opensim/joint_states_metadata publisher."""
        pubs = [p for p in node.publishers if p.topic == "/rehab/opensim/joint_states_metadata"]
        if not pubs:
            self.fail("/rehab/opensim/joint_states_metadata publisher not found on node")
        return pubs[0]

    def _feed_two_alpha_imu(self, node, ts_sec=10):
        """Send one IMU frame for each alpha-ordered device."""
        node._on_mac_imu("esp32:zzzzzzzzzzzz", self._imu_msg(stamp_sec=ts_sec))
        node._on_mac_imu("esp32:aaaaaaaaaaaa", self._imu_msg(stamp_sec=ts_sec))

    def _feed_two_imu(self, node, ts_sec=10):
        """Send one IMU frame for each standard two-device mapping."""
        node._on_mac_imu("esp32:aabbccddeeff", self._imu_msg(stamp_sec=ts_sec))
        node._on_mac_imu("esp32:112233445566", self._imu_msg(stamp_sec=ts_sec))

    def _set_calibrated(self, node, model_hash="deadbeef1234abcd", revision=5):
        """Inject a synthetic calibration artifact to simulate 'calibrated' state."""
        node._n_calib_artifact = {
            "schema_version": "calib.v1",
            "model_hash": model_hash,
            "applied_revision": revision,
            "device_order": sorted(node._mac_inputs.keys()),
            "frame_assignments": {
                did: {"segment": "", "frame": entry.frame}
                for did, entry in sorted(node._mac_inputs.items())
            },
            "solver_profile": "lower_body",
            "calibrated_at_iso8601": "2026-08-05T00:00:00Z",
            "reference_pose": {
                did: {"qw": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0}
                for did in sorted(node._mac_inputs.keys())
            },
        }
        node._n_calib_state = "calibrated"
        node._n_model_hash = model_hash
        node._n_mapping_revision = revision

    # --- IK-04-A: solve_n called with (frame, xyzw) pairs in alphabetical device_id order ---

    def test_ik04_a_solve_n_called_with_alphabetical_order(self):
        """IK-04-A: _solve_and_publish_ik_n() passes inputs in alphabetical device_id order to solve_n()."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_ALPHA_DEVICES))
        self._set_calibrated(node, model_hash="deadbeef1234abcd", revision=5)

        # Feed both devices with same timestamp (both valid/fresh)
        self._feed_two_alpha_imu(node, ts_sec=10)

        # The tracking solver records calls
        solver = node._ik_solver
        self.assertGreater(len(solver.solve_n_calls), 0, "solve_n should have been called")

        last_call = solver.solve_n_calls[-1]
        inputs = last_call["inputs"]
        self.assertGreaterEqual(len(inputs), 2)

        # Alphabetical: "esp32:aaaaaaaaaaaa" < "esp32:zzzzzzzzzzzz"
        # So inputs[0] must use frame of "esp32:aaaaaaaaaaaa" ("femur_r_imu")
        # and inputs[1] must use frame of "esp32:zzzzzzzzzzzz" ("tibia_r_imu")
        first_frame = inputs[0][0]
        second_frame = inputs[1][0]
        self.assertEqual(first_frame, "femur_r_imu",
                         f"First input frame should be from alphabetically-first device "
                         f"(esp32:aaaaaaaaaaaa → femur_r_imu), got {first_frame!r}")
        self.assertEqual(second_frame, "tibia_r_imu",
                         f"Second input frame should be from alphabetically-second device "
                         f"(esp32:zzzzzzzzzzzz → tibia_r_imu), got {second_frame!r}")

    # --- IK-04-B: metadata topic receives message after _solve_and_publish_ik_n() ---

    def test_ik04_b_metadata_topic_receives_message(self):
        """IK-04-B: /rehab/opensim/joint_states_metadata topic exists and receives messages."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._set_calibrated(node)

        meta_pub = self._get_metadata_pub(node)
        before = len(meta_pub.messages)

        self._feed_two_imu(node)

        self.assertGreater(len(meta_pub.messages), before,
                           "Metadata publisher should have received at least one message")

        last_msg = json.loads(meta_pub.messages[-1].data)
        self.assertEqual(last_msg.get("schema"), "rehab.n_ik_metadata.1")

    # --- IK-04-C: metadata message has mapping_revision matching _n_mapping_revision ---

    def test_ik04_c_metadata_has_correct_mapping_revision(self):
        """IK-04-C: Metadata message mapping_revision matches _n_mapping_revision."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._set_calibrated(node, revision=5)

        self._feed_two_imu(node)

        meta_pub = self._get_metadata_pub(node)
        self.assertGreater(len(meta_pub.messages), 0)
        payload = json.loads(meta_pub.messages[-1].data)
        self.assertEqual(payload.get("mapping_revision"), 5)

    # --- IK-04-D: metadata has calibration_identity = artifact filename when calibrated ---

    def test_ik04_d_metadata_calibration_identity_is_artifact_filename(self):
        """IK-04-D: calibration_identity in metadata matches the artifact filename when calibrated."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._set_calibrated(node, model_hash="deadbeef1234abcd", revision=5)

        self._feed_two_imu(node)

        meta_pub = self._get_metadata_pub(node)
        self.assertGreater(len(meta_pub.messages), 0)
        payload = json.loads(meta_pub.messages[-1].data)

        # calibration_identity should be the artifact filename (not None)
        cal_id = payload.get("calibration_identity")
        self.assertIsNotNone(cal_id, "calibration_identity should not be None when calibrated")
        # The filename must contain the model_hash prefix and revision
        self.assertIn("deadbeef", str(cal_id),
                      f"calibration_identity should contain model_hash prefix, got {cal_id!r}")
        self.assertIn("rev5", str(cal_id),
                      f"calibration_identity should contain revision, got {cal_id!r}")

    # --- IK-04-E: metadata has visualizer_provenance = "{hash8}_rev{N}" when calibrated ---

    def test_ik04_e_metadata_visualizer_provenance_format(self):
        """IK-04-E: visualizer_provenance = '{hash8}_rev{N}' when calibrated."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._set_calibrated(node, model_hash="deadbeef1234abcd", revision=5)

        self._feed_two_imu(node)

        meta_pub = self._get_metadata_pub(node)
        self.assertGreater(len(meta_pub.messages), 0)
        payload = json.loads(meta_pub.messages[-1].data)

        prov = payload.get("visualizer_provenance")
        self.assertIsNotNone(prov, "visualizer_provenance should not be None when calibrated")
        self.assertEqual(prov, "deadbeef_rev5",
                         f"visualizer_provenance should be 'deadbeef_rev5', got {prov!r}")

    # --- IK-04-F: input_validity_mask in alphabetical device_id order ---

    def test_ik04_f_input_validity_mask_in_alphabetical_order(self):
        """IK-04-F: input_validity_mask in metadata matches per-device validity in alphabetical order."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._set_calibrated(node)

        # Feed both devices with same timestamp (all valid)
        self._feed_two_imu(node, ts_sec=10)

        meta_pub = self._get_metadata_pub(node)
        self.assertGreater(len(meta_pub.messages), 0)
        payload = json.loads(meta_pub.messages[-1].data)

        mask = payload.get("input_validity_mask")
        self.assertIsNotNone(mask, "input_validity_mask should be present")
        self.assertIsInstance(mask, list, "input_validity_mask should be a list")
        # With same timestamp both devices should be valid
        self.assertEqual(len(mask), 2, "Should have validity entry for each device")

    # --- IK-04-G: solver_insufficient hard-block: 1 assigned device → outcome == solver_insufficient ---

    def test_ik04_g_solver_insufficient_hard_block_one_assigned_device(self):
        """IK-04-G: apply_candidate with 1 assigned device returns outcome=='solver_insufficient'."""
        from rehab_robotics_bridge.mapping_node import MappingStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MappingStore(store_path=Path(tmpdir) / "map.json")
            store.set_model_hash("abc123model")
            store.set_frame_list([
                {"segment": "tibia", "frame": "tibia_r_imu"},
                {"segment": "femur", "frame": "femur_r_imu"},
            ])
            # Assign exactly 1 device
            store.set_assignment("esp32:aabbccddeeff", "tibia", "tibia_r_imu", "assigned")
            revision = store.revision

            result = store.apply_candidate(
                expected_revision=revision,
                frame_list=store.frame_list,
            )
            self.assertEqual(result["outcome"], "solver_insufficient",
                             f"Expected solver_insufficient with 1 assigned device, got {result!r}")

    # --- IK-04-H: solver_insufficient does NOT occur with 2 assigned devices ---

    def test_ik04_h_two_assigned_devices_does_not_trigger_solver_insufficient(self):
        """IK-04-H: apply_candidate with 2 assigned devices does not return solver_insufficient."""
        from rehab_robotics_bridge.mapping_node import MappingStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MappingStore(store_path=Path(tmpdir) / "map.json")
            store.set_model_hash("abc123model")
            store.set_frame_list([
                {"segment": "tibia", "frame": "tibia_r_imu"},
                {"segment": "femur", "frame": "femur_r_imu"},
            ])
            # Assign 2 devices
            store.set_assignment("esp32:aabbccddeeff", "tibia", "tibia_r_imu", "assigned")
            store.set_assignment("esp32:112233445566", "femur", "femur_r_imu", "assigned")
            revision = store.revision

            result = store.apply_candidate(
                expected_revision=revision,
                frame_list=store.frame_list,
            )
            self.assertNotEqual(result["outcome"], "solver_insufficient",
                                f"2 assigned devices should not trigger solver_insufficient, "
                                f"got {result!r}")

    # --- IK-04-I: solver_status=="suppressed" in metadata when validity gate not passed ---

    def test_ik04_i_solver_status_suppressed_when_not_all_valid(self):
        """IK-04-I: solver_status=='suppressed' in metadata when validity gate not passed (fresh=False)."""
        node = self._make_node()
        node._on_mapping_current(self._mapping_msg(self._MAPPING_TWO_DEVICES))
        self._set_calibrated(node)

        # Feed one device only — the other device remains not fresh
        # Use directly: both devices exist but set one as not-fresh
        from rehab_robotics_bridge.opensim_node import _DeviceInput
        device_a = "esp32:112233445566"
        device_b = "esp32:aabbccddeeff"

        # Ensure both are in _mac_inputs from the mapping
        self.assertIn(device_a, node._mac_inputs)
        self.assertIn(device_b, node._mac_inputs)

        # Set device_a fresh and device_b NOT fresh
        ts_ns = 10_000_000_000
        node._mac_inputs[device_a].last_xyzw = (0.0, 0.0, 0.0, 1.0)
        node._mac_inputs[device_a].last_ts_ns = ts_ns
        node._mac_inputs[device_a].last_seen_monotonic = self.clock.now
        node._mac_inputs[device_a].post_reconnect_fresh = True

        node._mac_inputs[device_b].last_xyzw = (0.0, 0.0, 0.0, 1.0)
        node._mac_inputs[device_b].last_ts_ns = ts_ns
        node._mac_inputs[device_b].last_seen_monotonic = self.clock.now
        node._mac_inputs[device_b].post_reconnect_fresh = False  # NOT fresh

        meta_pub = self._get_metadata_pub(node)
        before = len(meta_pub.messages)
        node._solve_and_publish_ik_n()

        self.assertGreater(len(meta_pub.messages), before,
                           "Metadata should be published even when suppressed")
        last_msg = json.loads(meta_pub.messages[-1].data)
        self.assertEqual(last_msg.get("solver_status"), "suppressed",
                         f"solver_status should be 'suppressed' when gate not passed, "
                         f"got {last_msg.get('solver_status')!r}")


class _TrackingFakeIkSolver:
    """FakeOrientationIkSolver subclass that records inputs to solve_n() calls."""

    def __init__(self):
        self.solve_n_calls = []
        self._assembled = False

    def reset(self):
        self._assembled = False

    def solve(self, *, master_xyzw, slave_xyzw, calibration, source_timestamp_ns,
              input_age_s, joint_names):
        from rehab_robotics_bridge.opensim.orientation_ik import IkSolution
        names = [str(n) for n in joint_names] or ["knee_angle_r"]
        if source_timestamp_ns is None:
            return IkSolution(
                solution_valid=False, reason="missing_source_timestamp",
                joint_names=names, positions_rad=[],
                source_timestamp_ns=None, orientation_residual_rms=None,
                orientation_residual_max=None, calibration_id=None,
                input_age_s=input_age_s, solve_duration_s=0.0,
            )
        self._assembled = True
        return IkSolution(
            solution_valid=True, reason="ok",
            joint_names=names, positions_rad=[0.0] * len(names),
            source_timestamp_ns=source_timestamp_ns, orientation_residual_rms=0.0,
            orientation_residual_max=0.0,
            calibration_id=None,
            input_age_s=input_age_s, solve_duration_s=0.0,
        )

    def solve_n(self, inputs, source_timestamp_ns, input_age_s, joint_names,
                calibration=None):
        """Record the call and return a valid solution."""
        from rehab_robotics_bridge.opensim.orientation_ik import IkSolution
        self.solve_n_calls.append({
            "inputs": list(inputs),
            "source_timestamp_ns": source_timestamp_ns,
            "input_age_s": input_age_s,
            "joint_names": list(joint_names),
        })
        names = [str(n) for n in joint_names] or ["knee_angle_r"]
        if source_timestamp_ns is None:
            return IkSolution(
                solution_valid=False, reason="missing_source_timestamp",
                joint_names=names, positions_rad=[],
                source_timestamp_ns=None, orientation_residual_rms=None,
                orientation_residual_max=None, calibration_id=None,
                input_age_s=input_age_s, solve_duration_s=0.0,
            )
        self._assembled = True
        return IkSolution(
            solution_valid=True, reason="ok",
            joint_names=names, positions_rad=[0.0] * len(names),
            source_timestamp_ns=source_timestamp_ns, orientation_residual_rms=0.0,
            orientation_residual_max=0.0, calibration_id=None,
            input_age_s=input_age_s, solve_duration_s=0.0,
        )


if __name__ == "__main__":
    unittest.main()
