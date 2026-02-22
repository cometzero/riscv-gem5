#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/env.sh"

BUILDROOT_SRC="${REPO_ROOT}/sources/buildroot"
OUT_DIR="${REPO_ROOT}/build/buildroot"
DEFCONFIG="qemu_riscv64_virt_defconfig"
JOBS="$(nproc)"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/build_buildroot.sh [options]

Options:
  --buildroot-src <path>     Buildroot source path (default: sources/buildroot)
  --out-dir <path>           Output dir (default: build/buildroot)
  --defconfig <name>         Buildroot defconfig (default: qemu_riscv64_virt_defconfig)
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
    --buildroot-src) BUILDROOT_SRC="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --defconfig) DEFCONFIG="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

omx_ensure_build_layout
mkdir -p "${OUT_DIR}"

LOG_DIR="$(omx_log_dir buildroot)"
LOG_FILE="${LOG_DIR}/build_buildroot.log"

if [[ "${DRY_RUN}" -eq 0 ]]; then
  exec > >(tee -a "${LOG_FILE}") 2>&1
fi

if [[ ! -d "${BUILDROOT_SRC}" ]]; then
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[WARN] Buildroot source path not found (dry-run only): ${BUILDROOT_SRC}" >&2
  else
    echo "[ERROR] Buildroot source path not found: ${BUILDROOT_SRC}" >&2
    echo "[HINT] Bootstrap first: scripts/bootstrap_sources.sh apply" >&2
    exit 1
  fi
fi

CONFIG_FILE="${OUT_DIR}/.config"
CONFIG_TOOL="${BUILDROOT_SRC}/support/scripts/config"

# 1) baseline defconfig
run_cmd make -C "${BUILDROOT_SRC}" O="${OUT_DIR}" "${DEFCONFIG}"

# 2) enforce kernel-disabled policy in Buildroot flow
if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[DRY-RUN] enforce Buildroot kernel disabled: BR2_LINUX_KERNEL=n"
else
  if [[ -x "${CONFIG_TOOL}" ]]; then
    "${CONFIG_TOOL}" --file "${CONFIG_FILE}" --disable BR2_LINUX_KERNEL
  else
    # fallback when support/scripts/config is unavailable
    if grep -q '^BR2_LINUX_KERNEL=y$' "${CONFIG_FILE}"; then
      sed -i 's/^BR2_LINUX_KERNEL=y$/# BR2_LINUX_KERNEL is not set/' "${CONFIG_FILE}"
    fi
    if ! grep -q '^# BR2_LINUX_KERNEL is not set$' "${CONFIG_FILE}"; then
      echo '# BR2_LINUX_KERNEL is not set' >> "${CONFIG_FILE}"
    fi
  fi

  make -C "${BUILDROOT_SRC}" O="${OUT_DIR}" olddefconfig

  if grep -q '^BR2_LINUX_KERNEL=y$' "${CONFIG_FILE}"; then
    echo "[ERROR] Buildroot kernel build is still enabled; policy violation." >&2
    exit 1
  fi
fi

# 3) rootfs build with ccache
run_cmd env BR2_CCACHE=y BR2_CCACHE_DIR="${CCACHE_DIR}" \
  make -C "${BUILDROOT_SRC}" O="${OUT_DIR}" -j"${JOBS}"

echo "[OK] Buildroot build flow completed (kernel disabled policy enforced)"
