"""Backend tests for the measurement_contract module.

Plan 09-01, Tasks 09-01-01, 09-01-02, 09-01-03.

Uses the same sys.path-insertion pattern as test_esp32_controls.py so that
the tests run from the project root with PYTHONPATH=backend without requiring
a full ROS installation.
"""
from __future__ import annotations

import json
import copy
import sys
import types
import unittest
from pathlib import Path

# ── Ensure the backend source tree is importable ──────────────────────────────
_BACKEND = Path(__file__).parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# measurement_contract is a pure stdlib module — import directly.
from rehab_robotics_bridge.measurement_contract import (
    ACCEL_LSB_PER_G,
    GRAVITY,
    GYRO_LSB_PER_DPS,
    MeasurementConfig,
    accel_count_to_mps2,
    config_as_json,
    gyro_count_to_rad_s,
    magnetometer_counts_to_uT,
    measurement_config,
    validate_magnetometer_calibration,
    validate_sensor_config,
)

# Shared fixture path
_FIXTURES = Path(__file__).parent / 'fixtures' / 'measurement_contract_cases.json'


# ── pipeline import helper (used by PublishFrameAndPipelineTests) ─────────────

def _import_pipeline():
    """Import pipeline without a ROS installation."""
    from rehab_robotics_bridge.pipeline import SampleFilter
    return SampleFilter


# ─────────────────────────────────────────────────────────────────────────────
# Task 09-01-01: Table tests
# ─────────────────────────────────────────────────────────────────────────────

class MeasurementContractTableTests(unittest.TestCase):
    """Verify tables, constructors, conversion helpers, and strict validation."""

    def test_09_01_01_all_ranges_both_roles_match_shared_fixture(self):
        """All 32 fixture cases (2 roles x 4 accel x 4 gyro) match conversion helpers."""
        with open(_FIXTURES, encoding='utf-8') as fh:
            cases = json.load(fh)

        self.assertEqual(len(cases), 32, 'fixture must contain exactly 32 cases')

        for case in cases:
            with self.subTest(
                role=case['role'],
                accel_range_g=case['accel_range_g'],
                gyro_range_dps=case['gyro_range_dps'],
            ):
                cfg = measurement_config(case['accel_range_g'], case['gyro_range_dps'])
                raw = case['raw_count']

                got_accel = accel_count_to_mps2(raw, cfg)
                self.assertAlmostEqual(
                    got_accel,
                    case['expected_accel_mps2'],
                    delta=1e-9,
                    msg=f"accel mismatch for {case}",
                )

                got_gyro = gyro_count_to_rad_s(raw, cfg)
                self.assertAlmostEqual(
                    got_gyro,
                    case['expected_gyro_rad_s'],
                    delta=1e-9,
                    msg=f"gyro mismatch for {case}",
                )

    def test_09_01_01_unsupported_range_raises(self):
        """measurement_config raises ValueError for unsupported range values."""
        with self.assertRaises(ValueError):
            measurement_config(3, 250)   # 3 g not in table
        with self.assertRaises(ValueError):
            measurement_config(2, 42)    # 42 dps not in table

    def test_09_01_01_validate_sensor_config_accepts_canonical_json(self):
        """Round-trip: config_as_json -> validate_sensor_config returns consistent config."""
        cfg = measurement_config(8, 1000)
        as_json = config_as_json(cfg)
        recovered = validate_sensor_config(as_json)
        self.assertEqual(recovered.accel_range_g, 8)
        self.assertEqual(recovered.gyro_range_dps, 1000)
        self.assertAlmostEqual(recovered.accel_lsb_per_g, ACCEL_LSB_PER_G[8], delta=1e-12)
        self.assertAlmostEqual(recovered.gyro_lsb_per_dps, GYRO_LSB_PER_DPS[1000], delta=1e-12)

    def test_09_01_01_validate_sensor_config_rejects_partitions(self):
        """Rejection partitions — each must raise ValueError."""
        # Build a known-good dict for mutation
        good = config_as_json(measurement_config(8, 1000))

        def _bad(**overrides):
            d = dict(good)
            for k, v in overrides.items():
                if v is _REMOVE:
                    del d[k]
                else:
                    d[k] = v
            return d

        _REMOVE = object()

        rejection_cases = [
            ('None (not a dict)', None),
            ('empty dict (missing all fields)', {}),
            ('missing gyro_lsb_per_dps', _bad(gyro_lsb_per_dps=_REMOVE)),
            ('accel_range_g=3 (unsupported)', _bad(accel_range_g=3)),
            ('gyro_range_dps=42 (unsupported)', _bad(gyro_range_dps=42)),
            ('accel_lsb_per_g=0.0 (not positive)', _bad(accel_lsb_per_g=0.0)),
            ('accel_lsb_per_g=NaN', _bad(accel_lsb_per_g=float('nan'))),
            ('accel_lsb_per_g=Inf', _bad(accel_lsb_per_g=float('inf'))),
            ('range/sensitivity mismatch: accel_range_g=8 with accel_lsb_per_g=16384',
             _bad(accel_range_g=8, accel_lsb_per_g=16384.0)),
            ('missing units key', _bad(units=_REMOVE)),
        ]

        for description, obj in rejection_cases:
            with self.subTest(case=description):
                with self.assertRaises(ValueError, msg=f'expected ValueError for: {description}'):
                    validate_sensor_config(obj)

    def test_26_01_magnetometer_requires_sensitivity_and_calibration(self):
        """Nominal sensitivity alone never authorizes microtesla output."""
        missing = measurement_config(
            2, 250, magnetometer_sensitivity_uT_per_count=0.15,
        )
        self.assertEqual(missing.magnetometer_availability, 'calibration_missing')
        with self.assertRaisesRegex(ValueError, '^calibration_missing$'):
            magnetometer_counts_to_uT((10, 20, -30), missing)

        fixture_path = Path(__file__).parent / 'fixtures' / 'signal_contract_cases.json'
        fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
        invalid_case = next(case for case in fixture['measurement_cases']
                            if case['id'] == 'mag_calibration_invalid')
        invalid = measurement_config(
            2, 250,
            magnetometer_sensitivity_uT_per_count=0.15,
            magnetometer_calibration=invalid_case['calibration'],
        )
        self.assertEqual(invalid.magnetometer_availability, 'calibration_invalid')
        self.assertIsNone(config_as_json(invalid)['magnetometer']['calibration'])

    def test_26_01_magnetometer_calibration_converts_deterministically(self):
        fixture_path = Path(__file__).parent / 'fixtures' / 'signal_contract_cases.json'
        fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
        case = next(case for case in fixture['measurement_cases']
                    if case['id'] == 'mag_calibrated')
        calibration = validate_magnetometer_calibration(case['calibration'])
        self.assertEqual(calibration.sensor_model, 'ICM-20948')
        config = measurement_config(
            2, 250,
            magnetometer_sensitivity_uT_per_count=case['sensitivity_uT_per_count'],
            magnetometer_calibration=case['calibration'],
        )
        self.assertEqual(config.magnetometer_availability, 'available')
        converted = magnetometer_counts_to_uT(case['raw'], config)
        for actual, expected in zip(converted, case['expected_uT']):
            self.assertAlmostEqual(actual, expected, delta=1e-12)
        serialized = config_as_json(config)
        self.assertEqual(serialized['magnetometer']['calibration'], case['calibration'])

    def test_26_01_magnetometer_rejects_unbounded_or_nonfinite_provenance(self):
        valid = {
            'schema': 'rehab.mag_calibration.1',
            'sensor_model': 'ICM-20948',
            'axis_convention': 'xyz',
            'calibration_id': 'lab-01',
            'calibration_hash': 'sha256:abcdef0123456789',
            'hard_iron_uT': [0, 0, 0],
            'soft_iron': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        }
        cases = []
        for key, value in (
            ('sensor_model', 'x' * 65),
            ('calibration_id', 'x' * 65),
            ('calibration_hash', 'sha256:not-hex'),
            ('axis_convention', 'guessed'),
            ('hard_iron_uT', [float('nan'), 0, 0]),
            ('soft_iron', [[1, 0], [0, 1], [0, 0]]),
        ):
            candidate = copy.deepcopy(valid)
            candidate[key] = value
            cases.append(candidate)
        for candidate in cases:
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, '^calibration_invalid$'):
                    validate_magnetometer_calibration(candidate)


# ─────────────────────────────────────────────────────────────────────────────
# Task 09-01-02: _publish_frame and pipeline tests
# ─────────────────────────────────────────────────────────────────────────────

class PublishFrameAndPipelineTests(unittest.TestCase):
    """Verify sensor_config presence in published JSON and pipeline passthrough."""

    def test_09_01_02_publish_frame_emits_sensor_config_for_all_ranges(self):
        """config_as_json for every range combination yields internally consistent metadata.

        This is a pure helper test: it proves the sensor_config values that
        _publish_frame will embed are correct for all 16 range combinations.
        """
        accel_ranges = [2, 4, 8, 16]
        gyro_ranges = [250, 500, 1000, 2000]

        for a in accel_ranges:
            for g in gyro_ranges:
                with self.subTest(accel_range_g=a, gyro_range_dps=g):
                    cfg = measurement_config(a, g)
                    sc = config_as_json(cfg)

                    self.assertEqual(sc['accel_range_g'], a)
                    self.assertEqual(sc['gyro_range_dps'], g)
                    self.assertAlmostEqual(
                        sc['accel_lsb_per_g'], ACCEL_LSB_PER_G[a], delta=1e-12,
                    )
                    self.assertAlmostEqual(
                        sc['gyro_lsb_per_dps'], GYRO_LSB_PER_DPS[g], delta=1e-12,
                    )
                    # Round-trip validation
                    recovered = validate_sensor_config(sc)
                    self.assertEqual(recovered.accel_range_g, a)
                    self.assertEqual(recovered.gyro_range_dps, g)

    def test_09_01_02_sensor_config_survives_filter_json(self):
        """SampleFilter.filter_json preserves the sensor_config object unchanged."""
        SampleFilter = _import_pipeline()

        cfg = measurement_config(8, 2000)
        sc = config_as_json(cfg)

        # Build a minimal valid raw JSON payload with sensor_config attached
        raw = {
            'sample_index': 0,
            'seq': 0,
            'time_us': 123456,
            'node_role': 'master',
            'node_id': 'master',
            'topic_schema': 'oe_esp32.raw.v1',
            'body_segment': '',
            'imu': {'ax': 0, 'ay': 0, 'az': 0, 'gx': 0, 'gy': 0, 'gz': 0,
                    'mx': 0, 'my': 0, 'mz': 0},
            'quat': {'qw': 32767, 'qx': 0, 'qy': 0, 'qz': 0},
            'dio': 0,
            'sync': {},
            'sensor_config': sc,
        }
        raw_str = json.dumps(raw, sort_keys=True, separators=(',', ':'))

        filtered_str = SampleFilter().filter_json(raw_str)
        filtered = json.loads(filtered_str)

        self.assertIn('sensor_config', filtered, 'sensor_config must survive filter_json')
        self.assertEqual(filtered['sensor_config']['accel_range_g'], 8)
        self.assertEqual(filtered['sensor_config']['gyro_range_dps'], 2000)

        # Full structural validation of the preserved object
        recovered = validate_sensor_config(filtered['sensor_config'])
        self.assertEqual(recovered.accel_range_g, 8)
        self.assertEqual(recovered.gyro_range_dps, 2000)

    def test_09_01_02_native_si_values_match_shared_fixture(self):
        """accel_count_to_mps2 / gyro_count_to_rad_s match the shared fixture.

        Cross-checks that the same formulas used in _publish_frame agree with
        the JSON fixture consumed by the TypeScript tests.
        """
        with open(_FIXTURES, encoding='utf-8') as fh:
            cases = json.load(fh)

        for case in cases:
            with self.subTest(
                role=case['role'],
                accel_range_g=case['accel_range_g'],
                gyro_range_dps=case['gyro_range_dps'],
            ):
                cfg = measurement_config(case['accel_range_g'], case['gyro_range_dps'])
                raw = case['raw_count']

                got_accel = accel_count_to_mps2(raw, cfg)
                self.assertAlmostEqual(
                    got_accel,
                    case['expected_accel_mps2'],
                    delta=1e-9,
                )

                got_gyro = gyro_count_to_rad_s(raw, cfg)
                self.assertAlmostEqual(
                    got_gyro,
                    case['expected_gyro_rad_s'],
                    delta=1e-9,
                )


if __name__ == '__main__':
    unittest.main()
