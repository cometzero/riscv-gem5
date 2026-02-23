# Implementation & Change Guide (Current Baseline)

- Scope: gem5 RISC-V workspace status and recent implementation changes
- Audience: bring-up engineer, CI integrator, reviewer

## 1) Recommendation (TL;DR)

Use `riscv_hybrid` as the integrated validation target, but run with a longer
timeout for strict Linux shell markers:

```bash
cd /build/risc-v/riscv-gem5
python3 scripts/run_gem5.py --target riscv_hybrid --mode simple --timeout-sec 900
```

If you want a fixed-duration soak (no early-stop on markers):

```bash
python3 scripts/run_gem5.py --target riscv_hybrid --mode simple --timeout-sec 900 --no-stop-on-marker
```

---

## 2) What is implemented now

## 2.1 Target matrix

| Target | Status | Main purpose |
|---|---|---|
| `riscv32_simple` | implemented | CPU0-only Zephyr smoke/bring-up |
| `riscv32_mixed` | implemented | one gem5 RV32 mixed AMP/SMP |
| `riscv64_smp` | implemented | RV64 Linux SMP boot + initramfs shell |
| `riscv_hybrid` | implemented | one gem5 process running RV32 mixed + RV64 Linux |

## 2.2 Hybrid topology (one gem5 process)

- `system32` (RV32 mixed):
  - Cluster0: CPU0/CPU1 AMP
  - Cluster1: CPU2/3/4/5 SMP
  - UART policy:
    - UART0 -> CPU0 instance
    - UART1 -> CPU1 instance
    - UART2 -> CPU2-5 SMP instance
- `system64` (RV64 Linux):
  - CPU0-3 SMP
  - OpenSBI + Linux kernel + initramfs

---

## 3) Marker policy (strict)

## 3.1 RV64 strict markers in hybrid

Required for strict pass:

- `OpenSBI`
- `Linux version`
- `Loaded bootloader`
- `Loaded kernel`
- `Run /init as init process`
- `INITRAMFS_SHELL_READY`
- `initramfs#`

Forbidden:

- `Kernel panic`
- `panic`
- `fatal:`

## 3.2 Hybrid staged reporting

`run_gem5.py` now evaluates and reports stages:

- `rv32_workloads_ready`
- `rv64_boot_banner`
- `rv64_kernel_loaded`
- `rv64_init_handoff`
- `rv64_shell_ready`
- `panic_free`

Outputs:

1. Console logs (`[STAGE][PASS|FAIL] ...`)
2. Manifest field: `stage_report`

Example readout:

```bash
TS=$(ls -1t workloads/results | head -n1)
python3 - <<'PY' "$TS"
import json,sys
ts=sys.argv[1]
p=f"workloads/results/{ts}/run_gem5_riscv_hybrid_simple.json"
d=json.load(open(p, encoding="utf-8"))
for s in d.get("stage_report", []):
    print(s["name"], "PASS" if s["passed"] else "FAIL", "missing=", s["missing"])
PY
```

---

## 4) Timeout behavior guide

- Default hybrid simple mode uses marker-based early-stop.
  - `--timeout-sec` is upper bound, not guaranteed runtime.
- `--no-stop-on-marker` disables early-stop.
  - Useful for soak/time-boxed runs.
- Practical recommendation for strict marker completion:
  - start from `--timeout-sec 900`
  - increase further when `rv64_init_handoff` / `rv64_shell_ready` is pending

---

## 5) Artifact map

- Run manifest:
  - `workloads/results/<TS>/run_gem5_<target>_<mode>.json`
- Target logs:
  - `build/logs/<target>/<TS>/`
- Hybrid UART logs:
  - `system32.platform.terminal*`
  - `system64.platform.terminal`
- Fast access links:
  - `workloads/results/latest*`
  - `build/logs/riscv_hybrid/latest*`

---

## 6) Recent change summary (traceability)

Recent key commits:

- `66967fb0d84c` feat(run): staged hybrid marker reporting
- `1085ce0eaa82` fix(run): tighter hybrid RV64 strict markers
- `0c594ffada97` fix(run): timeout-pass policy for `--no-stop-on-marker`
- `1829ca4d0d50` fix(run): explicit marker-stop behavior
- `87aab4c5df4f` feat(run): initial `riscv_hybrid` one-gem5 target
- `aed506958ef5` test(run): hybrid dry-run coverage
- `042392d6562c` docs(run): hybrid workflow documentation

Check exact history:

```bash
git log --oneline --decorate -n 20
```

---

## 7) Definition of Done (DoD) for integrated run

- [ ] `riscv_hybrid` command uses one gem5 command (`commands` length = 1)
- [ ] `checks.rv32_markers_ok == true`
- [ ] `checks.rv64_boot_ok == true`
- [ ] `checks.required_markers_ok == true`
- [ ] `checks.panic_free == true`
- [ ] all `stage_report` entries are `passed=true`
- [ ] evidence files kept under `workloads/results/<TS>/` and `build/logs/riscv_hybrid/<TS>/`

