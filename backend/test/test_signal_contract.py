"""Fixture-driven tests for the ROS-free canonical signal contract."""
from __future__ import annotations

import copy
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from rehab_robotics_bridge.signal_contract import build_canonical_signal_sample
from rehab_robotics_bridge.measurement_contract import measurement_config


FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'signal_contract_cases.json'
with FIXTURE_PATH.open(encoding='utf-8') as fixture_file:
    FIXTURE = json.load(fixture_file)


def _merge(base: dict, overrides: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        result[key] = copy.deepcopy(value)
    return result


def _input(case: dict) -> dict:
    value = _merge(FIXTURE['base_input'], case.get('overrides', {}))
    for key in case.get('remove', []):
        value.pop(key, None)
    return value


def _assert_subset(test: unittest.TestCase, actual: object, expected: object) -> None:
    if isinstance(expected, dict):
        test.assertIsInstance(actual, dict)
        for key, value in expected.items():
            test.assertIn(key, actual)
            _assert_subset(test, actual[key], value)
    else:
        test.assertEqual(actual, expected)


class SignalContractTests(unittest.TestCase):
    def _build(self, case: dict):
        return build_canonical_signal_sample(
            topic_token=case['topic_token'], sample=_input(case)
        )

    def test_identity_time_fixture_cases(self):
        cases = [case for case in FIXTURE['accepted'] if case['id'].startswith('identity_time')]
        self.assertEqual(len(cases), 2)
        for case in cases:
            with self.subTest(case=case['id']):
                _assert_subset(self, self._build(case).as_dict(), case['expect'])

    def test_identity_time_rejections_have_exact_bounded_codes(self):
        ids = {'schema_invalid', 'device_id_malformed', 'topic_mismatch', 'sequence_fractional',
               'sequence_origin_invalid', 'acquisition_pair_invalid', 'bridge_time_negative',
               'reconnect_negative', 'mapping_epoch_fractional', 'error_detail_overlong'}
        for case in FIXTURE['rejected']:
            if case['id'] not in ids:
                continue
            with self.subTest(case=case['id']):
                with self.assertRaisesRegex(ValueError, f"^{case['reason']}$"):
                    self._build(case)

    def test_raw_counts_cover_int16_edges_and_rejections(self):
        accepted = next(case for case in FIXTURE['accepted'] if case['id'] == 'raw_int16_edges')
        _assert_subset(self, self._build(accepted).as_dict(), accepted['expect'])
        for case in FIXTURE['rejected']:
            if case['id'].startswith('raw_') or case['id'] == 'capabilities_missing':
                with self.subTest(case=case['id']):
                    with self.assertRaisesRegex(ValueError, f"^{case['reason']}$"):
                        self._build(case)

    def test_applied_snapshot_is_copied_and_immutable(self):
        case = next(case for case in FIXTURE['accepted'] if case['id'] == 'applied_snapshot')
        source = _input(case)
        result = build_canonical_signal_sample(topic_token=case['topic_token'], sample=source)
        before = result.as_dict()
        source['applied_mapping']['segment'] = 'tibia_r'
        self.assertEqual(result.as_dict(), before)
        self.assertEqual(result.as_dict()['applied_mapping']['segment'], 'femur_r')
        with self.assertRaises((FrozenInstanceError, TypeError, AttributeError)):
            result.value = {}  # type: ignore[misc]

    def test_applied_partitions_reject_drafts_and_overlong_values(self):
        for case in FIXTURE['accepted']:
            if case['id'].startswith('applied_'):
                _assert_subset(self, self._build(case).as_dict(), case['expect'])
        for case in FIXTURE['rejected']:
            if case['id'] in {'draft_provenance', 'mapping_label_overlong', 'model_hash_overlong'}:
                with self.subTest(case=case['id']):
                    with self.assertRaisesRegex(ValueError, f"^{case['reason']}$"):
                        self._build(case)

    def test_quaternion_partitions_never_fabricate_identity(self):
        cases = [case for case in FIXTURE['accepted'] if case['id'].startswith('quaternion_')]
        self.assertEqual(len(cases), 8)
        for case in cases:
            with self.subTest(case=case['id']):
                value = self._build(case).as_dict()
                _assert_subset(self, value, case['expect'])
                if not case['expect']['quaternion']['available']:
                    self.assertNotIn('values', value['quaternion'])
                    self.assertNotEqual(value['quaternion'].get('values'), [1, 0, 0, 0])

    def test_fixture_traces_every_locked_decision_and_requirement(self):
        traced = {trace for partition in ('accepted', 'rejected', 'measurement_cases')
                  for case in FIXTURE[partition] for trace in case['traces']}
        self.assertEqual(traced, {f'D-{index:02d}' for index in range(1, 17)})
        self.assertEqual(set(FIXTURE['requirement_partitions']),
                         {f'SIG-{index:02d}' for index in range(1, 6)})

    def test_si_conversion_availability_and_units(self):
        base = copy.deepcopy(FIXTURE['base_input'])
        config = measurement_config(2, 250)
        sample = build_canonical_signal_sample(
            topic_token='mac_aabbccddeeff', sample=base, measurement=config,
        ).as_dict()
        self.assertTrue(sample['si']['accel']['available'])
        self.assertEqual(sample['si']['accel']['unit'], 'm/s^2')
        self.assertTrue(sample['si']['gyro']['available'])
        self.assertEqual(sample['si']['gyro']['unit'], 'rad/s')
        self.assertFalse(sample['si']['magnetometer']['available'])
        self.assertEqual(sample['si']['magnetometer']['reason'], 'calibration_missing')
        self.assertNotIn('unit', sample['si']['magnetometer'])

        mag_case = next(case for case in FIXTURE['measurement_cases']
                        if case['id'] == 'mag_calibrated')
        base['raw'].update(dict(zip(('mx', 'my', 'mz'), mag_case['raw'])))
        calibrated = measurement_config(
            2, 250,
            magnetometer_sensitivity_uT_per_count=mag_case['sensitivity_uT_per_count'],
            magnetometer_calibration=mag_case['calibration'],
        )
        converted = build_canonical_signal_sample(
            topic_token='mac_aabbccddeeff', sample=base, measurement=calibrated,
        ).as_dict()
        self.assertEqual(converted['raw']['mx'], 10)
        self.assertEqual(converted['si']['magnetometer']['unit'], 'µT')
        for axis, expected in zip('xyz', mag_case['expected_uT']):
            self.assertAlmostEqual(
                converted['si']['magnetometer']['values'][axis], expected, delta=1e-12,
            )

    def test_invalid_measurement_config_remains_raw_only(self):
        sample = build_canonical_signal_sample(
            topic_token='mac_aabbccddeeff',
            sample=copy.deepcopy(FIXTURE['base_input']),
            measurement={'accel_range_g': 3},
        ).as_dict()
        self.assertEqual(sample['raw']['ax'], -32768)
        self.assertEqual(sample['si']['accel'],
                         {'available': False, 'reason': 'config_invalid'})
        self.assertNotIn('unit', sample['si']['accel'])


if __name__ == '__main__':
    unittest.main()
