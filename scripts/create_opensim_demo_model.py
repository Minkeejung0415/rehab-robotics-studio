"""Create the minimal model used by the OpenSim live-link smoke test."""

from pathlib import Path
import sys

import opensim


def _add_sensor_frame(model, parent, name, translation):
    frame = opensim.PhysicalOffsetFrame()
    frame.setName(name)
    frame.connectSocket_parent(parent)
    frame.set_translation(opensim.Vec3(*translation))
    model.addComponent(frame)


def _add_segment_geometry(body, radius, half_length, color):
    geometry = opensim.Cylinder(radius, half_length)
    geometry.setColor(opensim.Vec3(*color))
    body.attachGeometry(geometry)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: create_opensim_demo_model.py OUTPUT.osim",
        )

    output = Path(sys.argv[1]).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    model = opensim.Model()
    model.setName("rehab_quaternion_live_link_demo")

    femur = opensim.Body(
        "femur_r",
        1.0,
        opensim.Vec3(0),
        opensim.Inertia(0.01, 0.01, 0.01),
    )
    tibia = opensim.Body(
        "tibia_r",
        1.0,
        opensim.Vec3(0),
        opensim.Inertia(0.01, 0.01, 0.01),
    )
    _add_segment_geometry(femur, 0.045, 0.225, (0.2, 0.55, 0.95))
    _add_segment_geometry(tibia, 0.04, 0.225, (0.95, 0.55, 0.2))
    model.addBody(femur)
    model.addBody(tibia)

    hip = opensim.WeldJoint(
        "hip_r",
        model.getGround(),
        opensim.Vec3(0.0, 0.9, 0.0),
        opensim.Vec3(0),
        femur,
        opensim.Vec3(0.0, 0.225, 0.0),
        opensim.Vec3(0),
    )
    knee = opensim.PinJoint(
        "knee_r",
        femur,
        opensim.Vec3(0.0, -0.225, 0.0),
        opensim.Vec3(0),
        tibia,
        opensim.Vec3(0.0, 0.225, 0.0),
        opensim.Vec3(0),
    )
    knee.upd_coordinates(0).setName("knee_angle_r")
    model.addJoint(hip)
    model.addJoint(knee)

    _add_sensor_frame(model, femur, "femur_r_imu", (0.0, 0.10, 0.0))
    _add_sensor_frame(model, tibia, "tibia_r_imu", (0.0, 0.10, 0.0))
    model.finalizeConnections()
    model.initSystem()
    model.printToXML(str(output))

    loaded = opensim.Model(str(output))
    loaded.initSystem()
    for frame_path in ("femur_r_imu", "tibia_r_imu"):
        frame = opensim.Frame.safeDownCast(loaded.getComponent(frame_path))
        if frame is None or not frame:
            raise RuntimeError(f"generated frame not found: {frame_path}")
    loaded.getCoordinateSet().get("knee_angle_r")
    print(f"Created and verified {output}")


if __name__ == "__main__":
    main()
