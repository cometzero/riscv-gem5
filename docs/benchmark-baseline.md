# Benchmark Baseline and Pass Criteria

- Date: 2026-02-21
- Scope: gem5 RISC-V bootstrap 단계의 simple/complex workload 검증 기준
- Principle: 기능 통과(boot/IPC 안정성)와 성능 회귀(상대 비교)를 분리 평가

## 1) Workload Definition

## 1.1 Simple Workload (Smoke + Memory)
- 대상
  - RV64 SMP Linux boot smoke
  - RV32 mixed Zephyr boot smoke
- 작업
  - boot 완료 후 memory micro benchmark 1회 실행
- 목적
  - 초기 bring-up에서 최소 기능 + 기본 성능 sanity 확인

## 1.2 Complex Workload (Stress + IPC)
- 대상
  - RV64 SMP: CPU/memory stress
  - RV32 mixed: mailbox IPC + hwsem contention
- 작업
  - stress workload와 IPC/lock test를 일정 시간 연속 수행
- 목적
  - deadlock/livelock/IRQ loss/성능 급락 여부 탐지

## 2) Timeout and Hard-Fail Criteria

| Stage | Timeout | Hard-Fail Condition |
|---|---:|---|
| OpenSBI banner | 60s | timeout or crash |
| U-Boot prompt | 120s | timeout or reset loop |
| Linux userspace ready (RV64) | 240s | kernel panic/hang |
| Zephyr app ready (RV32) | 120s | boot fail/hang |
| Simple benchmark run | 120s | non-zero exit or timeout |
| Complex workload run | 300s | deadlock, panic, watchdog reset |

## 3) Baseline Metrics

## 3.1 Functional Metrics (must pass)
- Boot milestone pass rate = 100%
- IPC message success rate >= 99.9%
- HW semaphore lock/unlock correctness = 100% (error count 0)

## 3.2 Performance Metrics (regression gate)
- 지표
  - boot_time_sec
  - mem_bw_mb_s
  - ipc_roundtrip_us (p50, p99)
  - lock_contention_ops_s
- Baseline source
  - 첫 "golden run" 결과를 baseline으로 고정
- 허용 회귀 임계값
  - boot_time_sec: +15% 이내
  - mem_bw_mb_s: -15% 이내
  - ipc_roundtrip_us(p99): +20% 이내
  - lock_contention_ops_s: -20% 이내

## 4) Pass / Fail Decision Rules

## 4.1 Simple Workload
PASS 조건:
1. 모든 boot milestone timeout 내 통과
2. memory benchmark 정상 종료(exit code 0)
3. 핵심 지표가 baseline 대비 임계값 내

FAIL 조건:
- milestone 실패, benchmark timeout, panic/hang, 회귀 임계 초과

## 4.2 Complex Workload
PASS 조건:
1. 300초 연속 실행 중 crash/deadlock 없음
2. IPC success rate >= 99.9%
3. hwsem correctness 100%
4. 성능 지표가 임계값 내

FAIL 조건:
- deadlock/livelock, message loss 초과, lock 오류, 임계값 초과

## 5) Artifact Contract

- 로그/결과 경로
  - `build/logs/<target>/<timestamp>/console.log`
  - `build/logs/<target>/<timestamp>/benchmark.log`
  - `workloads/results/<timestamp>/summary.md`
  - `workloads/results/<timestamp>/metrics.json`
- `metrics.json` 최소 키
  - `boot_time_sec`
  - `mem_bw_mb_s`
  - `ipc_roundtrip_us_p50`
  - `ipc_roundtrip_us_p99`
  - `lock_contention_ops_s`
  - `pass`

## 6) Re-Baselining Rule

아래 중 하나라도 만족하면 baseline 재설정 검토:
1. submodule major update 또는 toolchain 변경
2. gem5 config topology 변경
3. workload 시나리오 변경

재설정 시 기존 baseline은 archive하고, 변경 사유를 리뷰 문서/PR 본문에 기록한다.

