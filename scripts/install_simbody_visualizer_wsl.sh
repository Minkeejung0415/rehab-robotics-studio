#!/usr/bin/env bash
set -euo pipefail

MAMBA_BIN="${HOME}/.local/bin/micromamba"
CONDA_ENV="${HOME}/.micromamba/envs/rehab-opensim"
SOURCE_DIR="${HOME}/.cache/simbody-3.8-src"
INSTALL_DIR="${HOME}/.local/libexec/simbody"
VISUALIZER="${INSTALL_DIR}/simbody-visualizer"
SIMBODY_COMMIT="f260ff30381826728da721226151e733715d0df9"
OPENGL_LIB_DIR="${CONDA_ENV}/lib"
PATCH_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/patches/simbody-visualizer-threadsafe-ui.patch"

if [[ ! -x "${MAMBA_BIN}" || ! -d "${CONDA_ENV}" ]]; then
    echo "The rehab-opensim micromamba environment is not installed." >&2
    exit 1
fi
if ! command -v git >/dev/null 2>&1 || ! command -v g++ >/dev/null 2>&1; then
    echo "git and g++ are required to build simbody-visualizer." >&2
    exit 1
fi

"${MAMBA_BIN}" install -y -p "${CONDA_ENV}" -c conda-forge \
    freeglut libglu --freeze-installed

for library in libglut.so.3 libGLU.so.1 libGL.so.1; do
    if [[ ! -f "${OPENGL_LIB_DIR}/${library}" ]]; then
        echo "Required OpenSim environment library is missing: ${OPENGL_LIB_DIR}/${library}" >&2
        exit 1
    fi
done
if [[ ! -f "${PATCH_FILE}" ]]; then
    echo "Visualizer thread-safety patch is missing: ${PATCH_FILE}" >&2
    exit 1
fi

mkdir -p "$(dirname -- "${SOURCE_DIR}")" "${INSTALL_DIR}"
if [[ ! -d "${SOURCE_DIR}/.git" ]]; then
    git clone --no-checkout https://github.com/simbody/simbody.git "${SOURCE_DIR}"
fi
git -C "${SOURCE_DIR}" fetch --depth 1 origin "${SIMBODY_COMMIT}"
git -C "${SOURCE_DIR}" checkout --detach "${SIMBODY_COMMIT}"
if git -C "${SOURCE_DIR}" apply --check "${PATCH_FILE}"; then
    git -C "${SOURCE_DIR}" apply "${PATCH_FILE}"
elif git -C "${SOURCE_DIR}" apply --reverse --check "${PATCH_FILE}"; then
    echo "Visualizer thread-safety patch is already applied."
else
    echo "Visualizer thread-safety patch does not apply cleanly." >&2
    exit 1
fi

g++ -std=c++14 -O2 \
    -I"${CONDA_ENV}/simbody/include/simbody" \
    -I"${CONDA_ENV}/include/simbody" \
    -I"${CONDA_ENV}/include" \
    "${SOURCE_DIR}/Simbody/Visualizer/simbody-visualizer/simbody-visualizer.cpp" \
    "${SOURCE_DIR}/Simbody/Visualizer/simbody-visualizer/lodepng.cpp" \
    -L"${CONDA_ENV}/simbody/lib" \
    -Wl,--disable-new-dtags,-rpath,"${OPENGL_LIB_DIR}:${CONDA_ENV}/simbody/lib" \
    -lSimTKcommon \
    "${OPENGL_LIB_DIR}/libglut.so.3" \
    "${OPENGL_LIB_DIR}/libGLU.so.1" \
    "${OPENGL_LIB_DIR}/libGL.so.1" \
    -lpthread -ldl -o "${VISUALIZER}"

if ldd "${VISUALIZER}" | grep -q "not found"; then
    echo "simbody-visualizer has unresolved native libraries." >&2
    ldd "${VISUALIZER}" >&2
    exit 1
fi
if ! LD_LIBRARY_PATH="${CONDA_ENV}/lib:${CONDA_ENV}/simbody/lib" \
    ldd "${VISUALIZER}" | grep -q "libglut.so.3 => ${OPENGL_LIB_DIR}/libglut.so.3"; then
    echo "simbody-visualizer did not resolve the OpenSim environment freeglut." >&2
    ldd "${VISUALIZER}" >&2
    exit 1
fi

echo "Installed ${VISUALIZER}"
