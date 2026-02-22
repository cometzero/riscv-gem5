#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

echo "[INFO] bash -n checks"
bash -n scripts/bootstrap_sources.sh
bash -n scripts/env.sh
bash -n scripts/build_linux.sh
bash -n scripts/build_buildroot.sh
bash -n scripts/build_linux_buildroot.sh
bash -n scripts/build_zephyr.sh
bash -n scripts/run_bench.sh
bash -n tests/smoke/test_layout.sh
bash -n tests/smoke/test_scripts_syntax.sh
bash -n tests/integration/test_run_dry.sh

echo "[INFO] python compile checks"
python3 -m py_compile \
  conf/riscv64_smp.py \
  conf/riscv32_mixed.py \
  scripts/run_gem5.py

echo "[OK] syntax checks passed"
