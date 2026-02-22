# Unified Build Environment (ccache + logs)

- Date: 2026-02-21
- Scope: gem5 / Zephyr(no-west) / Linux / Buildroot 공통 빌드 환경
- Script: `scripts/env.sh`

## 1) 결론

모든 빌드 진입점에서 아래 1줄을 먼저 실행한다.

```bash
source scripts/env.sh
```

이 스크립트는 다음을 강제한다.
- 공통 ccache 설정 (`CCACHE_DIR`, `CCACHE_BASEDIR`, `CC`, `CXX`)
- Zephyr no-west 기본 환경 (`ZEPHYR_BASE`, `ZEPHYR_SDK_INSTALL_DIR`)
- 로그 경로 규약 `build/logs/<target>/<timestamp>`

## 2) ccache Contract

기본값:
- `CCACHE_DIR=build/.ccache`
- `CCACHE_BASEDIR=<repo-root>`
- `CCACHE_MAXSIZE=20G`
- `CC="ccache gcc"`, `CXX="ccache g++"`

override 예시:

```bash
export OMX_CCACHE_C_COMPILER=clang
export OMX_CCACHE_CXX_COMPILER=clang++
source scripts/env.sh
```

## 3) Log Path Convention

```bash
source scripts/env.sh
log_dir=$(omx_log_dir riscv64_smp)
echo "$log_dir"
# -> build/logs/riscv64_smp/<timestamp>
```

- target 예시: `riscv64_smp`, `riscv32_mixed`, `linux`, `buildroot`, `zephyr`
- timestamp 형식: UTC `YYYYmmddTHHMMSSZ`

## 4) Build Command Examples

## 4.1 gem5

```bash
source scripts/env.sh
log_dir=$(omx_log_dir gem5)
scons -C sources/gem5 build/RISCV/gem5.opt -j"$(nproc)" 2>&1 | tee "$log_dir/gem5-build.log"
```

## 4.2 Zephyr (no-west)

```bash
source scripts/env.sh
log_dir=$(omx_log_dir zephyr)
cmake -S <app_dir> -B build/zephyr/<target> \
  -DZEPHYR_BASE="$ZEPHYR_BASE" \
  -DZEPHYR_TOOLCHAIN_VARIANT="$ZEPHYR_TOOLCHAIN_VARIANT" \
  -DZEPHYR_SDK_INSTALL_DIR="$ZEPHYR_SDK_INSTALL_DIR" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
cmake --build build/zephyr/<target> -j"$(nproc)" 2>&1 | tee "$log_dir/zephyr-build.log"
```

## 4.3 Linux kernel

```bash
source scripts/env.sh
log_dir=$(omx_log_dir linux)
make -C sources/linux O=build/linux ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- \
  CC="$CC" HOSTCC="$CC" -j"$(nproc)" 2>&1 | tee "$log_dir/linux-build.log"
```

## 4.4 Buildroot

```bash
source scripts/env.sh
log_dir=$(omx_log_dir buildroot)
make -C sources/buildroot O=build/buildroot BR2_CCACHE=y BR2_CCACHE_DIR="$CCACHE_DIR" \
  -j"$(nproc)" 2>&1 | tee "$log_dir/buildroot-build.log"
```

## 5) Quick Verification

```bash
scripts/env.sh print
scripts/env.sh mklog riscv64_smp
```

기대 결과:
- 환경 변수 출력에 ccache/zephyr/build/log root 포함
- `build/logs/riscv64_smp/<timestamp>/` 디렉토리 생성

