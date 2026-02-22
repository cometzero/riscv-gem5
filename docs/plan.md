# Gem5 RISC-V Simulation Plan

- Date: 2026-02-21
- Scope: `riscv-gem5` repository bootstrap + execution plan
- Goal: gem5에서 RISC-V 32bit AMP/SMP mixed + RISC-V 64bit SMP 시뮬레이션 환경을 재현 가능하게 구축

## 1) 결론 (권장 접근)

권장안은 **2단계 Bring-up + 공통 인프라 선구축**입니다.

1. 공통 인프라(디렉토리, submodule, build scripts, ccache, CI smoke test) 먼저 고정
2. `RV64 Linux SMP`를 먼저 bring-up (경로가 안정적)
3. `RV32 Zephyr AMP/SMP mixed`를 단계적으로 확장
4. Mailbox/HW Semaphore는 "표준 우선, 부재 시 custom IP" 순서로 적용

## 2) 접근 옵션 비교

| Option | 설명 | 장점 | 단점 |
|---|---|---|---|
| A | RV32/RV64 동시 개발 | 총 기간 단축 가능 | 디버깅 복잡도 급증 |
| B (Recommended) | RV64 SMP 선행 후 RV32 mixed 확장 | 리스크 분리, 검증 명확 | 초기 기능 체감이 늦음 |
| C | RV32 mixed 선행 | AMP 요구사항 조기 검증 | Zephyr + custom IP 동시 리스크 |

## 3) 단계별 실행 계획

### Phase 0 — Repository/Source Bootstrap
- 디렉토리 생성: `docs/ tests/ scripts/ sources/ conf/ workloads/`
- 모든 외부 소스는 `sources/`에 git submodule로 등록
- 커밋 정책: Conventional Commits + Atomic commits
- Linux kernel submodule은 shallow policy 적용 (`v5.15` 이후 히스토리 제한)

### Phase 1 — Toolchain/Build System
- gem5 build toolchain 확인
- `ccache` 강제 활성화 (`CCACHE_BASEDIR`, `CCACHE_DIR`, compiler launcher)
- Zephyr SDK 경로 고정 (`ZEPHYR_SDK_INSTALL_DIR`)
- Zephyr build는 `west` 미사용, `cmake` 직접 호출

### Phase 2 — Platform Modeling in gem5
- RV32 mixed config
  - Cluster0: CPU0/CPU1 AMP
  - Cluster1: CPU2/CPU3/CPU4/CPU5 SMP
  - Core별 L1 I/D, Cluster별 L2 Unified
- RV64 SMP config
  - Cluster0: CPU0/CPU1/CPU2/CPU3 SMP
  - Core별 L1 I/D, Cluster별 L2 Unified
- UART 정책
  - AMP: core별 UART
  - SMP: cluster별 1 UART
- Mailbox/HW Semaphore
  - 표준 IP 확인 후 적용
  - 부재 시 custom MMIO IP + 드라이버

### Phase 3 — Software Integration
- RV32: Zephyr RTOS
  - Cluster0 AMP(코어별 image 또는 overlay 분리)
  - Cluster1 SMP(single image)
  - Device Tree Overlay 별도 관리
- RV64: Linux kernel + Buildroot initramfs
  - Buildroot: rootfs 전용 (kernel build 비활성)
  - Linux kernel: 별도 소스/빌드 파이프라인

### Phase 4 — Workloads
- Simple: boot smoke + basic memory bandwidth/latency
- Complex: stress test + IPC(mailbox/semaphore) contention
- 결과 저장: `workloads/results/<timestamp>/`

### Phase 5 — Validation & Review Gate
- 기능 검증 + 성능 sanity + 로그 수집 자동화
- 실패 시 원인 분류(구성/빌드/런타임/IP 드라이버)

## 4) 산출물(DoD)

- [ ] `conf/`에 RV32 mixed, RV64 SMP gem5 config 존재
- [ ] `scripts/`에 bootstrap/build/run/benchmark 자동화 스크립트 존재
- [ ] `sources/` submodule 재현 가능 (`git submodule sync/update --init --recursive`)
- [ ] RV32 Zephyr AMP/SMP boot 로그 확보
- [ ] RV64 Linux SMP boot + initramfs 진입 로그 확보
- [ ] Mailbox/HW Semaphore 테스트 workload pass
- [ ] 간단/복잡 workload 결과 리포트 생성

## 5) 리스크 및 대응

1. Zephyr non-west 구성 복잡성
   - 대응: 필요 module 최소 집합을 lockfile화, `scripts/bootstrap_sources.py`로 고정
2. gem5에 표준 mailbox/hwsem 모델 부재 가능성
   - 대응: custom MMIO IP 사양 먼저 확정 후 드라이버 병행 개발
3. Linux kernel clone/size 이슈
   - 대응: shallow submodule + 필요 브랜치만 fetch
