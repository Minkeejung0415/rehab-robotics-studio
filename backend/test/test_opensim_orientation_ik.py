"""ROS-free TDD for Orientation IK seam (Phase 18-01)."""
from __future__ import annotations

import math
import unittest

from rehab_robotics_bridge.opensim.calibration import CalibrationArtifact
from rehab_robotics_bridge.opensim.orientation_ik import (
    FakeOrientationIkSolver,
    UnavailableOrientationIkSolver,
    apply_mounting_offsets,
)


def _identity_artifact() -> CalibrationArtifact:
    identity = (0.0, 0.0, 0.0, 1.0)
    return CalibrationArtifact(
        calibration_id="test-cal-id",
        known_pose="standing_knees_extended",
        master_xyzw=identity,
        slave_xyzw=identity,
        captured_at_monotonic=1.0,
        sample_count=10,
        window_s=1.5,
        mean_dispersion_deg=0.1,
    )


def _quat_about_x(angle_rad: float) -> tuple[float, float, float, float]:
    """ROS xyzw quaternion for rotation about +X (Fake flexion axis)."""
    half = angle_rad / 2.0
    return (math.sin(half), 0.0, 0.0, math.cos(half))


class UnavailableOrientationIkSolverTests(unittest.TestCase):
    def test_solve_never_valid_and_no_publish_positions(self):
        solver = UnavailableOrientationIkSolver("opensim_ik_api_unavailable")
        solution = solver.solve(
            master_xyzw=(0.0, 0.0, 0.0, 1.0),
            slave_xyzw=(0.0, 0.0, 0.0, 1.0),
            calibration=_identity_artifact(),
            source_timestamp_ns=1_000_000_000,
            input_age_s=0.01,
            joint_names=["knee_angle_r"],
        )
        self.assertFalse(solution.solution_valid)
        self.assertEqual(solution.reason, "opensim_ik_api_unavailable")
        # Never invent positions suitable for JointState publish.
        self.assertEqual(solution.positions_rad, [])


class FakeOrientationIkSolverTests(unittest.TestCase):
    def test_without_calibration_invalid(self):
        solver = FakeOrientationIkSolver()
        solution = solver.solve(
            master_xyzw=(0.0, 0.0, 0.0, 1.0),
            slave_xyzw=(0.0, 0.0, 0.0, 1.0),
            calibration=None,
            source_timestamp_ns=1_000_000_000,
            input_age_s=0.01,
            joint_names=["knee_angle_r"],
        )
        self.assertFalse(solution.solution_valid)
        self.assertIn("calibration", solution.reason.lower())

    def test_identity_corrected_pair_zero_knee(self):
        solver = FakeOrientationIkSolver()
        artifact = _identity_artifact()
        identity = (0.0, 0.0, 0.0, 1.0)
        solution = solver.solve(
            master_xyzw=identity,
            slave_xyzw=identity,
            calibration=artifact,
            source_timestamp_ns=2_000_000_000,
            input_age_s=0.02,
            joint_names=["knee_angle_r"],
        )
        self.assertTrue(solution.solution_valid)
        self.assertEqual(solution.joint_names, ["knee_angle_r"])
        self.assertEqual(len(solution.positions_rad), 1)
        self.assertAlmostEqual(solution.positions_rad[0], 0.0, places=6)
        self.assertEqual(solution.source_timestamp_ns, 2_000_000_000)
        self.assertEqual(solution.calibration_id, "test-cal-id")

    def test_flexed_fixture_positive_pi_over_2(self):
        """Slave +90° about +X after offset correction → knee_angle_r ≈ +π/2."""
        solver = FakeOrientationIkSolver()
        artifact = _identity_artifact()
        master = (0.0, 0.0, 0.0, 1.0)
        slave = _quat_about_x(math.pi / 2.0)
        solution = solver.solve(
            master_xyzw=master,
            slave_xyzw=slave,
            calibration=artifact,
            source_timestamp_ns=3_000_000_000,
            input_age_s=0.03,
            joint_names=["knee_angle_r"],
        )
        self.assertTrue(solution.solution_valid)
        self.assertAlmostEqual(
            solution.positions_rad[0],
            math.pi / 2.0,
            delta=1e-3,
        )
        self.assertGreater(solution.positions_rad[0], 0.0)

    def test_reset_callable_and_solve_still_works(self):
        solver = FakeOrientationIkSolver()
        solver.reset()
        artifact = _identity_artifact()
        solution = solver.solve(
            master_xyzw=(0.0, 0.0, 0.0, 1.0),
            slave_xyzw=(0.0, 0.0, 0.0, 1.0),
            calibration=artifact,
            source_timestamp_ns=4_000_000_000,
            input_age_s=0.0,
            joint_names=["knee_angle_r"],
        )
        self.assertTrue(solution.solution_valid)


class MountingOffsetTests(unittest.TestCase):
    def test_identity_mounts_leave_orientations_unchanged(self):
        identity = (0.0, 0.0, 0.0, 1.0)
        artifact = _identity_artifact()
        master_in = (0.1, 0.2, 0.3, 0.9)
        # Normalize via solve path expectation — offsets with identity mounts.
        master_corr, slave_corr = apply_mounting_offsets(
            master_in,
            identity,
            artifact,
        )
        # Identity mount: q_corr = q_sensor ⊗ conjugate(I) = q_sensor (unit).
        from rehab_robotics_bridge.opensim_adapter import ros_xyzw_to_opensim_rotation

        expected = ros_xyzw_to_opensim_rotation(*master_in)
        w, x, y, z = expected.scalar_first
        expected_xyzw = (x, y, z, w)
        for a, b in zip(master_corr, expected_xyzw):
            self.assertAlmostEqual(a, b, delta=1e-9)
        for a, b in zip(slave_corr, identity):
            self.assertAlmostEqual(a, b, delta=1e-9)


class ModuleContractTests(unittest.TestCase):
    def test_orientation_ik_does_not_import_relative_orientation_angle_deg(self):
        import pathlib

        path = (
            pathlib.Path(__file__).parents[1]
            / "rehab_robotics_bridge"
            / "opensim"
            / "orientation_ik.py"
        )
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("relative_orientation_angle_deg", source)


if __name__ == "__main__":
    unittest.main()
