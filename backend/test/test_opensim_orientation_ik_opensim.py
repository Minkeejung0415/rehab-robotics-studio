"""OpenSim-binding tests for orientation IK factory (Phase 18-02).

Always-on factory negative paths run without OpenSim. Real solve fixtures
are skipUnless opensim is importable.
"""
from __future__ import annotations

import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

from rehab_robotics_bridge.opensim.calibration import CalibrationArtifact
from rehab_robotics_bridge.opensim.opensim_orientation_ik import (
    create_orientation_ik_solver,
    probe_opensim_orientation_ik_apis,
)
from rehab_robotics_bridge.opensim.orientation_ik import (
    FakeOrientationIkSolver,
    UnavailableOrientationIkSolver,
)


def _identity_artifact() -> CalibrationArtifact:
    identity = (0.0, 0.0, 0.0, 1.0)
    return CalibrationArtifact(
        calibration_id="osim-cal",
        known_pose="standing_knees_extended",
        master_xyzw=identity,
        slave_xyzw=identity,
        captured_at_monotonic=1.0,
        sample_count=10,
        window_s=1.5,
        mean_dispersion_deg=0.1,
    )


def _quat_about_z(angle_rad: float) -> tuple[float, float, float, float]:
    half = angle_rad / 2.0
    return (0.0, 0.0, math.sin(half), math.cos(half))


class FactoryAlwaysOnTests(unittest.TestCase):
    def test_empty_model_path_unavailable(self):
        solver = create_orientation_ik_solver(
            model_path="",
            master_frame="femur_r_imu",
            slave_frame="tibia_r_imu",
            coordinate_paths=["knee_angle_r"],
        )
        self.assertIsInstance(solver, UnavailableOrientationIkSolver)
        solution = solver.solve(
            master_xyzw=(0.0, 0.0, 0.0, 1.0),
            slave_xyzw=(0.0, 0.0, 0.0, 1.0),
            calibration=_identity_artifact(),
            source_timestamp_ns=1,
            input_age_s=0.0,
            joint_names=["knee_angle_r"],
        )
        self.assertFalse(solution.solution_valid)
        self.assertIn("model_path_empty", solution.reason)

    def test_missing_model_file_unavailable(self):
        solver = create_orientation_ik_solver(
            model_path=str(Path(tempfile.gettempdir()) / "no-such-opensim-model.osim"),
            master_frame="femur_r_imu",
            slave_frame="tibia_r_imu",
            coordinate_paths=["knee_angle_r"],
        )
        self.assertIsInstance(solver, UnavailableOrientationIkSolver)
        solution = solver.solve(
            master_xyzw=(0.0, 0.0, 0.0, 1.0),
            slave_xyzw=(0.0, 0.0, 0.0, 1.0),
            calibration=_identity_artifact(),
            source_timestamp_ns=1,
            input_age_s=0.0,
            joint_names=["knee_angle_r"],
        )
        self.assertFalse(solution.solution_valid)
        self.assertIn("model_path_not_found", solution.reason)

    def test_factory_never_returns_fake(self):
        solver = create_orientation_ik_solver(
            model_path="",
            master_frame="femur_r_imu",
            slave_frame="tibia_r_imu",
            coordinate_paths=["knee_angle_r"],
        )
        self.assertNotIsInstance(solver, FakeOrientationIkSolver)


def _write_ik_runtime_model(opensim, temp_dir: str) -> str:
    """Minimal pin-joint model with knee_angle_r and IMU frames."""

    model_path = str(Path(temp_dir) / "ik-smoke.osim")
    model = opensim.Model()
    model.setName("ik_smoke")

    tibia = opensim.Body(
        "tibia_r",
        1.0,
        opensim.Vec3(0),
        opensim.Inertia(0.01, 0.01, 0.01),
    )
    model.addBody(tibia)

    pin = opensim.PinJoint(
        "knee_r",
        model.getGround(),
        opensim.Vec3(0),
        opensim.Vec3(0),
        tibia,
        opensim.Vec3(0, 0.4, 0),
        opensim.Vec3(0),
    )
    # Rename the PinJoint coordinate to the product name when possible.
    coord = pin.upd_coordinates(0)
    coord.setName("knee_angle_r")
    model.addJoint(pin)

    for name, parent, offset in (
        ("femur_r_imu", model.getGround(), opensim.Vec3(0.1, 0.0, 0.0)),
        ("tibia_r_imu", tibia, opensim.Vec3(0.0, 0.2, 0.0)),
    ):
        frame = opensim.PhysicalOffsetFrame()
        frame.setName(name)
        frame.connectSocket_parent(parent)
        frame.set_translation(offset)
        if parent is model.getGround():
            model.addComponent(frame)
        else:
            tibia.addComponent(frame)

    model.finalizeConnections()
    model.printToXML(model_path)
    return model_path


@unittest.skipUnless(
    importlib.util.find_spec("opensim") is not None,
    "opensim module is not installed",
)
class OpenSimOrientationIkBindingTests(unittest.TestCase):
    def test_probe_reports_required_keys(self):
        import opensim

        probe = probe_opensim_orientation_ik_apis(opensim)
        self.assertIsInstance(probe, dict)
        for key in (
            "InverseKinematicsSolver",
            "OrientationsReference",
            "BufferedOrientationsReference",
        ):
            self.assertIn(key, probe)
            self.assertIsInstance(probe[key], bool)

    def test_factory_or_real_solve_when_apis_present(self):
        import opensim

        probe = probe_opensim_orientation_ik_apis(opensim)
        required = probe.get("InverseKinematicsSolver") and probe.get(
            "OrientationsReference"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = _write_ik_runtime_model(opensim, temp_dir)
            solver = create_orientation_ik_solver(
                model_path=model_path,
                master_frame="femur_r_imu",
                slave_frame="tibia_r_imu",
                coordinate_paths=["knee_angle_r"],
                opensim_module=opensim,
            )
            if not required:
                self.assertIsInstance(solver, UnavailableOrientationIkSolver)
                solution = solver.solve(
                    master_xyzw=(0.0, 0.0, 0.0, 1.0),
                    slave_xyzw=(0.0, 0.0, 0.0, 1.0),
                    calibration=_identity_artifact(),
                    source_timestamp_ns=1,
                    input_age_s=0.0,
                    joint_names=["knee_angle_r"],
                )
                self.assertFalse(solution.solution_valid)
                self.assertTrue(
                    "opensim_ik_api_unavailable" in solution.reason
                    or "missing_" in solution.reason,
                    msg=f"probe={probe} reason={solution.reason}",
                )
                return

            artifact = _identity_artifact()
            identity = solver.solve(
                master_xyzw=(0.0, 0.0, 0.0, 1.0),
                slave_xyzw=(0.0, 0.0, 0.0, 1.0),
                calibration=artifact,
                source_timestamp_ns=10,
                input_age_s=0.01,
                joint_names=["knee_angle_r"],
            )
            flexed = solver.solve(
                master_xyzw=(0.0, 0.0, 0.0, 1.0),
                slave_xyzw=_quat_about_z(math.pi / 2.0),
                calibration=artifact,
                source_timestamp_ns=20,
                input_age_s=0.01,
                joint_names=["knee_angle_r"],
            )
            self.assertTrue(identity.solution_valid, msg=identity.reason)
            self.assertTrue(flexed.solution_valid, msg=flexed.reason)
            self.assertGreater(
                flexed.positions_rad[0] - identity.positions_rad[0],
                0.2,
            )
            self.assertGreater(flexed.positions_rad[0], 0.0)

    def test_runtime_skeleton_uses_bone_meshes_and_equal_sensor_sensitivity(self):
        import opensim

        model_path = (
            Path(__file__).resolve().parents[2]
            / "examples"
            / "opensim_quaternion_demo.osim"
        )
        self.assertTrue(model_path.is_file())
        model_xml = model_path.read_text(encoding="utf-8")
        self.assertIn("rehab_lower_limb_skeleton_live_link", model_xml)
        for mesh_file in (
            "r_pelvis.vtp",
            "femur_r.vtp",
            "tibia_r.vtp",
        ):
            self.assertIn(f"<mesh_file>{mesh_file}</mesh_file>", model_xml)

        artifact = _identity_artifact()
        identity = (0.0, 0.0, 0.0, 1.0)

        def solve_changed(
            master_xyzw,
            slave_xyzw,
        ) -> float:
            solver = create_orientation_ik_solver(
                model_path=str(model_path),
                master_frame="femur_r_imu",
                slave_frame="tibia_r_imu",
                coordinate_paths=["knee_angle_r"],
                opensim_module=opensim,
            )
            baseline = solver.solve(
                master_xyzw=identity,
                slave_xyzw=identity,
                calibration=artifact,
                source_timestamp_ns=10,
                input_age_s=0.01,
                joint_names=["knee_angle_r"],
            )
            changed = solver.solve(
                master_xyzw=master_xyzw,
                slave_xyzw=slave_xyzw,
                calibration=artifact,
                source_timestamp_ns=20,
                input_age_s=0.01,
                joint_names=["knee_angle_r"],
            )
            self.assertTrue(baseline.solution_valid, baseline.reason)
            self.assertTrue(changed.solution_valid, changed.reason)
            return changed.positions_rad[0] - baseline.positions_rad[0]

        rotation = _quat_about_z(math.radians(30.0))
        slave_delta = solve_changed(identity, rotation)
        master_delta = solve_changed(rotation, identity)

        self.assertGreater(slave_delta, 0.4)
        self.assertLess(master_delta, -0.4)
        self.assertAlmostEqual(
            abs(master_delta),
            abs(slave_delta),
            delta=0.05,
        )


if __name__ == "__main__":
    unittest.main()
