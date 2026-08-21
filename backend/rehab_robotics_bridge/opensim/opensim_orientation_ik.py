"""OpenSim Python orientation-IK adapter (Phase 18).

Research preferred a dedicated C++ OpenSense package on OpenSim 4.6 with
``BufferedOrientationsReference``. This milestone uses the pragmatic Python
path inside ``opensim_bridge`` on WSL OpenSim 4.5.2 (D-18-02). When required
bindings are missing, the factory returns ``UnavailableOrientationIkSolver``
— never a custom relative-quaternion product angle.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
import time
from typing import Any, Sequence

from rehab_robotics_bridge.opensim.calibration import CalibrationArtifact
from rehab_robotics_bridge.opensim.n_sensor_calibration import (
    apply_reference_pose_offsets,
)
from rehab_robotics_bridge.opensim.orientation_ik import (
    DEFAULT_JOINT_NAME,
    IkSolution,
    UnavailableOrientationIkSolver,
    apply_mounting_offsets,
)
from rehab_robotics_bridge.opensim_adapter import (
    configure_opensim_geometry_search_paths,
    ros_xyzw_to_opensim_rotation,
)


def probe_opensim_orientation_ik_apis(opensim_module: Any) -> dict[str, bool]:
    """Report presence of symbols required for orientation InverseKinematics."""

    return {
        "InverseKinematicsSolver": hasattr(opensim_module, "InverseKinematicsSolver"),
        "OrientationsReference": hasattr(opensim_module, "OrientationsReference"),
        "BufferedOrientationsReference": hasattr(
            opensim_module,
            "BufferedOrientationsReference",
        ),
        "TimeSeriesTableQuaternion": hasattr(
            opensim_module,
            "TimeSeriesTableQuaternion",
        ),
        "MarkersReference": hasattr(opensim_module, "MarkersReference"),
        "OpenSenseUtilities": hasattr(opensim_module, "OpenSenseUtilities"),
        "Rotation": hasattr(opensim_module, "Rotation"),
        "Quaternion": hasattr(opensim_module, "Quaternion"),
    }


def _strip_leading_slash(name: str) -> str:
    return name[1:] if name.startswith("/") else name


def _component_path(frame_name: str) -> str:
    stripped = _strip_leading_slash(frame_name)
    return stripped if stripped.startswith("/") else f"/{stripped}"


class OpenSimOrientationIkSolver:
    """Single-thread owner of Model/State/InverseKinematicsSolver for live IK."""

    def __init__(
        self,
        *,
        model_path: str,
        master_frame: str,
        slave_frame: str,
        coordinate_paths: Sequence[str],
        opensim_module: Any,
    ) -> None:
        self._osim = opensim_module
        logger = getattr(self._osim, "Logger", None)
        set_log_level = getattr(logger, "setLevelString", None)
        if callable(set_log_level):
            # The 4.5.2 fallback rebuilds its static reference per sample.
            # Suppress the solver constructor's INFO line at acquisition rates.
            try:
                set_log_level("Warn")
            except Exception:
                pass
        self._master_frame = _strip_leading_slash(master_frame)
        self._slave_frame = _strip_leading_slash(slave_frame)
        self._coordinate_paths = [
            _strip_leading_slash(path) for path in coordinate_paths
        ] or [DEFAULT_JOINT_NAME]
        self._assembled = False
        self._last_calibration_id: str | None = None
        self._time_s = 0.0

        configure_opensim_geometry_search_paths(
            self._osim,
            model_path,
        )
        self._model = self._osim.Model(str(model_path))
        self._model.setUseVisualizer(False)
        self._state = self._model.initSystem()
        self._solver: Any | None = None
        self._orientations_ref: Any | None = None
        self._solver_orientations_ref: Any | None = None
        self._use_buffered = False
        self._probe = probe_opensim_orientation_ik_apis(self._osim)
        self._build_solver()

    def reset(self) -> None:
        self._assembled = False
        self._last_calibration_id = None
        self._time_s = 0.0
        try:
            self._state = self._model.initSystem()
        except Exception:
            pass
        self._solver = None
        self._orientations_ref = None
        self._solver_orientations_ref = None
        try:
            self._build_solver()
        except Exception:
            # Leave solver None; solve() will fail closed.
            self._solver = None

    def _build_solver(self) -> None:
        osim = self._osim
        if not (
            self._probe.get("InverseKinematicsSolver")
            and self._probe.get("OrientationsReference")
        ):
            raise RuntimeError("opensim_ik_api_unavailable")

        # Seed a one-row orientation table (identity) so references construct.
        column_labels = [self._master_frame, self._slave_frame]
        identity_sf = (1.0, 0.0, 0.0, 0.0)  # w,x,y,z
        table = self._make_quat_table(column_labels, identity_sf, identity_sf, 0.0)

        if self._probe.get("BufferedOrientationsReference") and hasattr(
            osim,
            "BufferedOrientationsReference",
        ):
            try:
                # Buffered updates require passing a shared_ptr into the solver.
                # OpenSim 4.5.2 exposes this class but its Python shared_ptr
                # wrapper cannot be constructed from an instance; using the
                # legacy overload silently slices it to a static reference.
                rotations_table = self._quats_to_rotations(table)
                buffered_ref = osim.BufferedOrientationsReference(
                    rotations_table,
                )
                shared_ctor = getattr(osim, "SharedOrientationsReference", None)
                if not callable(shared_ctor):
                    raise TypeError("shared_orientation_reference_unavailable")
                shared_ref = shared_ctor(buffered_ref)
                self._orientations_ref = buffered_ref
                self._solver_orientations_ref = shared_ref
                self._use_buffered = True
            except Exception:
                self._use_buffered = False

        if not self._use_buffered:
            rotations_table = self._quats_to_rotations(table)
            self._orientations_ref = osim.OrientationsReference(rotations_table)
            self._solver_orientations_ref = self._orientations_ref

        markers_ref = None
        if self._probe.get("MarkersReference"):
            try:
                markers_ref = osim.MarkersReference()
            except Exception:
                markers_ref = None

        coord_refs = self._empty_coordinate_refs()
        # Try shared_ptr-style / Python overloaded constructors.
        constructed = False
        last_exc: Exception | None = None
        for args in (
            (self._model, markers_ref, self._solver_orientations_ref, coord_refs),
            (self._model, self._solver_orientations_ref, coord_refs),
            (
                self._model,
                markers_ref if markers_ref is not None else osim.MarkersReference(),
                self._solver_orientations_ref,
                coord_refs,
            ),
        ):
            try:
                self._solver = osim.InverseKinematicsSolver(*args)
                constructed = True
                break
            except Exception as exc:
                last_exc = exc
                continue
        if not constructed:
            raise RuntimeError(
                f"opensim_ik_api_unavailable:{type(last_exc).__name__ if last_exc else 'ctor'}"
            )

    def _empty_coordinate_refs(self) -> Any:
        osim = self._osim
        for name in (
            "SimTKArrayCoordinateReference",
            "ArrayCoordinateReference",
        ):
            ctor = getattr(osim, name, None)
            if callable(ctor):
                try:
                    return ctor()
                except Exception:
                    continue
        # Last resort: empty Python list (some bindings accept it).
        return []

    def _make_quat_table(
        self,
        labels: Sequence[str],
        master_wxyz: tuple[float, float, float, float],
        slave_wxyz: tuple[float, float, float, float],
        time_s: float,
    ) -> Any:
        osim = self._osim
        table = osim.TimeSeriesTableQuaternion()
        table.setColumnLabels(list(labels))
        row = osim.RowVectorQuaternion(2)
        # OpenSim Quaternion is (w, x, y, z).
        q0 = osim.Quaternion(*master_wxyz)
        q1 = osim.Quaternion(*slave_wxyz)
        # OpenSim 4.5.x's SWIG binding does not expose assignment of a whole
        # Quaternion into RowVectorQuaternion. It does expose the mutable
        # Quaternion returned by updElt(row, column), whose four components can
        # be set individually.
        set_ok = False
        try:
            for column, values in enumerate((master_wxyz, slave_wxyz)):
                target = row.updElt(0, column)
                for component, value in enumerate(values):
                    target.set(component, float(value))
            set_ok = True
        except Exception:
            pass

        # Keep compatibility with bindings that expose whole-value setters.
        if not set_ok:
            for setter in ("set", "setItem"):
                if hasattr(row, setter):
                    try:
                        getattr(row, setter)(0, q0)
                        getattr(row, setter)(1, q1)
                        set_ok = True
                        break
                    except Exception:
                        continue
        if not set_ok:
            # Fall back to constructing via appendRow with a flat list if exposed.
            try:
                table.appendRow(time_s, [q0, q1])
                return table
            except Exception as exc:
                raise RuntimeError(f"quaternion_row_failed:{exc}") from exc
        table.appendRow(time_s, row)
        return table

    def _quats_to_rotations(self, quat_table: Any) -> Any:
        osim = self._osim
        utilities = getattr(osim, "OpenSenseUtilities", None)
        if utilities is not None and hasattr(
            utilities,
            "convertQuaternionsToRotations",
        ):
            return utilities.convertQuaternionsToRotations(quat_table)
        # Some bindings accept OrientationsReference(TimeSeriesTableQuaternion).
        return quat_table

    def _xyzw_to_wxyz(
        self,
        xyzw: Sequence[float],
    ) -> tuple[float, float, float, float]:
        rotation = ros_xyzw_to_opensim_rotation(
            float(xyzw[0]),
            float(xyzw[1]),
            float(xyzw[2]),
            float(xyzw[3]),
        )
        return rotation.scalar_first

    def _update_orientation_targets(
        self,
        master_corr: Sequence[float],
        slave_corr: Sequence[float],
        time_s: float,
    ) -> None:
        master_wxyz = self._xyzw_to_wxyz(master_corr)
        slave_wxyz = self._xyzw_to_wxyz(slave_corr)
        labels = [self._master_frame, self._slave_frame]
        table = self._make_quat_table(labels, master_wxyz, slave_wxyz, time_s)
        rotations = self._quats_to_rotations(table)

        if self._use_buffered and self._orientations_ref is not None:
            put = getattr(self._orientations_ref, "putValues", None)
            if callable(put):
                # putValues(time, Array_<Rotation>) — build when possible.
                try:
                    rotations_row = rotations.getRowAtIndex(0)
                    # OpenSim 4.5.2 returns a non-owning RowVectorViewRotation,
                    # while BufferedOrientationsReference.putValues() requires
                    # an owning RowVectorRotation.
                    row_ctor = getattr(self._osim, "RowVectorRotation", None)
                    if callable(row_ctor):
                        rotations_row = row_ctor(rotations_row)
                    put(time_s, rotations_row)
                    return
                except Exception:
                    pass

        # Rebuild OrientationsReference + solver for non-buffered 4.5.x path.
        osim = self._osim
        self._orientations_ref = osim.OrientationsReference(rotations)
        markers_ref = osim.MarkersReference() if self._probe.get("MarkersReference") else None
        coord_refs = self._empty_coordinate_refs()
        try:
            self._solver = osim.InverseKinematicsSolver(
                self._model,
                markers_ref,
                self._orientations_ref,
                coord_refs,
            )
        except Exception:
            self._solver = osim.InverseKinematicsSolver(
                self._model,
                self._orientations_ref,
                coord_refs,
            )
        self._assembled = False

    def _read_coordinates(self) -> list[float]:
        positions: list[float] = []
        for path in self._coordinate_paths:
            coord = None
            try:
                coord = self._model.getCoordinateSet().get(path)
            except Exception:
                try:
                    component = self._model.getComponent(_component_path(path))
                    coord = component
                except Exception:
                    coord = None
            if coord is None:
                raise RuntimeError(f"coordinate_not_found:{path}")
            value = float(coord.getValue(self._state))
            positions.append(value)
        return positions

    def _read_visualization_pose(self) -> tuple[list[str], list[float]]:
        """Return every solved model coordinate for the separate visualizer."""

        coordinate_set = self._model.getCoordinateSet()
        names: list[str] = []
        positions: list[float] = []
        for index in range(int(coordinate_set.getSize())):
            coordinate = coordinate_set.get(index)
            names.append(str(coordinate.getName()))
            positions.append(float(coordinate.getValue(self._state)))
        return names, positions

    def _orientation_residuals(self) -> tuple[float | None, float | None]:
        solver = self._solver
        if solver is None:
            return None, None
        for method_name in (
            "computeCurrentOrientationError",
            "getOrientationError",
            "calcOrientationError",
        ):
            method = getattr(solver, method_name, None)
            if not callable(method):
                continue
            try:
                errors = method()
                values = [float(errors[i]) for i in range(len(errors))]
                if not values:
                    return None, None
                rms = (sum(v * v for v in values) / len(values)) ** 0.5
                return rms, max(abs(v) for v in values)
            except Exception:
                continue
        return None, None

    def solve(
        self,
        *,
        master_xyzw: Sequence[float],
        slave_xyzw: Sequence[float],
        calibration: CalibrationArtifact | None,
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
    ) -> IkSolution:
        started = time.perf_counter()
        names = [str(name) for name in joint_names] or list(self._coordinate_paths)

        if calibration is None:
            return IkSolution(
                solution_valid=False,
                reason="calibration_required",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )
        if source_timestamp_ns is None:
            return IkSolution(
                solution_valid=False,
                reason="missing_source_timestamp",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=None,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=calibration.calibration_id,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        try:
            if self._solver is None:
                self._build_solver()

            if self._last_calibration_id != calibration.calibration_id:
                self._assembled = False
                self._last_calibration_id = calibration.calibration_id

            master_corr, slave_corr = apply_mounting_offsets(
                master_xyzw,
                slave_xyzw,
                calibration,
            )
            self._time_s += 0.01
            self._update_orientation_targets(master_corr, slave_corr, self._time_s)
            self._state.setTime(self._time_s)

            assert self._solver is not None
            if not self._assembled:
                self._solver.assemble(self._state)
                self._assembled = True
            else:
                try:
                    self._solver.track(self._state)
                except Exception:
                    self._solver.assemble(self._state)

            positions = self._read_coordinates()
            visualization_names, visualization_positions = (
                self._read_visualization_pose()
            )
            # Align published names with requested joint_names length.
            if len(positions) != len(names):
                if len(positions) == 1 and len(names) >= 1:
                    positions = [positions[0]] * len(names)
                    names = list(names)
                else:
                    names = list(self._coordinate_paths[: len(positions)])

            rms, residual_max = self._orientation_residuals()
            return IkSolution(
                solution_valid=True,
                reason="ok",
                joint_names=list(names),
                positions_rad=list(positions),
                source_timestamp_ns=int(source_timestamp_ns),
                orientation_residual_rms=rms,
                orientation_residual_max=residual_max,
                calibration_id=calibration.calibration_id,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
                visualization_coordinate_names=visualization_names,
                visualization_positions_rad=visualization_positions,
            )
        except Exception as exc:
            self._assembled = False
            reason = f"opensim_ik_solve_failed:{type(exc).__name__}"
            message = str(exc)
            if message and len(message) < 80:
                reason = f"{reason}:{message}"
            return IkSolution(
                solution_valid=False,
                reason=reason,
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=calibration.calibration_id,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

    def _make_quat_table_n(
        self,
        inputs: list[tuple[str, Any]],
        time_s: float,
    ) -> Any:
        """Build a TimeSeriesTableQuaternion from N (frame_name, wxyz) pairs."""
        osim = self._osim
        n = len(inputs)
        table = osim.TimeSeriesTableQuaternion()
        labels = [frame for frame, _ in inputs]
        table.setColumnLabels(labels)
        row = osim.RowVectorQuaternion(n)
        set_ok = False
        try:
            for column, (_, wxyz) in enumerate(inputs):
                target = row.updElt(0, column)
                for component, value in enumerate(wxyz):
                    target.set(component, float(value))
            set_ok = True
        except Exception:
            pass

        if not set_ok:
            quats = [osim.Quaternion(*wxyz) for _, wxyz in inputs]
            for setter in ("set", "setItem"):
                if hasattr(row, setter):
                    try:
                        for idx, q in enumerate(quats):
                            getattr(row, setter)(idx, q)
                        set_ok = True
                        break
                    except Exception:
                        continue
        if not set_ok:
            try:
                quats = [osim.Quaternion(*wxyz) for _, wxyz in inputs]
                table.appendRow(time_s, quats)
                return table
            except Exception as exc:
                raise RuntimeError(f"quaternion_row_n_failed:{exc}") from exc
        table.appendRow(time_s, row)
        return table

    def solve_n(
        self,
        inputs: list[tuple[str, Any]],
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
        calibration: Any = None,
    ) -> IkSolution:
        """Solve IK for N-sensor orientation table; additive to solve()."""
        started = time.perf_counter()
        names = [str(name) for name in joint_names] or list(self._coordinate_paths)

        if not inputs:
            return IkSolution(
                solution_valid=False,
                reason="no_inputs",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        if source_timestamp_ns is None:
            return IkSolution(
                solution_valid=False,
                reason="missing_source_timestamp",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=None,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        if calibration is None:
            return IkSolution(
                solution_valid=False,
                reason="calibration_required",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        try:
            if self._solver is None:
                self._build_solver()

            # Convert each xyzw to wxyz for OpenSim
            corrected_inputs = apply_reference_pose_offsets(inputs, calibration)
            n_inputs = [
                (frame, self._xyzw_to_wxyz(xyzw))
                for frame, xyzw in corrected_inputs
            ]

            self._time_s += 0.01
            table = self._make_quat_table_n(n_inputs, self._time_s)
            rotations_table = self._quats_to_rotations(table)

            # Rebuild OrientationsReference + solver for non-buffered N-sensor path
            osim = self._osim
            self._orientations_ref = osim.OrientationsReference(rotations_table)
            markers_ref = (
                osim.MarkersReference() if self._probe.get("MarkersReference") else None
            )
            coord_refs = self._empty_coordinate_refs()
            try:
                self._solver = osim.InverseKinematicsSolver(
                    self._model,
                    markers_ref,
                    self._orientations_ref,
                    coord_refs,
                )
            except Exception:
                self._solver = osim.InverseKinematicsSolver(
                    self._model,
                    self._orientations_ref,
                    coord_refs,
                )
            self._assembled = False

            self._state.setTime(self._time_s)
            assert self._solver is not None
            if not self._assembled:
                self._solver.assemble(self._state)
                self._assembled = True
            else:
                try:
                    self._solver.track(self._state)
                except Exception:
                    self._solver.assemble(self._state)

            positions = self._read_coordinates()
            visualization_names, visualization_positions = self._read_visualization_pose()

            if len(positions) != len(names):
                if len(positions) == 1 and len(names) >= 1:
                    positions = [positions[0]] * len(names)
                    names = list(names)
                else:
                    names = list(self._coordinate_paths[: len(positions)])

            rms, residual_max = self._orientation_residuals()
            return IkSolution(
                solution_valid=True,
                reason="ok",
                joint_names=list(names),
                positions_rad=list(positions),
                source_timestamp_ns=int(source_timestamp_ns),
                orientation_residual_rms=rms,
                orientation_residual_max=residual_max,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
                visualization_coordinate_names=visualization_names,
                visualization_positions_rad=visualization_positions,
            )
        except Exception as exc:
            self._assembled = False
            reason = f"opensim_ik_solve_n_failed:{type(exc).__name__}"
            message = str(exc)
            if message and len(message) < 80:
                reason = f"{reason}:{message}"
            return IkSolution(
                solution_valid=False,
                reason=reason,
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )


def create_orientation_ik_solver(
    *,
    model_path: str,
    master_frame: str,
    slave_frame: str,
    coordinate_paths: Sequence[str],
    opensim_module: Any | None = None,
):
    """Return OpenSimOrientationIkSolver when model+APIs OK; else Unavailable."""

    path = str(model_path or "").strip()
    if not path:
        return UnavailableOrientationIkSolver("model_path_empty")
    if not Path(path).is_file():
        return UnavailableOrientationIkSolver("model_path_not_found")

    try:
        osim = opensim_module or import_module("opensim")
    except Exception:
        return UnavailableOrientationIkSolver("opensim_ik_api_unavailable")

    probe = probe_opensim_orientation_ik_apis(osim)
    if not (
        probe.get("InverseKinematicsSolver") and probe.get("OrientationsReference")
    ):
        return UnavailableOrientationIkSolver("opensim_ik_api_unavailable")

    try:
        return OpenSimOrientationIkSolver(
            model_path=path,
            master_frame=master_frame,
            slave_frame=slave_frame,
            coordinate_paths=coordinate_paths,
            opensim_module=osim,
        )
    except Exception as exc:
        reason = "opensim_ik_api_unavailable"
        detail = str(exc)
        if "model" in detail.lower():
            reason = f"opensim_ik_api_unavailable:{type(exc).__name__}"
        return UnavailableOrientationIkSolver(reason)


__all__ = [
    "OpenSimOrientationIkSolver",
    "create_orientation_ik_solver",
    "probe_opensim_orientation_ik_apis",
]
