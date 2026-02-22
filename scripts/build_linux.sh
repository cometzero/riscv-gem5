#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/env.sh"

LINUX_SRC="${REPO_ROOT}/sources/linux"
OUT_DIR="${REPO_ROOT}/build/linux"
ARCH="riscv"
CROSS_COMPILE="riscv64-linux-gnu-"
DEFCONFIG="defconfig"
JOBS="$(nproc)"
MAKE_TARGETS="Image dtbs"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/build_linux.sh [options]

Options:
  --linux-src <path>         Linux source path (default: sources/linux)
  --out-dir <path>           Output dir (default: build/linux)
  --arch <arch>              Kernel ARCH (default: riscv)
  --cross-compile <prefix>   CROSS_COMPILE prefix (default: riscv64-linux-gnu-)
  --defconfig <name>         Defconfig target (default: defconfig)
  --make-targets "<targets>" Make targets to build (default: "Image dtbs")
  --jobs <n>                 Parallel jobs (default: nproc)
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
    --linux-src) LINUX_SRC="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --arch) ARCH="$2"; shift 2 ;;
    --cross-compile) CROSS_COMPILE="$2"; shift 2 ;;
    --defconfig) DEFCONFIG="$2"; shift 2 ;;
    --make-targets) MAKE_TARGETS="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

omx_ensure_build_layout
mkdir -p "${OUT_DIR}"

LOG_DIR="$(omx_log_dir linux)"
LOG_FILE="${LOG_DIR}/build_linux.log"

if [[ "${DRY_RUN}" -eq 0 ]]; then
  exec > >(tee -a "${LOG_FILE}") 2>&1
fi

if [[ ! -d "${LINUX_SRC}" ]]; then
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[WARN] Linux source path not found (dry-run only): ${LINUX_SRC}" >&2
  else
    echo "[ERROR] Linux source path not found: ${LINUX_SRC}" >&2
    echo "[HINT] Bootstrap first: scripts/bootstrap_sources.sh apply" >&2
    exit 1
  fi
fi

echo "[INFO] Linux build started"
echo "[INFO] ARCH=${ARCH} CROSS_COMPILE=${CROSS_COMPILE}"
echo "[INFO] OUT_DIR=${OUT_DIR}"
echo "[INFO] MAKE_TARGETS=${MAKE_TARGETS}"
echo "[INFO] LOG_FILE=${LOG_FILE}"

run_cmd env ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" CC="${CC}" HOSTCC="${CC}" \
  make -C "${LINUX_SRC}" O="${OUT_DIR}" "${DEFCONFIG}"

run_cmd env ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" CC="${CC}" HOSTCC="${CC}" \
  make -C "${LINUX_SRC}" O="${OUT_DIR}" olddefconfig

run_cmd env ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" CC="${CC}" HOSTCC="${CC}" \
  make -C "${LINUX_SRC}" O="${OUT_DIR}" -j"${JOBS}" ${MAKE_TARGETS}

echo "[OK] Linux build flow completed"
