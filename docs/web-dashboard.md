# Web Dashboard Guide (Headless gem5 Server)

- Date: 2026-02-22
- Scope: Run gem5 simulation from browser and view progress/results/logs/config artifacts

## 1) Recommendation

`Flask + existing run_bench/run_gem5 pipeline` 경로를 사용합니다.
새로운 실행 엔진을 만들지 않고 현재 검증된 스크립트를 그대로 호출하므로,
재현성과 추적성이 유지됩니다.

## 2) Files

- Backend: `scripts/web_dashboard.py`
- Launcher: `scripts/run_web_dashboard.sh`
- UI template: `dashboard/templates/index.html`
- UI logic/style: `dashboard/static/app.js`, `dashboard/static/styles.css`

## 3) Prerequisites

```bash
cd /build/risc-v/riscv-gem5
python3 -c "import flask; print(flask.__version__)"
```

If Flask is missing:

```bash
sudo apt-get update
sudo apt-get install -y python3-flask
```

## 4) Start dashboard

```bash
cd /build/risc-v/riscv-gem5
scripts/run_web_dashboard.sh
```

Custom host/port:

```bash
cd /build/risc-v/riscv-gem5
GEM5_DASHBOARD_HOST=0.0.0.0 GEM5_DASHBOARD_PORT=18080 scripts/run_web_dashboard.sh
```

Then access from browser:

- `http://<ubuntu-server-ip>:8080` (or custom port)

## 5) Required features mapping

1. target/workload 선택 + 실행
   - `Run Simulation` card
2. simulation progress
   - `Progress` card + live stage/progress polling
3. interpreted result + graph
   - `Interpreted Results` card
   - metric/check charts (canvas)
4. log filter
   - source/level/query filter
5. gem5 config SVG view (auto-load + zoom)
   - simulation completion 시 `config.dot.svg` 자동 로드
   - Zoom +/- / 100% reset

## 6) API contract (for automation)

- `GET /api/options` : targets/workloads
- `POST /api/simulations` : create job
- `GET /api/simulations` : list jobs
- `GET /api/simulations/<job_id>` : job detail + interpreted summary
- `GET /api/simulations/<job_id>/logs` : filtered log lines
- `GET /api/simulations/<job_id>/config/svg` : SVG artifact
- `GET /api/simulations/<job_id>/config/dot` : DOT artifact

## 7) Quick verification

### 7.1 Server/API smoke

```bash
cd /build/risc-v/riscv-gem5
scripts/run_web_dashboard.sh >/tmp/gem5-dashboard.log 2>&1 &
DASH_PID=$!
sleep 2
curl -fsS http://127.0.0.1:8080/api/options | jq '.targets | length'
kill "$DASH_PID"
```

Expected: target count `>= 1`

### 7.2 Create one simulation job via API

```bash
cd /build/risc-v/riscv-gem5
scripts/run_web_dashboard.sh >/tmp/gem5-dashboard.log 2>&1 &
DASH_PID=$!
sleep 2
JOB_JSON=$(curl -fsS -X POST http://127.0.0.1:8080/api/simulations \
  -H 'Content-Type: application/json' \
  -d '{"target":"riscv32_simple","workload":"simple"}')
JOB_ID=$(echo "$JOB_JSON" | jq -r '.job_id')

echo "job_id=${JOB_ID}"
curl -fsS "http://127.0.0.1:8080/api/simulations/${JOB_ID}" | jq '{status,progress,stage}'
kill "$DASH_PID"
```

Expected:
- JSON has `job_id`
- status in `{queued,running,completed,failed}`

## 8) Troubleshooting

- `Artifact missing: config.dot.svg`
  - gem5 run did not produce config artifacts yet.
  - check `build/logs/<target>/<timestamp>/`.
- Job fails immediately with `run_bench.sh exited`
  - prerequisite binaries/images missing.
  - run build flow in `docs/execution-guide.md` first.
- Dashboard reachable only on localhost
  - verify bind host: `GEM5_DASHBOARD_HOST=0.0.0.0`.
  - open firewall port.

## 9) DoD

- [ ] Browser can start simulation with selected target/workload
- [ ] Progress/stage updates while simulation is running
- [ ] Result summary + charts rendered after completion
- [ ] Log filter by source/level/query works
- [ ] config svg/dot are viewable when artifacts exist
