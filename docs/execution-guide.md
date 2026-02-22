# Execution Guide (gem5 RISC-V)

- Date: 2026-02-22
- Audience: reproducible bring-up for RV32 simple/mixed + RV64 SMP targets

## 1) Recommendation

권장 실행 순서:

1. source bootstrap (pinned submodule)
2. build env + gem5 build
3. Linux + Buildroot build
4. Zephyr (4 targets) build
5. non-dry simulation run (RV64, RV32 mixed, RV32 simple)
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
scripts/build_zephyr.sh --target riscv32_simple --jobs "$(nproc)"
```

Note:
- mixed targets (`cluster0_amp_cpu0|cluster0_amp_cpu1|cluster1_smp`) build
  `workloads/zephyr/riscv32_mixed` by default.
- mixed targets apply per-target `EXTRA_CONF_FILE`
  (`conf/zephyr/<target>.conf`) for boot-hart/SMP role separation.
- optional per-phase verbose logs are controlled by
  `CONFIG_RISCV32_MIXED_VERBOSE` in `workloads/zephyr/riscv32_mixed/prj.conf`.
- one-gem5 mixed boot trampoline is auto-built by `run_gem5.py` and can be
  built manually via `scripts/build_riscv32_mixed_boot.sh`.
- mixed UART split policy:
  - `cluster0_amp_cpu0` -> `UART0` (`0x10000000`)
  - `cluster0_amp_cpu1` -> `UART1` (`0x10001000`)
  - `cluster1_smp` -> `UART2` (`0x10002000`)

Key outputs:

- `build/zephyr/cluster0_amp_cpu0/zephyr/zephyr.elf`
- `build/zephyr/cluster0_amp_cpu1/zephyr/zephyr.elf`
- `build/zephyr/cluster1_smp/zephyr/zephyr.elf`
- `build/zephyr/riscv32_simple/zephyr/zephyr.elf`

## 5) Run Simulation (non-dry)

## 5.1 RV64 SMP

```bash
cd /build/risc-v/riscv-gem5
python3 scripts/run_gem5.py --target riscv64_smp --mode simple
```

## 5.2 RV32 mixed (single gem5, mixed AMP/SMP path)

```bash
cd /build/risc-v/riscv-gem5
python3 scripts/run_gem5.py --target riscv32_mixed --mode complex
```

## 5.3 RV32 simple (CPU0 only)

```bash
cd /build/risc-v/riscv-gem5
python3 scripts/run_gem5.py --target riscv32_simple --mode simple
```

## 5.4 Bench wrappers

```bash
cd /build/risc-v/riscv-gem5
scripts/run_bench.sh --target riscv64_smp --mode simple
scripts/run_bench.sh --target riscv32_mixed --mode complex --ipc-case mailbox_pingpong
scripts/run_bench.sh --target riscv32_simple --mode simple
```

## 5.5 Web dashboard (headless server)

```bash
cd /build/risc-v/riscv-gem5
scripts/run_web_dashboard.sh
```

Browser access:

- `http://<server-ip>:8080`

Detailed usage:

- `docs/web-dashboard.md`

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
find build/logs/riscv32_mixed -maxdepth 3 -name 'system.platform.terminal*' | sort | tail -n 9
```

Quick access symlinks:

```bash
ls -l workloads/results/latest*
ls -l build/logs/riscv64_smp/latest*
ls -l build/logs/riscv32_mixed/latest*
ls -l build/logs/riscv32_simple/latest*
```

Pass criteria:

- run manifest has `"run_result": { "returncode": 0, ... }`
- `riscv32_mixed` run manifest has exactly one command (`commands` length = 1)
- `riscv32_mixed` run manifest has `checks` with all fields `true`
  (`returncode_ok`, `required_markers_ok`, `terminal_markers_ok`, `panic_free`)
- `riscv32_mixed` run manifest `terminal_logs` includes:
  `system.platform.terminal`, `system.platform.terminal1`, `system.platform.terminal2`
- `riscv32_mixed` terminal logs contain one-simulator sync marker:
  `RISCV32 MIXED ROLE_SYNC mask=0x7 status=READY`
- `riscv32_mixed` terminal logs contain DONE markers for all instances:
  - `RISCV32 MIXED AMP CPU0 WORKLOAD DONE`
  - `RISCV32 MIXED AMP CPU1 WORKLOAD DONE`
  - `RISCV32 MIXED CLUSTER1 SMP WORKLOAD DONE`
- benchmark manifest exists for all enabled targets

## 7) Known Caveat

- `riscv64_smp` 는 `fs_linux.py` 경로에서 OpenSBI bootloader(`fw_jump.elf`)를 함께 지정해야
  kernel mapping fatal을 피할 수 있다.
- `scripts/run_gem5.py`는 `fw_jump.elf`를 자동 탐색하여 `--bootloader`를 주입한다.

## 8) Definition of Done (DoD)

- [ ] `scripts/bootstrap_sources.sh apply` success
- [ ] gem5 binary build success
- [ ] Linux/Buildroot outputs present
- [ ] Zephyr ELFs (4 targets) present
- [ ] RV64/RV32 mixed/RV32 simple non-dry manifests generated with RC=0
- [ ] smoke/syntax/integration tests all pass
