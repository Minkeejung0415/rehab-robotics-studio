"""Contracts for the optional OpenSim quaternion visualizer boundary."""

from __future__ import annotations

import math
import unittest

from rehab_robotics_bridge.opensim_adapter import (
    ros_xyzw_to_opensim_rotation,
)


class QuaternionConversionTests(unittest.TestCase):
    """Golden tests for ROS xyzw to right-handed active rotation conversion."""

    def assertMatrixAlmostEqual(self, actual, expected, places=12):
        self.assertEqual(len(actual), 3)
        for actual_row, expected_row in zip(actual, expected):
            self.assertEqual(len(actual_row), 3)
            for actual_value, expected_value in zip(actual_row, expected_row):
                self.assertAlmostEqual(
                    actual_value,
                    expected_value,
                    places=places,
                )

    def test_identity_maps_to_identity_rotation(self):
        rotation = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)
        self.assertEqual(rotation.scalar_first, (1.0, 0.0, 0.0, 0.0))
        self.assertMatrixAlmostEqual(
            rotation.matrix,
            (
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
        )

    def test_positive_ninety_degree_x_rotation(self):
        half_sqrt = math.sqrt(0.5)
        rotation = ros_xyzw_to_opensim_rotation(
            half_sqrt,
            0.0,
            0.0,
            half_sqrt,
        )
        self.assertMatrixAlmostEqual(
            rotation.matrix,
            (
                (1.0, 0.0, 0.0),
                (0.0, 0.0, -1.0),
                (0.0, 1.0, 0.0),
            ),
        )

    def test_positive_ninety_degree_y_rotation(self):
        half_sqrt = math.sqrt(0.5)
        rotation = ros_xyzw_to_opensim_rotation(
            0.0,
            half_sqrt,
            0.0,
            half_sqrt,
        )
        self.assertMatrixAlmostEqual(
            rotation.matrix,
            (
                (0.0, 0.0, 1.0),
                (0.0, 1.0, 0.0),
                (-1.0, 0.0, 0.0),
            ),
        )

    def test_positive_ninety_degree_z_rotation(self):
        half_sqrt = math.sqrt(0.5)
        rotation = ros_xyzw_to_opensim_rotation(
            0.0,
            0.0,
            half_sqrt,
            half_sqrt,
        )
        self.assertMatrixAlmostEqual(
            rotation.matrix,
            (
                (0.0, -1.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
        )

    def test_non_unit_input_is_normalized_once_at_boundary(self):
        unit = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)
        scaled = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 42.0)
        self.assertEqual(scaled, unit)

    def test_antipodal_inputs_produce_the_same_rotation_matrix(self):
        positive = ros_xyzw_to_opensim_rotation(0.1, -0.2, 0.3, 0.4)
        negative = ros_xyzw_to_opensim_rotation(-0.1, 0.2, -0.3, -0.4)
        self.assertEqual(positive.matrix, negative.matrix)

    def test_non_finite_component_is_rejected_with_reason_code(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "^quaternion_non_finite$",
                ):
                    ros_xyzw_to_opensim_rotation(value, 0.0, 0.0, 1.0)

    def test_near_zero_norm_is_rejected_with_reason_code(self):
        with self.assertRaisesRegex(
            ValueError,
            "^quaternion_near_zero$",
        ):
            ros_xyzw_to_opensim_rotation(1e-9, 0.0, 0.0, 0.0)


if __name__ == "__main__":
    unittest.main()
