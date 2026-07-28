#!/usr/bin/env bash
set -euo pipefail

WS_DIR="${HOME}/rehab_robotics_ws"
ENV_PYTHON="${HOME}/.micromamba/envs/rehab-opensim/bin/python"

if [[ $# -lt 2 ]]; then
    echo "usage: run_opensim_live_link_wsl.sh MODEL_PATH TEST_PUBLISHER [ROS args...]" >&2
    exit 2
fi

MODEL_PATH="$1"
TEST_PUBLISHER="$2"
shift 2

if [[ ! -x "${ENV_PYTHON}" || ! -f "${WS_DIR}/install/setup.bash" ]]; then
    echo "Run scripts/setup_opensim_live_link.ps1 first." >&2
    exit 1
fi
if [[ ! -f "${MODEL_PATH}" ]]; then
    echo "OpenSim model not found: ${MODEL_PATH}" >&2
    exit 1
fi

set +u
source /opt/ros/humble/setup.bash
source "${WS_DIR}/install/setup.bash"
set -u

# ROS-generated entry points use /usr/bin/python3. Add the ABI-compatible
# OpenSim 4.5.2 package and native libraries to that process.
CONDA_ENV="$(dirname -- "$(dirname -- "${ENV_PYTHON}")")"
export PATH="${HOME}/.local/libexec/simbody:${PATH}"
export PYTHONPATH="${CONDA_ENV}/lib/python3.10/site-packages:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="${CONDA_ENV}/simbody/lib:${CONDA_ENV}/lib:${LD_LIBRARY_PATH:-}"

exec ros2 launch rehab_robotics_bridge opensim_live_link.launch.py \
    "model_path:=${MODEL_PATH}" \
    "enable_test_publisher:=${TEST_PUBLISHER}" \
    "$@"
