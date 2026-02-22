# Mailbox Ping-Pong Test Procedure

- Date: 2026-02-21
- Type: procedure scaffold (runtime 미검증)

## 1) Goal
- AMP 경로에서 core 간 mailbox round-trip 기능 검증
- message loss / timeout / irq miss 여부 확인

## 2) Preconditions
- mailbox MMIO map 적용 완료 (`conf/ip/mailbox_hwsem_map.yaml`)
- AMP 대상 firmware/app image 준비
- run script 사용 가능 (`scripts/run_gem5.py`, `scripts/run_bench.sh`)

## 3) Test Steps
1. CPU0 sender / CPU1 receiver app 로드
2. CPU0 -> CPU1 ping message 전송
3. CPU1 -> CPU0 pong 응답
4. N회 반복 (기본 10,000회)
5. 성공률/지연/p99 측정

## 4) Suggested Command Skeleton

```bash
# dry-run only (현재 단계)
scripts/run_bench.sh --target riscv32_mixed --mode complex --dry-run
```

```bash
# execution phase target (예시)
scripts/run_bench.sh --target riscv32_mixed --mode complex \
  --ipc-case mailbox_pingpong --iterations 10000
```

## 5) Pass/Fail
PASS:
- success_rate >= 99.9%
- timeout_count == 0
- irq_miss_count == 0

FAIL:
- message loss > 0.1%
- deadlock/hang 발생
- 비정상 리셋 또는 panic

## 6) Artifacts
- `build/logs/riscv32_mixed/<ts>/ipc_mailbox.log`
- `workloads/results/<ts>/mailbox_pingpong.json`
- `workloads/results/<ts>/summary.md`
