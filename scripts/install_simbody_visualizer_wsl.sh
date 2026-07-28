#!/usr/bin/env bash
set -euo pipefail

MAMBA_BIN="${HOME}/.local/bin/micromamba"
CONDA_ENV="${HOME}/.micromamba/envs/rehab-opensim"
SOURCE_DIR="${HOME}/.cache/simbody-3.8-src"
INSTALL_DIR="${HOME}/.local/libexec/simbody"
VISUALIZER="${INSTALL_DIR}/simbody-visualizer"

if [[ ! -x "${MAMBA_BIN}" || ! -d "${CONDA_ENV}" ]]; then
    echo "The rehab-opensim micromamba environment is not installed." >&2
    exit 1
fi
if ! command -v git >/dev/null 2>&1 ||
   ! command -v g++ >/dev/null 2>&1; then
    echo "git and g++ are required to build simbody-visualizer." >&2
    exit 1
fi

"${MAMBA_BIN}" install -y \
    -p "${CONDA_ENV}" \
    -c conda-forge \
    freeglut \
    libglu \
    --freeze-installed

mkdir -p "$(dirname -- "${SOURCE_DIR}")" "${INSTALL_DIR}"
if [[ ! -d "${SOURCE_DIR}/.git" ]]; then
    git clone --depth 1 --branch Simbody-3.8 \
        https://github.com/simbody/simbody.git \
        "${SOURCE_DIR}"
fi

g++ -std=c++14 -O2 \
    -I"${CONDA_ENV}/simbody/include/simbody" \
    -I"${CONDA_ENV}/include/simbody" \
    -I"${CONDA_ENV}/include" \
    "${SOURCE_DIR}/Simbody/Visualizer/simbody-visualizer/simbody-visualizer.cpp" \
    "${SOURCE_DIR}/Simbody/Visualizer/simbody-visualizer/lodepng.cpp" \
    -L"${CONDA_ENV}/simbody/lib" \
    -L"${CONDA_ENV}/lib" \
    -Wl,-rpath,"${CONDA_ENV}/simbody/lib:${CONDA_ENV}/lib" \
    -lSimTKsimbody \
    -lSimTKmath \
    -lSimTKcommon \
    -lglut \
    -lGLU \
    -lGL \
    -lpthread \
    -ldl \
    -o "${VISUALIZER}"

if ldd "${VISUALIZER}" | grep -q "not found"; then
    echo "simbody-visualizer has unresolved native libraries." >&2
    ldd "${VISUALIZER}" >&2
    exit 1
fi

echo "Installed ${VISUALIZER}"
