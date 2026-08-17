"""Fail-closed, immutable, ROS-free canonical signal sample contract."""
from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .measurement_contract import (
    MeasurementConfig,
    accel_count_to_mps2,
    gyro_count_to_rad_s,
    magnetometer_counts_to_uT,
    validate_sensor_config,
)


SCHEMA = 'rehab.signal_sample.1'
RAW_FIELDS = ('ax', 'ay', 'az', 'gx', 'gy', 'gz', 'mx', 'my', 'mz')
CAPABILITY_FIELDS = ('accel', 'gyro', 'magnetometer', 'quaternion')
MAX_SAFE_INTEGER = 2**53 - 1
MAX_LABEL_LENGTH = 64
MAX_HASH_LENGTH = 128
MAX_CLOCK_LENGTH = 64
MIN_QUATERNION_NORM = 1e-8
MIN_AVAILABLE_QUATERNION_NORM = 0.5
MAX_AVAILABLE_QUATERNION_NORM = 1.5
_COMPACT_MAC_RE = re.compile(r'^[0-9a-fA-F]{12}$')
_DISPLAY_MAC_RE = re.compile(r'^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


def normalize_device_id(value: str) -> str:
    """Return the established canonical full eFuse/base-MAC identity."""
    if not isinstance(value, str) or not value:
        raise ValueError('device_id_invalid')
    if value.startswith('esp32:'):
        compact = value[6:]
    elif _DISPLAY_MAC_RE.fullmatch(value):
        compact = value.replace(':', '')
    else:
        compact = value
    if not _COMPACT_MAC_RE.fullmatch(compact):
        raise ValueError('device_id_invalid')
    return f'esp32:{compact.lower()}'


def device_topic_token(value: str) -> str:
    """Return the collision-safe full-MAC topic token."""
    return f'mac_{normalize_device_id(value)[6:]}'


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return copy.deepcopy(value)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return copy.deepcopy(value)


@dataclass(frozen=True)
class CanonicalSignalSample:
    """Deeply immutable canonical sample with detached JSON serialization."""

    value: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return _thaw(self.value)


def _uint(value: object, reason: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SAFE_INTEGER:
        raise ValueError(reason)
    return value


def _bounded_nullable_label(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > MAX_LABEL_LENGTH:
        raise ValueError('applied_mapping_invalid')
    return value


def _validate_raw(raw: object) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        raise ValueError('raw_field_missing')
    if any(field not in raw for field in RAW_FIELDS) or set(raw) != set(RAW_FIELDS):
        raise ValueError('raw_field_missing')
    result: dict[str, int] = {}
    for field in RAW_FIELDS:
        count = raw[field]
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError('raw_field_invalid')
        if not -32768 <= count <= 32767:
            raise ValueError('raw_field_out_of_range')
        result[field] = count
    return result


def _validate_capabilities(value: object) -> dict[str, bool]:
    if not isinstance(value, Mapping) or set(value) != set(CAPABILITY_FIELDS):
        raise ValueError('capability_invalid')
    if any(not isinstance(value[field], bool) for field in CAPABILITY_FIELDS):
        raise ValueError('capability_invalid')
    return {field: value[field] for field in CAPABILITY_FIELDS}


def _quaternion_availability(value: object, capable: bool) -> dict[str, Any]:
    if not capable:
        return {'available': False, 'reason': 'capability_absent'}
    if value is None:
        return {'available': False, 'reason': 'missing'}
    if not isinstance(value, Mapping):
        return {'available': False, 'reason': 'malformed'}
    status = value.get('status')
    if status == 'stale':
        return {'available': False, 'reason': 'stale'}
    values = value.get('values')
    if status != 'available' or not isinstance(values, (list, tuple)) or len(values) != 4:
        return {'available': False, 'reason': 'malformed'}
    if any(isinstance(component, bool) or not isinstance(component, (int, float))
           for component in values):
        if any(component in ('NaN', 'Infinity', '-Infinity') for component in values):
            return {'available': False, 'reason': 'non_finite'}
        return {'available': False, 'reason': 'malformed'}
    components = tuple(float(component) for component in values)
    if not all(math.isfinite(component) for component in components):
        return {'available': False, 'reason': 'non_finite'}
    scale = max(abs(component) for component in components)
    if scale == 0.0:
        return {'available': False, 'reason': 'zero_norm'}
    scaled_norm = math.hypot(*(component / scale for component in components))
    norm = scale * scaled_norm
    if norm < MIN_QUATERNION_NORM:
        return {'available': False, 'reason': 'zero_norm'}
    if not MIN_AVAILABLE_QUATERNION_NORM <= norm <= MAX_AVAILABLE_QUATERNION_NORM:
        return {'available': False, 'reason': 'norm_out_of_range'}
    return {'available': True, 'values': list(values)}


def _si_snapshot(
    raw: Mapping[str, int],
    measurement: object | None,
    capabilities: Mapping[str, bool],
) -> dict[str, Any]:
    """Build deterministic SI groups without attaching units to unavailable data."""
    config: MeasurementConfig | None
    if isinstance(measurement, MeasurementConfig):
        config = measurement
    elif isinstance(measurement, Mapping):
        try:
            config = validate_sensor_config(measurement)
        except ValueError:
            config = None
    else:
        config = None

    result: dict[str, Any] = {}
    if not capabilities['accel']:
        result['accel'] = {'available': False, 'reason': 'capability_absent'}
    elif config is None:
        result['accel'] = {'available': False, 'reason': 'config_invalid'}
    else:
        result['accel'] = {
            'available': True,
            'unit': 'm/s^2',
            'values': {axis: accel_count_to_mps2(raw[f'a{axis}'], config) for axis in 'xyz'},
        }
    if not capabilities['gyro']:
        result['gyro'] = {'available': False, 'reason': 'capability_absent'}
    elif config is None:
        result['gyro'] = {'available': False, 'reason': 'config_invalid'}
    else:
        result['gyro'] = {
            'available': True,
            'unit': 'rad/s',
            'values': {axis: gyro_count_to_rad_s(raw[f'g{axis}'], config) for axis in 'xyz'},
        }
    if not capabilities['magnetometer']:
        result['magnetometer'] = {'available': False, 'reason': 'capability_absent'}
    elif config is None:
        result['magnetometer'] = {'available': False, 'reason': 'calibration_missing'}
    elif config.magnetometer_availability != 'available':
        result['magnetometer'] = {
            'available': False,
            'reason': config.magnetometer_availability,
        }
    else:
        converted = magnetometer_counts_to_uT([raw['mx'], raw['my'], raw['mz']], config)
        result['magnetometer'] = {
            'available': True,
            'unit': 'µT',
            'values': dict(zip('xyz', converted)),
        }
    return result


def build_canonical_signal_sample(
    *,
    topic_token: str,
    sample: Mapping[str, Any],
    measurement: object | None = None,
) -> CanonicalSignalSample:
    """Validate, copy, and deeply freeze one canonical signal sample.

    Required-envelope violations raise a stable allowlisted ``ValueError`` code.
    Channel-level absence remains an explicit availability state.
    """
    if not isinstance(sample, Mapping) or sample.get('schema') != SCHEMA:
        raise ValueError('schema_invalid')
    allowed = {
        'schema', 'device_id', 'sequence', 'sequence_origin', 'acquisition_time_us',
        'acquisition_clock', 'bridge_monotonic_time_us', 'reconnect_epoch',
        'mapping_epoch', 'capabilities', 'raw', 'quaternion', 'applied_mapping',
    }
    if set(sample) - allowed:
        if any(key in sample for key in ('draft_mapping', 'desired_mapping', 'current_mapping')):
            raise ValueError('applied_mapping_invalid')
        raise ValueError('schema_invalid')

    device_id = normalize_device_id(sample.get('device_id'))
    if not isinstance(topic_token, str) or topic_token != device_topic_token(device_id):
        raise ValueError('topic_device_mismatch')
    sequence = _uint(sample.get('sequence'), 'sequence_invalid')
    sequence_origin = sample.get('sequence_origin')
    if sequence_origin not in ('device', 'bridge_session'):
        raise ValueError('sequence_origin_invalid')

    acquisition_time = sample.get('acquisition_time_us')
    acquisition_clock = sample.get('acquisition_clock')
    if acquisition_time is None:
        if acquisition_clock is not None:
            raise ValueError('acquisition_time_invalid')
    else:
        acquisition_time = _uint(acquisition_time, 'acquisition_time_invalid')
        if (not isinstance(acquisition_clock, str) or not acquisition_clock
                or len(acquisition_clock) > MAX_CLOCK_LENGTH):
            raise ValueError('acquisition_time_invalid')

    bridge_time = _uint(sample.get('bridge_monotonic_time_us'), 'bridge_time_invalid')
    reconnect_epoch = _uint(sample.get('reconnect_epoch'), 'reconnect_epoch_invalid')
    mapping_epoch = _uint(sample.get('mapping_epoch'), 'mapping_epoch_invalid')
    capabilities = _validate_capabilities(sample.get('capabilities'))
    raw = _validate_raw(sample.get('raw'))

    mapping = sample.get('applied_mapping')
    if not isinstance(mapping, Mapping) or set(mapping) != {'revision', 'segment', 'frame', 'model_hash'}:
        raise ValueError('applied_mapping_invalid')
    revision = _uint(mapping.get('revision'), 'applied_mapping_invalid')
    segment = _bounded_nullable_label(mapping.get('segment'))
    frame = _bounded_nullable_label(mapping.get('frame'))
    if (segment is None) != (frame is None):
        raise ValueError('applied_mapping_invalid')
    model_hash = mapping.get('model_hash')
    if not isinstance(model_hash, str) or not model_hash or len(model_hash) > MAX_HASH_LENGTH:
        raise ValueError('applied_mapping_invalid')

    canonical = {
        'schema': SCHEMA,
        'device_id': device_id,
        'topic_token': topic_token,
        'sequence': sequence,
        'sequence_origin': sequence_origin,
        'acquisition_time_us': acquisition_time,
        'acquisition_clock': acquisition_clock,
        'bridge_monotonic_time_us': bridge_time,
        'reconnect_epoch': reconnect_epoch,
        'mapping_epoch': mapping_epoch,
        'capabilities': capabilities,
        'raw': raw,
        'raw_units': 'counts',
        'si': _si_snapshot(raw, measurement, capabilities),
        'quaternion': _quaternion_availability(sample.get('quaternion'), capabilities['quaternion']),
        'applied_mapping': {
            'revision': revision,
            'segment': segment,
            'frame': frame,
            'model_hash': model_hash,
        },
    }
    return CanonicalSignalSample(_freeze(canonical))
