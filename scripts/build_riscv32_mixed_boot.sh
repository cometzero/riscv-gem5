#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/env.sh"

BOOT_START="0x80000000"
AMP_CPU0_ENTRY="0x81000000"
AMP_CPU1_ENTRY="0x84000000"
CLUSTER1_SMP_ENTRY="0x88000000"
OUTPUT="${REPO_ROOT}/build/boot/riscv32_mixed_boot.elf"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/build_riscv32_mixed_boot.sh [options]

Options:
  --boot-start <addr>
  --amp-cpu0-entry <addr>
  --amp-cpu1-entry <addr>
  --cluster1-smp-entry <addr>
  --output <path>
  --dry-run
  -h, --help
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
    --boot-start) BOOT_START="$2"; shift 2 ;;
    --amp-cpu0-entry) AMP_CPU0_ENTRY="$2"; shift 2 ;;
    --amp-cpu1-entry) AMP_CPU1_ENTRY="$2"; shift 2 ;;
    --cluster1-smp-entry) CLUSTER1_SMP_ENTRY="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

TOOLCHAIN_BIN="${ZEPHYR_SDK_INSTALL_DIR}/riscv64-zephyr-elf/bin"
CC="${TOOLCHAIN_BIN}/riscv64-zephyr-elf-gcc"
if [[ ! -x "${CC}" ]]; then
  echo "[ERROR] compiler not found: ${CC}" >&2
  exit 1
fi

OUT_DIR="$(dirname -- "${OUTPUT}")"
mkdir -p "${OUT_DIR}"
TMP_DIR="${OUT_DIR}/.riscv32_mixed_boot_tmp"
mkdir -p "${TMP_DIR}"
ADDR_HEADER="${TMP_DIR}/riscv32_mixed_boot_addr.h"

cat > "${ADDR_HEADER}" <<EOF2
#define AMP_CPU0_ENTRY ${AMP_CPU0_ENTRY}
#define AMP_CPU1_ENTRY ${AMP_CPU1_ENTRY}
#define CLUSTER1_SMP_ENTRY ${CLUSTER1_SMP_ENTRY}
EOF2

run_cmd "${CC}" \
  -march=rv32imac_zicsr_zifencei -mabi=ilp32 \
  -nostdlib -nostartfiles -ffreestanding \
  -I"${TMP_DIR}" \
  -Wl,-T,"${SCRIPT_DIR}/riscv32_mixed_boot.ld" \
  -Wl,--defsym,BOOT_START="${BOOT_START}" \
  -Wl,--build-id=none \
  "${SCRIPT_DIR}/riscv32_mixed_boot.S" \
  -o "${OUTPUT}"

echo "[OK] mixed boot trampoline: ${OUTPUT}"
echo "[INFO] boot_start=${BOOT_START} amp_cpu0=${AMP_CPU0_ENTRY} amp_cpu1=${AMP_CPU1_ENTRY} cluster1_smp=${CLUSTER1_SMP_ENTRY}"
