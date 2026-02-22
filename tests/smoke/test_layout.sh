#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

required_files=(
  conf/riscv64_smp.py
  conf/riscv32_mixed.py
  conf/riscv32_simple.py
  conf/submodules.lock.json
  conf/ip/mailbox_hwsem_map.yaml
  conf/zephyr/cluster0_amp_cpu0.conf
  conf/zephyr/cluster0_amp_cpu0.overlay
  conf/zephyr/cluster0_amp_cpu1.conf
  conf/zephyr/cluster0_amp_cpu1.overlay
  conf/zephyr/cluster1_smp.conf
  conf/zephyr/cluster1_smp.overlay
  conf/zephyr/riscv32_simple.overlay
  docs/ip-implementation-plan.md
  docs/acceptance.md
  workloads/ipc/mailbox_pingpong.md
  workloads/ipc/hwsem_contention.md
  workloads/zephyr/riscv32_mixed/CMakeLists.txt
  workloads/zephyr/riscv32_mixed/Kconfig
  workloads/zephyr/riscv32_mixed/prj.conf
  workloads/zephyr/riscv32_mixed/src/main.c
  workloads/zephyr/riscv32_simple/CMakeLists.txt
  workloads/zephyr/riscv32_simple/prj.conf
  workloads/zephyr/riscv32_simple/src/main.c
  scripts/bootstrap_sources.sh
  scripts/env.sh
  scripts/build_linux.sh
  scripts/build_buildroot.sh
  scripts/build_linux_buildroot.sh
  scripts/build_riscv32_mixed_boot.sh
  scripts/build_zephyr.sh
  scripts/riscv32_mixed_boot.S
  scripts/riscv32_mixed_boot.ld
  scripts/run_gem5.py
  scripts/run_bench.sh
)

required_exec=(
  scripts/bootstrap_sources.sh
  scripts/env.sh
  scripts/build_linux.sh
  scripts/build_buildroot.sh
  scripts/build_linux_buildroot.sh
  scripts/build_riscv32_mixed_boot.sh
  scripts/build_zephyr.sh
  scripts/run_bench.sh
)

missing=0
for f in "${required_files[@]}"; do
  if [[ ! -f "${f}" ]]; then
    echo "[FAIL] missing file: ${f}"
    missing=1
  else
    echo "[OK] file: ${f}"
  fi
done

for f in "${required_exec[@]}"; do
  if [[ ! -x "${f}" ]]; then
    echo "[FAIL] not executable: ${f}"
    missing=1
  else
    echo "[OK] executable: ${f}"
  fi
done

if [[ "${missing}" -ne 0 ]]; then
  echo "[FAIL] layout test failed"
  exit 1
fi

echo "[OK] layout test passed"
