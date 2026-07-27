"""ROS-free publisher, cross-component, and launch source contracts."""
from __future__ import annotations

import ast
import math
from pathlib import Path
import types
import unittest

if __package__ == "backend.test":
    from backend.test import test_opensim_node as node_contracts
else:
    import test_opensim_node as node_contracts


ROOT = Path(__file__).parents[2]
SETUP_PATH = ROOT / "backend" / "setup.py"
LAUNCH_PATH = ROOT / "backend" / "launch" / "rehab_robotics.launch.py"


class _StampClock:
    def __init__(self):
        self.sequence = 0

    def now(self):
        self.sequence += 1
        return types.SimpleNamespace(
            to_msg=lambda: types.SimpleNamespace(
                sec=self.sequence,
                nanosec=self.sequence * 100,
            )
        )


def _get_clock(node):
    if not hasattr(node, "_test_stamp_clock"):
        node._test_stamp_clock = _StampClock()
    return node._test_stamp_clock


node_contracts._StubNode.get_clock = _get_clock

from rehab_robotics_bridge import opensim_test_publisher  # noqa: E402
from rehab_robotics_bridge import opensim_node  # noqa: E402


class OpenSimTestPublisherContractTests(unittest.TestCase):
    def setUp(self):
        node_contracts._StubNode.parameter_overrides = {}

    def test_known_orientations_are_exact_repeatable_native_imu_messages(self):
        first = opensim_test_publisher.known_orientations()
        second = opensim_test_publisher.known_orientations()

        self.assertEqual(set(first), {"master", "slave"})
        self.assertIsNot(first["master"], second["master"])
        self.assertEqual(
            (
                first["master"].orientation.x,
                first["master"].orientation.y,
                first["master"].orientation.z,
                first["master"].orientation.w,
            ),
            (0.0, 0.0, 0.0, 1.0),
        )
        self.assertEqual(
            (
                first["slave"].orientation.x,
                first["slave"].orientation.y,
                first["slave"].orientation.z,
                first["slave"].orientation.w,
            ),
            (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5)),
        )
        self.assertEqual(first["master"].header.frame_id, "opensim_test_master")
        self.assertEqual(first["slave"].header.frame_id, "opensim_test_slave")

    def test_publisher_overrides_topics_and_rate_and_refreshes_timestamps(self):
        node_contracts._StubNode.parameter_overrides = {
            "master_imu_topic": "/test/master",
            "slave_imu_topic": "/test/slave",
            "publish_rate_hz": 4.0,
        }
        node = opensim_test_publisher.OpenSimTestPublisher()

        self.assertEqual(
            [publisher.topic for publisher in node.publishers],
            ["/test/master", "/test/slave"],
        )
        self.assertEqual(len(node.timers), 1)
        self.assertAlmostEqual(node.timers[0].period, 0.25)

        node.timers[0].callback()
        first_master = node.publishers[0].messages[-1]
        first_slave = node.publishers[1].messages[-1]
        node.timers[0].callback()
        second_master = node.publishers[0].messages[-1]
        second_slave = node.publishers[1].messages[-1]

        self.assertEqual(len(node.publishers[0].messages), 2)
        self.assertEqual(len(node.publishers[1].messages), 2)
        self.assertEqual(first_master.header.stamp, first_slave.header.stamp)
        self.assertEqual(second_master.header.stamp, second_slave.header.stamp)
        self.assertNotEqual(first_master.header.stamp, second_master.header.stamp)
        self.assertEqual(first_master.header.frame_id, "opensim_test_master")
        self.assertEqual(first_slave.header.frame_id, "opensim_test_slave")

    def test_setup_adds_publisher_without_removing_existing_console_scripts(self):
        setup_source = SETUP_PATH.read_text(encoding="utf-8")
        required_entries = (
            "esp32_bridge_node = rehab_robotics_bridge.esp32_bridge_node:main",
            "esp_filter = rehab_robotics_bridge.filter_node:main",
            "opensim_bridge = rehab_robotics_bridge.opensim_node:main",
            "esp_record = rehab_robotics_bridge.recorder_node:main",
            "esp_status = rehab_robotics_bridge.status_node:main",
            "processing_block_observer = "
            "rehab_robotics_bridge.processing_block_observer:main",
            "opensim_test_publisher = "
            "rehab_robotics_bridge.opensim_test_publisher:main",
        )
        for entry in required_entries:
            with self.subTest(entry=entry):
                self.assertIn(entry, setup_source)
        ast.parse(setup_source)


class OpenSimPublisherBridgeIntegrationTests(unittest.TestCase):
    def setUp(self):
        node_contracts._StubNode.parameter_overrides = {
            "master_imu_topic": "/verification/master",
            "slave_imu_topic": "/verification/slave",
            "master_frame": "custom_master_frame",
            "slave_frame": "custom_slave_frame",
            "model_path": "verification.osim",
            "status_topic": "/verification/opensim/status",
            "stale_timeout_s": 2.0,
        }
        self.clock = node_contracts._Clock(now=20.0)
        self.adapter = node_contracts._FakeAdapter(
            available=True,
            reason="fake_visualizer",
        )
        self.node = opensim_node.OpenSimBridgeNode(
            adapter=self.adapter,
            monotonic_clock=self.clock,
        )

    def test_exact_publisher_messages_cross_both_configured_bridge_paths(self):
        messages = opensim_test_publisher.known_orientations()

        self.node._on_master_imu(messages["master"])
        self.assertEqual(len(self.adapter.calls), 1)
        master_role, master_frame, master_rotation = self.adapter.calls[0]
        self.assertEqual(
            (master_role, master_frame),
            ("master", "custom_master_frame"),
        )
        self.assertEqual(master_rotation.scalar_first, (1.0, 0.0, 0.0, 0.0))
        self.assertEqual(
            master_rotation.matrix,
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        )
        master_after_first = self.node.status_snapshot()["sensors"]["master"]
        slave_before_update = self.node.status_snapshot()["sensors"]["slave"]
        self.assertEqual(master_after_first["state"], "live")
        self.assertEqual(master_after_first["updates"], 1)
        self.assertEqual(slave_before_update["state"], "waiting")
        self.assertEqual(slave_before_update["updates"], 0)

        self.clock.now = 20.5
        self.node._on_slave_imu(messages["slave"])
        self.assertEqual(len(self.adapter.calls), 2)
        slave_role, slave_frame, slave_rotation = self.adapter.calls[1]
        self.assertEqual(
            (slave_role, slave_frame),
            ("slave", "custom_slave_frame"),
        )
        self.assertEqual(
            slave_rotation.scalar_first,
            (math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)),
        )
        expected_90z = (
            (0.0, -1.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        )
        for actual_row, expected_row in zip(
            slave_rotation.matrix,
            expected_90z,
        ):
            for actual, expected in zip(actual_row, expected_row):
                self.assertAlmostEqual(actual, expected)

        status = self.node.status_snapshot()
        self.assertTrue(status["visualization"]["available"])
        self.assertEqual(status["visualization"]["reason"], "fake_visualizer")
        self.assertEqual(status["sensors"]["master"]["state"], "live")
        self.assertEqual(status["sensors"]["master"]["updates"], 1)
        self.assertAlmostEqual(status["sensors"]["master"]["age_s"], 0.5)
        self.assertEqual(status["sensors"]["slave"]["state"], "live")
        self.assertEqual(status["sensors"]["slave"]["updates"], 1)
        self.assertAlmostEqual(status["sensors"]["slave"]["age_s"], 0.0)

        slave_call = self.adapter.calls[1]
        slave_state = dict(status["sensors"]["slave"])
        self.clock.now = 20.75
        self.node._on_master_imu(messages["master"])
        updated_status = self.node.status_snapshot()
        self.assertEqual(self.adapter.calls[1], slave_call)
        self.assertEqual(updated_status["sensors"]["slave"]["updates"], 1)
        self.assertEqual(
            updated_status["sensors"]["slave"]["last_error"],
            slave_state["last_error"],
        )
        self.assertEqual(updated_status["sensors"]["master"]["updates"], 2)


class OpenSimLaunchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = LAUNCH_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_launch_declares_locked_live_link_defaults(self):
        expected = {
            "master_imu_topic": "/esp32/master/imu",
            "slave_imu_topic": "/esp32/slave/imu",
            "master_frame": "femur_r_imu",
            "slave_frame": "tibia_r_imu",
            "model_path": "",
            "stale_timeout_s": "1.0",
            "status_topic": "/opensim/status",
            "enable_opensim_bridge": "true",
            "enable_opensim_test_publisher": "false",
        }
        declared = {}
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            if not (
                isinstance(node.func, ast.Name)
                and node.func.id == "DeclareLaunchArgument"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                continue
            default = next(
                (
                    keyword.value.value
                    for keyword in node.keywords
                    if keyword.arg == "default_value"
                    and isinstance(keyword.value, ast.Constant)
                ),
                None,
            )
            declared[node.args[0].value] = default
        for name, default in expected.items():
            with self.subTest(argument=name):
                self.assertEqual(declared.get(name), default)

    def test_bridge_and_default_off_publisher_wire_exact_topic_parameters(self):
        for parameter in (
            "master_imu_topic",
            "slave_imu_topic",
            "master_frame",
            "slave_frame",
            "model_path",
            "stale_timeout_s",
            "status_topic",
        ):
            with self.subTest(parameter=parameter):
                self.assertIn(
                    f"'{parameter}': LaunchConfiguration('{parameter}')",
                    self.source,
                )
        self.assertIn("executable='opensim_bridge'", self.source)
        self.assertIn(
            "condition=IfCondition(LaunchConfiguration('enable_opensim_bridge'))",
            self.source,
        )
        self.assertIn("executable='opensim_test_publisher'", self.source)
        self.assertIn(
            "condition=IfCondition("
            "LaunchConfiguration('enable_opensim_test_publisher'))",
            self.source,
        )

    def test_unrelated_nodes_are_retained_and_legacy_opensim_udp_is_removed(self):
        for executable in (
            "esp32_bridge_node",
            "esp_filter",
            "esp_record",
            "esp_status",
            "processing_block_observer",
            "rosbridge_websocket",
        ):
            with self.subTest(executable=executable):
                self.assertIn(f"executable='{executable}'", self.source)
        self.assertNotIn("opensim_udp_host", self.source)
        self.assertNotIn("opensim_udp_port", self.source)
        self.assertNotIn("'filtered_topic': '/esp/filtered/master'", self.source)


if __name__ == "__main__":
    unittest.main()
