# Submodule Revision Policy

- Date: 2026-02-21
- Scope: `sources/` 하위 외부 의존 소스(gem5, linux, buildroot, zephyr, zephyr modules)
- Goal: "latest" 추적 요구와 재현성 요구를 동시에 만족

## 1) 정책 결론

`latest`는 직접 참조하지 않고 **항상 commit SHA로 lock**한다.

- 저장소의 진실 원천(Source of Truth)
  1. Git submodule gitlink SHA (필수)
  2. `conf/submodules.lock.json` (메타데이터 + bootstrap 입력)
- 모든 빌드/실행은 lock된 SHA 기준으로만 수행한다.

## 2) Revision Lock Rules

1. 각 submodule은 branch name이 아니라 **고정 SHA**를 사용한다.
2. 업데이트는 PR에서만 수행하며, 본문에 변경 이유/리스크를 남긴다.
3. 한 PR에서 여러 submodule 동시 갱신은 가능하지만, commit은 구성요소별로 분리한다.
4. Linux kernel은 shallow 정책을 유지한다(`--depth 1`, v5.15+ history policy note).

## 3) Update Cadence

- 정기 업데이트: 2주 주기(격주)
- 긴급 업데이트: 보안/빌드 실패/치명 버그 발생 시 즉시
- 릴리스 직전: code freeze 이후 submodule 업데이트 금지(예외는 승인 필요)

## 4) Bootstrap Workflow (Scripted)

### 4.1 Lock 초기화 (network metadata only, no clone)

```bash
scripts/bootstrap_sources.sh init-lock
scripts/bootstrap_sources.sh verify-lock
```

- `init-lock`: `git ls-remote`로 `tracking_ref`를 SHA로 고정
- `verify-lock`: lock file의 SHA pin 상태 검증

### 4.2 Submodule bootstrap (shallow only)

```bash
scripts/bootstrap_sources.sh apply
```

- 동작
  - `sources/` 하위 submodule shallow 추가/동기화
  - lock된 SHA checkout
  - Linux shallow 정책 강제 확인
- 비동작
  - full history clone 금지

## 5) Zephyr No-West Structure

`conf/submodules.lock.json`의 `zephyr_no_west_placeholders`를 기준으로 아래 구조를 유지한다.

```text
sources/
  zephyr/
  zephyr-modules/
    libmetal/
    open-amp/
    # optional placeholders
    mbedtls/
    littlefs/
```

## 6) Commit / PR Convention

- Commit type: `chore(submodule)`
- Commit message 예시
  - `chore(submodule): bump gem5 to 1a2b3c4`
  - `chore(submodule): bootstrap pinned sources`
- PR 본문 필수 항목
  - 왜 업데이트했는지 (보안/기능/빌드복구)
  - 영향 범위 (RV32/RV64, AMP/SMP)
  - 검증 결과 (boot/smoke)
  - 롤백 SHA

## 7) Verification Gate

업데이트 PR merge 전 최소 검증:
1. `scripts/bootstrap_sources.sh verify-lock` 통과
2. `git submodule status --recursive` 결과가 lock SHA와 일치
3. smoke boot 로그 확보(RV64 우선)
4. 실패 시 lock SHA로 즉시 rollback 가능

## 8) Rollback

- 기본 rollback: 이전 gitlink SHA로 되돌리는 revert commit
- 원칙: 재수정(push -f) 금지, 명시적 revert commit 사용

