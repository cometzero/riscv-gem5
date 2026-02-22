#!/usr/bin/env python3
"""gem5 web dashboard for headless Ubuntu servers.

Features:
- Target/workload selection and simulation execution
- Live progress and stage updates
- Interpreted simulation result summaries
- Log browsing with level/text filtering
- gem5 config.svg / config.dot visualization
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from flask import Flask, Response, abort, jsonify, render_template, request

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = REPO_ROOT / "workloads" / "results"
LOGS_ROOT = REPO_ROOT / "build" / "logs"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def safe_json_load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_stats_file(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}

    wanted = {
        "simTicks",
        "simSeconds",
        "simInsts",
        "hostSeconds",
        "hostInstRate",
        "hostTickRate",
    }
    stats: Dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        columns = line.split()
        if len(columns) < 2:
            continue
        key, value = columns[0], columns[1]
        if key not in wanted:
            continue
        try:
            stats[key] = float(value)
        except ValueError:
            continue
    return stats


def detect_log_level(line: str) -> str:
    lowered = line.lower()
    if "[error]" in lowered or " error:" in lowered or lowered.startswith("error"):
        return "ERROR"
    if "[warn]" in lowered or " warn:" in lowered or lowered.startswith("warn"):
        return "WARN"
    if "[info]" in lowered or " info:" in lowered or lowered.startswith("info"):
        return "INFO"
    return "DEBUG"


TARGET_OPTIONS: Dict[str, Dict[str, Any]] = {
    "riscv32_simple": {
        "label": "RISC-V32 Simple (CPU0 only)",
        "workloads": {
            "simple": {
                "label": "Simple workload",
                "description": "Zephyr single-core boot + simple workload",
                "mode": "simple",
                "ipc_case": "",
            }
        },
    },
    "riscv32_mixed": {
        "label": "RISC-V32 Mixed AMP/SMP",
        "workloads": {
            "simple": {
                "label": "Simple mixed workload",
                "description": "One-shot mixed run with role sync validation",
                "mode": "simple",
                "ipc_case": "",
            },
            "mailbox_pingpong": {
                "label": "Complex + Mailbox ping-pong",
                "description": "Stress run with mailbox ping-pong IPC case",
                "mode": "complex",
                "ipc_case": "mailbox_pingpong",
            },
            "hwsem_contention": {
                "label": "Complex + HWSEM contention",
                "description": "Stress run with HW semaphore contention case",
                "mode": "complex",
                "ipc_case": "hwsem_contention",
            },
        },
    },
    "riscv64_smp": {
        "label": "RISC-V64 SMP Linux",
        "workloads": {
            "simple": {
                "label": "Simple Linux workload",
                "description": "Linux SMP boot + simple benchmark scaffold",
                "mode": "simple",
                "ipc_case": "",
            },
            "complex": {
                "label": "Complex Linux stress workload",
                "description": "Linux SMP stress benchmark scaffold",
                "mode": "complex",
                "ipc_case": "",
            },
        },
    },
}


@dataclass
class SimulationJob:
    job_id: str
    target: str
    workload_key: str
    workload_label: str
    mode: str
    ipc_case: str
    created_at: str
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    started_at: str = ""
    completed_at: str = ""
    timestamp: str = ""
    returncode: Optional[int] = None
    command: List[str] = field(default_factory=list)
    error: str = ""
    result_dir: str = ""
    logs_dir: str = ""
    run_manifest: str = ""
    bench_manifest: str = ""
    recent_output: Deque[str] = field(default_factory=lambda: deque(maxlen=800))


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, SimulationJob] = {}
        self._lock = threading.Lock()

    def add(self, job: SimulationJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Optional[SimulationJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[SimulationJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda item: item.created_at, reverse=True)
        return jobs


STORE = JobStore()
APP = Flask(
    __name__,
    template_folder=str(REPO_ROOT / "dashboard" / "templates"),
    static_folder=str(REPO_ROOT / "dashboard" / "static"),
)


def update_progress(job: SimulationJob, line: str) -> None:
    mapping = [
        ("[INFO] target=", 5, "Preparing workload"),
        ("Building mixed boot trampoline", 20, "Preparing boot image"),
        ("[INFO] Executing:", 45, "Running simulation"),
        ("[OK] Manifest: ", 75, "Collecting run artifacts"),
        ("[OK] Benchmark scaffold manifest", 90, "Building benchmark summary"),
        ("[OK] Benchmark scaffold summary", 95, "Finalizing result"),
    ]
    for token, progress, stage in mapping:
        if token in line:
            if progress > job.progress:
                job.progress = progress
            job.stage = stage


def build_command(target: str, workload_key: str, option: Dict[str, Any], timestamp: str) -> List[str]:
    cmd = [
        str(REPO_ROOT / "scripts" / "run_bench.sh"),
        "--target",
        target,
        "--mode",
        str(option["mode"]),
        "--timestamp",
        timestamp,
    ]
    ipc_case = str(option.get("ipc_case", ""))
    if ipc_case:
        cmd.extend(["--ipc-case", ipc_case])
    return cmd


def run_job(job: SimulationJob) -> None:
    try:
        target_meta = TARGET_OPTIONS[job.target]
        option = target_meta["workloads"][job.workload_key]

        timestamp = utc_timestamp()
        cmd = build_command(job.target, job.workload_key, option, timestamp)

        job.started_at = utc_now_iso()
        job.status = "running"
        job.stage = "Launching run_bench.sh"
        job.progress = 1
        job.timestamp = timestamp
        job.command = cmd
        job.result_dir = str(RESULTS_ROOT / timestamp)
        job.logs_dir = str(LOGS_ROOT / job.target / timestamp)
        job.run_manifest = str(RESULTS_ROOT / timestamp / f"run_gem5_{job.target}_{job.mode}.json")
        job.bench_manifest = str(RESULTS_ROOT / timestamp / f"bench_{job.target}_{job.mode}.json")

        process = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )

        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n")
            job.recent_output.append(line)
            update_progress(job, line)

        process.wait()
        job.returncode = process.returncode

        if process.returncode == 0:
            job.status = "completed"
            job.stage = "Completed"
            job.progress = 100
        else:
            job.status = "failed"
            job.stage = "Failed"
            job.progress = min(99, max(job.progress, 50))
            job.error = f"run_bench.sh exited with rc={process.returncode}"
        job.completed_at = utc_now_iso()

    except Exception as exc:  # pragma: no cover - safety path
        job.status = "failed"
        job.stage = "Failed"
        job.error = str(exc)
        job.returncode = -1
        job.progress = min(99, max(job.progress, 1))
        job.completed_at = utc_now_iso()


def ensure_job(job_id: str) -> SimulationJob:
    job = STORE.get(job_id)
    if job is None:
        abort(404, description=f"Unknown job id: {job_id}")
    return job


def collect_log_sources(job: SimulationJob, run_manifest: Dict[str, Any]) -> Dict[str, Path]:
    sources: Dict[str, Path] = {}

    for key in ["run_log", "terminal_log"]:
        value = run_manifest.get(key)
        if isinstance(value, str) and value:
            path = resolve_repo_path(value)
            sources[path.name] = path

    for value in run_manifest.get("terminal_logs", []):
        if isinstance(value, str) and value:
            path = resolve_repo_path(value)
            sources[path.name] = path

    log_dir = Path(job.logs_dir) if job.logs_dir else Path()
    if log_dir.exists():
        for path in sorted(log_dir.glob("run_*.log")):
            sources[path.name] = path
        for path in sorted(log_dir.glob("system.platform.terminal*")):
            sources[path.name] = path

    return sources


def build_result_summary(job: SimulationJob) -> Dict[str, Any]:
    run_manifest_path = Path(job.run_manifest) if job.run_manifest else Path()
    bench_manifest_path = Path(job.bench_manifest) if job.bench_manifest else Path()

    run_manifest = safe_json_load(run_manifest_path)
    bench_manifest = safe_json_load(bench_manifest_path)

    checks = run_manifest.get("checks", {}) if isinstance(run_manifest.get("checks"), dict) else {}
    checks_list = [
        {"name": key, "passed": bool(value)}
        for key, value in checks.items()
    ]
    checks_ok = all(item["passed"] for item in checks_list) if checks_list else None

    run_result = run_manifest.get("run_result", {}) if isinstance(run_manifest.get("run_result"), dict) else {}
    rc = run_result.get("returncode")

    stats_path_raw = run_manifest.get("stats_path")
    stats = {}
    if isinstance(stats_path_raw, str) and stats_path_raw:
        stats = parse_stats_file(resolve_repo_path(stats_path_raw))

    metrics = []
    for key in ["simInsts", "simTicks", "simSeconds", "hostInstRate", "hostSeconds", "hostTickRate"]:
        if key in stats:
            metrics.append({"name": key, "value": stats[key]})

    if "sim_insts" in run_manifest and isinstance(run_manifest["sim_insts"], (int, float)):
        metrics.append({"name": "sim_insts_manifest", "value": float(run_manifest["sim_insts"])})

    marker_map = run_manifest.get("markers", {}) if isinstance(run_manifest.get("markers"), dict) else {}
    marker_list = [
        {"name": key, "present": bool(value)}
        for key, value in marker_map.items()
    ]

    interpretation: List[str] = []
    if isinstance(rc, int):
        interpretation.append("Simulation command exited successfully." if rc == 0 else f"Simulation command failed (rc={rc}).")
    if checks_list:
        passed_count = sum(1 for item in checks_list if item["passed"])
        interpretation.append(f"Validation checks: {passed_count}/{len(checks_list)} passed.")
    if marker_list:
        done_markers = [item for item in marker_list if item["name"].endswith("WORKLOAD DONE") and item["present"]]
        interpretation.append(f"Workload completion markers found: {len(done_markers)}")

    overall_pass = False
    if isinstance(rc, int) and rc == 0:
        overall_pass = checks_ok if checks_ok is not None else True

    log_sources = collect_log_sources(job, run_manifest)

    return {
        "overall_pass": overall_pass,
        "run_result": run_result,
        "checks": checks_list,
        "checks_ok": checks_ok,
        "metrics": metrics,
        "markers": marker_list,
        "interpretation": interpretation,
        "validation": run_manifest.get("validation", {}),
        "log_sources": [{"id": key, "path": str(path)} for key, path in log_sources.items()],
        "run_manifest": run_manifest,
        "bench_manifest": bench_manifest,
    }


def job_to_payload(job: SimulationJob) -> Dict[str, Any]:
    payload = {
        "job_id": job.job_id,
        "target": job.target,
        "workload_key": job.workload_key,
        "workload_label": job.workload_label,
        "mode": job.mode,
        "ipc_case": job.ipc_case,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "timestamp": job.timestamp,
        "returncode": job.returncode,
        "command": shlex.join(job.command) if job.command else "",
        "command_tokens": job.command,
        "error": job.error,
        "artifacts": {
            "result_dir": job.result_dir,
            "logs_dir": job.logs_dir,
            "run_manifest": job.run_manifest,
            "bench_manifest": job.bench_manifest,
        },
        "recent_output": list(job.recent_output),
    }
    payload["summary"] = build_result_summary(job)
    return payload


@APP.get("/")
def index() -> str:
    return render_template("index.html")


@APP.get("/api/options")
def api_options() -> Response:
    targets = []
    for target, meta in TARGET_OPTIONS.items():
        workloads = []
        for workload_key, workload_meta in meta["workloads"].items():
            workloads.append(
                {
                    "key": workload_key,
                    "label": workload_meta["label"],
                    "description": workload_meta["description"],
                    "mode": workload_meta["mode"],
                    "ipc_case": workload_meta["ipc_case"],
                }
            )
        targets.append({"key": target, "label": meta["label"], "workloads": workloads})

    return jsonify({"targets": targets})


@APP.get("/api/simulations")
def api_list_simulations() -> Response:
    jobs = STORE.list_jobs()
    return jsonify(
        {
            "jobs": [
                {
                    "job_id": job.job_id,
                    "target": job.target,
                    "workload_key": job.workload_key,
                    "workload_label": job.workload_label,
                    "mode": job.mode,
                    "status": job.status,
                    "progress": job.progress,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "timestamp": job.timestamp,
                }
                for job in jobs
            ]
        }
    )


@APP.post("/api/simulations")
def api_create_simulation() -> Response:
    payload = request.get_json(silent=True) or {}
    target = str(payload.get("target", "")).strip()
    workload_key = str(payload.get("workload", "")).strip()

    if target not in TARGET_OPTIONS:
        abort(400, description=f"Unsupported target: {target}")
    if workload_key not in TARGET_OPTIONS[target]["workloads"]:
        abort(400, description=f"Unsupported workload {workload_key} for target {target}")

    option = TARGET_OPTIONS[target]["workloads"][workload_key]
    job = SimulationJob(
        job_id=uuid.uuid4().hex,
        target=target,
        workload_key=workload_key,
        workload_label=option["label"],
        mode=option["mode"],
        ipc_case=option["ipc_case"],
        created_at=utc_now_iso(),
    )
    STORE.add(job)

    thread = threading.Thread(target=run_job, args=(job,), daemon=True)
    thread.start()

    return jsonify({"job_id": job.job_id, "status": job.status})


@APP.get("/api/simulations/<job_id>")
def api_get_simulation(job_id: str) -> Response:
    job = ensure_job(job_id)
    return jsonify(job_to_payload(job))


@APP.get("/api/simulations/<job_id>/logs")
def api_get_logs(job_id: str) -> Response:
    job = ensure_job(job_id)
    summary = build_result_summary(job)
    source_map = {item["id"]: resolve_repo_path(item["path"]) for item in summary["log_sources"]}

    if not source_map:
        return jsonify({"source": "", "lines": [], "available_sources": []})

    requested_source = request.args.get("source", "")
    source = requested_source if requested_source in source_map else next(iter(source_map.keys()))
    level = str(request.args.get("level", "ALL")).upper()
    query = str(request.args.get("q", "")).strip().lower()
    try:
        limit = int(request.args.get("limit", "400"))
    except ValueError:
        limit = 400
    limit = max(50, min(limit, 5000))

    path = source_map[source]
    if not path.exists():
        return jsonify({"source": source, "lines": [], "available_sources": list(source_map.keys())})

    filtered: List[Dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line_level = detect_log_level(raw)
        if level != "ALL" and line_level != level:
            continue
        if query and query not in raw.lower():
            continue
        filtered.append({"level": line_level, "text": raw})

    return jsonify(
        {
            "source": source,
            "path": str(path),
            "lines": filtered[-limit:],
            "available_sources": list(source_map.keys()),
        }
    )


@APP.get("/api/simulations/<job_id>/config/<fmt>")
def api_get_config_artifact(job_id: str, fmt: str) -> Response:
    job = ensure_job(job_id)
    logs_dir = Path(job.logs_dir)
    if not logs_dir.exists():
        abort(404, description="Logs directory is not ready yet")

    if fmt == "svg":
        path = logs_dir / "config.dot.svg"
        content_type = "image/svg+xml"
    elif fmt == "dot":
        path = logs_dir / "config.dot"
        content_type = "text/plain; charset=utf-8"
    else:
        abort(400, description=f"Unsupported format: {fmt}")

    if not path.exists():
        abort(404, description=f"Artifact missing: {path}")

    return Response(path.read_text(encoding="utf-8", errors="ignore"), content_type=content_type)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run gem5 web dashboard (headless-friendly)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[INFO] repo_root={REPO_ROOT}")
    print(f"[INFO] dashboard_url=http://{args.host}:{args.port}")
    APP.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
