"""Frozen OpenSim IK / calibration ROS contract constants for Phases 17–19.

Contracts only — no publishers, service servers, or OpenSim solver imports.
Human-readable twin: ``docs/opensim-ik-contracts.md``.
"""
from __future__ import annotations

from enum import Enum

# Locked product output (D-16-03). Supersedes ARCHITECTURE.md draft ``/joint_states``.
JOINT_STATES_TOPIC = "/opensim/joint_states"
JOINT_STATES_MSG_TYPE = "sensor_msgs/msg/JointState"

# Paired IMU inputs (defaults; topics remain configurable at launch).
DEFAULT_MASTER_IMU_TOPIC = "/esp32/master/imu"
DEFAULT_SLAVE_IMU_TOPIC = "/esp32/slave/imu"
DEFAULT_MASTER_FRAME = "femur_r_imu"
DEFAULT_SLAVE_FRAME = "tibia_r_imu"

# Calibration controls (Phase 17).
CALIBRATION_CAPTURE_SERVICE = "/opensim/calibration/capture"
CALIBRATION_CLEAR_SERVICE = "/opensim/calibration/clear"
VISUALIZER_OPEN_SERVICE = "/opensim/visualizer/open"

# Status / diagnostics topics (Phase 18).
IK_STATUS_TOPIC = "/opensim/ik_status"
IK_STATUS_SCHEMA = "rehab.opensim_ik_status.1"
CALIBRATION_STATUS_TOPIC = "/opensim/calibration_status"
DIAGNOSTICS_TOPIC = "/diagnostics"
DIAGNOSTICS_SCHEMA = "rehab.opensim_diagnostics.1"

# Default product coordinate (D-18-08).
DEFAULT_IK_JOINT_NAME = "knee_angle_r"

# Retired non-product path (D-16-01). Debug only; never the product IK output.
PRODUCT_JOINT_ANGLE_TOPIC = "/opensim/joint_angle"  # deprecated


class CalibrationState(str, Enum):
    """Hard calibration gate states for joint-state publication (D-16-04)."""

    UNCALIBRATED = "UNCALIBRATED"
    CAPTURING = "CAPTURING"
    CALIBRATED = "CALIBRATED"
    FAILED = "FAILED"


def may_publish_joint_states(state: CalibrationState | str) -> bool:
    """Return True only when calibration state is CALIBRATED.

    Hard gate (D-16-04): no ``sensor_msgs/JointState`` publication on
    ``JOINT_STATES_TOPIC`` until the system is CALIBRATED and a solution is
    valid (validity is enforced by the future solver — this helper covers the
    calibration half of the gate).
    """

    value = state.value if isinstance(state, CalibrationState) else str(state)
    return value == CalibrationState.CALIBRATED.value
