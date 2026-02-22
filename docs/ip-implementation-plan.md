# Mailbox/HWSEM Implementation Plan (Standard-or-Custom)

- Date: 2026-02-21
- Scope: Task 11 scaffolding only (runtime integration 미실행)
- Input reference: `docs/ip-standards-matrix.md`

## 1) Decision

현재 단계 권장 결정:
- Mailbox: **Hybrid (Case B)**
  - OS framework/abstraction은 최대 활용
  - gem5 측 모델은 custom MMIO mailbox로 시작
- HW Semaphore: **Custom (Case C)**
  - custom MMIO hwsem + 최소 드라이버 경로로 시작

결정 근거:
1. gem5 표준 모델 가용성이 불확실
2. bring-up 리스크를 줄이려면 주소/IRQ/레지스터 스펙 먼저 고정 필요
3. RTOS/Linux 프레임워크와의 접점은 후속 단계에서 어댑터로 결합 가능

## 2) Current Artifacts

- MMIO spec: `conf/ip/mailbox_hwsem_map.yaml`
- Test procedures:
  - `workloads/ipc/mailbox_pingpong.md`
  - `workloads/ipc/hwsem_contention.md`

## 3) Integration Steps (Next execution phase)

## 3.1 gem5 side
1. mailbox/hwsem custom MMIO model 클래스 추가
2. `conf/riscv32_mixed.py` / `conf/riscv64_smp.py`에 MMIO + IRQ 라우팅 연결
3. UART/log와 동일한 방식으로 IP event trace 포인트 추가

## 3.2 Zephyr side
1. DTS overlay에 mailbox/hwsem 노드 추가 (`compatible`, `reg`, `interrupts`)
2. mailbox driver shim + OpenAMP transport 경로 연결
3. hwsem wrapper API를 AMP critical section에 적용

## 3.3 Linux side
1. mailbox controller/client 드라이버 스켈레톤 추가
2. hwsem용 hwspinlock adapter 구현
3. device tree binding 문서 및 probe 확인 로그 확보

## 4) Verification Gate (planned)

Gate-A (driver probe):
- Zephyr/Linux 모두 mailbox/hwsem 디바이스 probe 로그 확인

Gate-B (functionality):
- mailbox ping-pong 성공률 >= 99.9%
- hwsem contention test에서 lock 오류 0

Gate-C (stability):
- complex workload 300s 동안 deadlock/livelock 없음

## 5) TODO Limits (this phase)

이번 단계에서는 아래를 **수행하지 않음**:
- 실제 gem5 디바이스 모델 구현
- Linux/Zephyr 드라이버 빌드/부팅 검증
- IPC/hwsem 실측 성능 수집

즉, 본 문서는 **실행 가능한 설계/검증 절차 scaffold**이며, runtime success claim은 포함하지 않는다.
