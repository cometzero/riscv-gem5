const state = {
  options: null,
  currentJobId: null,
  pollTimer: null,
  configZoom: 1,
  configSvgLoadedForJobId: "",
};

const el = {
  serverTime: document.getElementById("server-time"),
  targetSelect: document.getElementById("target-select"),
  workloadSelect: document.getElementById("workload-select"),
  workloadDescription: document.getElementById("workload-description"),
  runForm: document.getElementById("run-form"),
  runButton: document.getElementById("run-button"),
  activeJob: document.getElementById("active-job"),
  activeStage: document.getElementById("active-stage"),
  activeStatus: document.getElementById("active-status"),
  jobsBody: document.getElementById("jobs-body"),
  progressBar: document.getElementById("progress-bar"),
  progressValue: document.getElementById("progress-value"),
  startedAt: document.getElementById("started-at"),
  completedAt: document.getElementById("completed-at"),
  returncode: document.getElementById("returncode"),
  commandBox: document.getElementById("command-box"),
  recentOutput: document.getElementById("recent-output"),
  overallPass: document.getElementById("overall-pass"),
  checkRatio: document.getElementById("check-ratio"),
  interpretationList: document.getElementById("interpretation-list"),
  checksBody: document.getElementById("checks-body"),
  logSource: document.getElementById("log-source"),
  logLevel: document.getElementById("log-level"),
  logQuery: document.getElementById("log-query"),
  logRefresh: document.getElementById("log-refresh"),
  logLines: document.getElementById("log-lines"),
  zoomOut: document.getElementById("zoom-out"),
  zoomReset: document.getElementById("zoom-reset"),
  zoomIn: document.getElementById("zoom-in"),
  zoomValue: document.getElementById("zoom-value"),
  configStatus: document.getElementById("config-status"),
  configSvgViewport: document.getElementById("config-svg-viewport"),
  configSvgCanvas: document.getElementById("config-svg-canvas"),
  metricsChart: document.getElementById("metrics-chart"),
  checksChart: document.getElementById("checks-chart"),
};

function fmtIso(value) {
  if (!value) {
    return "-";
  }
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return value;
  }
  return dt.toLocaleString();
}

function fmtNumber(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  if (Math.abs(value) >= 1e6) {
    return value.toExponential(3);
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function setBadgeStatus(node, text, kind) {
  node.textContent = text;
  node.className = "badge";
  if (kind === "ok") {
    node.classList.add("ok");
  } else if (kind === "warn") {
    node.classList.add("warn");
  } else if (kind === "err") {
    node.classList.add("err");
  }
}

function statusKind(status) {
  if (status === "completed") {
    return "ok";
  }
  if (status === "failed") {
    return "err";
  }
  if (status === "running") {
    return "warn";
  }
  return "warn";
}

async function fetchJson(url, init) {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

function getTargetMeta(key) {
  return (state.options?.targets || []).find((item) => item.key === key) || null;
}

function getWorkloadMeta(targetKey, workloadKey) {
  const target = getTargetMeta(targetKey);
  if (!target) {
    return null;
  }
  return target.workloads.find((item) => item.key === workloadKey) || null;
}

function populateTargets() {
  el.targetSelect.innerHTML = "";
  for (const target of state.options?.targets || []) {
    const option = document.createElement("option");
    option.value = target.key;
    option.textContent = `${target.key} - ${target.label}`;
    el.targetSelect.appendChild(option);
  }
  populateWorkloads();
}

function populateWorkloads() {
  const target = getTargetMeta(el.targetSelect.value);
  el.workloadSelect.innerHTML = "";

  if (!target) {
    el.workloadDescription.textContent = "-";
    return;
  }

  for (const workload of target.workloads) {
    const option = document.createElement("option");
    option.value = workload.key;
    option.textContent = `${workload.key} (${workload.mode})`;
    el.workloadSelect.appendChild(option);
  }

  updateWorkloadDescription();
}

function updateWorkloadDescription() {
  const targetKey = el.targetSelect.value;
  const workloadKey = el.workloadSelect.value;
  const meta = getWorkloadMeta(targetKey, workloadKey);

  if (!meta) {
    el.workloadDescription.textContent = "-";
    return;
  }

  const ipcText = meta.ipc_case ? ` | ipc_case=${meta.ipc_case}` : "";
  el.workloadDescription.textContent = `${meta.description} | mode=${meta.mode}${ipcText}`;
}

function renderJobsTable(jobs) {
  el.jobsBody.innerHTML = "";

  if (!jobs.length) {
    el.jobsBody.innerHTML = '<tr><td colspan="6" class="muted">No jobs yet.</td></tr>';
    return;
  }

  for (const job of jobs) {
    const tr = document.createElement("tr");
    tr.classList.add("clickable");
    if (job.job_id === state.currentJobId) {
      tr.classList.add("selected");
    }

    tr.innerHTML = `
      <td><code>${job.job_id.slice(0, 8)}</code></td>
      <td>${job.target}</td>
      <td>${job.workload_key}</td>
      <td class="status-${job.status}">${job.status}</td>
      <td>${job.progress}%</td>
      <td>${fmtIso(job.created_at)}</td>
    `;

    tr.addEventListener("click", async () => {
      state.currentJobId = job.job_id;
      renderJobsTable(jobs);
      await refreshCurrentJob();
    });

    el.jobsBody.appendChild(tr);
  }
}

function drawMetricChart(metrics) {
  const canvas = el.metricsChart;
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0b1220";
  ctx.fillRect(0, 0, w, h);

  if (!metrics.length) {
    ctx.fillStyle = "#9ca3af";
    ctx.font = "14px sans-serif";
    ctx.fillText("No metric data", 16, 28);
    return;
  }

  const values = metrics.map((item) => Number(item.value) || 0);
  const maxValue = Math.max(...values, 1);
  const left = 48;
  const right = 12;
  const top = 14;
  const bottom = 42;
  const chartW = w - left - right;
  const chartH = h - top - bottom;
  const stepW = chartW / metrics.length;
  const barW = Math.max(10, stepW * 0.6);

  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(left, top);
  ctx.lineTo(left, h - bottom);
  ctx.lineTo(w - right, h - bottom);
  ctx.stroke();

  ctx.fillStyle = "#93c5fd";
  ctx.font = "11px sans-serif";

  metrics.forEach((metric, index) => {
    const value = Number(metric.value) || 0;
    const ratio = value / maxValue;
    const barH = Math.max(2, chartH * ratio);
    const x = left + index * stepW + (stepW - barW) / 2;
    const y = h - bottom - barH;

    ctx.fillStyle = "#60a5fa";
    ctx.fillRect(x, y, barW, barH);

    ctx.fillStyle = "#cbd5e1";
    const label = String(metric.name).slice(0, 14);
    ctx.fillText(label, x, h - bottom + 14);

    ctx.fillStyle = "#e2e8f0";
    ctx.fillText(fmtNumber(value), x, Math.max(y - 4, top + 10));
  });
}

function drawCheckChart(checks) {
  const canvas = el.checksChart;
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0b1220";
  ctx.fillRect(0, 0, w, h);

  if (!checks.length) {
    ctx.fillStyle = "#9ca3af";
    ctx.font = "14px sans-serif";
    ctx.fillText("No check data", 16, 28);
    return;
  }

  const passed = checks.filter((item) => item.passed).length;
  const failed = checks.length - passed;
  const total = checks.length;

  const passRatio = passed / total;
  const failRatio = failed / total;

  const x = 24;
  const y = 64;
  const width = w - 48;
  const barH = 30;

  ctx.fillStyle = "#334155";
  ctx.fillRect(x, y, width, barH);

  ctx.fillStyle = "#34d399";
  ctx.fillRect(x, y, width * passRatio, barH);

  ctx.fillStyle = "#f87171";
  ctx.fillRect(x + width * passRatio, y, width * failRatio, barH);

  ctx.fillStyle = "#e5e7eb";
  ctx.font = "14px sans-serif";
  ctx.fillText(`PASS: ${passed}`, x, y + barH + 24);
  ctx.fillText(`FAIL: ${failed}`, x + 120, y + barH + 24);
}

function renderSummary(summary) {
  const checks = summary.checks || [];
  const metrics = summary.metrics || [];

  if (summary.overall_pass === true) {
    setBadgeStatus(el.overallPass, "PASS", "ok");
  } else if (summary.overall_pass === false) {
    setBadgeStatus(el.overallPass, "FAIL", "err");
  } else {
    setBadgeStatus(el.overallPass, "UNKNOWN", "warn");
  }

  const passed = checks.filter((item) => item.passed).length;
  el.checkRatio.textContent = `${passed}/${checks.length}`;

  el.interpretationList.innerHTML = "";
  if (!summary.interpretation || summary.interpretation.length === 0) {
    el.interpretationList.innerHTML = '<li class="muted">No interpretation yet.</li>';
  } else {
    for (const line of summary.interpretation) {
      const li = document.createElement("li");
      li.textContent = line;
      el.interpretationList.appendChild(li);
    }
  }

  el.checksBody.innerHTML = "";
  if (!checks.length) {
    el.checksBody.innerHTML = '<tr><td colspan="2" class="muted">No checks yet.</td></tr>';
  } else {
    for (const check of checks) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${check.name}</td>
        <td class="${check.passed ? "status-completed" : "status-failed"}">${check.passed ? "PASS" : "FAIL"}</td>
      `;
      el.checksBody.appendChild(tr);
    }
  }

  drawMetricChart(metrics);
  drawCheckChart(checks);
}

function renderJobPayload(payload) {
  el.activeJob.textContent = payload.job_id || "none";
  el.activeStage.textContent = payload.stage || "idle";
  setBadgeStatus(el.activeStatus, payload.status || "idle", statusKind(payload.status));

  const progress = Number(payload.progress) || 0;
  el.progressBar.value = progress;
  el.progressValue.textContent = `${progress}%`;
  el.startedAt.textContent = fmtIso(payload.started_at);
  el.completedAt.textContent = fmtIso(payload.completed_at);
  el.returncode.textContent = payload.returncode ?? "-";
  el.commandBox.textContent = payload.command || "-";

  const recent = payload.recent_output || [];
  el.recentOutput.textContent = recent.length ? recent.slice(-200).join("\n") : "No output yet.";

  renderSummary(payload.summary || {});

  el.runButton.disabled = payload.status === "running";
}

function setLogSources(logSources) {
  const prev = el.logSource.value;
  el.logSource.innerHTML = "";

  for (const item of logSources || []) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.id;
    el.logSource.appendChild(option);
  }

  if (!logSources || !logSources.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "(no logs)";
    el.logSource.appendChild(option);
    return;
  }

  const keep = (logSources || []).some((item) => item.id === prev);
  el.logSource.value = keep ? prev : logSources[0].id;
}

async function refreshLogs() {
  if (!state.currentJobId) {
    return;
  }

  const params = new URLSearchParams({
    source: el.logSource.value || "",
    level: el.logLevel.value || "ALL",
    q: el.logQuery.value || "",
    limit: "500",
  });

  try {
    const payload = await fetchJson(`/api/simulations/${state.currentJobId}/logs?${params.toString()}`);

    if (payload.available_sources && payload.available_sources.length > 0) {
      const sourceExists = Array.from(el.logSource.options).some((opt) => opt.value === payload.source);
      if (!sourceExists) {
        el.logSource.innerHTML = "";
        for (const name of payload.available_sources) {
          const option = document.createElement("option");
          option.value = name;
          option.textContent = name;
          el.logSource.appendChild(option);
        }
      }
      el.logSource.value = payload.source;
    }

    const lines = payload.lines || [];
    el.logLines.textContent = lines.length
      ? lines.map((item) => `[${item.level}] ${item.text}`).join("\n")
      : "No logs matched the filter.";
  } catch (error) {
    el.logLines.textContent = `Failed to load logs: ${error}`;
  }
}

function setConfigStatus(message) {
  el.configStatus.textContent = message;
}

function setConfigZoom(nextZoom) {
  const clamped = Math.min(4.0, Math.max(0.25, nextZoom));
  state.configZoom = clamped;
  el.configSvgCanvas.style.transform = `scale(${clamped})`;
  el.zoomValue.textContent = `${Math.round(clamped * 100)}%`;
}

function resetConfigSvg(message) {
  el.configSvgCanvas.innerHTML = `<div class="config-svg-placeholder">${message}</div>`;
  el.configSvgCanvas.style.transform = "scale(1)";
  state.configZoom = 1;
  el.zoomValue.textContent = "100%";
}

async function loadSvgArtifact(jobId, { auto = false, force = false } = {}) {
  if (!jobId) {
    resetConfigSvg("Select a job first.");
    return;
  }
  if (!force && state.configSvgLoadedForJobId === jobId) {
    return;
  }

  const modeText = auto ? "auto-loading" : "loading";
  setConfigStatus(`config.dot.svg ${modeText}...`);
  try {
    const res = await fetch(`/api/simulations/${jobId}/config/svg?ts=${Date.now()}`);
    if (!res.ok) {
      resetConfigSvg(`config.dot.svg unavailable (${res.status})`);
      setConfigStatus("config.dot.svg not ready yet.");
      return;
    }

    const svgText = await res.text();
    el.configSvgCanvas.innerHTML = svgText;
    setConfigZoom(state.configZoom);
    state.configSvgLoadedForJobId = jobId;
    setConfigStatus("config.dot.svg loaded.");
  } catch (error) {
    resetConfigSvg(`Failed to load SVG: ${error}`);
    setConfigStatus("Failed to load config.dot.svg.");
  }
}

async function refreshCurrentJob() {
  if (!state.currentJobId) {
    return;
  }

  try {
    const payload = await fetchJson(`/api/simulations/${state.currentJobId}`);
    renderJobPayload(payload);
    setLogSources(payload.summary?.log_sources || []);

    if (payload.status === "running" || payload.status === "queued") {
      state.configSvgLoadedForJobId = "";
      setConfigStatus("Simulation running... SVG will be auto-loaded on completion.");
    } else if (payload.status === "completed") {
      await loadSvgArtifact(payload.job_id, { auto: true });
    } else if (payload.status === "failed") {
      setConfigStatus("Simulation failed. SVG artifact may not be available.");
    }

    await refreshLogs();
  } catch (error) {
    setBadgeStatus(el.activeStatus, "error", "err");
    el.activeStage.textContent = `Failed to load job: ${error}`;
  }
}

async function refreshJobs() {
  const payload = await fetchJson("/api/simulations");
  const jobs = payload.jobs || [];
  renderJobsTable(jobs);

  if (!state.currentJobId && jobs.length > 0) {
    state.currentJobId = jobs[0].job_id;
    renderJobsTable(jobs);
  }
}

async function createSimulation(event) {
  event.preventDefault();
  const target = el.targetSelect.value;
  const workload = el.workloadSelect.value;

  try {
    const created = await fetchJson("/api/simulations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, workload }),
    });

    state.currentJobId = created.job_id;
    el.runButton.disabled = true;
    state.configSvgLoadedForJobId = "";
    resetConfigSvg("Simulation started. Waiting for completion...");
    setConfigStatus("Simulation started. SVG will auto-load after completion.");

    await refreshJobs();
    await refreshCurrentJob();
  } catch (error) {
    setBadgeStatus(el.activeStatus, "submit error", "err");
    el.activeStage.textContent = String(error);
  }
}

function tickServerTime() {
  el.serverTime.textContent = new Date().toLocaleString();
}

function startPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
  }

  state.pollTimer = setInterval(async () => {
    try {
      await refreshJobs();
      await refreshCurrentJob();
    } catch (error) {
      el.activeStage.textContent = `Polling error: ${error}`;
    }
  }, 2000);
}

async function bootstrap() {
  tickServerTime();
  setInterval(tickServerTime, 1000);

  state.options = await fetchJson("/api/options");
  populateTargets();
  resetConfigSvg("No SVG loaded yet.");
  setConfigStatus("Simulation 완료 후 config.dot.svg가 자동으로 로드됩니다.");
  setConfigZoom(1);

  await refreshJobs();
  await refreshCurrentJob();
  startPolling();
}

el.targetSelect.addEventListener("change", () => {
  populateWorkloads();
});
el.workloadSelect.addEventListener("change", () => {
  updateWorkloadDescription();
});
el.runForm.addEventListener("submit", createSimulation);
el.logRefresh.addEventListener("click", refreshLogs);
el.logSource.addEventListener("change", refreshLogs);
el.logLevel.addEventListener("change", refreshLogs);
el.logQuery.addEventListener("change", refreshLogs);
el.zoomIn.addEventListener("click", () => {
  setConfigZoom(state.configZoom * 1.2);
});
el.zoomOut.addEventListener("click", () => {
  setConfigZoom(state.configZoom / 1.2);
});
el.zoomReset.addEventListener("click", () => {
  setConfigZoom(1);
});

bootstrap().catch((error) => {
  setBadgeStatus(el.activeStatus, "init error", "err");
  el.activeStage.textContent = `Failed to initialize dashboard: ${error}`;
});
