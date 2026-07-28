#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
WS_DIR="${HOME}/rehab_robotics_ws"
MAMBA_BIN="${HOME}/.local/bin/micromamba"
MAMBA_ROOT_PREFIX="${HOME}/.micromamba"
ENV_NAME="rehab-opensim"
ENV_PYTHON="${MAMBA_ROOT_PREFIX}/envs/${ENV_NAME}/bin/python"
DEMO_MODEL="${PROJECT_DIR}/examples/opensim_quaternion_demo.osim"
RUNTIME_DEMO_MODEL="${WS_DIR}/opensim_quaternion_demo.osim"
RUNTIME_RUNNER="${WS_DIR}/run_opensim_live_link_wsl.sh"
OPENSENSE_EXAMPLE_DIR="${MAMBA_ROOT_PREFIX}/envs/${ENV_NAME}/share/doc/OpenSim/Code/Python/OpenSenseExample"
RUNTIME_GEOMETRY_DIR="${WS_DIR}/Geometry"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
    echo "ROS 2 Humble is not installed at /opt/ros/humble." >&2
    exit 1
fi
if ! command -v colcon >/dev/null 2>&1; then
    echo "colcon is not installed in WSL." >&2
    exit 1
fi

mkdir -p "${HOME}/.local/bin" "${WS_DIR}/src"
ln -sfn "${PROJECT_DIR}/backend" \
    "${WS_DIR}/src/rehab_robotics_bridge"
ln -sfn "${PROJECT_DIR}/rehab_robotics_interfaces" \
    "${WS_DIR}/src/rehab_robotics_interfaces"

if [[ ! -x "${MAMBA_BIN}" ]]; then
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest |
        tar -xj -C "${HOME}/.local/bin" --strip-components=1 bin/micromamba
fi

if [[ ! -x "${ENV_PYTHON}" ]]; then
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${MAMBA_BIN}" create -y \
        -n "${ENV_NAME}" \
        -c opensim-org \
        -c conda-forge \
        python=3.10 \
        opensim=4.5.2
fi

bash "${PROJECT_DIR}/scripts/install_simbody_visualizer_wsl.sh"

set +u
source /opt/ros/humble/setup.bash
set -u
cd "${WS_DIR}"
colcon build \
    --packages-select rehab_robotics_interfaces rehab_robotics_bridge \
    --symlink-install
set +u
source "${WS_DIR}/install/setup.bash"
set -u

"${ENV_PYTHON}" "${PROJECT_DIR}/scripts/create_opensim_demo_model.py" \
    "${DEMO_MODEL}"
if [[ ! -d "${OPENSENSE_EXAMPLE_DIR}/Geometry" ]]; then
    echo "OpenSim OpenSense skeleton Geometry directory is unavailable." >&2
    exit 1
fi
mkdir -p "${RUNTIME_GEOMETRY_DIR}"
cp -a "${OPENSENSE_EXAMPLE_DIR}/Geometry/." "${RUNTIME_GEOMETRY_DIR}/"
cp -f "${DEMO_MODEL}" "${RUNTIME_DEMO_MODEL}"
cp -f "${PROJECT_DIR}/scripts/run_opensim_live_link_wsl.sh" \
    "${RUNTIME_RUNNER}"

export PYTHONPATH="${MAMBA_ROOT_PREFIX}/envs/${ENV_NAME}/lib/python3.10/site-packages:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="${MAMBA_ROOT_PREFIX}/envs/${ENV_NAME}/lib:${LD_LIBRARY_PATH:-}"
/usr/bin/python3 -c \
    "import opensim, rclpy; print(opensim.GetVersionAndDate()); print('rclpy import OK')"
ros2 pkg executables rehab_robotics_bridge | grep opensim

echo
echo "Setup complete."
echo "Run from PowerShell:"
echo "  .\\scripts\\run_opensim_live_link.ps1 -Test"
echo "  .\\scripts\\run_opensim_live_link.ps1"
