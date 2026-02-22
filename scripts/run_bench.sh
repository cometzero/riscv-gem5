#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="riscv64_smp"
MODE="simple"
TIMESTAMP=""
DRY_RUN=0
JOBS="$(nproc)"
IPC_CASE=""
DURATION_SEC="300"
ITERATIONS="10000"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_bench.sh [options]

Options:
  --target <riscv64_smp|riscv32_mixed>
  --mode <simple|complex>
  --timestamp <UTC-TS>          Reuse one timestamp for logs/results
  --jobs <n>
  --ipc-case <mailbox_pingpong|hwsem_contention>
  --duration-sec <n>
  --iterations <n>
  --dry-run
  -h, --help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --timestamp) TIMESTAMP="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --ipc-case) IPC_CASE="$2"; shift 2 ;;
    --duration-sec) DURATION_SEC="$2"; shift 2 ;;
    --iterations) ITERATIONS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

case "${TARGET}" in
  riscv64_smp|riscv32_mixed) ;;
  *) echo "[ERROR] Invalid target: ${TARGET}" >&2; exit 1 ;;
esac

case "${MODE}" in
  simple|complex) ;;
  *) echo "[ERROR] Invalid mode: ${MODE}" >&2; exit 1 ;;
esac

if [[ -z "${TIMESTAMP}" ]]; then
  TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
fi

RESULT_DIR="${REPO_ROOT}/workloads/results/${TIMESTAMP}"
LOG_DIR="$(omx_log_dir "${TARGET}" "${TIMESTAMP}")"
mkdir -p "${RESULT_DIR}"

MANIFEST_JSON="${RESULT_DIR}/bench_${TARGET}_${MODE}.json"
SUMMARY_MD="${RESULT_DIR}/summary_${TARGET}_${MODE}.md"

GEM5_ARGS=(
  --target "${TARGET}"
  --mode "${MODE}"
  --timestamp "${TIMESTAMP}"
)
if [[ "${DRY_RUN}" -eq 1 ]]; then
  GEM5_ARGS+=(--dry-run)
fi

echo "[INFO] target=${TARGET} mode=${MODE} dry_run=${DRY_RUN}"
echo "[INFO] result_dir=${RESULT_DIR}"
echo "[INFO] log_dir=${LOG_DIR}"

python3 "${SCRIPT_DIR}/run_gem5.py" "${GEM5_ARGS[@]}"

if [[ "${MODE}" == "simple" ]]; then
  WORKLOAD_DESC="smoke + memory micro-benchmark"
  BENCH_STEPS=(
    "boot-smoke"
    "memory-bandwidth"
  )
else
  WORKLOAD_DESC="stress + ipc/hwsem contention"
  BENCH_STEPS=(
    "cpu-stress"
    "ipc-${IPC_CASE:-mailbox_pingpong}"
    "hwsem-contention"
  )
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  STATUS="planned"
else
  STATUS="executed"
fi

cat > "${MANIFEST_JSON}" <<EOF2
{
  "timestamp": "${TIMESTAMP}",
  "target": "${TARGET}",
  "mode": "${MODE}",
  "dry_run": ${DRY_RUN},
  "status": "${STATUS}",
  "jobs": ${JOBS},
  "ipc_case": "${IPC_CASE}",
  "duration_sec": ${DURATION_SEC},
  "iterations": ${ITERATIONS},
  "result_dir": "${RESULT_DIR}",
  "log_dir": "${LOG_DIR}",
  "limits": [
    "Guest benchmark coverage depends on workload image capabilities and simulation timeout"
  ]
}
EOF2

{
  echo "# Benchmark Scaffold Summary"
  echo
  echo "- timestamp: ${TIMESTAMP}"
  echo "- target: ${TARGET}"
  echo "- mode: ${MODE}"
  echo "- dry-run: ${DRY_RUN}"
  echo "- workload: ${WORKLOAD_DESC}"
  echo "- result_dir: ${RESULT_DIR}"
  echo "- log_dir: ${LOG_DIR}"
  echo "- status: ${STATUS}"
  echo
  echo "## Steps"
  for s in "${BENCH_STEPS[@]}"; do
    echo "- ${s}"
  done
} > "${SUMMARY_MD}"

echo "[OK] Benchmark scaffold manifest: ${MANIFEST_JSON}"
echo "[OK] Benchmark scaffold summary: ${SUMMARY_MD}"
