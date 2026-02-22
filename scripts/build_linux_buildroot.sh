#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

LINUX_DEFCONFIG="defconfig"
BUILDROOT_DEFCONFIG="qemu_riscv64_virt_defconfig"
JOBS="$(nproc)"
DRY_RUN=0
SKIP_LINUX=0
SKIP_BUILDROOT=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/build_linux_buildroot.sh [options]

Options:
  --linux-defconfig <name>      Linux defconfig (default: defconfig)
  --buildroot-defconfig <name>  Buildroot defconfig (default: qemu_riscv64_virt_defconfig)
  --jobs <n>                    Parallel jobs (default: nproc)
  --skip-linux                  Skip Linux build
  --skip-buildroot              Skip Buildroot build
  --dry-run                     Pass dry-run to child scripts
  -h, --help                    Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --linux-defconfig) LINUX_DEFCONFIG="$2"; shift 2 ;;
    --buildroot-defconfig) BUILDROOT_DEFCONFIG="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --skip-linux) SKIP_LINUX=1; shift ;;
    --skip-buildroot) SKIP_BUILDROOT=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

DRY_ARG=()
if [[ "${DRY_RUN}" -eq 1 ]]; then
  DRY_ARG=(--dry-run)
fi

if [[ "${SKIP_LINUX}" -eq 0 ]]; then
  "${SCRIPT_DIR}/build_linux.sh" \
    --defconfig "${LINUX_DEFCONFIG}" \
    --jobs "${JOBS}" \
    "${DRY_ARG[@]}"
else
  echo "[INFO] Linux build skipped"
fi

if [[ "${SKIP_BUILDROOT}" -eq 0 ]]; then
  "${SCRIPT_DIR}/build_buildroot.sh" \
    --defconfig "${BUILDROOT_DEFCONFIG}" \
    --jobs "${JOBS}" \
    "${DRY_ARG[@]}"
else
  echo "[INFO] Buildroot build skipped"
fi

echo "[OK] Linux+Buildroot orchestration completed"
