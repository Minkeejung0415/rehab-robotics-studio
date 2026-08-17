import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import type {
  CanonicalSignalSample,
  SignalAvailabilityReason,
} from '../../types/signals';
import {
  SignalSourceCard,
  availabilityReasonText,
  buildChannelPresentation,
} from './SignalContractPanel';

function sample(
  overrides: Partial<CanonicalSignalSample> = {},
): CanonicalSignalSample {
  return {
    schema: 'rehab.signal_sample.1',
    device_id: 'esp32:aabbccddeeff',
    topic_token: 'mac_aabbccddeeff',
    sequence: 17,
    sequence_origin: 'bridge_session',
    acquisition_time_us: null,
    acquisition_clock: null,
    bridge_monotonic_time_us: 123456,
    reconnect_epoch: 0,
    mapping_epoch: 0,
    capabilities: {
      accel: true,
      gyro: true,
      magnetometer: true,
      quaternion: true,
    },
    raw: {
      ax: -32768,
      ay: 0,
      az: 32767,
      gx: -3,
      gy: 4,
      gz: 5,
      mx: 6,
      my: 7,
      mz: 8,
    },
    raw_units: 'counts',
    si: {
      accel: { available: true, unit: 'm/s^2', values: { x: -19.6133, y: 0, z: 19.6127 } },
      gyro: { available: true, unit: 'rad/s', values: { x: -0.03, y: 0.04, z: 0.05 } },
      magnetometer: { available: true, unit: 'µT', values: { x: 0.6, y: 0.7, z: 0.8 } },
    },
    quaternion: { available: true, values: [1, 0.1, 0.2, 0.3] },
    applied_mapping: {
      revision: 0,
      segment: 'femur_r',
      frame: '/bodyset/femur_r/imu',
      model_hash: 'a'.repeat(64),
    },
    ...overrides,
  };
}

function row(
  value: CanonicalSignalSample,
  mode: 'raw' | 'si',
  key: 'accel' | 'gyro' | 'magnetometer' | 'quaternion',
) {
  const found = buildChannelPresentation(value, mode).find((candidate) => candidate.key === key);
  assert.ok(found, `missing ${key} presentation`);
  return found;
}

describe('Signal Contract presentation', () => {
  it('defaults source markup to exact lossless raw counts', () => {
    const value = sample();
    const raw = buildChannelPresentation(value, 'raw');
    assert.deepEqual(raw[0]?.values.map((item) => item.value), ['-32768', '0', '32767']);
    assert.equal(raw[0]?.badge, 'AVAILABLE');
    assert.equal(raw[0]?.unit, 'counts');

    const markup = renderToStaticMarkup(<SignalSourceCard sample={value} />);
    assert.match(markup, /aria-pressed="true"[^>]*>Show Raw Counts/);
    assert.match(markup, />-32768</);
  });

  it('uses only validated accel, gyro, and magnetometer SI representations', () => {
    assert.deepEqual(row(sample(), 'si', 'accel'), {
      key: 'accel', label: 'Acceleration', badge: 'AVAILABLE', unit: 'm/s²',
      values: [
        { label: 'ax', value: '-19.6133' },
        { label: 'ay', value: '0' },
        { label: 'az', value: '19.6127' },
      ],
      reason: null,
    });
    assert.equal(row(sample(), 'si', 'gyro').unit, 'rad/s');
    assert.equal(row(sample(), 'si', 'magnetometer').unit, 'µT');
  });

  it('shows RAW ONLY and exact config-invalid copy without false SI units', () => {
    const value = sample({
      si: {
        ...sample().si,
        accel: { available: false, reason: 'config_invalid' },
        gyro: { available: false, reason: 'config_invalid' },
      },
    });
    const accel = row(value, 'si', 'accel');
    assert.equal(accel.badge, 'RAW ONLY');
    assert.equal(accel.unit, null);
    assert.deepEqual(accel.values.map((item) => item.value), ['—', '—', '—']);
    assert.equal(
      accel.reason,
      'SI unavailable — sensor sensitivity is invalid. Raw counts remain available.',
    );
    assert.equal(row(value, 'raw', 'accel').unit, 'counts');
  });

  it('distinguishes absent magnetometer capability from raw-only calibration states', () => {
    const absent = sample({
      capabilities: { ...sample().capabilities, magnetometer: false },
      si: { ...sample().si, magnetometer: { available: false, reason: 'capability_absent' } },
    });
    assert.deepEqual(row(absent, 'raw', 'magnetometer'), {
      key: 'magnetometer', label: 'Magnetic field', badge: 'UNAVAILABLE', unit: null,
      values: [{ label: 'mx', value: '—' }, { label: 'my', value: '—' }, { label: 'mz', value: '—' }],
      reason: 'Magnetometer unavailable — source capability not declared.',
    });

    for (const reason of ['calibration_missing', 'calibration_invalid'] as const) {
      const rawOnly = sample({
        si: { ...sample().si, magnetometer: { available: false, reason } },
      });
      assert.equal(row(rawOnly, 'raw', 'magnetometer').unit, 'counts');
      const si = row(rawOnly, 'si', 'magnetometer');
      assert.equal(si.badge, 'RAW ONLY');
      assert.equal(si.unit, null);
      assert.ok(!JSON.stringify(si).includes('µT'));
      assert.equal(
        si.reason,
        `SI unavailable — ${availabilityReasonText(reason)}. Raw counts remain available.`,
      );
    }
  });

  it('distinguishes unavailable and invalid quaternion states and never fabricates orientation', () => {
    const absent = sample({
      capabilities: { ...sample().capabilities, quaternion: false },
      quaternion: { available: false, reason: 'capability_absent' },
    });
    assert.equal(row(absent, 'raw', 'quaternion').badge, 'UNAVAILABLE');
    assert.equal(
      row(absent, 'raw', 'quaternion').reason,
      'Quaternion unavailable — source capability not declared.',
    );

    const invalidReasons: SignalAvailabilityReason[] = [
      'stale', 'missing', 'malformed', 'non_finite', 'zero_norm', 'norm_out_of_range',
    ];
    for (const reason of invalidReasons) {
      const invalid = row(sample({ quaternion: { available: false, reason } }), 'raw', 'quaternion');
      assert.equal(invalid.badge, 'INVALID');
      assert.deepEqual(invalid.values.map((item) => item.value), ['—', '—', '—', '—']);
      assert.equal(
        invalid.reason,
        `Quaternion invalid — ${availabilityReasonText(reason)}. No orientation value is displayed.`,
      );
      assert.ok(!JSON.stringify(invalid).includes('[1,0,0,0]'));
    }

    const valid = row(sample({ quaternion: { available: true, values: [0.9, -0.1, 0.2, -0.3] } }), 'raw', 'quaternion');
    assert.deepEqual(valid.values.map((item) => item.value), ['0.9', '-0.1', '0.2', '-0.3']);
    assert.equal(valid.unit, 'unitless');
  });

  it('renders full identity, applied mapping, independent zero epochs, and complete provenance accessibly', () => {
    const markup = renderToStaticMarkup(<SignalSourceCard sample={sample()} initialUnitMode="si" />);
    assert.match(markup, /aria-labelledby="signal-source-esp32-aabbccddeeff"/);
    assert.match(markup, />esp32:aabbccddeeff</);
    assert.match(markup, /Applied r0 · femur_r \/ \/bodyset\/femur_r\/imu/);
    assert.match(markup, /Authoritative applied mapping revision 0, segment femur_r, frame \/bodyset\/femur_r\/imu/);
    assert.match(markup, /Mapping epoch 0/);
    assert.match(markup, /Reconnect epoch 0/);
    assert.match(markup, /aria-label="Display units for esp32:aabbccddeeff"/);
    assert.match(markup, /aria-pressed="true"[^>]*>Show SI Values/);
    assert.match(markup, /aria-expanded="false"/);

    const expanded = renderToStaticMarkup(<SignalSourceCard sample={sample()} initialProvenanceOpen />);
    for (const label of [
      'Schema version', 'Full MAC', 'Sequence', 'Sequence origin', 'Acquisition time',
      'Acquisition clock', 'Bridge monotonic time', 'Reconnect epoch',
      'Mapping provenance epoch', 'Applied revision', 'Exact segment', 'Exact frame',
      'Model hash', 'Channel capabilities', 'Validity reason codes',
    ]) {
      assert.match(expanded, new RegExp(label));
    }
    assert.match(expanded, /Acquisition time<\/span><strong>Unavailable/);
    assert.match(expanded, /Acquisition clock<\/span><strong>Unavailable/);
  });

  it('disables SI only when no group has validated SI and describes why', () => {
    const value = sample({
      si: {
        accel: { available: false, reason: 'config_invalid' },
        gyro: { available: false, reason: 'config_invalid' },
        magnetometer: { available: false, reason: 'calibration_missing' },
      },
    });
    const markup = renderToStaticMarkup(<SignalSourceCard sample={value} />);
    assert.match(markup, /Show SI Values<\/button>/);
    assert.match(markup, /disabled="" aria-describedby="signal-si-disabled-esp32-aabbccddeeff"/);
    assert.match(markup, /SI values are unavailable for every channel group/);
  });
});
