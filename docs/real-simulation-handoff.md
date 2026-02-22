# Real Simulation Handoff (Phase: Runtime Validation)

- Date: 2026-02-22
- Team: `riscv-gem5-real-simulation-pha`
- Scope: non-dry-run execution evidence for RV32 mixed path + RV64 SMP path

## 1) Conclusion

Real simulation executions were completed with `returncode=0` on both target flows below:

- RV32 mixed flow (AMP cpu0/cpu1 + SMP cluster1 split execution path)
- RV64 SMP flow (resource kernel + Buildroot rootfs)

Team tasks are complete:

- `.omx/state/team/riscv-gem5-real-simulation-pha/tasks/task-1.json` => `completed`
- `.omx/state/team/riscv-gem5-real-simulation-pha/tasks/task-2.json` => `completed`

## 2) Runtime Evidence (non-dry)

## 2.1 RV32 mixed

- Manifest:
  - `workloads/results/20260222T032724Z/run_gem5_riscv32_mixed_complex.json`
- Logs:
  - `build/logs/riscv32_mixed/20260222T032724Z/run_riscv32_mixed_amp_cpu0.log`
  - `build/logs/riscv32_mixed/20260222T032724Z/run_riscv32_mixed_amp_cpu1.log`
  - `build/logs/riscv32_mixed/20260222T032724Z/run_riscv32_mixed_cluster1_smp.log`
- Bench manifest:
  - `workloads/results/20260222T032735Z/bench_riscv32_mixed_complex.json`

## 2.2 RV64 SMP

- Manifest:
  - `workloads/results/20260222T034250Z/run_gem5_riscv64_smp_simple.json`
- Log:
  - `build/logs/riscv64_smp/20260222T034250Z/run_riscv64_smp.log`
- Bench manifest:
  - `workloads/results/20260222T034252Z/bench_riscv64_smp_simple.json`

## 3) Verification Commands (executed)

```bash
# Team status
omx team status riscv-gem5-real-simulation-pha

# Smoke + integration tests
bash tests/smoke/test_layout.sh
bash tests/smoke/test_scripts_syntax.sh
bash tests/integration/test_run_dry.sh

# State cleanup after completion
omx cancel
```

## 4) Verification Results

- Team status: `phase=complete`, `completed=2`, `failed=0`
- Tests:
  - `tests/smoke/test_layout.sh` => PASS
  - `tests/smoke/test_scripts_syntax.sh` => PASS
  - `tests/integration/test_run_dry.sh` => PASS
- Mode state cleanup:
  - `Cancelled: ralph`
  - `Cancelled: team`
  - `Cancelled: ultrawork`

## 5) Known Limitation

- `build/linux/vmlinux` with deprecated `fs_linux.py` path showed invalid mapping/panic in prior attempts.
- Stable runtime path in this phase used resource kernel fallback + Buildroot rootfs.

## 6) Definition of Done (Runtime Phase)

- [x] non-dry RV32 mixed execution evidence collected
- [x] non-dry RV64 SMP execution evidence collected
- [x] benchmark manifests generated for both targets
- [x] team tasks closed as completed
- [x] smoke/integration tests passed
- [x] OMX active modes cleaned up
