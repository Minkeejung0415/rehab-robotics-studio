"""Create the minimal model used by the OpenSim live-link smoke test."""

from pathlib import Path
import sys

import opensim


def _add_sensor_frame(model, name, translation):
    frame = opensim.PhysicalOffsetFrame()
    frame.setName(name)
    frame.setParentFrame(model.getGround())
    frame.set_translation(opensim.Vec3(*translation))
    model.addComponent(frame)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: create_opensim_demo_model.py OUTPUT.osim",
        )

    output = Path(sys.argv[1]).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    model = opensim.Model()
    model.setName("rehab_quaternion_live_link_demo")
    _add_sensor_frame(model, "femur_r_imu", (0.0, 0.9, 0.0))
    _add_sensor_frame(model, "tibia_r_imu", (0.0, 0.45, 0.0))
    model.finalizeConnections()
    model.initSystem()
    model.printToXML(str(output))

    loaded = opensim.Model(str(output))
    loaded.initSystem()
    for frame_name in ("femur_r_imu", "tibia_r_imu"):
        frame = opensim.Frame.safeDownCast(loaded.getComponent(frame_name))
        if frame is None or not frame:
            raise RuntimeError(f"generated frame not found: {frame_name}")
    print(f"Created and verified {output}")


if __name__ == "__main__":
    main()
