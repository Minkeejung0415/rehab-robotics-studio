"""ROS-free publisher, cross-component, and launch source contracts."""
from __future__ import annotations

import ast
import math
from pathlib import Path
import types
import unittest

from backend.test import test_opensim_node as node_contracts


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


if __name__ == "__main__":
    unittest.main()
