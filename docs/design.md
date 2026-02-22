# Gem5 RISC-V Simulation Design

- Date: 2026-02-21
- Version: v0.1 (Draft for review)

## 1) Goal + Constraints

### Goal
- gem5 기반으로 아래 2개 타겟을 재현 가능한 방식으로 구축
  1. RV32 AMP/SMP Mixed (6 cores, 2 clusters)
  2. RV64 SMP (4 cores, 1 cluster)

### Constraints
- 소스는 `sources/`에 submodule로 관리
- Linux kernel은 `v5.15` 이후 shallow history 정책
- Zephyr는 `west` 없이 `cmake` + Zephyr SDK 사용
- 빌드 캐시는 `ccache` 필수

## 2) High-Level Architecture

## 2.1 Repository Layout

```text
/build/risc-v/riscv-gem5/
  docs/
  tests/
  scripts/
  sources/
  conf/
  workloads/
```

## 2.2 Runtime Targets

### Target-A: RV32 Mixed
- Cluster0 (AMP): CPU0, CPU1
- Cluster1 (SMP): CPU2, CPU3, CPU4, CPU5
- Cache:
  - per core: `L1I + L1D`
  - per cluster: `L2 unified`

### Target-B: RV64 SMP
- Cluster0: CPU0, CPU1, CPU2, CPU3 (SMP)
- Cache:
  - per core: `L1I + L1D`
  - per cluster: `L2 unified`

## 3) IP Design

## 3.1 UART
- 기본: 표준 UART(16550 계열) 우선 사용
- 연결 규칙
  - AMP: core별 UART console endpoint
  - SMP: cluster당 1 UART shared console

## 3.2 Mailbox (AMP IPC)
- 1차: gem5/OS 표준 mailbox primitive 탐색
- 2차(부재 시): custom MMIO mailbox IP
  - register set (예): `TX_DATA`, `RX_DATA`, `STATUS`, `IRQ_EN`, `IRQ_STATUS`
  - interrupt 기반 notify
- 드라이버
  - Zephyr용 mailbox driver + DTS binding
  - Linux 필요 시 mailbox controller/client driver

## 3.3 HW Semaphore (Spinlock)
- 1차: 표준 hwspinlock 모델 지원 여부 확인
- 2차: custom MMIO hwsem IP
  - register set (예): `LOCK[n]`, `OWNER[n]`, `STATUS`
  - test-and-set semantics 보장
- 드라이버
  - Zephyr AMP core 동기화 우선
  - Linux는 필요 시 hwspinlock framework 연계

## 4) Software Build Design

## 4.1 Sources/Submodule Policy
- Example candidate repos (latest revision tracking):
  - `sources/gem5`
  - `sources/linux`
  - `sources/buildroot`
  - `sources/zephyr`
  - `sources/zephyr-modules/*` (west manifest를 submodule로 변환)
- kernel shallow 정책
  - `git submodule add --depth 1 ... sources/linux`
  - 필요 시 `--shallow-since=<v5.15-release-date>` 적용 검토

## 4.2 Zephyr (No west)
- Zephyr SDK 설치 전제
- `ZEPHYR_BASE`, `ZEPHYR_SDK_INSTALL_DIR`를 script에서 명시
- build command template:

```bash
cmake -S sources/zephyr -B build/zephyr/<target> \
  -DBOARD=<board> \
  -DDTC_OVERLAY_FILE=<overlay>.overlay \
  -DZEPHYR_TOOLCHAIN_VARIANT=zephyr
cmake --build build/zephyr/<target> -j
```

## 4.3 Linux + Buildroot
- Linux kernel: `sources/linux`에서 별도 빌드
- Buildroot: kernel build disable, initramfs/rootfs 전용
- kernel + initramfs 조합을 gem5 workload로 전달

## 5) Gem5 Config Design (conf/)

- `conf/riscv32_mixed.py`
  - cluster topology + per-core/per-cluster cache
  - AMP UART split + SMP UART merge
  - mailbox/hwsem MMIO map
- `conf/riscv64_smp.py`
  - 4-core SMP topology + cache
  - shared UART

## 6) Script Design (scripts/)

- `scripts/bootstrap_sources.sh`:
  - submodule init/sync/update
  - shallow policy enforcement
- `scripts/build_all.sh`:
  - gem5, zephyr, linux, buildroot 빌드 orchestration
  - ccache export
- `scripts/run_gem5.py`:
  - target 선택(`riscv32_mixed` / `riscv64_smp`)
  - workload 선택(simple/complex)
- `scripts/run_bench.sh`:
  - memory benchmark + stress test 실행

## 7) Verification Design

- Boot checks
  - RV32 AMP: CPU0/CPU1 개별 로그 확인
  - RV32 SMP: CPU2~CPU5 online 확인
  - RV64 SMP: Linux 4 cores online 확인
- IP checks
  - mailbox send/recv roundtrip
  - hw semaphore lock/unlock contention
- Performance checks
  - baseline 대비 회귀율(%) 기록

## 8) Open Items (Review Required)

1. RV32 Linux 불필요 가정 유지 여부 (현재 요구상 Zephyr only)
2. Mailbox/HW Semaphore를 양 OS 모두 지원할지, Zephyr 우선 지원할지
3. zephyr module subset을 어디까지 포함할지 (최소/확장)
