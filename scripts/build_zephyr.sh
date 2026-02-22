#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="cluster1_smp"
APP_DIR="${REPO_ROOT}/sources/zephyr/samples/hello_world"
BOARD="qemu_riscv32"
BUILD_ROOT="${REPO_ROOT}/build/zephyr"
OVERLAY=""
JOBS="$(nproc)"
DRY_RUN=0
CMAKE_ONLY=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/build_zephyr.sh [options]

Options:
  --target <cluster0_amp_cpu0|cluster0_amp_cpu1|cluster1_smp>
  --app <path>               Zephyr application source dir
  --board <board>            Zephyr board name
  --build-root <path>        Zephyr build root (default: build/zephyr)
  --overlay <path>           Override overlay file path
  --jobs <n>                 Build jobs (default: nproc)
  --cmake-only               Configure only; skip build step
  --dry-run                  Print commands only
  -h, --help                 Show help
USAGE
}

run_cmd() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[DRY-RUN] $*"
  else
    echo "+ $*"
    "$@"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --app) APP_DIR="$2"; shift 2 ;;
    --board) BOARD="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$2"; shift 2 ;;
    --overlay) OVERLAY="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --cmake-only) CMAKE_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

case "${TARGET}" in
  cluster0_amp_cpu0|cluster0_amp_cpu1|cluster1_smp) ;;
  *)
    echo "[ERROR] Invalid target: ${TARGET}" >&2
    usage
    exit 1
    ;;
esac

if [[ -z "${OVERLAY}" ]]; then
  OVERLAY="${REPO_ROOT}/conf/zephyr/${TARGET}.overlay"
fi

if [[ -z "${ZEPHYR_MODULES:-}" ]]; then
  export ZEPHYR_MODULES="${REPO_ROOT}/sources/zephyr-modules/libmetal;${REPO_ROOT}/sources/zephyr-modules/open-amp"
fi

BUILD_DIR="${BUILD_ROOT}/${TARGET}"
LOG_DIR="$(omx_log_dir zephyr-${TARGET})"
LOG_FILE="${LOG_DIR}/build_zephyr.log"

if [[ "${DRY_RUN}" -eq 0 ]]; then
  exec > >(tee -a "${LOG_FILE}") 2>&1
fi

if [[ ! -d "${APP_DIR}" ]]; then
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[WARN] App dir not found (dry-run only): ${APP_DIR}" >&2
  else
    echo "[ERROR] App dir not found: ${APP_DIR}" >&2
    exit 1
  fi
fi

if [[ ! -f "${OVERLAY}" ]]; then
  echo "[ERROR] Overlay not found: ${OVERLAY}" >&2
  exit 1
fi

echo "[INFO] Zephyr no-west build target=${TARGET}"
echo "[INFO] APP_DIR=${APP_DIR}"
echo "[INFO] BUILD_DIR=${BUILD_DIR}"
echo "[INFO] OVERLAY=${OVERLAY}"
echo "[INFO] LOG_FILE=${LOG_FILE}"

run_cmd cmake -S "${APP_DIR}" -B "${BUILD_DIR}" \
  -DBOARD="${BOARD}" \
  -DZEPHYR_BASE="${ZEPHYR_BASE}" \
  -DZEPHYR_SDK_INSTALL_DIR="${ZEPHYR_SDK_INSTALL_DIR}" \
  -DZEPHYR_TOOLCHAIN_VARIANT="${ZEPHYR_TOOLCHAIN_VARIANT}" \
  -DZEPHYR_MODULES="${ZEPHYR_MODULES}" \
  -DDTC_OVERLAY_FILE="${OVERLAY}" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache

if [[ "${CMAKE_ONLY}" -eq 0 ]]; then
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    run_cmd cmake --build "${BUILD_DIR}" -j"${JOBS}"
  else
    if ! cmake --build "${BUILD_DIR}" -j"${JOBS}"; then
      if [[ "${TARGET}" == "cluster1_smp" && "${JOBS}" != "1" ]]; then
        echo "[WARN] initial parallel build failed for ${TARGET}; retrying with -j1"
        cmake --build "${BUILD_DIR}" -j1
      else
        echo "[ERROR] Zephyr build failed for ${TARGET}" >&2
        exit 1
      fi
    fi
  fi
else
  echo "[INFO] --cmake-only set; skipping build step"
fi

echo "[OK] Zephyr build flow completed"
