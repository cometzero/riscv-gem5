#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
LOCK_FILE="${REPO_ROOT}/conf/submodules.lock.json"

usage() {
  cat <<'USAGE'
Usage:
  scripts/bootstrap_sources.sh plan
  scripts/bootstrap_sources.sh init-lock
  scripts/bootstrap_sources.sh verify-lock
  scripts/bootstrap_sources.sh apply

Commands:
  plan         Show module list and pin status from lock file.
  init-lock    Resolve tracking_ref with git ls-remote and write pinned SHA.
  verify-lock  Validate every module revision is a pinned 40-hex SHA.
  apply        Add/sync/update submodules from locked revisions (shallow only).
USAGE
}

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "[ERROR] Missing file: ${path}" >&2
    exit 1
  fi
}

is_valid_sha() {
  local sha="$1"
  [[ "${sha}" =~ ^[0-9a-f]{40}$ ]] && [[ "${sha}" != "0000000000000000000000000000000000000000" ]]
}

print_modules_tsv() {
  python3 - "${LOCK_FILE}" <<'PY'
import json, sys
lock = json.load(open(sys.argv[1], encoding='utf-8'))
for m in lock.get('modules', []):
    print('\t'.join([
        m.get('name', ''),
        m.get('path', ''),
        m.get('url', ''),
        m.get('tracking_ref', ''),
        m.get('revision', ''),
    ]))
PY
}

cmd_plan() {
  require_file "${LOCK_FILE}"
  echo "[INFO] Lock file: ${LOCK_FILE}"
  echo "[INFO] Module pin status"
  printf '%-26s %-38s %-12s\n' "MODULE" "REVISION" "PINNED"
  printf '%-26s %-38s %-12s\n' "------" "--------" "------"

  local name path url tracking_ref revision
  while IFS=$'\t' read -r name path url tracking_ref revision; do
    local pinned="no"
    if is_valid_sha "${revision}"; then
      pinned="yes"
    fi
    printf '%-26s %-38s %-12s\n' "${name}" "${revision}" "${pinned}"
  done < <(print_modules_tsv)
}

cmd_verify_lock() {
  require_file "${LOCK_FILE}"
  local failed=0
  local name path url tracking_ref revision
  while IFS=$'\t' read -r name path url tracking_ref revision; do
    if ! is_valid_sha "${revision}"; then
      echo "[ERROR] ${name}: revision is not pinned SHA (${revision})" >&2
      failed=1
    fi
  done < <(print_modules_tsv)

  if [[ "${failed}" -ne 0 ]]; then
    echo "[ERROR] Lock verification failed. Run: scripts/bootstrap_sources.sh init-lock" >&2
    exit 1
  fi

  echo "[OK] Lock verification passed."
}

cmd_init_lock() {
  require_file "${LOCK_FILE}"
  python3 - "${LOCK_FILE}" <<'PY'
import datetime as dt
import json
import subprocess
import sys

lock_path = sys.argv[1]
with open(lock_path, encoding='utf-8') as f:
    lock = json.load(f)

for module in lock.get('modules', []):
    name = module['name']
    url = module['url']
    ref = module.get('tracking_ref', '')
    if not ref:
        raise SystemExit(f"[ERROR] {name}: tracking_ref is required for init-lock")
    out = subprocess.check_output(['git', 'ls-remote', url, ref], text=True).strip().splitlines()
    if not out:
        raise SystemExit(f"[ERROR] {name}: cannot resolve {ref} from {url}")
    sha = out[0].split()[0]
    if len(sha) != 40:
        raise SystemExit(f"[ERROR] {name}: invalid sha resolved ({sha})")
    module['revision'] = sha
    print(f"[OK] {name}: {sha}")

lock['generated_at_utc'] = dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
with open(lock_path, 'w', encoding='utf-8') as f:
    json.dump(lock, f, ensure_ascii=False, indent=2)
    f.write('\n')

print(f"[OK] Updated lock file: {lock_path}")
PY
}

submodule_exists() {
  local path="$1"
  git -C "${REPO_ROOT}" config -f .gitmodules --get-regexp '^submodule\..*\.path$' 2>/dev/null \
    | awk '{print $2}' \
    | grep -Fxq "${path}"
}

apply_module() {
  local name="$1"
  local path="$2"
  local url="$3"
  local revision="$4"

  if [[ -z "${path}" || -z "${url}" ]]; then
    echo "[ERROR] Invalid module entry: name=${name} path=${path} url=${url}" >&2
    exit 1
  fi

  mkdir -p "${REPO_ROOT}/$(dirname -- "${path}")"

  if submodule_exists "${path}"; then
    echo "[INFO] Sync/update existing submodule: ${name} (${path})"
    git -C "${REPO_ROOT}" submodule sync -- "${path}"
    git -C "${REPO_ROOT}" submodule update --init --depth 1 "${path}"
  else
    if [[ -e "${REPO_ROOT}/${path}" && ! -L "${REPO_ROOT}/${path}" && -n "$(ls -A "${REPO_ROOT}/${path}" 2>/dev/null || true)" ]]; then
      echo "[ERROR] ${path} exists and is not an empty submodule path" >&2
      exit 1
    fi
    echo "[INFO] Add shallow submodule: ${name} (${path})"
    git -C "${REPO_ROOT}" submodule add --force --depth 1 "${url}" "${path}"
  fi

  echo "[INFO] Checkout pinned revision: ${name} -> ${revision}"
  git -C "${REPO_ROOT}/${path}" fetch --depth 1 origin "${revision}"
  git -C "${REPO_ROOT}/${path}" checkout --detach "${revision}"

  if [[ "${name}" == "linux" ]]; then
    local shallow
    shallow="$(git -C "${REPO_ROOT}/${path}" rev-parse --is-shallow-repository)"
    if [[ "${shallow}" != "true" ]]; then
      echo "[ERROR] Linux submodule must remain shallow." >&2
      exit 1
    fi
    echo "[INFO] Linux shallow policy enforced (--depth 1; v5.15+ compatible history note)."
  fi
}

cmd_apply() {
  require_file "${LOCK_FILE}"
  cmd_verify_lock

  mkdir -p "${REPO_ROOT}/sources"
  mkdir -p "${REPO_ROOT}/sources/zephyr-modules"

  echo "[INFO] Sync all known submodules first"
  git -C "${REPO_ROOT}" submodule sync --recursive || true

  local name path url tracking_ref revision
  while IFS=$'\t' read -r name path url tracking_ref revision; do
    apply_module "${name}" "${path}" "${url}" "${revision}"
  done < <(print_modules_tsv)

  echo "[INFO] Final submodule status"
  git -C "${REPO_ROOT}" submodule status --recursive

  cat <<'NEXT'
[OK] Bootstrap apply finished.
Next:
  1) git add .gitmodules sources conf/submodules.lock.json
  2) git commit -m "chore(submodule): bootstrap pinned sources"
NEXT
}

main() {
  local cmd="${1:-plan}"
  case "${cmd}" in
    -h|--help|help)
      usage
      ;;
    plan)
      cmd_plan
      ;;
    init-lock)
      cmd_init_lock
      ;;
    verify-lock)
      cmd_verify_lock
      ;;
    apply)
      cmd_apply
      ;;
    *)
      echo "[ERROR] Unknown command: ${cmd}" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
