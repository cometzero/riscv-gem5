# riscv-gem5

Reproducible gem5-based RISC-V simulation workspace for:

- **riscv32_mixed**: one gem5 instance, AMP+SMP mixed Zephyr topology
  - Cluster0: CPU0/CPU1 (AMP)
  - Cluster1: CPU2/CPU3/CPU4/CPU5 (SMP)
- **riscv32_simple**: single-core Zephyr smoke target (CPU0)
- **riscv64_smp**: Linux full-system SMP target
- **riscv_hybrid**: one gem5 process running `riscv32_mixed` + `riscv64`

The repository is structured for deterministic bring-up:
- pinned submodules (`conf/submodules.lock.json`)
- build/log artifacts under `build/` and `workloads/results/`
- automation scripts for build, run, benchmark, and web dashboard

---

## Repository Layout

```text
docs/          design, plan, review, execution guides
tests/         smoke and integration checks
scripts/       bootstrap/build/run/dashboard automation
sources/       external sources via git submodules
conf/          gem5 + workload configuration
workloads/     workload sources and result manifests
build/         local build and log outputs
```

---

## Prerequisites

- Ubuntu 22.04+ (recommended)
- `git`, `python3`, `cmake`, `ninja`, `ccache`, `scons`
- RISC-V cross toolchain
- Zephyr SDK (for no-west Zephyr build)

Quick environment check:

```bash
cd /build/risc-v/riscv-gem5
scripts/env.sh print
```

---

## Quick Start

### 1) Bootstrap pinned sources

```bash
cd /build/risc-v/riscv-gem5
scripts/bootstrap_sources.sh plan
scripts/bootstrap_sources.sh verify-lock
scripts/bootstrap_sources.sh apply
git submodule status --recursive
```

### 2) Build toolchain outputs

```bash
cd /build/risc-v/riscv-gem5
scripts/build_linux_buildroot.sh --jobs "$(nproc)"
scripts/build_zephyr.sh --target cluster0_amp_cpu0 --jobs "$(nproc)"
scripts/build_zephyr.sh --target cluster0_amp_cpu1 --jobs "$(nproc)"
scripts/build_zephyr.sh --target cluster1_smp --jobs "$(nproc)"
scripts/build_zephyr.sh --target riscv32_simple --jobs "$(nproc)"
```

Build gem5 if needed:

```bash
cd /build/risc-v/riscv-gem5
source scripts/env.sh
scons -C sources/gem5 build/RISCV/gem5.opt -j"$(nproc)"
```

### 3) Run simulations

Use `run_gem5.py` for direct runs:

```bash
cd /build/risc-v/riscv-gem5
./scripts/run_gem5.py --target riscv64_smp --mode simple
./scripts/run_gem5.py --target riscv32_mixed --mode complex
./scripts/run_gem5.py --target riscv32_simple --mode simple
./scripts/run_gem5.py --target riscv_hybrid --mode simple
# keep hybrid running until timeout (disable marker early-stop)
./scripts/run_gem5.py --target riscv_hybrid --mode simple --timeout-sec 300 --no-stop-on-marker
```

Use benchmark wrapper:

```bash
cd /build/risc-v/riscv-gem5
scripts/run_bench.sh --target riscv64_smp --mode simple
scripts/run_bench.sh --target riscv32_mixed --mode complex --ipc-case mailbox_pingpong
scripts/run_bench.sh --target riscv32_simple --mode simple
```

### 4) Verify RV64 initramfs shell boot

`riscv64_smp --mode simple` is tuned for initramfs shell visibility.

```bash
cd /build/risc-v/riscv-gem5
TS=$(ls -1t workloads/results | head -n1)
MANIFEST="workloads/results/${TS}/run_gem5_riscv64_smp_simple.json"
LOGDIR=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1], encoding="utf-8"))["logs_dir"])' "${MANIFEST}")

rg -n "Run /init as init process|INITRAMFS_SHELL_READY|initramfs#|OpenSBI|Linux version" \
  "${LOGDIR}/system.platform.terminal"
```

---

## Web Dashboard (Headless Server)

Run:

```bash
cd /build/risc-v/riscv-gem5
scripts/run_web_dashboard.sh
```

Access:
- `http://<server-ip>:8080`

Supports:
- target/workload selection
- progress tracking
- interpreted result view + charts
- filtered logs
- config SVG auto-display with zoom controls

---

## Result/Log Paths

- Result manifests: `workloads/results/<timestamp>/run_gem5_*.json`
- Logs: `build/logs/<target>/<timestamp>/`
- Quick links:
  - `workloads/results/latest*`
  - `build/logs/riscv64_smp/latest*`
  - `build/logs/riscv32_mixed/latest*`
  - `build/logs/riscv32_simple/latest*`

---

## Remote Policy (origin + upstream)

Recommended policy:
- top repository: `origin = your GitHub repo`
- each submodule:
  - `origin = your fork/mirror repo`
  - `upstream = original open-source repo`

Current submodule URLs tracked by `.gitmodules`:
- `sources/gem5`
- `sources/linux`
- `sources/buildroot`
- `sources/zephyr`
- `sources/zephyr-modules/libmetal`
- `sources/zephyr-modules/open-amp`

---

## Docs Index

- `docs/execution-guide.md`: end-to-end execution flow
- `docs/design.md`: architecture and target design
- `docs/review.md`: design/plan review notes
- `docs/web-dashboard.md`: dashboard API/usage
- `docs/submodule-policy.md`: pin/update policy
