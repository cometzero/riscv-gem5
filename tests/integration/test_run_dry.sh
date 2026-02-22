#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"

echo "[INFO] dry-run gem5 scripts"
python3 scripts/run_gem5.py --target riscv64_smp --mode simple --timestamp "${TS}" --dry-run
python3 scripts/run_gem5.py --target riscv32_mixed --mode complex --timestamp "${TS}" --dry-run

echo "[INFO] dry-run benchmark wrapper"
scripts/run_bench.sh --target riscv64_smp --mode simple --timestamp "${TS}" --dry-run
scripts/run_bench.sh --target riscv32_mixed --mode complex --timestamp "${TS}" --dry-run --ipc-case mailbox_pingpong

assert_file() {
  local f="$1"
  if [[ ! -f "${f}" ]]; then
    echo "[FAIL] missing file: ${f}"
    exit 1
  fi
  echo "[OK] file exists: ${f}"
}

assert_dir() {
  local d="$1"
  if [[ ! -d "${d}" ]]; then
    echo "[FAIL] missing dir: ${d}"
    exit 1
  fi
  echo "[OK] dir exists: ${d}"
}

assert_dir "workloads/results/${TS}"
assert_dir "build/logs/riscv64_smp/${TS}"
assert_dir "build/logs/riscv32_mixed/${TS}"

assert_file "workloads/results/${TS}/run_gem5_riscv64_smp_simple.json"
assert_file "workloads/results/${TS}/run_gem5_riscv32_mixed_complex.json"
assert_file "workloads/results/${TS}/bench_riscv64_smp_simple.json"
assert_file "workloads/results/${TS}/bench_riscv32_mixed_complex.json"
assert_file "workloads/results/${TS}/summary_riscv64_smp_simple.md"
assert_file "workloads/results/${TS}/summary_riscv32_mixed_complex.md"

echo "[OK] integration dry-run test passed"
