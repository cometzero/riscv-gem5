# RV32 Simple Validation Report

- Date: 2026-02-22
- Target: `riscv32_simple` (CPU0 only)

## 1) Objective

`riscv32_mixed` bring-up 이슈를 분리하기 위해, 단일 코어 `riscv32_simple` 경로를 추가하고
Zephyr boot + simple workload marker 동작을 확인한다.

## 2) Commands Executed

```bash
cd /build/risc-v/riscv-gem5

# Build custom Zephyr workload app
scripts/build_zephyr.sh --target riscv32_simple --jobs "$(nproc)"

# Non-dry runtime check
python3 scripts/run_gem5.py --target riscv32_simple --mode simple

# Bench wrapper (manifest/summary generation)
scripts/run_bench.sh --target riscv32_simple --mode simple
```

## 3) Evidence

Primary evidence timestamp: `20260222T044818Z`

- Run manifest:
  - `workloads/results/20260222T044818Z/run_gem5_riscv32_simple_simple.json`
- Bench manifest:
  - `workloads/results/20260222T044818Z/bench_riscv32_simple_simple.json`
- Run log:
  - `build/logs/riscv32_simple/20260222T044818Z/run_riscv32_simple.log`
- Terminal log (Zephyr UART):
  - `build/logs/riscv32_simple/20260222T044818Z/system.platform.terminal`

Observed terminal output:

```text
*** Booting Zephyr OS build a6fb8b8a19f9 ***
RISCV32 SIMPLE WORKLOAD START
RISCV32 SIMPLE WORKLOAD DONE acc=17500
```

Manifest checks (`run_gem5_riscv32_simple_simple.json`):

- `run_result.returncode = 0`
- `markers["*** Booting Zephyr OS"] = true`
- `markers["RISCV32 SIMPLE WORKLOAD START"] = true`
- `markers["RISCV32 SIMPLE WORKLOAD DONE"] = true`
- `sim_insts = 49505`

## 4) Acceptance

- [x] CPU0-only RV32 target added
- [x] Zephyr boot marker detected
- [x] Workload start/done markers detected
- [x] non-dry run manifest and bench manifest generated
