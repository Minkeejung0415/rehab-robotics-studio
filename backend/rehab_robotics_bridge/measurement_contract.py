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
from dataclasses import dataclass

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


# ── Public factory ────────────────────────────────────────────────────────────

def measurement_config(accel_range_g: int, gyro_range_dps: int) -> MeasurementConfig:
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
    return MeasurementConfig(
        accel_range_g=accel_range_g,
        gyro_range_dps=gyro_range_dps,
        accel_lsb_per_g=ACCEL_LSB_PER_G[accel_range_g],
        gyro_lsb_per_dps=GYRO_LSB_PER_DPS[gyro_range_dps],
    )


# ── Wire-format serialiser ────────────────────────────────────────────────────

def config_as_json(config: MeasurementConfig) -> dict:
    """Serialize a MeasurementConfig to the sensor_config wire dict.

    Values are taken from the canonical literal table (not re-derived floats)
    to guarantee exact round-trip through JSON without floating-point drift.
    """
    return {
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
        },
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

    return MeasurementConfig(
        accel_range_g=accel_range_g,
        gyro_range_dps=gyro_range_dps,
        accel_lsb_per_g=accel_lsb,
        gyro_lsb_per_dps=gyro_lsb,
    )


# ── SI conversion helpers ─────────────────────────────────────────────────────

def accel_count_to_mps2(count: int, config: MeasurementConfig) -> float:
    """Convert a raw accelerometer count to m/s² using the config snapshot."""
    return count / config.accel_lsb_per_g * GRAVITY


def gyro_count_to_rad_s(count: int, config: MeasurementConfig) -> float:
    """Convert a raw gyroscope count to rad/s using the config snapshot."""
    return count / config.gyro_lsb_per_dps * DEG_TO_RAD
