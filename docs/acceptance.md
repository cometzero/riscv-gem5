# Acceptance Checklist (Scaffolding Phase)

- Date: 2026-02-21
- Scope: Tasks 11~14 산출물 검증 (dry-run 기반)
- Note: 외부 source tree가 미완성이라 runtime success claim은 제외

## 1) DoD Checklist

## 1.1 IP path (Task 11)
- [x] `conf/ip/mailbox_hwsem_map.yaml` 존재
- [x] `docs/ip-implementation-plan.md` 존재
- [x] IPC 절차 문서 2종 존재 (`workloads/ipc/*.md`)

## 1.2 Run/bench scripts (Task 12)
- [x] `scripts/run_gem5.py` 존재 (simple/complex + dry-run)
- [x] `scripts/run_bench.sh` 존재 (simple/complex + dry-run)
- [x] 출력 경로 계약 반영 (`workloads/results/<ts>`, `build/logs/<target>/<ts>`)

## 1.3 Tests (Task 13)
- [x] `tests/smoke/test_layout.sh`
- [x] `tests/smoke/test_scripts_syntax.sh`
- [x] `tests/integration/test_run_dry.sh`

## 1.4 Final handoff (Task 14)
- [x] `docs/final-handoff.md` 작성 및 증빙 반영

## 2) Verification Commands

```bash
bash tests/smoke/test_layout.sh
bash tests/smoke/test_scripts_syntax.sh
bash tests/integration/test_run_dry.sh
```

## 3) Pass Criteria

PASS if:
1. 상기 3개 검증 스크립트가 모두 exit code 0
2. dry-run 실행 후 expected manifest/summary 파일이 생성됨
3. 모든 claim/result가 team task 상태에 반영됨

## 4) Out-of-Scope (this phase)

- 실제 gem5 full-system boot 성공
- Linux/Zephyr runtime benchmark 성능 수치 확정
- mailbox/hwsem 실디바이스 드라이버 동작 검증

