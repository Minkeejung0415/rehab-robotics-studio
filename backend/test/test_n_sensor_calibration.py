"""ROS-free contract tests for CalibrationArtifactStore (IK-02).

All tests are offline — no live ROS, no live filesystem except for
tempfile.TemporaryDirectory isolation.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make sure the backend package is importable
backend_root = str(Path(__file__).parents[1])
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from rehab_robotics_bridge.opensim.n_sensor_calibration import CalibrationArtifactStore


class CalibrationArtifactStoreBasicTests(unittest.TestCase):
    """Basic contract tests for CalibrationArtifactStore (pure Python, no ROS)."""

    # ------------------------------------------------------------------
    # compute_artifact_path
    # ------------------------------------------------------------------

    def test_compute_artifact_path_uses_first_8_chars_and_revision(self):
        """compute_artifact_path returns Path with calibration_{hash8}_rev{N}.json."""
        store = CalibrationArtifactStore()
        path = store.compute_artifact_path("abc123def456789", 3)
        self.assertEqual(path.name, "calibration_abc123de_rev3.json")

    def test_compute_artifact_path_parent_is_ros_rehab_robotics(self):
        """Path parent is ~/.ros/rehab_robotics/."""
        store = CalibrationArtifactStore()
        path = store.compute_artifact_path("abc123def456789", 3)
        expected_parent = Path.home() / ".ros" / "rehab_robotics"
        self.assertEqual(path.parent, expected_parent)

    def test_compute_artifact_path_revision_zero(self):
        """Revision 0 produces _rev0 suffix."""
        store = CalibrationArtifactStore()
        path = store.compute_artifact_path("deadbeef1234", 0)
        self.assertEqual(path.name, "calibration_deadbeef_rev0.json")

    # ------------------------------------------------------------------
    # save + load round-trip
    # ------------------------------------------------------------------

    def test_save_and_load_round_trip_preserves_all_fields(self):
        """save() + load() round-trip returns identical dict for a calib.v1 artifact."""
        store = CalibrationArtifactStore()
        data = {
            "schema_version": "calib.v1",
            "model_hash": "abc123def456",
            "applied_revision": 5,
            "device_order": ["esp32:aabbccddeeff", "esp32:112233445566"],
            "frame_assignments": {
                "esp32:aabbccddeeff": {"segment": "tibia", "frame": "tibia_r_imu"},
                "esp32:112233445566": {"segment": "femur", "frame": "femur_r_imu"},
            },
            "solver_profile": "lower_body",
            "calibrated_at_iso8601": "2026-08-05T12:00:00.000Z",
            "reference_pose": {
                "esp32:aabbccddeeff": {"qw": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0},
                "esp32:112233445566": {"qw": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0},
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "calibration_abc123de_rev5.json"
            store.save(artifact_path, data)
            loaded = store.load(artifact_path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded, data)

    def test_save_atomic_no_tmp_file_left_behind(self):
        """save() must not leave a .tmp file after successful write."""
        store = CalibrationArtifactStore()
        data = {
            "schema_version": "calib.v1",
            "model_hash": "abc123",
            "applied_revision": 1,
            "device_order": [],
            "frame_assignments": {},
            "solver_profile": "lower_body",
            "calibrated_at_iso8601": "2026-08-05T12:00:00Z",
            "reference_pose": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "calibration_abc123_rev1.json"
            store.save(artifact_path, data)
            tmp_path = artifact_path.with_suffix(".tmp")
            self.assertFalse(tmp_path.exists(), ".tmp file left behind after save()")
            self.assertTrue(artifact_path.exists(), "Final artifact file not written")

    def test_save_creates_parent_directories(self):
        """save() creates parent directories if they don't exist."""
        store = CalibrationArtifactStore()
        data = {
            "schema_version": "calib.v1",
            "model_hash": "abc123",
            "applied_revision": 1,
            "device_order": [],
            "frame_assignments": {},
            "solver_profile": "lower_body",
            "calibrated_at_iso8601": "2026-08-05T12:00:00Z",
            "reference_pose": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "a" / "b" / "c"
            artifact_path = nested / "calibration_abc123_rev1.json"
            store.save(artifact_path, data)
            self.assertTrue(artifact_path.exists())

    # ------------------------------------------------------------------
    # load() error cases
    # ------------------------------------------------------------------

    def test_load_returns_none_for_missing_file(self):
        """load() returns None when the file does not exist."""
        store = CalibrationArtifactStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "nonexistent.json"
            result = store.load(missing)
        self.assertIsNone(result)

    def test_load_returns_none_for_corrupt_json(self):
        """load() returns None when the file contains invalid JSON."""
        store = CalibrationArtifactStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            corrupt = Path(tmpdir) / "corrupt.json"
            corrupt.write_text("NOT_VALID_JSON{{{", encoding="utf-8")
            result = store.load(corrupt)
        self.assertIsNone(result)

    def test_load_returns_none_for_wrong_schema_version(self):
        """load() returns None when schema_version != 'calib.v1'."""
        store = CalibrationArtifactStore()
        wrong_schema = {
            "schema_version": "calib.v2",
            "model_hash": "abc",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            path.write_text(json.dumps(wrong_schema), encoding="utf-8")
            result = store.load(path)
        self.assertIsNone(result)

    def test_load_returns_none_for_non_dict_json(self):
        """load() returns None when JSON parses to a non-dict (list, string, etc.)."""
        store = CalibrationArtifactStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            result = store.load(path)
        self.assertIsNone(result)

    def test_load_returns_none_for_missing_schema_version_key(self):
        """load() returns None when schema_version key is absent."""
        store = CalibrationArtifactStore()
        no_schema = {"model_hash": "abc"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            path.write_text(json.dumps(no_schema), encoding="utf-8")
            result = store.load(path)
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # is_valid
    # ------------------------------------------------------------------

    def _valid_artifact(self):
        return {
            "schema_version": "calib.v1",
            "model_hash": "deadbeef1234",
            "applied_revision": 7,
            "device_order": ["esp32:aabbccddeeff", "esp32:112233445566"],
            "frame_assignments": {},
            "solver_profile": "lower_body",
            "calibrated_at_iso8601": "2026-08-05T12:00:00Z",
            "reference_pose": {},
        }

    def test_is_valid_returns_true_when_all_fields_match(self):
        """is_valid() returns True when model_hash, applied_revision, and device_order match."""
        store = CalibrationArtifactStore()
        artifact = self._valid_artifact()
        result = store.is_valid(
            artifact,
            "deadbeef1234",
            7,
            ["esp32:aabbccddeeff", "esp32:112233445566"],
        )
        self.assertTrue(result)

    def test_is_valid_device_order_comparison_is_order_independent(self):
        """is_valid() uses set comparison for device_order (order-independent)."""
        store = CalibrationArtifactStore()
        artifact = self._valid_artifact()
        # Reverse order — should still be valid
        result = store.is_valid(
            artifact,
            "deadbeef1234",
            7,
            ["esp32:112233445566", "esp32:aabbccddeeff"],
        )
        self.assertTrue(result)

    def test_is_valid_returns_false_when_model_hash_differs(self):
        """is_valid() returns False when model_hash does not match."""
        store = CalibrationArtifactStore()
        artifact = self._valid_artifact()
        result = store.is_valid(
            artifact,
            "DIFFERENT_HASH",
            7,
            ["esp32:aabbccddeeff", "esp32:112233445566"],
        )
        self.assertFalse(result)

    def test_is_valid_returns_false_when_applied_revision_differs(self):
        """is_valid() returns False when applied_revision does not match."""
        store = CalibrationArtifactStore()
        artifact = self._valid_artifact()
        result = store.is_valid(
            artifact,
            "deadbeef1234",
            99,  # different revision
            ["esp32:aabbccddeeff", "esp32:112233445566"],
        )
        self.assertFalse(result)

    def test_is_valid_returns_false_when_device_set_changes(self):
        """is_valid() returns False when device set differs (even if count is same)."""
        store = CalibrationArtifactStore()
        artifact = self._valid_artifact()
        result = store.is_valid(
            artifact,
            "deadbeef1234",
            7,
            ["esp32:aabbccddeeff", "esp32:NEW_DEVICE_99"],  # different device
        )
        self.assertFalse(result)

    def test_is_valid_returns_false_for_none_artifact(self):
        """is_valid(None, ...) returns False."""
        store = CalibrationArtifactStore()
        result = store.is_valid(
            None,
            "deadbeef1234",
            7,
            ["esp32:aabbccddeeff"],
        )
        self.assertFalse(result)

    def test_is_valid_returns_false_when_device_count_changes(self):
        """is_valid() returns False when a device is added to current_device_order."""
        store = CalibrationArtifactStore()
        artifact = self._valid_artifact()
        result = store.is_valid(
            artifact,
            "deadbeef1234",
            7,
            ["esp32:aabbccddeeff", "esp32:112233445566", "esp32:EXTRA"],
        )
        self.assertFalse(result)


class IkTwoArtifactTests(unittest.TestCase):
    """IK-02 contract tests for CalibrationArtifactStore (IK-02-A through IK-02-E, IK-02-I).

    All offline, no live ROS, no live filesystem writes except tempfile isolation.
    """

    def setUp(self):
        self.store = CalibrationArtifactStore()
        self._tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir_obj.name)

    def tearDown(self):
        self._tmpdir_obj.cleanup()

    def _make_artifact(self, model_hash="abc123def456", revision=5):
        return {
            "schema_version": "calib.v1",
            "model_hash": model_hash,
            "applied_revision": revision,
            "device_order": ["esp32:aabbccddeeff", "esp32:112233445566"],
            "frame_assignments": {
                "esp32:aabbccddeeff": {"segment": "tibia", "frame": "tibia_r_imu"},
                "esp32:112233445566": {"segment": "femur", "frame": "femur_r_imu"},
            },
            "solver_profile": "lower_body",
            "calibrated_at_iso8601": "2026-08-05T12:00:00.000Z",
            "reference_pose": {
                "esp32:aabbccddeeff": {"qw": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0},
                "esp32:112233445566": {"qw": 1.0, "qx": 0.0, "qy": 0.0, "qz": 0.0},
            },
        }

    def test_ik02_a_save_load_round_trip_preserves_all_calib_v1_fields(self):
        """IK-02-A: save() + load() round-trip preserves all calib.v1 fields."""
        artifact = self._make_artifact()
        path = self.tmpdir / "calibration_abc123de_rev5.json"
        self.store.save(path, artifact)
        loaded = self.store.load(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["schema_version"], "calib.v1")
        self.assertEqual(loaded["model_hash"], "abc123def456")
        self.assertEqual(loaded["applied_revision"], 5)
        self.assertEqual(
            loaded["device_order"],
            ["esp32:aabbccddeeff", "esp32:112233445566"],
        )
        self.assertIn("frame_assignments", loaded)
        self.assertIn("reference_pose", loaded)
        self.assertEqual(loaded["solver_profile"], "lower_body")
        self.assertEqual(loaded["calibrated_at_iso8601"], "2026-08-05T12:00:00.000Z")

    def test_ik02_b_is_valid_false_when_model_hash_differs(self):
        """IK-02-B: is_valid() returns False when model_hash differs."""
        artifact = self._make_artifact(model_hash="abc123def456")
        result = self.store.is_valid(
            artifact,
            current_model_hash="COMPLETELY_DIFFERENT",
            current_applied_revision=5,
            current_device_order=["esp32:aabbccddeeff", "esp32:112233445566"],
        )
        self.assertFalse(result)

    def test_ik02_c_is_valid_false_when_applied_revision_differs(self):
        """IK-02-C: is_valid() returns False when applied_revision differs."""
        artifact = self._make_artifact(revision=5)
        result = self.store.is_valid(
            artifact,
            current_model_hash="abc123def456",
            current_applied_revision=99,
            current_device_order=["esp32:aabbccddeeff", "esp32:112233445566"],
        )
        self.assertFalse(result)

    def test_ik02_d_is_valid_false_when_device_set_changes(self):
        """IK-02-D: is_valid() returns False when device set changes."""
        artifact = self._make_artifact()
        result = self.store.is_valid(
            artifact,
            current_model_hash="abc123def456",
            current_applied_revision=5,
            current_device_order=["esp32:aabbccddeeff", "esp32:NEW_DEVICE"],
        )
        self.assertFalse(result)

    def test_ik02_e_load_returns_none_for_corrupt_wrong_schema_missing_file(self):
        """IK-02-E: load() returns None for corrupt file, wrong schema_version, missing file."""
        # Corrupt JSON
        corrupt = self.tmpdir / "corrupt.json"
        corrupt.write_text("NOT_JSON{{", encoding="utf-8")
        self.assertIsNone(self.store.load(corrupt))

        # Wrong schema_version
        wrong_schema = self.tmpdir / "wrong.json"
        wrong_schema.write_text(
            json.dumps({"schema_version": "calib.v99", "model_hash": "abc"}),
            encoding="utf-8",
        )
        self.assertIsNone(self.store.load(wrong_schema))

        # Missing file
        missing = self.tmpdir / "does_not_exist.json"
        self.assertIsNone(self.store.load(missing))

    def test_ik02_i_compute_artifact_path_uses_hash8_and_revision(self):
        """IK-02-I: compute_artifact_path uses first 8 chars of model_hash and applied_revision."""
        path = self.store.compute_artifact_path("abc123def456789abcde", 3)
        self.assertEqual(path.name, "calibration_abc123de_rev3.json")
        self.assertTrue(str(path).startswith(str(Path.home() / ".ros" / "rehab_robotics")))


if __name__ == "__main__":
    unittest.main()
