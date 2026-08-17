import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import type {
  CanonicalSignalSample,
  SignalAvailabilityReason,
} from '../../types/signals';
import {
  SignalContractPanelView,
  SignalSourceCard,
  availabilityReasonText,
  buildChannelPresentation,
} from './SignalContractPanel';
import type { SignalSnapshot } from '../../data/signalBus';

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

function snapshot(overrides: Partial<SignalSnapshot> = {}): SignalSnapshot {
  return {
    t: 0,
    forceRaw: 0,
    forceProcessed: 0,
    emgRaw: 0,
    emgEnvelope: 0,
    kneeAngle: null,
    motor: {
      position: 0, velocity: 0, torque: 0, current: 0,
      temperature: 0, enabled: false, fault: false, t: 0,
    },
    forceSeries: [],
    emgSeries: [],
    kneeSeries: [],
    canonicalSamplesByMac: {},
    canonicalAcceptedCount: 0,
    canonicalRejectedCount: 0,
    canonicalRejectionsBySource: {},
    ...overrides,
  };
}

describe('Signal Contract panel composition', () => {
  it('renders the exact empty state without synthesizing a source', () => {
    const markup = renderToStaticMarkup(<SignalContractPanelView snapshot={snapshot()} />);
    assert.match(markup, /role="status" aria-live="polite">0 accepted/);
    assert.match(markup, /No canonical samples/);
    assert.match(markup, /Start acquisition or check the ROS bridge connection\./);
    assert.doesNotMatch(markup, /signal-source-card/);
  });

  it('sorts accepted cards by canonical full MAC and summarizes accepted and rejected counts', () => {
    const later = sample({ device_id: 'esp32:ffeeddccbbaa', topic_token: 'mac_ffeeddccbbaa' });
    const earlier = sample();
    const markup = renderToStaticMarkup(<SignalContractPanelView snapshot={snapshot({
      canonicalSamplesByMac: {
        [later.device_id]: later,
        [earlier.device_id]: earlier,
      },
      canonicalAcceptedCount: 12,
      canonicalRejectedCount: 2,
    })} />);
    assert.match(markup, /12 accepted · <span class="signal-summary-rejected">2 rejected<\/span>/);
    assert.ok(markup.indexOf(earlier.device_id) < markup.indexOf(later.device_id));
  });

  it('keeps the last accepted values visible beside bounded persistent rejection feedback', () => {
    const value = sample();
    const markup = renderToStaticMarkup(<SignalContractPanelView snapshot={snapshot({
      canonicalSamplesByMac: { [value.device_id]: value },
      canonicalAcceptedCount: 1,
      canonicalRejectedCount: 1,
      canonicalRejectionsBySource: {
        [value.device_id]: {
          device_id: value.device_id,
          reason: 'topic_device_mismatch',
          rejected_at_ms: 1_700_000_000_000,
          count: 1,
          should_announce: true,
          last_update_rejected: true,
        },
      },
    })} />);
    assert.match(markup, /Last update rejected/);
    assert.match(markup, /Topic identity does not match the canonical full MAC/);
    assert.match(markup, /role="alert"/);
    assert.match(markup, />-32768</);
  });

  it('renders rejection-only feedback without a value card and suppresses duplicate alerts', () => {
    const rejectedMac = 'esp32:112233445566';
    const markup = renderToStaticMarkup(<SignalContractPanelView snapshot={snapshot({
      canonicalRejectedCount: 3,
      canonicalRejectionsBySource: {
        [rejectedMac]: {
          device_id: rejectedMac,
          reason: 'schema_invalid',
          rejected_at_ms: 1_700_000_000_000,
          count: 3,
          should_announce: false,
          last_update_rejected: true,
        },
      },
    })} />);
    assert.match(markup, /Sample rejected/);
    assert.match(markup, /Canonical schema is invalid/);
    assert.match(markup, /role="status"/);
    assert.doesNotMatch(markup, /signal-source-card/);
  });
});
