"""Machine-checkable OpenSim IK ROS contract constants (Phase 16 — contracts only)."""
from __future__ import annotations

import unittest


class IkContractsImportTests(unittest.TestCase):
    def test_locked_joint_states_topic_and_type(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            JOINT_STATES_MSG_TYPE,
            JOINT_STATES_TOPIC,
        )

        self.assertEqual(JOINT_STATES_TOPIC, "/opensim/joint_states")
        self.assertEqual(JOINT_STATES_MSG_TYPE, "sensor_msgs/msg/JointState")

    def test_calibration_service_names(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            CALIBRATION_CAPTURE_SERVICE,
            CALIBRATION_CLEAR_SERVICE,
        )

        self.assertEqual(
            CALIBRATION_CAPTURE_SERVICE,
            "/opensim/calibration/capture",
        )
        self.assertEqual(
            CALIBRATION_CLEAR_SERVICE,
            "/opensim/calibration/clear",
        )

    def test_calibration_states_include_required_values(self):
        from rehab_robotics_bridge.opensim.ik_contracts import CalibrationState

        self.assertEqual(CalibrationState.UNCALIBRATED, "UNCALIBRATED")
        self.assertEqual(CalibrationState.CAPTURING, "CAPTURING")
        self.assertEqual(CalibrationState.CALIBRATED, "CALIBRATED")
        self.assertEqual(CalibrationState.FAILED, "FAILED")

    def test_may_publish_joint_states_only_when_calibrated(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            CalibrationState,
            may_publish_joint_states,
        )

        self.assertTrue(may_publish_joint_states(CalibrationState.CALIBRATED))
        for state in (
            CalibrationState.UNCALIBRATED,
            CalibrationState.CAPTURING,
            CalibrationState.FAILED,
        ):
            with self.subTest(state=state):
                self.assertFalse(may_publish_joint_states(state))

    def test_deprecated_product_joint_angle_topic_is_not_joint_states(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            JOINT_STATES_TOPIC,
            PRODUCT_JOINT_ANGLE_TOPIC,
        )

        self.assertEqual(PRODUCT_JOINT_ANGLE_TOPIC, "/opensim/joint_angle")
        self.assertNotEqual(PRODUCT_JOINT_ANGLE_TOPIC, JOINT_STATES_TOPIC)


if __name__ == "__main__":
    unittest.main()
