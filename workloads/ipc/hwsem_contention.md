# HWSEM Contention Test Procedure

- Date: 2026-02-21
- Type: procedure scaffold (runtime 미검증)

## 1) Goal
- 다중 코어 경쟁 상황에서 hw semaphore lock/unlock 정합성 검증
- starvation/deadlock 여부 확인

## 2) Preconditions
- hwsem MMIO spec 반영 (`conf/ip/mailbox_hwsem_map.yaml`)
- contention test app 준비 (AMP/SMP 혼합)
- benchmark runner 준비 (`scripts/run_bench.sh`)

## 3) Test Steps
1. 경쟁 코어 수 설정 (예: 6 cores)
2. 공유 자원 접근 루프 수행
3. lock 획득/해제 카운트 수집
4. owner mismatch / double unlock / stuck lock 확인
5. 300초 이상 연속 실행

## 4) Suggested Command Skeleton

```bash
# dry-run only (현재 단계)
scripts/run_bench.sh --target riscv32_mixed --mode complex --dry-run
```

```bash
# execution phase target (예시)
scripts/run_bench.sh --target riscv32_mixed --mode complex \
  --ipc-case hwsem_contention --duration-sec 300
```

## 5) Pass/Fail
PASS:
- lock_error_count == 0
- owner_mismatch_count == 0
- deadlock_count == 0
- throughput 회귀가 baseline 임계 내

FAIL:
- lock correctness 위반 발생
- deadlock/livelock 발생
- watchdog reset/panic 발생

## 6) Artifacts
- `build/logs/riscv32_mixed/<ts>/ipc_hwsem.log`
- `workloads/results/<ts>/hwsem_contention.json`
- `workloads/results/<ts>/summary.md`
