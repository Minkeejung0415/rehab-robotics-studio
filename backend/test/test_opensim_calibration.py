"""Deterministic unit tests for reference-pose CalibrationController (Phase 17)."""
from __future__ import annotations

import math
import unittest


class CalibrationControllerTests(unittest.TestCase):
    def _controller(self, **kwargs):
        from rehab_robotics_bridge.opensim.calibration import CalibrationController

        return CalibrationController(**kwargs)

    def test_new_controller_starts_uncalibrated_with_closed_gate(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            CalibrationState,
            may_publish_joint_states,
        )

        controller = self._controller()
        self.assertEqual(controller.state, CalibrationState.UNCALIBRATED)
        self.assertIsNone(controller.artifact)
        self.assertFalse(may_publish_joint_states(controller.state))

    def test_begin_capture_enters_capturing_and_needs_min_samples(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            CalibrationState,
            may_publish_joint_states,
        )

        controller = self._controller(window_s=1.5, min_samples=10)
        ok, message = controller.begin_capture()
        self.assertTrue(ok)
        self.assertEqual(controller.state, CalibrationState.CAPTURING)
        self.assertIn("captur", message.lower())

        identity = (0.0, 0.0, 0.0, 1.0)
        for i in range(5):
            state = controller.feed_pair(identity, identity, monotonic_time=10.0 + i * 0.05)
            self.assertEqual(state, CalibrationState.CAPTURING)
        self.assertIsNone(controller.artifact)
        self.assertFalse(may_publish_joint_states(controller.state))

    def test_stable_identity_window_yields_calibrated_artifact(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            CalibrationState,
            may_publish_joint_states,
        )

        controller = self._controller(window_s=1.5, min_samples=10)
        controller.begin_capture()
        identity = (0.0, 0.0, 0.0, 1.0)
        t0 = 20.0
        state = CalibrationState.CAPTURING
        for i in range(12):
            state = controller.feed_pair(
                identity,
                identity,
                monotonic_time=t0 + i * 0.15,
            )
        self.assertEqual(state, CalibrationState.CALIBRATED)
        self.assertEqual(controller.state, CalibrationState.CALIBRATED)
        artifact = controller.artifact
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact.known_pose, "standing_knees_extended")
        self.assertEqual(len(artifact.master_xyzw), 4)
        self.assertEqual(len(artifact.slave_xyzw), 4)
        self.assertAlmostEqual(math.hypot(*artifact.master_xyzw), 1.0, places=6)
        self.assertAlmostEqual(math.hypot(*artifact.slave_xyzw), 1.0, places=6)
        self.assertTrue(may_publish_joint_states(controller.state))
        status = controller.status_dict()
        self.assertEqual(status["state"], "CALIBRATED")
        self.assertTrue(status["has_offsets"])
        self.assertEqual(status["known_pose"], "standing_knees_extended")
        self.assertIsNotNone(status["calibration_id"])

    def test_unstable_window_fails_without_prior_artifact(self):
        from rehab_robotics_bridge.opensim.calibration import DEFAULT_MAX_DISPERSION_DEG
        from rehab_robotics_bridge.opensim.ik_contracts import (
            CalibrationState,
            may_publish_joint_states,
        )

        controller = self._controller(
            window_s=1.5,
            min_samples=10,
            max_dispersion_deg=DEFAULT_MAX_DISPERSION_DEG,
        )
        controller.begin_capture()
        identity = (0.0, 0.0, 0.0, 1.0)
        # ~45 deg yaw about Z — far above 8 deg dispersion threshold
        yaw = (0.0, 0.0, math.sin(math.radians(22.5)), math.cos(math.radians(22.5)))
        t0 = 30.0
        state = controller.feed_pair(identity, identity, monotonic_time=t0)
        self.assertEqual(state, CalibrationState.CAPTURING)
        state = controller.feed_pair(yaw, identity, monotonic_time=t0 + 0.1)
        self.assertEqual(state, CalibrationState.FAILED)
        reason = controller.status_dict()["reason"]
        self.assertTrue(
            any(token in reason.lower() for token in ("stability", "dispersion", "motion")),
            msg=f"expected stability/dispersion language in reason: {reason!r}",
        )
        self.assertIsNone(controller.artifact)
        self.assertFalse(may_publish_joint_states(controller.state))

    def test_clear_from_calibrated_invalidates_offsets(self):
        from rehab_robotics_bridge.opensim.ik_contracts import (
            CalibrationState,
            may_publish_joint_states,
        )

        controller = self._controller(window_s=0.5, min_samples=5)
        controller.begin_capture()
        identity = (0.0, 0.0, 0.0, 1.0)
        for i in range(8):
            controller.feed_pair(identity, identity, monotonic_time=40.0 + i * 0.1)
        self.assertEqual(controller.state, CalibrationState.CALIBRATED)
        controller.clear()
        self.assertEqual(controller.state, CalibrationState.UNCALIBRATED)
        self.assertIsNone(controller.artifact)
        self.assertFalse(may_publish_joint_states(controller.state))

    def test_begin_capture_while_capturing_is_rejected(self):
        controller = self._controller()
        self.assertTrue(controller.begin_capture()[0])
        ok, message = controller.begin_capture()
        self.assertFalse(ok)
        self.assertTrue(message)

    def test_first_frame_alone_never_calibrates(self):
        from rehab_robotics_bridge.opensim.ik_contracts import CalibrationState

        controller = self._controller(window_s=1.5, min_samples=10)
        controller.begin_capture()
        identity = (0.0, 0.0, 0.0, 1.0)
        state = controller.feed_pair(identity, identity, monotonic_time=50.0)
        self.assertEqual(state, CalibrationState.CAPTURING)
        self.assertIsNone(controller.artifact)
        self.assertNotEqual(state, CalibrationState.CALIBRATED)


if __name__ == "__main__":
    unittest.main()
