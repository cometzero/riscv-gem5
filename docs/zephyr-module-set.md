# Minimal Zephyr Module Set (No-West)

- Date: 2026-02-21
- Scope: gem5 RISC-V bootstrap에서 `west` 없이 Zephyr를 재현 가능하게 빌드하기 위한 최소 모듈 집합
- Policy: 필요한 모듈만 명시적으로 pin (SHA lock)

## 1) 결론 (Recommended Minimal Set)

### Mandatory (Phase-1 bring-up)

| Module | Path (under `sources/`) | Why required |
|---|---|---|
| zephyr | `sources/zephyr` | RTOS core + build system |
| libmetal | `sources/zephyr-modules/libmetal` | OpenAMP 기반 IPC/transport 의존 |
| open-amp | `sources/zephyr-modules/open-amp` | AMP IPC 경로(메일박스/vring) 후보 |

### Optional (enable only if feature needed)

| Module | Path | Enable condition |
|---|---|---|
| mbedtls | `sources/zephyr-modules/mbedtls` | TLS/crypto 요구 시 |
| littlefs | `sources/zephyr-modules/littlefs` | 파일시스템 persistence 요구 시 |

> 원칙: optional 모듈은 기능 요구가 명시될 때만 추가하고, 추가 즉시 lockfile/문서를 갱신한다.

## 2) No-West Build Contract

`west update`를 사용하지 않고 CMake에 module 경로를 명시한다.

```bash
export ZEPHYR_BASE=$PWD/sources/zephyr
export ZEPHYR_MODULES="$PWD/sources/zephyr-modules/libmetal;$PWD/sources/zephyr-modules/open-amp"

cmake -S <app_dir> -B build/zephyr/<target> \
  -DZEPHYR_BASE="$ZEPHYR_BASE" \
  -DZEPHYR_MODULES="$ZEPHYR_MODULES" \
  -DZEPHYR_TOOLCHAIN_VARIANT=zephyr
cmake --build build/zephyr/<target> -j
```

## 3) Lock Strategy

- module 버전은 branch가 아닌 commit SHA로 lock
- lock 소스
  1. Git submodule gitlink SHA
  2. `conf/zephyr-modules.lock.json` (향후 생성)
- update는 `chore(submodule)` 커밋으로만 반영

## 4) Add/Remove Governance

모듈 추가 허용 조건:
1. 기능 요구가 plan/review 문서에 존재
2. 빌드 또는 런타임에서 모듈 의존 실패가 재현됨
3. 추가 후 smoke test + 영향 범위 기록

모듈 제거 허용 조건:
1. 2회 이상 release cycle 미사용
2. 대체 경로 확인
3. 제거 후 전 타겟 빌드 smoke pass

## 5) Verification Gate

- `ZEPHYR_MODULES` 문자열이 lock 목록과 일치
- RV32 target smoke build pass
- AMP IPC workload에서 OpenAMP 경로 최소 1회 성공

