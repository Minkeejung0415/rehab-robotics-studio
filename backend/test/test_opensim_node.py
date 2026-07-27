"""ROS-free contracts for the dual-IMU OpenSim bridge node."""
from __future__ import annotations

import json
import math
import sys
import types
import unittest
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

    def info(self, message):
        self.info_messages.append(message)

    def warning(self, message):
        self.warning_messages.append(message)


class _StubNode:
    parameter_overrides = {}

    def __init__(self, name):
        self.node_name = name
        self.parameters = {}
        self.subscriptions = []
        self.publishers = []
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

    def create_timer(self, period, callback):
        timer = types.SimpleNamespace(period=period, callback=callback)
        self.timers.append(timer)
        return timer

    def get_logger(self):
        return self.logger


class _Imu:
    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self.orientation = types.SimpleNamespace(x=x, y=y, z=z, w=w)


class _String:
    def __init__(self):
        self.data = ""


def _install_ros_stubs():
    backend_root = str(Path(__file__).parents[1])
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    rclpy = types.ModuleType("rclpy")
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = _StubNode
    rclpy.init = lambda args=None: None
    rclpy.spin = lambda node: None
    rclpy.try_shutdown = lambda: None
    sys.modules["rclpy"] = rclpy
    sys.modules["rclpy.node"] = rclpy.node

    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs.msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs.msg.Imu = _Imu
    sys.modules["sensor_msgs"] = sensor_msgs
    sys.modules["sensor_msgs.msg"] = sensor_msgs.msg

    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = types.ModuleType("std_msgs.msg")
    std_msgs.msg.String = _String
    sys.modules["std_msgs"] = std_msgs
    sys.modules["std_msgs.msg"] = std_msgs.msg


_install_ros_stubs()
from rehab_robotics_bridge import opensim_node  # noqa: E402
from rehab_robotics_bridge.opensim_adapter import (  # noqa: E402
    UnavailableVisualizerAdapter,
)


class _FakeAdapter:
    def __init__(self, *, accepted=True, available=True, reason=""):
        self.accepted = accepted
        self.calls = []
        self._status = {
            "available": available,
            "state": "ready" if available else "unavailable",
            "reason": reason,
        }

    def update_sensor(self, sensor_id, frame_name, rotation):
        self.calls.append((sensor_id, frame_name, rotation))
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
        self.assertEqual(len(node.subscriptions), 2)
        self.assertEqual(
            [subscription.topic for subscription in node.subscriptions],
            ["/esp32/master/imu", "/esp32/slave/imu"],
        )
        self.assertTrue(
            all(subscription.message_type is _Imu for subscription in node.subscriptions)
        )
        self.assertEqual(len(node.publishers), 1)
        self.assertEqual(node.publishers[0].topic, "/opensim/status")

    def test_parameter_overrides_control_topics_frames_model_timeout_and_status(self):
        _StubNode.parameter_overrides = {
            "master_imu_topic": "/custom/master",
            "slave_imu_topic": "/custom/slave",
            "master_frame": "pelvis_imu",
            "slave_frame": "torso_imu",
            "model_path": "model.osim",
            "stale_timeout_s": 2.5,
            "status_topic": "/custom/status",
        }
        factory_calls = []

        def factory(model_path, frame_mappings):
            factory_calls.append((model_path, frame_mappings))
            return _FakeAdapter()

        node = opensim_node.OpenSimBridgeNode(
            adapter_factory=factory,
            monotonic_clock=self.clock,
        )

        self.assertEqual(
            [subscription.topic for subscription in node.subscriptions],
            ["/custom/master", "/custom/slave"],
        )
        self.assertEqual(node.publishers[0].topic, "/custom/status")
        self.assertEqual(
            factory_calls,
            [("model.osim", {"master": "pelvis_imu", "slave": "torso_imu"})],
        )

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


if __name__ == "__main__":
    unittest.main()
