# Plan/Design Review

- Date: 2026-02-21
- Reviewer mode: Architecture + Delivery feasibility
- Review scope: `docs/plan.md`, `docs/design.md`

## 1) Review Verdict

**Conditional Approve**

- 이유: 요구사항 커버리지는 높고 실행 순서가 명확함
- 조건: 아래 "필수 보완" 4개를 task에 반영해야 execution phase 진입 가능

## 2) Requirement Coverage Check

| Requirement | Coverage | Note |
|---|---|---|
| RV32 AMP/SMP mixed topology | PASS | cluster/core/cache 구조 반영 |
| RV64 SMP topology | PASS | 4-core SMP + cache 반영 |
| UART policy (AMP per-core, SMP shared) | PASS | 설계 반영 |
| Mailbox/HW Semaphore | PASS* | 표준 우선 + custom fallback 정의 |
| Zephyr non-west + cmake | PASS | 설계/스크립트 반영 |
| Buildroot initramfs (no kernel build) | PASS | 역할 분리 명시 |
| kernel shallow policy | PASS | depth/since 정책 명시 |
| scripts under `./scripts` | PASS | 스크립트 목록 반영 |
| source as submodule under `sources/` | PASS | 정책 명시 |
| workload simple/complex | PASS | validation plan 반영 |

## 3) 필수 보완 (Must-Fix Before Execution)

1. **Submodule revision policy 명확화**
   - "latest revision"은 재현성에 불리함
   - 방안: 초기 bootstrap 시점의 commit SHA lock + 주기적 update PR
   - ✅ Addressed (2026-02-21): `docs/submodule-policy.md`

2. **Mailbox/HW Semaphore 표준 여부 체크리스트 추가**
   - gem5/Zephyr/Linux 각각 "표준 지원 여부" 표를 만들고, 없을 때만 custom 진입
   - ✅ Addressed (2026-02-21): `docs/ip-standards-matrix.md`

3. **Zephyr module 최소 집합 정의**
   - west 미사용 시 module 과다 등록 리스크 큼
   - 방안: core + 필요한 driver module만 1차 등록
   - ✅ Addressed (2026-02-21): `docs/zephyr-module-set.md`

4. **성능 benchmark baseline 정의**
   - simple/complex workload pass 기준과 timeout 명시 필요
   - ✅ Addressed (2026-02-21): `docs/benchmark-baseline.md`

## 4) Nice-to-Have

- `tests/`에 smoke test를 CI-friendly 형태로 분리
- 로그 경로 규약 표준화: `build/logs/<target>/<ts>/`

## 5) Decision Log

- D1: 단계적 bring-up(RV64 -> RV32 mixed) 채택
- D2: UART는 표준 드라이버 우선
- D3: Mailbox/HW Semaphore는 표준 부재 시 custom MMIO IP
- D4: Zephyr는 `west` 미사용, `cmake` 직접 사용

## 6) Execution Gate (DoD for Planning Stage)

- [x] Plan 문서 작성
- [x] Design 문서 작성
- [x] Review 수행 및 verdict 기록
- [x] Must-Fix #1~#4 addressed (docs 완료)

