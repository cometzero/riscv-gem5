#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="cluster1_smp"
APP_DIR=""
APP_EXPLICIT=0
BOARD="qemu_riscv32"
BUILD_ROOT="${REPO_ROOT}/build/zephyr"
OVERLAY=""
EXTRA_CONF=""
JOBS="$(nproc)"
DRY_RUN=0
CMAKE_ONLY=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/build_zephyr.sh [options]

Options:
  --target <cluster0_amp_cpu0|cluster0_amp_cpu1|cluster1_smp|riscv32_simple>
  --app <path>               Zephyr application source dir
  --board <board>            Zephyr board name
  --build-root <path>        Zephyr build root (default: build/zephyr)
  --overlay <path>           Override overlay file path
  --extra-conf <path>        Additional Zephyr config fragment
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
    --app) APP_DIR="$2"; APP_EXPLICIT=1; shift 2 ;;
    --board) BOARD="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$2"; shift 2 ;;
    --overlay) OVERLAY="$2"; shift 2 ;;
    --extra-conf) EXTRA_CONF="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --cmake-only) CMAKE_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

case "${TARGET}" in
  cluster0_amp_cpu0|cluster0_amp_cpu1|cluster1_smp|riscv32_simple) ;;
  *)
    echo "[ERROR] Invalid target: ${TARGET}" >&2
    usage
    exit 1
    ;;
esac

if [[ "${APP_EXPLICIT}" -eq 0 ]]; then
  case "${TARGET}" in
    riscv32_simple)
      APP_DIR="${REPO_ROOT}/workloads/zephyr/riscv32_simple"
      ;;
    cluster0_amp_cpu0|cluster0_amp_cpu1|cluster1_smp)
      APP_DIR="${REPO_ROOT}/workloads/zephyr/riscv32_mixed"
      ;;
    *)
      APP_DIR="${REPO_ROOT}/sources/zephyr/samples/hello_world"
      ;;
  esac
fi

if [[ -z "${OVERLAY}" ]]; then
  OVERLAY="${REPO_ROOT}/conf/zephyr/${TARGET}.overlay"
fi

if [[ -z "${EXTRA_CONF}" ]]; then
  case "${TARGET}" in
    cluster0_amp_cpu0|cluster0_amp_cpu1|cluster1_smp)
      EXTRA_CONF="${REPO_ROOT}/conf/zephyr/${TARGET}.conf"
      ;;
    *)
      EXTRA_CONF=""
      ;;
  esac
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

if [[ -n "${EXTRA_CONF}" && ! -f "${EXTRA_CONF}" ]]; then
  echo "[ERROR] extra conf not found: ${EXTRA_CONF}" >&2
  exit 1
fi

if [[ -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  cached_home="$(grep -E '^CMAKE_HOME_DIRECTORY:INTERNAL=' "${BUILD_DIR}/CMakeCache.txt" | cut -d= -f2- || true)"
  if [[ -n "${cached_home}" && "${cached_home}" != "${APP_DIR}" ]]; then
    echo "[WARN] Existing build dir is bound to another app:"
    echo "[WARN]   cached=${cached_home}"
    echo "[WARN]   current=${APP_DIR}"
    echo "[WARN] Cleaning ${BUILD_DIR} for reconfigure."
    rm -rf "${BUILD_DIR}"
  fi
fi

echo "[INFO] Zephyr no-west build target=${TARGET}"
echo "[INFO] APP_DIR=${APP_DIR}"
echo "[INFO] BUILD_DIR=${BUILD_DIR}"
echo "[INFO] OVERLAY=${OVERLAY}"
if [[ -n "${EXTRA_CONF}" ]]; then
  echo "[INFO] EXTRA_CONF=${EXTRA_CONF}"
fi
echo "[INFO] LOG_FILE=${LOG_FILE}"

cmake_args=(
  -S "${APP_DIR}"
  -B "${BUILD_DIR}"
  -DBOARD="${BOARD}"
  -DZEPHYR_BASE="${ZEPHYR_BASE}"
  -DZEPHYR_SDK_INSTALL_DIR="${ZEPHYR_SDK_INSTALL_DIR}"
  -DZEPHYR_TOOLCHAIN_VARIANT="${ZEPHYR_TOOLCHAIN_VARIANT}"
  -DZEPHYR_MODULES="${ZEPHYR_MODULES}"
  -DDTC_OVERLAY_FILE="${OVERLAY}"
  -DCMAKE_C_COMPILER_LAUNCHER=ccache
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
)
if [[ -n "${EXTRA_CONF}" ]]; then
  cmake_args+=(-DEXTRA_CONF_FILE="${EXTRA_CONF}")
fi

run_cmd cmake "${cmake_args[@]}"

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
