/**
 * CinemaGuard — Frontend Application Logic
 * Handles file upload, progress simulation, API calls, and result rendering.
 */

// ─────────────────────────── State ────────────────────────────────────────
let currentJobId  = null;
let selectedFile  = null;
let allSpikes     = [];
let activeFilter  = "all";

// ─────────────────────────── DOM Refs ─────────────────────────────────────
const dropZone       = document.getElementById("drop-zone");
const fileInput      = document.getElementById("file-input");
const analyzeBtn     = document.getElementById("analyze-btn");
const demoBtn        = document.getElementById("demo-btn");
const fileInfo       = document.getElementById("file-info");
const fileNameDisp   = document.getElementById("file-name-display");
const fileSizeDisp   = document.getElementById("file-size-display");
const progressCont   = document.getElementById("progress-container");
const progressBar    = document.getElementById("progress-bar");
const progressLabel  = document.getElementById("progress-label");
const resultsSection = document.getElementById("results-section");
const verdictBanner  = document.getElementById("verdict-banner");
const verdictIcon    = document.getElementById("verdict-icon");
const verdictValue   = document.getElementById("verdict-value");
const verdictMsg     = document.getElementById("verdict-msg");
const downloadBtn    = document.getElementById("download-btn");
const statsGrid      = document.getElementById("stats-grid");
const timelineChart  = document.getElementById("timeline-chart");
const bandChart      = document.getElementById("band-chart");
const bandChartCard  = document.getElementById("band-chart-card");
const spikeTbody     = document.getElementById("spike-tbody");
const noSpikes       = document.getElementById("no-spikes");
const globalGrid     = document.getElementById("global-stats-grid");
const toast          = document.getElementById("toast");

// ─────────────────────────── File Handling ────────────────────────────────

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover",  e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  selectedFile = file;
  fileNameDisp.textContent = file.name;
  fileSizeDisp.textContent = formatBytes(file.size);
  fileInfo.classList.remove("hidden");
  analyzeBtn.disabled = false;
  showToast(`✅ Loaded: ${file.name}`, "success");
}

// ─────────────────────────── Analysis ─────────────────────────────────────

analyzeBtn.addEventListener("click", () => {
  if (!selectedFile) return;
  const fd = new FormData();
  fd.append("file", selectedFile);
  runAnalysis(fetch("/analyze", { method: "POST", body: fd }));
});

demoBtn.addEventListener("click", () => {
  runAnalysis(fetch("/demo"));
});

async function runAnalysis(fetchPromise) {
  // Hide results, show progress
  resultsSection.classList.add("hidden");
  progressCont.classList.remove("hidden");
  progressCont.classList.add("analyzing");
  analyzeBtn.disabled = true;
  demoBtn.disabled    = true;

  const steps = ["step-load","step-segment","step-psycho","step-detect","step-report"];
  const labels = [
    "Loading audio file…",
    "Segmenting into 30ms frames…",
    "Running psychoacoustic analysis…",
    "Detecting and classifying spikes…",
    "Generating PDF report…",
  ];
  const pcts = [10, 25, 60, 85, 98];

  let stepIdx = 0;
  const stepTimer = setInterval(() => {
    if (stepIdx < steps.length) {
      if (stepIdx > 0) document.getElementById(steps[stepIdx-1]).classList.add("done");
      document.getElementById(steps[stepIdx]).classList.add("active");
      progressBar.style.width = pcts[stepIdx] + "%";
      progressLabel.textContent = labels[stepIdx];
      stepIdx++;
    }
  }, 900);

  try {
    const resp = await fetchPromise;
    clearInterval(stepTimer);

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Server error");
    }

    progressBar.style.width = "100%";
    progressLabel.textContent = "Analysis complete!";
    steps.forEach(s => {
      const el = document.getElementById(s);
      el.classList.add("done"); el.classList.remove("active");
    });

    await new Promise(r => setTimeout(r, 600));

    const data = await resp.json();
    renderResults(data);

    progressCont.classList.add("hidden");
    progressCont.classList.remove("analyzing");
    resultsSection.classList.remove("hidden");
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

    if (data.demo) showToast("⚡ Demo analysis complete!", "success");
    else showToast("🎬 Analysis complete!", "success");

  } catch (e) {
    clearInterval(stepTimer);
    progressCont.classList.add("hidden");
    progressCont.classList.remove("analyzing");
    showToast(`❌ Error: ${e.message}`, "error");
  } finally {
    analyzeBtn.disabled = !selectedFile;
    demoBtn.disabled    = false;
    // Reset progress steps
    steps.forEach(s => {
      const el = document.getElementById(s);
      el.classList.remove("active","done");
    });
    document.getElementById("step-load").classList.add("active");
    progressBar.style.width = "0%";
    progressLabel.textContent = "Initializing pipeline…";
  }
}

// ─────────────────────────── Render Results ───────────────────────────────

function renderResults(data) {
  currentJobId = data.job_id;
  allSpikes    = data.spikes || [];

  renderVerdict(data.summary);
  renderStatsGrid(data);
  renderCharts(data);
  renderSpikeTable(allSpikes);
  renderGlobalStats(data.global_stats);
  buildLegend();

  downloadBtn.onclick = () => downloadPDF();
}

function renderVerdict(summary) {
  const verdict  = summary.safety_verdict || "PASS";
  const iconMap  = { PASS: "✅", FAIL: "🚨", "PASS WITH NOTES": "⚠️" };
  const clsMap   = { PASS: "pass", FAIL: "fail", "PASS WITH NOTES": "review" };
  const cls      = clsMap[verdict] || "review";

  verdictBanner.className = `verdict-banner ${cls}`;
  verdictIcon.textContent = iconMap[verdict] || "⚠️";
  verdictValue.textContent = verdict;
  verdictValue.className   = `verdict-value ${cls}`;
  verdictMsg.textContent   = summary.safety_message || "";
}

function renderStatsGrid(data) {
  const s = data.summary;
  const m = data.metadata;
  statsGrid.innerHTML = "";

  const cards = [
    { label:"Total Frames",       value: data.total_frames,      sub:"analysed",        cls:"accent-blue"   },
    { label:"Total Spikes",       value: s.total_spikes,         sub:"detected",        cls: s.total_spikes > 0 ? "accent-red" : "accent-green" },
    { label:"Critical",           value: s.critical_count,       sub:"severity events", cls: s.critical_count > 0 ? "accent-red" : "accent-green" },
    { label:"High",               value: s.high_count,           sub:"severity events", cls: s.high_count > 0 ? "accent-orange" : "accent-green" },
    { label:"Editing Errors",     value: s.editing_errors,       sub:"edit discontinuities", cls:"accent-orange" },
    { label:"Clipping Artifacts", value: s.clipping_artifacts,   sub:"digital clips",   cls: s.clipping_artifacts > 0 ? "accent-red" : "accent-green" },
    { label:"Cinematic Effects",  value: s.cinematic_effects,    sub:"intentional",     cls:"accent-purple" },
    { label:"Duration",           value: `${m.duration_sec}s`,   sub:`${m.sample_rate} Hz`, cls:"accent-blue" },
  ];

  cards.forEach(c => {
    const div = document.createElement("div");
    div.className = `stat-card ${c.cls}`;
    div.innerHTML = `
      <div class="stat-label">${c.label}</div>
      <div class="stat-value">${c.value}</div>
      <div class="stat-sub">${c.sub}</div>
    `;
    statsGrid.appendChild(div);
  });
}

function renderCharts(data) {
  if (data.timeline_chart) {
    timelineChart.src = "data:image/png;base64," + data.timeline_chart;
  }
  if (data.band_chart) {
    bandChart.src = "data:image/png;base64," + data.band_chart;
    bandChartCard.classList.remove("hidden");
  } else {
    bandChartCard.classList.add("hidden");
  }
}

function buildLegend() {
  const legendRow = document.getElementById("legend-row");
  legendRow.innerHTML = "";
  const items = [
    { label:"Cinematic",     color:"#3b82f6" },
    { label:"Editing Error", color:"#f97316" },
    { label:"Clipping",      color:"#ef4444" },
    { label:"Safe Zone",     color:"#22c55e" },
  ];
  items.forEach(it => {
    legendRow.innerHTML += `
      <span class="legend-item">
        <span class="legend-dot" style="background:${it.color}"></span>${it.label}
      </span>`;
  });
}

// ─────────────────────────── Spike Table ──────────────────────────────────

function renderSpikeTable(spikes) {
  const filtered = activeFilter === "all"
    ? spikes
    : spikes.filter(s => s.spike_type === activeFilter);

  spikeTbody.innerHTML = "";

  if (filtered.length === 0) {
    noSpikes.classList.remove("hidden");
    return;
  }
  noSpikes.classList.add("hidden");

  filtered.forEach((sp, idx) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="color:var(--text-3);font-family:var(--mono)">${idx+1}</td>
      <td class="timestamp-cell">${sp.timestamp_hms}</td>
      <td>${typeBadge(sp.spike_type)}</td>
      <td>${severityPill(sp.severity)}</td>
      <td>${scoreBar(sp.perceived_score)}</td>
      <td style="font-family:var(--mono);font-size:0.78rem">${sp.a_weighted_db.toFixed(1)} dB</td>
      <td style="font-family:var(--mono);font-size:0.78rem">${sp.k_weighted_lufs.toFixed(1)}</td>
      <td class="rec-cell">${sp.recommendation}</td>
    `;
    spikeTbody.appendChild(tr);
  });
}

function typeBadge(type) {
  const cls = type === "Clipping Artifact" ? "type-clip"
            : type === "Editing Error"     ? "type-edit"
            : "type-cinematic";
  const icon = type === "Clipping Artifact" ? "🔴"
             : type === "Editing Error"     ? "🟠"
             : "🔵";
  return `<span class="type-badge ${cls}">${icon} ${type}</span>`;
}

function severityPill(sev) {
  const cls = { Critical:"sev-critical", High:"sev-high",
                Medium:"sev-medium",     Low:"sev-low" }[sev] || "sev-low";
  return `<span class="severity-pill ${cls}">${sev}</span>`;
}

function scoreBar(score) {
  const color = score >= 90 ? "#ef4444"
              : score >= 82 ? "#f97316"
              : score >= 72 ? "#f59e0b"
              : "#22c55e";
  return `
    <div class="score-bar">
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width:${score}%;background:${color}"></div>
      </div>
      <span class="score-val">${score.toFixed(0)}</span>
    </div>`;
}

// ─────────────────────────── Table Filters ────────────────────────────────

document.querySelectorAll(".filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.filter;
    renderSpikeTable(allSpikes);
  });
});

// ─────────────────────────── Global Stats ─────────────────────────────────

function renderGlobalStats(gs) {
  if (!gs) return;
  globalGrid.innerHTML = "";
  const items = [
    { label:"Peak Linear",        value: gs.peak_linear },
    { label:"Peak (dBFS)",        value: gs.peak_db + " dB" },
    { label:"RMS (dBFS)",         value: gs.rms_db + " dB" },
    { label:"Crest Factor",       value: gs.crest_factor_db + " dB" },
    { label:"Dynamic Range Est.", value: gs.dynamic_range_estimate_db + " dB" },
  ];
  items.forEach(it => {
    globalGrid.innerHTML += `
      <div class="gs-item">
        <div class="gs-label">${it.label}</div>
        <div class="gs-value">${it.value}</div>
      </div>`;
  });
}

// ─────────────────────────── PDF Download ─────────────────────────────────

function downloadPDF() {
  if (!currentJobId) return;
  window.open(`/download/${currentJobId}`, "_blank");
}

// ─────────────────────────── Toast ────────────────────────────────────────

let toastTimer = null;
function showToast(msg, type="") {
  toast.textContent = msg;
  toast.className   = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3800);
}

// ─────────────────────────── Helpers ──────────────────────────────────────

function formatBytes(bytes) {
  if (bytes < 1024)       return bytes + " B";
  if (bytes < 1048576)    return (bytes/1024).toFixed(1) + " KB";
  return (bytes/1048576).toFixed(1) + " MB";
}
