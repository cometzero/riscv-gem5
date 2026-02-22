# Execution Guide (gem5 RISC-V)

- Date: 2026-02-22
- Audience: reproducible bring-up for RV32 mixed + RV64 SMP targets

## 1) Recommendation

권장 실행 순서:

1. source bootstrap (pinned submodule)
2. build env + gem5 build
3. Linux + Buildroot build
4. Zephyr (3 targets) build
5. non-dry simulation run (RV64, RV32 mixed)
6. benchmark wrapper + evidence verification

## 2) Prerequisites

Assumption:

- Host: Linux (Ubuntu 22.04+ recommended)
- Tools: `git`, `python3`, `cmake`, `ninja`, `ccache`, `scons`, RISC-V cross toolchain
- Zephyr SDK installed (`/opt/zephyr-sdk` or `/build/risc-v/riscv-renode/build/zephyr-sdk`)

Quick check:

```bash
cd /build/risc-v/riscv-gem5
scripts/env.sh print
```

## 3) Source Bootstrap (submodule)

```bash
cd /build/risc-v/riscv-gem5
scripts/bootstrap_sources.sh plan
scripts/bootstrap_sources.sh verify-lock
scripts/bootstrap_sources.sh apply

git submodule status --recursive
```

Expected:

- `sources/*` submodule checkout complete
- `sources/linux` remains shallow

## 4) Build Steps

## 4.1 gem5

```bash
cd /build/risc-v/riscv-gem5
source scripts/env.sh
log_dir=$(omx_log_dir gem5)
scons -C sources/gem5 build/RISCV/gem5.opt -j"$(nproc)" 2>&1 | tee "$log_dir/gem5-build.log"
```

Output:

- `sources/gem5/build/RISCV/gem5.opt`

## 4.2 Linux + Buildroot

```bash
cd /build/risc-v/riscv-gem5
scripts/build_linux_buildroot.sh --jobs "$(nproc)"
```

Key outputs:

- `build/linux/arch/riscv/boot/Image`
- `build/buildroot/images/rootfs.ext2`

## 4.3 Zephyr (no-west, cmake only)

```bash
cd /build/risc-v/riscv-gem5
scripts/build_zephyr.sh --target cluster0_amp_cpu0 --jobs "$(nproc)"
scripts/build_zephyr.sh --target cluster0_amp_cpu1 --jobs "$(nproc)"
scripts/build_zephyr.sh --target cluster1_smp   --jobs "$(nproc)"
```

Key outputs:

- `build/zephyr/cluster0_amp_cpu0/zephyr/zephyr.elf`
- `build/zephyr/cluster0_amp_cpu1/zephyr/zephyr.elf`
- `build/zephyr/cluster1_smp/zephyr/zephyr.elf`

## 5) Run Simulation (non-dry)

## 5.1 RV64 SMP

```bash
cd /build/risc-v/riscv-gem5
python3 scripts/run_gem5.py --target riscv64_smp --mode simple
```

## 5.2 RV32 mixed (AMP/SMP split path)

```bash
cd /build/risc-v/riscv-gem5
python3 scripts/run_gem5.py --target riscv32_mixed --mode complex
```

## 5.3 Bench wrappers

```bash
cd /build/risc-v/riscv-gem5
scripts/run_bench.sh --target riscv64_smp --mode simple
scripts/run_bench.sh --target riscv32_mixed --mode complex --ipc-case mailbox_pingpong
```

## 6) Verification

## 6.1 Automated checks

```bash
cd /build/risc-v/riscv-gem5
bash tests/smoke/test_layout.sh
bash tests/smoke/test_scripts_syntax.sh
bash tests/integration/test_run_dry.sh
```

## 6.2 Runtime evidence checks

```bash
cd /build/risc-v/riscv-gem5
find workloads/results -maxdepth 2 -name 'run_gem5_*.json' | sort | tail -n 6
find build/logs -maxdepth 4 -name 'run_*.log' | sort | tail -n 6
```

Pass criteria:

- run manifest has `"run_result": { "returncode": 0, ... }`
- run log contains `**** REAL SIMULATION ****`
- benchmark manifest exists for both targets

## 7) Known Caveat

- Deprecated `fs_linux.py` path with local `build/linux/vmlinux` can fail with invalid mapping/panic.
- 현재 안정 경로는 resource kernel fallback + Buildroot rootfs 조합이다.

## 8) Definition of Done (DoD)

- [ ] `scripts/bootstrap_sources.sh apply` success
- [ ] gem5 binary build success
- [ ] Linux/Buildroot outputs present
- [ ] Zephyr ELFs (3 targets) present
- [ ] RV64 and RV32 non-dry manifests generated with RC=0
- [ ] smoke/syntax/integration tests all pass
