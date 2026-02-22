#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

HOST="${GEM5_DASHBOARD_HOST:-0.0.0.0}"
PORT="${GEM5_DASHBOARD_PORT:-8080}"

cd "${REPO_ROOT}"

echo "[INFO] Starting gem5 web dashboard"
echo "[INFO] URL: http://${HOST}:${PORT}"
python3 scripts/web_dashboard.py --host "${HOST}" --port "${PORT}"
