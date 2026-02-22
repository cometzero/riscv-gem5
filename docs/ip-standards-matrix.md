# Mailbox / HW Semaphore Standards Matrix

- Date: 2026-02-21
- Scope: gem5 + Zephyr + Linux 조합에서 표준 경로 우선 여부 결정
- Decision rule: **표준 경로가 end-to-end로 성립할 때만 채택**, 아니면 custom MMIO IP로 전환

## 1) Standards Support Matrix

| Layer | Mailbox Standard Path | HW Semaphore Standard Path | Current Assessment | Verification Gate |
|---|---|---|---|---|
| gem5 model | Generic mailbox IP 모델 직접 제공 여부 불명확 | Generic hwsem/hwspinlock IP 모델 직접 제공 여부 불명확 | **TBD (assume unavailable until proven)** | 대상 config에서 device model 존재/부팅 로그/IRQ 동작 확인 |
| Zephyr RTOS | Zephyr mailbox API + backend driver | 전용 hwsem 표준 subsystem은 제한적, custom driver 필요 가능성 높음 | **Mailbox: likely usable / HWSEM: custom likely** | DTS binding + driver probe + IPC/lock test pass |
| Linux kernel | Linux mailbox framework (controller/client) | Linux hwspinlock framework | **Framework available, HW dependent** | driver bind + userspace/selftest workload pass |

## 2) End-to-End Decision Matrix

| Case | Condition | Decision |
|---|---|---|
| A (Standard) | gem5 모델 + OS 드라이버 + 기능 테스트 모두 통과 | 표준 경로 채택 |
| B (Hybrid) | Linux/Zephyr framework는 있으나 gem5 모델 부재 | gem5 custom MMIO IP + OS framework adapter |
| C (Custom) | gem5 모델 부재 + OS 표준 연결도 불가 | custom MMIO IP + custom driver full path |

## 3) Fallback Trigger Criteria (Custom MMIO 진입 조건)

아래 중 하나라도 만족하면 custom MMIO IP로 전환한다.

1. gem5에서 mailbox/hwsem 대응 표준 모델을 재현 가능한 방식으로 선택할 수 없음
2. 표준 모델은 있으나 IRQ/data path 검증이 timeout 내 실패
3. Zephyr 또는 Linux에서 표준 드라이버 bind 실패/기능 실패
4. AMP IPC 또는 lock contention 테스트에서 안정성 기준 미달

## 4) Recommended Bootstrap Decision

현 시점 권장안:
- Mailbox: **Case B** 기준으로 시작 (gem5 custom MMIO + OS 표준 interface 최대 활용)
- HW Semaphore: **Case C** 기준으로 시작 (custom MMIO + 최소 드라이버)

이유:
- gem5 디바이스 모델 가용성이 가장 큰 불확실성
- bring-up 리스크를 줄이려면 모델 불확실성을 초기에 제거해야 함

## 5) Verification Artifacts (next phase)

- `build/logs/<target>/<ts>/mailbox_smoke.log`
- `build/logs/<target>/<ts>/hwsem_lock.log`
- `workloads/results/<ts>/ipc_summary.md`

