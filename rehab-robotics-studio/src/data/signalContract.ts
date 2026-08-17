import type {
  CanonicalAppliedMapping,
  CanonicalCapabilities,
  CanonicalConversions,
  CanonicalQuaternionAvailability,
  CanonicalRawChannels,
  CanonicalSignalParseResult,
  CanonicalSignalRejectionReason,
  CanonicalSignalSample,
  SignalAvailabilityReason,
} from '../types/signals.js';

const SCHEMA = 'rehab.signal_sample.1';
const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;
const MAX_LABEL_LENGTH = 64;
const MAX_HASH_LENGTH = 128;
const MAX_CLOCK_LENGTH = 64;
const MIN_QUATERNION_NORM = 1e-8;
const MIN_AVAILABLE_QUATERNION_NORM = 0.5;
const MAX_AVAILABLE_QUATERNION_NORM = 1.5;
const RAW_FIELDS = ['ax', 'ay', 'az', 'gx', 'gy', 'gz', 'mx', 'my', 'mz'] as const;
const CAPABILITY_FIELDS = ['accel', 'gyro', 'magnetometer', 'quaternion'] as const;
const INPUT_FIELDS = new Set([
  'schema', 'device_id', 'sequence', 'sequence_origin', 'acquisition_time_us',
  'acquisition_clock', 'bridge_monotonic_time_us', 'reconnect_epoch', 'mapping_epoch',
  'capabilities', 'raw', 'quaternion', 'applied_mapping',
]);
const CANONICAL_FIELDS = new Set([
  ...INPUT_FIELDS, 'topic_token', 'raw_units', 'si',
]);
const AVAILABILITY_REASONS = new Set<SignalAvailabilityReason>([
  'capability_absent', 'config_invalid', 'calibration_missing', 'calibration_invalid',
  'stale', 'missing', 'malformed', 'non_finite', 'zero_norm', 'norm_out_of_range',
]);

type RecordValue = Record<string, unknown>;

function isRecord(value: unknown): value is RecordValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function reject(reason: CanonicalSignalRejectionReason): CanonicalSignalParseResult {
  return { ok: false, reason };
}

function normalizeDeviceId(value: unknown): `esp32:${string}` | null {
  if (typeof value !== 'string' || value.length === 0) return null;
  let compact = value;
  if (compact.startsWith('esp32:')) compact = compact.slice(6);
  else if (/^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$/.test(compact)) compact = compact.replace(/:/g, '');
  if (!/^[0-9a-fA-F]{12}$/.test(compact)) return null;
  return `esp32:${compact.toLowerCase()}`;
}

function uint(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
    ? value
    : null;
}

function exactKeys(value: RecordValue, fields: readonly string[]): boolean {
  const keys = Object.keys(value);
  return keys.length === fields.length && fields.every((field) => Object.prototype.hasOwnProperty.call(value, field));
}

function parseCapabilities(value: unknown): CanonicalCapabilities | null {
  if (!isRecord(value) || !exactKeys(value, CAPABILITY_FIELDS)) return null;
  if (CAPABILITY_FIELDS.some((field) => typeof value[field] !== 'boolean')) return null;
  return {
    accel: value.accel as boolean,
    gyro: value.gyro as boolean,
    magnetometer: value.magnetometer as boolean,
    quaternion: value.quaternion as boolean,
  };
}

function parseRaw(value: unknown): CanonicalRawChannels | CanonicalSignalRejectionReason {
  if (!isRecord(value) || !exactKeys(value, RAW_FIELDS)) return 'raw_field_missing';
  const result: Record<string, number> = {};
  for (const field of RAW_FIELDS) {
    const count = value[field];
    if (typeof count !== 'number' || !Number.isInteger(count)) return 'raw_field_invalid';
    if (count < -32768 || count > 32767) return 'raw_field_out_of_range';
    result[field] = count;
  }
  return result as unknown as CanonicalRawChannels;
}

function unavailable(reason: SignalAvailabilityReason): { readonly available: false; readonly reason: SignalAvailabilityReason } {
  return { available: false, reason };
}

function quaternionFromInput(value: unknown, capable: boolean): CanonicalQuaternionAvailability {
  if (!capable) return unavailable('capability_absent');
  if (value === null) return unavailable('missing');
  if (!isRecord(value)) return unavailable('malformed');
  if (value.status === 'stale') return unavailable('stale');
  if (value.status !== 'available' || !Array.isArray(value.values) || value.values.length !== 4) {
    return unavailable('malformed');
  }
  if (value.values.some((component) => typeof component !== 'number')) {
    return value.values.some((component) => ['NaN', 'Infinity', '-Infinity'].includes(String(component)))
      ? unavailable('non_finite')
      : unavailable('malformed');
  }
  const components = value.values as number[];
  if (!components.every(Number.isFinite)) return unavailable('non_finite');
  const scale = Math.max(...components.map(Math.abs));
  if (scale === 0) return unavailable('zero_norm');
  const norm = scale * Math.hypot(...components.map((component) => component / scale));
  if (norm < MIN_QUATERNION_NORM) return unavailable('zero_norm');
  if (norm < MIN_AVAILABLE_QUATERNION_NORM || norm > MAX_AVAILABLE_QUATERNION_NORM) {
    return unavailable('norm_out_of_range');
  }
  return { available: true, values: [components[0]!, components[1]!, components[2]!, components[3]!] };
}

function parseQuaternionAvailability(value: unknown): CanonicalQuaternionAvailability | null {
  if (!isRecord(value) || typeof value.available !== 'boolean') return null;
  if (!value.available) {
    if (!exactKeys(value, ['available', 'reason']) || !AVAILABILITY_REASONS.has(value.reason as SignalAvailabilityReason)) return null;
    return unavailable(value.reason as SignalAvailabilityReason);
  }
  if (!exactKeys(value, ['available', 'values']) || !Array.isArray(value.values) || value.values.length !== 4) return null;
  if (!value.values.every((component) => typeof component === 'number' && Number.isFinite(component))) return null;
  return { available: true, values: [...value.values] as [number, number, number, number] };
}

function parseVectorAvailability<Unit extends 'm/s^2' | 'rad/s' | 'µT'>(
  value: unknown,
  unit: Unit,
): CanonicalConversions['accel'] | null {
  if (!isRecord(value) || typeof value.available !== 'boolean') return null;
  if (!value.available) {
    if (!exactKeys(value, ['available', 'reason']) || !AVAILABILITY_REASONS.has(value.reason as SignalAvailabilityReason)) return null;
    return unavailable(value.reason as SignalAvailabilityReason);
  }
  if (!exactKeys(value, ['available', 'unit', 'values']) || value.unit !== unit || !isRecord(value.values)) return null;
  if (!exactKeys(value.values, ['x', 'y', 'z'])) return null;
  if (!['x', 'y', 'z'].every((axis) => typeof (value.values as RecordValue)[axis] === 'number'
      && Number.isFinite((value.values as RecordValue)[axis]))) return null;
  return {
    available: true,
    unit,
    values: { x: value.values.x as number, y: value.values.y as number, z: value.values.z as number },
  } as CanonicalConversions['accel'];
}

function parseConversions(value: unknown): CanonicalConversions | null {
  if (!isRecord(value) || !exactKeys(value, ['accel', 'gyro', 'magnetometer'])) return null;
  const accel = parseVectorAvailability(value.accel, 'm/s^2');
  const gyro = parseVectorAvailability(value.gyro, 'rad/s');
  const magnetometer = parseVectorAvailability(value.magnetometer, 'µT');
  if (!accel || !gyro || !magnetometer) return null;
  return {
    accel: accel as CanonicalConversions['accel'],
    gyro: gyro as CanonicalConversions['gyro'],
    magnetometer: magnetometer as CanonicalConversions['magnetometer'],
  };
}

function parseAppliedMapping(value: unknown): CanonicalAppliedMapping | null {
  if (!isRecord(value) || !exactKeys(value, ['revision', 'segment', 'frame', 'model_hash'])) return null;
  const revision = uint(value.revision);
  if (revision === null) return null;
  const label = (candidate: unknown): candidate is string | null =>
    candidate === null || (typeof candidate === 'string' && candidate.length > 0 && candidate.length <= MAX_LABEL_LENGTH);
  if (!label(value.segment) || !label(value.frame) || (value.segment === null) !== (value.frame === null)) return null;
  if (typeof value.model_hash !== 'string' || value.model_hash.length === 0 || value.model_hash.length > MAX_HASH_LENGTH) return null;
  return { revision, segment: value.segment, frame: value.frame, model_hash: value.model_hash };
}

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    Object.freeze(value);
    for (const nested of Object.values(value as RecordValue)) deepFreeze(nested);
  }
  return value;
}

/** Parse one untrusted rosbridge canonical sample for its subscribed full-MAC topic. */
export function parseCanonicalSignalSample(
  raw: unknown,
  expectedTopicToken: string,
): CanonicalSignalParseResult {
  if (!isRecord(raw) || raw.schema !== SCHEMA) return reject('schema_invalid');
  const hasCanonicalFields = Object.prototype.hasOwnProperty.call(raw, 'si')
    || Object.prototype.hasOwnProperty.call(raw, 'topic_token')
    || Object.prototype.hasOwnProperty.call(raw, 'raw_units');
  const allowed = hasCanonicalFields ? CANONICAL_FIELDS : INPUT_FIELDS;
  const extras = Object.keys(raw).filter((key) => !allowed.has(key));
  if (extras.length > 0) {
    return extras.some((key) => ['draft_mapping', 'desired_mapping', 'current_mapping'].includes(key))
      ? reject('applied_mapping_invalid')
      : reject('schema_invalid');
  }

  const deviceId = normalizeDeviceId(raw.device_id);
  if (!deviceId) return reject('device_id_invalid');
  const topicToken = `mac_${deviceId.slice(6)}` as `mac_${string}`;
  if (expectedTopicToken !== topicToken || (hasCanonicalFields && raw.topic_token !== topicToken)) {
    return reject('topic_device_mismatch');
  }
  const sequence = uint(raw.sequence);
  if (sequence === null) return reject('sequence_invalid');
  if (raw.sequence_origin !== 'device' && raw.sequence_origin !== 'bridge_session') return reject('sequence_origin_invalid');

  let acquisitionTime: number | null = null;
  let acquisitionClock: string | null = null;
  if (raw.acquisition_time_us === null) {
    if (raw.acquisition_clock !== null) return reject('acquisition_time_invalid');
  } else {
    acquisitionTime = uint(raw.acquisition_time_us);
    if (acquisitionTime === null || typeof raw.acquisition_clock !== 'string'
        || raw.acquisition_clock.length === 0 || raw.acquisition_clock.length > MAX_CLOCK_LENGTH) {
      return reject('acquisition_time_invalid');
    }
    acquisitionClock = raw.acquisition_clock;
  }
  const bridgeTime = uint(raw.bridge_monotonic_time_us);
  if (bridgeTime === null) return reject('bridge_time_invalid');
  const reconnectEpoch = uint(raw.reconnect_epoch);
  if (reconnectEpoch === null) return reject('reconnect_epoch_invalid');
  const mappingEpoch = uint(raw.mapping_epoch);
  if (mappingEpoch === null) return reject('mapping_epoch_invalid');
  const capabilities = parseCapabilities(raw.capabilities);
  if (!capabilities) return reject('capability_invalid');
  const parsedRaw = parseRaw(raw.raw);
  if (typeof parsedRaw === 'string') return reject(parsedRaw);
  const appliedMapping = parseAppliedMapping(raw.applied_mapping);
  if (!appliedMapping) return reject('applied_mapping_invalid');

  let conversions: CanonicalConversions;
  let quaternion: CanonicalQuaternionAvailability;
  if (hasCanonicalFields) {
    if (raw.raw_units !== 'counts') return reject('conversion_invalid');
    const parsedConversions = parseConversions(raw.si);
    if (!parsedConversions) return reject('conversion_invalid');
    const parsedQuaternion = parseQuaternionAvailability(raw.quaternion);
    if (!parsedQuaternion) return reject('quaternion_invalid');
    const capabilityMatches = (
      capability: boolean,
      availability: { readonly available: boolean; readonly reason?: SignalAvailabilityReason },
    ): boolean => capability
      ? availability.available || availability.reason !== 'capability_absent'
      : !availability.available && availability.reason === 'capability_absent';
    if (!capabilityMatches(capabilities.accel, parsedConversions.accel)
        || !capabilityMatches(capabilities.gyro, parsedConversions.gyro)
        || !capabilityMatches(capabilities.magnetometer, parsedConversions.magnetometer)) {
      return reject('conversion_invalid');
    }
    if (!capabilityMatches(capabilities.quaternion, parsedQuaternion)) return reject('quaternion_invalid');
    conversions = parsedConversions;
    quaternion = parsedQuaternion;
  } else {
    conversions = {
      accel: capabilities.accel ? unavailable('config_invalid') : unavailable('capability_absent'),
      gyro: capabilities.gyro ? unavailable('config_invalid') : unavailable('capability_absent'),
      magnetometer: capabilities.magnetometer ? unavailable('calibration_missing') : unavailable('capability_absent'),
    };
    quaternion = quaternionFromInput(raw.quaternion, capabilities.quaternion);
  }

  const value: CanonicalSignalSample = {
    schema: SCHEMA,
    device_id: deviceId,
    topic_token: topicToken,
    sequence,
    sequence_origin: raw.sequence_origin,
    acquisition_time_us: acquisitionTime,
    acquisition_clock: acquisitionClock,
    bridge_monotonic_time_us: bridgeTime,
    reconnect_epoch: reconnectEpoch,
    mapping_epoch: mappingEpoch,
    capabilities: { ...capabilities },
    raw: { ...parsedRaw },
    raw_units: 'counts',
    si: conversions,
    quaternion,
    applied_mapping: { ...appliedMapping },
  };
  return { ok: true, value: deepFreeze(value) };
}
