#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC2034
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# ccache contract (shared by gem5/zephyr/linux/buildroot)
export CCACHE_DIR="${CCACHE_DIR:-${REPO_ROOT}/build/.ccache}"
export CCACHE_BASEDIR="${CCACHE_BASEDIR:-${REPO_ROOT}}"
export CCACHE_COMPRESS="${CCACHE_COMPRESS:-1}"
export CCACHE_COMPRESSLEVEL="${CCACHE_COMPRESSLEVEL:-6}"
export CCACHE_MAXSIZE="${CCACHE_MAXSIZE:-20G}"
export CCACHE_SLOPPINESS="${CCACHE_SLOPPINESS:-time_macros}"
export CCACHE_COMPILERCHECK="${CCACHE_COMPILERCHECK:-content}"

# Common compilers (override externally when needed)
export OMX_CCACHE_C_COMPILER="${OMX_CCACHE_C_COMPILER:-gcc}"
export OMX_CCACHE_CXX_COMPILER="${OMX_CCACHE_CXX_COMPILER:-g++}"

export CC="${CC:-ccache ${OMX_CCACHE_C_COMPILER}}"
export CXX="${CXX:-ccache ${OMX_CCACHE_CXX_COMPILER}}"

# Zephyr no-west defaults
export ZEPHYR_TOOLCHAIN_VARIANT="${ZEPHYR_TOOLCHAIN_VARIANT:-zephyr}"
export ZEPHYR_BASE="${ZEPHYR_BASE:-${REPO_ROOT}/sources/zephyr}"
if [[ -z "${ZEPHYR_SDK_INSTALL_DIR:-}" ]]; then
  if [[ -d "/opt/zephyr-sdk" ]]; then
    export ZEPHYR_SDK_INSTALL_DIR="/opt/zephyr-sdk"
  elif [[ -d "/build/risc-v/riscv-renode/build/zephyr-sdk" ]]; then
    export ZEPHYR_SDK_INSTALL_DIR="/build/risc-v/riscv-renode/build/zephyr-sdk"
  else
    export ZEPHYR_SDK_INSTALL_DIR="/opt/zephyr-sdk"
  fi
fi

# Build/log roots
export BUILD_ROOT="${BUILD_ROOT:-${REPO_ROOT}/build}"
export BUILD_LOG_ROOT="${BUILD_LOG_ROOT:-${BUILD_ROOT}/logs}"

omx_ts_utc() {
  date -u +%Y%m%dT%H%M%SZ
}

omx_ensure_build_layout() {
  mkdir -p \
    "${BUILD_ROOT}" \
    "${BUILD_ROOT}/gem5" \
    "${BUILD_ROOT}/linux" \
    "${BUILD_ROOT}/buildroot" \
    "${BUILD_ROOT}/zephyr" \
    "${BUILD_LOG_ROOT}"
}

omx_log_dir() {
  local target="$1"
  local ts="${2:-$(omx_ts_utc)}"
  local log_dir="${BUILD_LOG_ROOT}/${target}/${ts}"
  mkdir -p "${log_dir}"
  echo "${log_dir}"
}

omx_print_env_contract() {
  cat <<EOF2
REPO_ROOT=${REPO_ROOT}
CCACHE_DIR=${CCACHE_DIR}
CCACHE_BASEDIR=${CCACHE_BASEDIR}
CC=${CC}
CXX=${CXX}
ZEPHYR_BASE=${ZEPHYR_BASE}
ZEPHYR_SDK_INSTALL_DIR=${ZEPHYR_SDK_INSTALL_DIR}
BUILD_ROOT=${BUILD_ROOT}
BUILD_LOG_ROOT=${BUILD_LOG_ROOT}
EOF2
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  cmd="${1:-print}"
  case "${cmd}" in
    print)
      omx_ensure_build_layout
      omx_print_env_contract
      ;;
    mklog)
      if [[ $# -lt 2 ]]; then
        echo "Usage: scripts/env.sh mklog <target> [timestamp]" >&2
        exit 1
      fi
      omx_ensure_build_layout
      omx_log_dir "$2" "${3:-}"
      ;;
    *)
      echo "Usage: scripts/env.sh [print|mklog <target> [timestamp]]" >&2
      exit 1
      ;;
  esac
fi
