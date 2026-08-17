"""Canonical backend measurement contract for ESP32 ICM-20948 range-to-SI conversion.

Pure stdlib module — no ROS imports.

Exports:
    GRAVITY                 - Standard gravity (m/s² per g)
    DEG_TO_RAD              - Degree-to-radian conversion
    ACCEL_LSB_PER_G         - Accelerometer sensitivities by range (count/g)
    GYRO_LSB_PER_DPS        - Gyroscope sensitivities by range (count/(deg/s))
    SUPPORTED_ACCEL_RANGES_G  - Supported accelerometer ranges (frozenset)
    SUPPORTED_GYRO_RANGES_DPS - Supported gyroscope ranges (frozenset)
    MeasurementConfig       - Immutable config snapshot dataclass
    measurement_config()    - Build a MeasurementConfig from confirmed range values
    validate_sensor_config()- Strictly validate an inbound sensor_config dict
    config_as_json()        - Serialize a MeasurementConfig to the wire dict
    accel_count_to_mps2()   - Convert a raw count to m/s² using a config snapshot
    gyro_count_to_rad_s()   - Convert a raw count to rad/s using a config snapshot

Range tables match firmware kAccLsbPerG and kGyrLsbPerDps in step_node.ino /
step_node_slave.ino exactly.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping

# ── Physical constants ────────────────────────────────────────────────────────

GRAVITY: float = 9.80665          # m/s² per g  (BIPM / ISO 80000-3)
DEG_TO_RAD: float = math.pi / 180.0

# ── ICM-20948 full-scale range sensitivity tables ─────────────────────────────
# Keys are the range label used in ROS parameters and the wire sensor_config.
# Values are the LSB-per-unit sensitivity at that range preset.
# Matches firmware: kAccLsbPerG = {16384, 8192, 4096, 2048}
#                   kGyrLsbPerDps = {131.072, 65.536, 32.768, 16.384}

ACCEL_LSB_PER_G: dict[int, float] = {
    2:  16384.0,
    4:   8192.0,
    8:   4096.0,
    16:  2048.0,
}

GYRO_LSB_PER_DPS: dict[int, float] = {
    250:  131.072,
    500:   65.536,
    1000:  32.768,
    2000:  16.384,
}

SUPPORTED_ACCEL_RANGES_G: frozenset[int] = frozenset(ACCEL_LSB_PER_G)
SUPPORTED_GYRO_RANGES_DPS: frozenset[int] = frozenset(GYRO_LSB_PER_DPS)


# ── Immutable config snapshot ─────────────────────────────────────────────────

@dataclass(frozen=True)
class MeasurementConfig:
    """Immutable snapshot of one device's confirmed measurement configuration.

    Constructed only via measurement_config(). frozen=True prevents mutation
    between the point of JSON emission and native Imu field assignment.
    """
    accel_range_g: int
    gyro_range_dps: int
    accel_lsb_per_g: float
    gyro_lsb_per_dps: float
    magnetometer_sensitivity_uT_per_count: float | None = None
    magnetometer_calibration: 'MagnetometerCalibration | None' = None
    magnetometer_availability: str = 'calibration_missing'


@dataclass(frozen=True)
class MagnetometerCalibration:
    """Validated bounded calibration provenance and affine coefficients."""

    schema: str
    sensor_model: str
    axis_convention: str
    calibration_id: str
    calibration_hash: str
    hard_iron_uT: tuple[float, float, float]
    soft_iron: tuple[tuple[float, float, float], ...]


_CALIBRATION_HASH_RE = re.compile(r'^sha256:[0-9a-f]{16,64}$')
_MAX_PROVENANCE_TEXT = 64


def _finite_vector(value: object, length: int) -> tuple[float, ...] | None:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return None
    result = tuple(float(item) for item in value)
    return result if all(math.isfinite(item) for item in result) else None


def validate_magnetometer_calibration(obj: object) -> MagnetometerCalibration:
    """Validate a ``rehab.mag_calibration.1`` artifact or raise its stable code."""
    if not isinstance(obj, Mapping):
        raise ValueError('calibration_invalid')
    required = {
        'schema', 'sensor_model', 'axis_convention', 'calibration_id',
        'calibration_hash', 'hard_iron_uT', 'soft_iron',
    }
    if set(obj) != required or obj.get('schema') != 'rehab.mag_calibration.1':
        raise ValueError('calibration_invalid')
    for key in ('sensor_model', 'calibration_id'):
        value = obj.get(key)
        if not isinstance(value, str) or not value or len(value) > _MAX_PROVENANCE_TEXT:
            raise ValueError('calibration_invalid')
    if obj.get('axis_convention') != 'xyz':
        raise ValueError('calibration_invalid')
    calibration_hash = obj.get('calibration_hash')
    if not isinstance(calibration_hash, str) or not _CALIBRATION_HASH_RE.fullmatch(calibration_hash):
        raise ValueError('calibration_invalid')
    hard_iron = _finite_vector(obj.get('hard_iron_uT'), 3)
    matrix_obj = obj.get('soft_iron')
    if hard_iron is None or not isinstance(matrix_obj, (list, tuple)) or len(matrix_obj) != 3:
        raise ValueError('calibration_invalid')
    rows = tuple(_finite_vector(row, 3) for row in matrix_obj)
    if any(row is None for row in rows):
        raise ValueError('calibration_invalid')
    return MagnetometerCalibration(
        schema='rehab.mag_calibration.1',
        sensor_model=obj['sensor_model'],
        axis_convention='xyz',
        calibration_id=obj['calibration_id'],
        calibration_hash=calibration_hash,
        hard_iron_uT=hard_iron,
        soft_iron=rows,  # type: ignore[arg-type]
    )


# ── Public factory ────────────────────────────────────────────────────────────

def measurement_config(
    accel_range_g: int,
    gyro_range_dps: int,
    *,
    magnetometer_sensitivity_uT_per_count: float | None = None,
    magnetometer_calibration: object | None = None,
) -> MeasurementConfig:
    """Build a MeasurementConfig from confirmed range values.

    Raises ValueError for any unsupported range value.
    This is the only function that constructs MeasurementConfig.
    """
    if accel_range_g not in SUPPORTED_ACCEL_RANGES_G:
        raise ValueError(
            f'accel_range_g {accel_range_g!r} is not supported; '
            f'must be one of {sorted(SUPPORTED_ACCEL_RANGES_G)}'
        )
    if gyro_range_dps not in SUPPORTED_GYRO_RANGES_DPS:
        raise ValueError(
            f'gyro_range_dps {gyro_range_dps!r} is not supported; '
            f'must be one of {sorted(SUPPORTED_GYRO_RANGES_DPS)}'
        )
    sensitivity: float | None = None
    calibration: MagnetometerCalibration | None = None
    availability = 'calibration_missing'
    if magnetometer_sensitivity_uT_per_count is not None:
        candidate = magnetometer_sensitivity_uT_per_count
        if (isinstance(candidate, bool) or not isinstance(candidate, (int, float))
                or not math.isfinite(candidate) or candidate <= 0):
            availability = 'calibration_invalid'
        else:
            sensitivity = float(candidate)
            if magnetometer_calibration is not None:
                try:
                    calibration = validate_magnetometer_calibration(magnetometer_calibration)
                except ValueError:
                    availability = 'calibration_invalid'
                else:
                    availability = 'available'
    elif magnetometer_calibration is not None:
        availability = 'calibration_invalid'
    return MeasurementConfig(
        accel_range_g=accel_range_g,
        gyro_range_dps=gyro_range_dps,
        accel_lsb_per_g=ACCEL_LSB_PER_G[accel_range_g],
        gyro_lsb_per_dps=GYRO_LSB_PER_DPS[gyro_range_dps],
        magnetometer_sensitivity_uT_per_count=sensitivity,
        magnetometer_calibration=calibration,
        magnetometer_availability=availability,
    )


# ── Wire-format serialiser ────────────────────────────────────────────────────

def config_as_json(config: MeasurementConfig) -> dict:
    """Serialize a MeasurementConfig to the sensor_config wire dict.

    Values are taken from the canonical literal table (not re-derived floats)
    to guarantee exact round-trip through JSON without floating-point drift.
    """
    result = {
        'accel_range_g':     config.accel_range_g,
        'gyro_range_dps':    config.gyro_range_dps,
        'accel_lsb_per_g':   ACCEL_LSB_PER_G[config.accel_range_g],
        'gyro_lsb_per_dps':  GYRO_LSB_PER_DPS[config.gyro_range_dps],
        'units': {
            'raw':                 'count',
            'accel_range':         'g',
            'gyro_range':          'deg/s',
            'accel_sensitivity':   'count/g',
            'gyro_sensitivity':    'count/(deg/s)',
            'linear_acceleration': 'm/s^2',
            'angular_velocity':    'rad/s',
            'magnetic_field':      'µT',
        },
    }
    result['magnetometer'] = {
        'sensitivity_uT_per_count': config.magnetometer_sensitivity_uT_per_count,
        'availability': config.magnetometer_availability,
        'calibration': calibration_as_json(config.magnetometer_calibration),
    }
    return result


def calibration_as_json(calibration: MagnetometerCalibration | None) -> dict | None:
    if calibration is None:
        return None
    return {
        'schema': calibration.schema,
        'sensor_model': calibration.sensor_model,
        'axis_convention': calibration.axis_convention,
        'calibration_id': calibration.calibration_id,
        'calibration_hash': calibration.calibration_hash,
        'hard_iron_uT': list(calibration.hard_iron_uT),
        'soft_iron': [list(row) for row in calibration.soft_iron],
    }


# ── Strict inbound validator ──────────────────────────────────────────────────

def validate_sensor_config(obj: object) -> MeasurementConfig:
    """Strictly validate an inbound sensor_config dict and return the config.

    Raises ValueError with a descriptive message for any structural or
    semantic violation. On success, returns the equivalent MeasurementConfig.

    Checks performed (in order):
      1. obj must be a dict
      2. All required keys must be present
      3. accel_range_g must be in SUPPORTED_ACCEL_RANGES_G
      4. gyro_range_dps must be in SUPPORTED_GYRO_RANGES_DPS
      5. accel_lsb_per_g must be finite and positive
      6. gyro_lsb_per_dps must be finite and positive
      7. accel_lsb_per_g must be consistent with canonical table value (rtol 1e-9)
      8. gyro_lsb_per_dps must be consistent with canonical table value (rtol 1e-9)
      9. units must be a dict with a 'raw' key
    """
    _REQUIRED_KEYS = frozenset({
        'accel_range_g', 'gyro_range_dps', 'accel_lsb_per_g', 'gyro_lsb_per_dps', 'units',
    })

    if not isinstance(obj, dict):
        raise ValueError(
            f'sensor_config must be a dict, got {type(obj).__name__!r}'
        )

    missing = _REQUIRED_KEYS - obj.keys()
    if missing:
        raise ValueError(
            f'sensor_config is missing required keys: {sorted(missing)}'
        )

    accel_range_g = obj['accel_range_g']
    if accel_range_g not in SUPPORTED_ACCEL_RANGES_G:
        raise ValueError(
            f'sensor_config accel_range_g {accel_range_g!r} is not supported; '
            f'must be one of {sorted(SUPPORTED_ACCEL_RANGES_G)}'
        )

    gyro_range_dps = obj['gyro_range_dps']
    if gyro_range_dps not in SUPPORTED_GYRO_RANGES_DPS:
        raise ValueError(
            f'sensor_config gyro_range_dps {gyro_range_dps!r} is not supported; '
            f'must be one of {sorted(SUPPORTED_GYRO_RANGES_DPS)}'
        )

    accel_lsb = obj['accel_lsb_per_g']
    if not (isinstance(accel_lsb, (int, float)) and math.isfinite(accel_lsb) and accel_lsb > 0):
        raise ValueError(
            f'sensor_config accel_lsb_per_g must be a finite positive number, '
            f'got {accel_lsb!r}'
        )

    gyro_lsb = obj['gyro_lsb_per_dps']
    if not (isinstance(gyro_lsb, (int, float)) and math.isfinite(gyro_lsb) and gyro_lsb > 0):
        raise ValueError(
            f'sensor_config gyro_lsb_per_dps must be a finite positive number, '
            f'got {gyro_lsb!r}'
        )

    expected_accel_lsb = ACCEL_LSB_PER_G[accel_range_g]
    if not math.isclose(accel_lsb, expected_accel_lsb, rel_tol=1e-9):
        raise ValueError(
            f'sensor_config accel_lsb_per_g {accel_lsb!r} is inconsistent with '
            f'canonical value {expected_accel_lsb!r} for accel_range_g={accel_range_g}'
        )

    expected_gyro_lsb = GYRO_LSB_PER_DPS[gyro_range_dps]
    if not math.isclose(gyro_lsb, expected_gyro_lsb, rel_tol=1e-9):
        raise ValueError(
            f'sensor_config gyro_lsb_per_dps {gyro_lsb!r} is inconsistent with '
            f'canonical value {expected_gyro_lsb!r} for gyro_range_dps={gyro_range_dps}'
        )

    units = obj['units']
    if not isinstance(units, dict) or 'raw' not in units:
        raise ValueError(
            "sensor_config units must be a dict containing at least a 'raw' key"
        )

    mag = obj.get('magnetometer')
    if mag is None:
        return MeasurementConfig(
            accel_range_g=accel_range_g,
            gyro_range_dps=gyro_range_dps,
            accel_lsb_per_g=accel_lsb,
            gyro_lsb_per_dps=gyro_lsb,
        )
    if not isinstance(mag, Mapping):
        raise ValueError('sensor_config magnetometer must be a dict')
    return measurement_config(
        accel_range_g,
        gyro_range_dps,
        magnetometer_sensitivity_uT_per_count=mag.get('sensitivity_uT_per_count'),
        magnetometer_calibration=mag.get('calibration'),
    )


# ── SI conversion helpers ─────────────────────────────────────────────────────

def accel_count_to_mps2(count: int, config: MeasurementConfig) -> float:
    """Convert a raw accelerometer count to m/s² using the config snapshot."""
    return count / config.accel_lsb_per_g * GRAVITY


def gyro_count_to_rad_s(count: int, config: MeasurementConfig) -> float:
    """Convert a raw gyroscope count to rad/s using the config snapshot."""
    return count / config.gyro_lsb_per_dps * DEG_TO_RAD


def magnetometer_counts_to_uT(
    counts: tuple[int, int, int] | list[int],
    config: MeasurementConfig,
) -> tuple[float, float, float]:
    """Convert counts only when sensitivity and calibration both validate."""
    if (config.magnetometer_availability != 'available'
            or config.magnetometer_sensitivity_uT_per_count is None
            or config.magnetometer_calibration is None):
        raise ValueError(config.magnetometer_availability)
    if (not isinstance(counts, (tuple, list)) or len(counts) != 3
            or any(isinstance(count, bool) or not isinstance(count, int) for count in counts)):
        raise ValueError('raw_field_invalid')
    sensitivity = config.magnetometer_sensitivity_uT_per_count
    calibration = config.magnetometer_calibration
    centered = tuple(
        count * sensitivity - bias
        for count, bias in zip(counts, calibration.hard_iron_uT)
    )
    return tuple(
        sum(coefficient * value for coefficient, value in zip(row, centered))
        for row in calibration.soft_iron
    )
