"""Create the anatomical lower-limb model used by the OpenSim live link."""

from pathlib import Path
import sys

import opensim


_GEOMETRY_FILES = {
    "pelvis": ("r_pelvis.vtp", "l_pelvis.vtp", "sacrum.vtp"),
    "femur_r": ("femur_r.vtp",),
    "tibia_r": ("tibia_r.vtp", "r_fibula.vtp", "r_patella.vtp"),
}


def _add_sensor_frame(model, parent, name, translation):
    frame = opensim.PhysicalOffsetFrame()
    frame.setName(name)
    frame.connectSocket_parent(parent)
    frame.set_translation(opensim.Vec3(*translation))
    model.addComponent(frame)


def _opensense_example_dir() -> Path:
    environment_prefix = Path(sys.executable).resolve().parents[1]
    return (
        environment_prefix
        / "share"
        / "doc"
        / "OpenSim"
        / "Code"
        / "Python"
        / "OpenSenseExample"
    )


def _attach_anatomical_geometry(body, geometry_dir: Path) -> None:
    for filename in _GEOMETRY_FILES[body.getName()]:
        source = geometry_dir / filename
        if not source.is_file():
            raise RuntimeError(f"OpenSim skeleton geometry not found: {source}")
        body.attachGeometry(opensim.Mesh(filename))


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: create_opensim_demo_model.py OUTPUT.osim",
        )

    output = Path(sys.argv[1]).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    example_dir = _opensense_example_dir()
    geometry_dir = example_dir / "Geometry"
    template_model = example_dir / "Rajagopal_2015.osim"
    if not template_model.is_file() or not geometry_dir.is_dir():
        raise RuntimeError(
            "OpenSim OpenSense Rajagopal skeleton assets are not installed",
        )
    opensim.ModelVisualizer.addDirToGeometrySearchPaths(str(geometry_dir))

    model = opensim.Model()
    model.setName("rehab_lower_limb_skeleton_live_link")

    pelvis = opensim.Body(
        "pelvis",
        10.0,
        opensim.Vec3(0),
        opensim.Inertia(0.1, 0.1, 0.1),
    )
    femur = opensim.Body(
        "femur_r",
        8.0,
        opensim.Vec3(0),
        opensim.Inertia(0.01, 0.01, 0.01),
    )
    tibia = opensim.Body(
        "tibia_r",
        4.0,
        opensim.Vec3(0),
        opensim.Inertia(0.01, 0.01, 0.01),
    )
    for body in (pelvis, femur, tibia):
        model.addBody(body)
    for body_name in _GEOMETRY_FILES:
        _attach_anatomical_geometry(
            model.updBodySet().get(body_name),
            geometry_dir,
        )

    pelvis_ground = opensim.WeldJoint(
        "pelvis_ground",
        model.getGround(),
        opensim.Vec3(0.0, 1.0, 0.0),
        opensim.Vec3(0),
        pelvis,
        opensim.Vec3(0),
        opensim.Vec3(0),
    )
    hip = opensim.BallJoint(
        "hip_r",
        pelvis,
        opensim.Vec3(-0.056276, -0.07849, 0.07726),
        opensim.Vec3(0),
        femur,
        opensim.Vec3(0),
        opensim.Vec3(0),
    )
    for index, coordinate_name in enumerate(
        ("hip_flexion_r", "hip_adduction_r", "hip_rotation_r"),
    ):
        hip.upd_coordinates(index).setName(coordinate_name)

    knee = opensim.PinJoint(
        "knee_r",
        femur,
        opensim.Vec3(-0.00809, -0.40796, -0.00275),
        opensim.Vec3(0),
        tibia,
        opensim.Vec3(-0.00809, -0.003535, -0.001485),
        opensim.Vec3(0),
    )
    knee_coordinate = knee.upd_coordinates(0)
    knee_coordinate.setName("knee_angle_r")
    # Permit equal-and-opposite master/slave sensitivity around the calibrated
    # reference pose. Product limits can be imposed downstream if required.
    knee_coordinate.setRangeMin(-2.0944)
    knee_coordinate.setRangeMax(2.0944)

    model.addJoint(pelvis_ground)
    model.addJoint(hip)
    model.addJoint(knee)

    _add_sensor_frame(model, femur, "femur_r_imu", (0.0, -0.15, 0.0))
    _add_sensor_frame(model, tibia, "tibia_r_imu", (0.0, -0.15, 0.0))
    model.finalizeConnections()
    model.initSystem()
    model.printToXML(str(output))

    loaded = opensim.Model(str(output))
    loaded.initSystem()
    for frame_path in ("femur_r_imu", "tibia_r_imu"):
        frame = opensim.Frame.safeDownCast(loaded.getComponent(frame_path))
        if frame is None or not frame:
            raise RuntimeError(f"generated frame not found: {frame_path}")
    for coordinate_name in (
        "hip_flexion_r",
        "hip_adduction_r",
        "hip_rotation_r",
        "knee_angle_r",
    ):
        loaded.getCoordinateSet().get(coordinate_name)
    print(
        f"Created and verified anatomical skeleton {output} "
        f"using {template_model}",
    )


if __name__ == "__main__":
    main()
