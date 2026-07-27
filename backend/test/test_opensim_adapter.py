"""Contracts for the optional OpenSim quaternion visualizer boundary."""

from __future__ import annotations

import math
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from rehab_robotics_bridge.opensim_adapter import (
    OpenSimVisualizerAdapter,
    UnavailableVisualizerAdapter,
    create_visualizer_adapter,
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

    def test_extreme_finite_components_normalize_without_overflow(self):
        rotation = ros_xyzw_to_opensim_rotation(
            1e308,
            1e308,
            1e308,
            1e308,
        )
        self.assertEqual(rotation.scalar_first, (0.5, 0.5, 0.5, 0.5))
        self.assertMatrixAlmostEqual(
            rotation.matrix,
            (
                (0.0, 0.0, 1.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
            ),
        )

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

    def test_component_scale_does_not_replace_total_norm_threshold(self):
        rotation = ros_xyzw_to_opensim_rotation(6e-9, 6e-9, 6e-9, 6e-9)
        self.assertEqual(rotation.scalar_first, (0.5, 0.5, 0.5, 0.5))


class _FakeTransform:
    def __init__(self, rotation=None, translation=None):
        self.rotation = rotation
        self.translation = translation

    def p(self):
        return self.translation


class _FakeFrame:
    def __init__(self, path, translation):
        self.path = path
        self._transform = _FakeTransform(translation=translation)
        self.transform_requests = []

    def getTransformInGround(self, state):
        self.transform_requests.append(state)
        return self._transform


class _FakeDecorativeGeometry:
    def __init__(self):
        self.color = None
        self.transform = None

    def setColor(self, color):
        self.color = color
        return self

    def setTransform(self, transform):
        self.transform = transform
        return self


class _FakeDecorativeFrame(_FakeDecorativeGeometry):
    def __init__(self, axis_length=1.0):
        super().__init__()
        self.axis_length = axis_length


class _FakeDecorativeText(_FakeDecorativeGeometry):
    def __init__(self, text):
        super().__init__()
        self.text = text


class _FakeDecorations(_FakeDecorativeGeometry):
    def __init__(self):
        super().__init__()
        self.children = []

    def addDecoration(self, decoration):
        self.children.append(decoration)
        return self


class _FakeSimbodyVisualizer:
    def __init__(self):
        self.decorations = []
        self.add_calls = []
        self.updated_indices = []

    def addDecoration(self, body_index, transform, decoration):
        self.add_calls.append((body_index, transform, decoration))
        self.decorations.append(decoration)
        return len(self.decorations) - 1

    def updDecoration(self, index):
        self.updated_indices.append(index)
        return self.decorations[index]


class _FakeModelVisualizer:
    def __init__(self, calls):
        self.calls = calls
        self.simbody = _FakeSimbodyVisualizer()
        self.show_states = []

    def updSimbodyVisualizer(self):
        self.calls.append("updSimbodyVisualizer")
        return self.simbody

    def show(self, state):
        self.show_states.append(state)


class _FakeModel:
    def __init__(self, module, path):
        self.module = module
        self.path = path
        self.calls = module.calls
        self.frames = {
            "/bodyset/femur_r_imu": _FakeFrame(
                "/bodyset/femur_r_imu",
                module.Vec3(1.0, 2.0, 3.0),
            ),
            "/bodyset/tibia_r_imu": _FakeFrame(
                "/bodyset/tibia_r_imu",
                module.Vec3(4.0, 5.0, 6.0),
            ),
        }
        self.visualizer = _FakeModelVisualizer(self.calls)
        self.state = object()

    def setUseVisualizer(self, enabled):
        self.calls.append(("setUseVisualizer", enabled))

    def initSystem(self):
        self.calls.append("initSystem")
        return self.state

    def getComponent(self, path):
        self.calls.append(("getComponent", path))
        if path not in self.frames:
            raise RuntimeError("component not found")
        return self.frames[path]

    def updVisualizer(self):
        self.calls.append("updVisualizer")
        return self.visualizer


class _FakeFrameType:
    @staticmethod
    def safeDownCast(component):
        return component if isinstance(component, _FakeFrame) else None


class _FakeQuaternion:
    def __init__(self, w, x, y, z):
        self.values = (w, x, y, z)


class _FakeOpenSim:
    Frame = _FakeFrameType
    Transform = _FakeTransform
    Decorations = _FakeDecorations
    DecorativeFrame = _FakeDecorativeFrame
    DecorativeText = _FakeDecorativeText
    Quaternion = _FakeQuaternion

    def __init__(self):
        self.calls = []
        self.models = []

    def Model(self, path):
        self.calls.append(("Model", path))
        model = _FakeModel(self, path)
        self.models.append(model)
        return model

    @staticmethod
    def Rotation(quaternion):
        if not isinstance(quaternion, _FakeQuaternion):
            raise TypeError("Rotation requires an OpenSim Quaternion")
        return ("Rotation", quaternion)

    @staticmethod
    def Vec3(*values):
        return ("Vec3", values)

    @staticmethod
    def MobilizedBodyIndex(index):
        return ("MobilizedBodyIndex", index)


class OpenSimAdapterContractTests(unittest.TestCase):
    """Always-run tests against an API-shaped fake OpenSim binding."""

    def setUp(self):
        self.model_file = tempfile.NamedTemporaryFile(
            suffix=".osim",
            delete=False,
        )
        self.model_file.close()
        self.addCleanup(
            lambda: Path(self.model_file.name).unlink(missing_ok=True),
        )
        self.mappings = {
            "master": "/bodyset/femur_r_imu",
            "slave": "/bodyset/tibia_r_imu",
        }

    def test_unavailable_adapter_is_stable_successful_no_op_for_both_roles(self):
        adapter = UnavailableVisualizerAdapter(
            reason="opensim_bindings_unavailable",
            frame_mappings=self.mappings,
        )
        rotation = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)

        self.assertTrue(adapter.update_sensor("master", self.mappings["master"], rotation))
        self.assertTrue(adapter.update_sensor("slave", self.mappings["slave"], rotation))
        self.assertEqual(
            adapter.status(),
            {
                "available": False,
                "state": "unavailable",
                "reason": "opensim_bindings_unavailable",
            },
        )

    def test_factory_reports_empty_and_missing_model_paths_before_import(self):
        empty = create_visualizer_adapter("", self.mappings)
        missing = create_visualizer_adapter(
            str(Path(self.model_file.name).with_name("missing.osim")),
            self.mappings,
        )
        self.assertEqual(empty.status()["reason"], "model_path_empty")
        self.assertEqual(missing.status()["reason"], "model_path_not_found")

    def test_factory_reports_absent_bindings_without_import_time_failure(self):
        from unittest.mock import patch

        with patch(
            "rehab_robotics_bridge.opensim_adapter.import_module",
            side_effect=ModuleNotFoundError("opensim"),
        ):
            adapter = create_visualizer_adapter(self.model_file.name, self.mappings)
        self.assertIsInstance(adapter, UnavailableVisualizerAdapter)
        self.assertEqual(
            adapter.status()["reason"],
            "opensim_bindings_unavailable",
        )

    def test_factory_reports_model_load_and_unknown_frame_failures(self):
        from unittest.mock import patch

        broken_module = SimpleNamespace(
            Model=lambda _path: (_ for _ in ()).throw(RuntimeError("bad model")),
        )
        with patch(
            "rehab_robotics_bridge.opensim_adapter.import_module",
            return_value=broken_module,
        ):
            broken = create_visualizer_adapter(self.model_file.name, self.mappings)
        self.assertEqual(broken.status()["reason"], "model_load_failed")

        fake = _FakeOpenSim()
        unknown_mappings = {"master": "/missing"}
        with patch(
            "rehab_robotics_bridge.opensim_adapter.import_module",
            return_value=fake,
        ):
            unknown = create_visualizer_adapter(
                self.model_file.name,
                unknown_mappings,
            )
        self.assertEqual(
            unknown.status()["reason"],
            "frame_not_found:master:/missing",
        )

    def test_factory_reports_unsupported_dynamic_decoration_bindings(self):
        from unittest.mock import patch

        fake = _FakeOpenSim()
        original_model_factory = fake.Model

        def model_without_dynamic_decorations(path):
            model = original_model_factory(path)
            model.visualizer.simbody.addDecoration = None
            model.visualizer.simbody.updDecoration = None
            return model

        fake.Model = model_without_dynamic_decorations
        with patch(
            "rehab_robotics_bridge.opensim_adapter.import_module",
            return_value=fake,
        ):
            adapter = create_visualizer_adapter(
                self.model_file.name,
                self.mappings,
            )
        self.assertEqual(
            adapter.status()["reason"],
            "dynamic_decorations_unsupported_by_bindings",
        )

    def test_initialization_owns_model_resolves_exact_frames_and_retains_labels(self):
        fake = _FakeOpenSim()
        adapter = OpenSimVisualizerAdapter(
            self.model_file.name,
            self.mappings,
            opensim_module=fake,
        )
        model = fake.models[0]

        self.assertLess(
            fake.calls.index(("setUseVisualizer", True)),
            fake.calls.index("initSystem"),
        )
        self.assertIn(("getComponent", self.mappings["master"]), fake.calls)
        self.assertIn(("getComponent", self.mappings["slave"]), fake.calls)
        for frame in model.frames.values():
            self.assertEqual(frame.transform_requests, [model.state])

        retained = model.visualizer.simbody.decorations
        self.assertEqual(len(retained), 2)
        labels = [
            child.text
            for group in retained
            for child in group.children
            if isinstance(child, _FakeDecorativeText)
        ]
        self.assertEqual(
            labels,
            [
                "master: /bodyset/femur_r_imu",
                "slave: /bodyset/tibia_r_imu",
            ],
        )
        self.assertEqual(adapter.status()["available"], True)

    def test_fake_enforces_supported_quaternion_rotation_constructor(self):
        fake = _FakeOpenSim()
        quaternion = fake.Quaternion(1.0, 0.0, 0.0, 0.0)

        native_rotation = fake.Rotation(quaternion)

        self.assertIs(native_rotation[1], quaternion)
        with self.assertRaises(TypeError):
            fake.Rotation(*range(9))

    def test_each_update_mutates_only_its_retained_ground_decoration_and_shows(self):
        fake = _FakeOpenSim()
        adapter = OpenSimVisualizerAdapter(
            self.model_file.name,
            self.mappings,
            opensim_module=fake,
        )
        model = fake.models[0]
        simbody = model.visualizer.simbody
        master_before = simbody.decorations[0].transform
        slave_before = simbody.decorations[1].transform
        rotation = ros_xyzw_to_opensim_rotation(
            0.0,
            0.0,
            math.sqrt(0.5),
            math.sqrt(0.5),
        )

        self.assertTrue(
            adapter.update_sensor(
                "master",
                self.mappings["master"],
                rotation,
            ),
        )

        self.assertEqual(simbody.updated_indices, [0])
        self.assertIsNot(simbody.decorations[0].transform, master_before)
        self.assertIs(simbody.decorations[1].transform, slave_before)
        self.assertEqual(
            simbody.decorations[0].transform.translation,
            model.frames[self.mappings["master"]]._transform.p(),
        )
        self.assertEqual(
            simbody.decorations[0].transform.rotation[0],
            "Rotation",
        )
        self.assertEqual(
            simbody.decorations[0].transform.rotation[1].values,
            rotation.scalar_first,
        )
        self.assertEqual(model.visualizer.show_states, [model.state])

    def test_mapping_mismatch_is_rejected_without_mutation(self):
        fake = _FakeOpenSim()
        adapter = OpenSimVisualizerAdapter(
            self.model_file.name,
            self.mappings,
            opensim_module=fake,
        )
        model = fake.models[0]
        rotation = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)

        with self.assertRaisesRegex(ValueError, "^frame_mapping_mismatch$"):
            adapter.update_sensor("master", self.mappings["slave"], rotation)
        self.assertEqual(model.visualizer.simbody.updated_indices, [])
        self.assertEqual(model.visualizer.show_states, [])

    def test_native_update_failure_becomes_explicit_unavailable_status(self):
        fake = _FakeOpenSim()
        adapter = OpenSimVisualizerAdapter(
            self.model_file.name,
            self.mappings,
            opensim_module=fake,
        )
        model = fake.models[0]
        model.visualizer.show = lambda _state: (_ for _ in ()).throw(
            RuntimeError("visualizer closed"),
        )
        rotation = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)

        self.assertFalse(
            adapter.update_sensor(
                "master",
                self.mappings["master"],
                rotation,
            ),
        )
        self.assertEqual(
            adapter.status()["reason"],
            "visualizer_update_failed",
        )
        self.assertFalse(adapter.status()["available"])

    def test_successful_update_recovers_after_transient_native_failure(self):
        fake = _FakeOpenSim()
        adapter = OpenSimVisualizerAdapter(
            self.model_file.name,
            self.mappings,
            opensim_module=fake,
        )
        model = fake.models[0]
        attempts = 0

        def fail_once(state):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("transient visualizer failure")
            model.visualizer.show_states.append(state)

        model.visualizer.show = fail_once
        rotation = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)

        self.assertFalse(
            adapter.update_sensor(
                "master",
                self.mappings["master"],
                rotation,
            ),
        )
        self.assertEqual(
            adapter.status(),
            {
                "available": False,
                "state": "unavailable",
                "reason": "visualizer_update_failed",
                "mode": "retained_decorations",
            },
        )

        self.assertTrue(
            adapter.update_sensor(
                "master",
                self.mappings["master"],
                rotation,
            ),
        )
        self.assertEqual(
            adapter.status(),
            {
                "available": True,
                "state": "ready",
                "reason": "",
                "mode": "retained_decorations",
            },
        )


@unittest.skipUnless(
    importlib.util.find_spec("opensim") is not None,
    "opensim module is not installed",
)
class OpenSimInstalledRuntimeSmokeTests(unittest.TestCase):
    """Exercise a minimal real model when OpenSim is already installed."""

    def test_supported_rotation_constructor_contract(self):
        import opensim

        quaternion = opensim.Quaternion(1.0, 0.0, 0.0, 0.0)
        rotation = opensim.Rotation(quaternion)

        self.assertIsNotNone(rotation)
        with self.assertRaises(TypeError):
            opensim.Rotation(*range(9))

    def test_minimal_model_accepts_identity_and_positive_ninety_z_updates(self):
        import opensim

        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = str(Path(temp_dir) / "adapter-smoke.osim")
            model = opensim.Model()
            model.setName("adapter_smoke")
            for name, offset in (
                ("femur_r_imu", opensim.Vec3(0.1, 0.0, 0.0)),
                ("tibia_r_imu", opensim.Vec3(0.0, 0.2, 0.0)),
            ):
                frame = opensim.PhysicalOffsetFrame()
                frame.setName(name)
                frame.connectSocket_parent(model.getGround())
                frame.set_translation(offset)
                model.addComponent(frame)
            model.printToXML(model_path)

            mappings = {
                "master": "/femur_r_imu",
                "slave": "/tibia_r_imu",
            }
            adapter = create_visualizer_adapter(model_path, mappings)
            self.assertTrue(adapter.status()["available"], adapter.status())
            identity = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)
            positive_z = ros_xyzw_to_opensim_rotation(
                0.0,
                0.0,
                math.sqrt(0.5),
                math.sqrt(0.5),
            )
            self.assertTrue(
                adapter.update_sensor("master", mappings["master"], identity),
            )
            self.assertTrue(
                adapter.update_sensor("slave", mappings["slave"], positive_z),
            )


if __name__ == "__main__":
    unittest.main()
