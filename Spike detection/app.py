"""
Flask Application — Psychoacoustic Audio Spike Detection System
===============================================================
Endpoints:
  GET  /                   – Serve the web UI
  POST /analyze            – Upload + analyze audio file
  GET  /download/<job_id>  – Download PDF report
  GET  /demo               – Run a synthetic demo (no file upload needed)
"""

import os
import json
import uuid
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, send_file, abort

from audio_processor import AudioProcessor
from psychoacoustic_model import batch_psychoacoustic_analysis
from spike_detector import SpikeDetector
from report_generator import (
    generate_json_report,
    generate_pdf_report,
    build_timeline_chart,
    build_band_chart,
)

# ─────────────────────────── App Setup ────────────────────────────────────

BASE_DIR    = Path(__file__).parent
STATIC_DIR  = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
UPLOAD_DIR  = BASE_DIR / "uploads"
REPORT_DIR  = BASE_DIR / "reports"

for d in (UPLOAD_DIR, REPORT_DIR):
    d.mkdir(exist_ok=True)

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATE_DIR),
)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024   # 500 MB

ALLOWED = {".wav", ".flac", ".mp3", ".ogg", ".aac", ".m4a", ".aiff"}

# In-memory job store (keyed by job_id)
jobs: dict[str, dict] = {}


# ─────────────────────────── Routes ───────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(TEMPLATE_DIR), "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(STATIC_DIR), filename)


@app.route("/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    suffix = Path(f.filename).suffix.lower()
    if suffix not in ALLOWED:
        return jsonify({"error": f"Unsupported format: {suffix}"}), 400

    job_id  = str(uuid.uuid4())
    tmp_path = UPLOAD_DIR / f"{job_id}{suffix}"
    f.save(str(tmp_path))

    try:
        result = _run_pipeline(str(tmp_path), job_id)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@app.route("/demo", methods=["GET"])
def demo():
    """Generate synthetic cinema-like 30-second audio and run the pipeline."""
    import numpy as np
    import soundfile as sf

    job_id = str(uuid.uuid4())
    sr     = 22050   # 22 kHz is sufficient for psychoacoustic analysis & much faster
    dur    = 20       # seconds
    t      = np.linspace(0, dur, sr * dur, endpoint=False)

    # Ambient cinema bed (low rumble + music-like tones) — keep quiet
    audio  = 0.02 * np.sin(2 * np.pi * 60  * t)   # sub-bass rumble
    audio += 0.03 * np.sin(2 * np.pi * 440 * t)   # A4 tone
    audio += 0.02 * np.sin(2 * np.pi * 800 * t)   # mid tone

    # Inject clearly distinct spikes (amplitude must dominate the ambient bed)
    spike_positions = [
        (3.0,  0.98, 0.06,  "clip"),      # clipping at 3 s  — very short, very loud
        (8.5,  0.75, 0.12,  "cinematic"), # cinematic boom    — wide, loud
        (13.0, 0.85, 0.08,  "edit_err"),  # abrupt edit error — sudden
        (17.5, 0.70, 0.15,  "cinematic"), # another cinematic — sustained
        (25.0, 0.92, 0.06,  "clip"),      # second clipping
    ]
    for ts, amp, width_s, _ in spike_positions:
        idx  = int(ts * sr)
        w    = int(width_s * sr)
        env  = np.hanning(w * 2)
        end  = min(idx + w, len(audio))
        wlen = end - idx
        audio[idx:end] += amp * env[:wlen]

    # Normalise to -0.5 dBFS (some spikes will still clip)
    audio = np.clip(audio, -1.0, 1.0)

    tmp_path = UPLOAD_DIR / f"{job_id}_demo.wav"
    sf.write(str(tmp_path), audio, sr)

    try:
        result = _run_pipeline(str(tmp_path), job_id)
        result["demo"] = True
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@app.route("/download/<job_id>", methods=["GET"])
def download_report(job_id):
    if job_id not in jobs:
        abort(404)
    pdf_path = jobs[job_id].get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        abort(404)
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f"spike_report_{job_id[:8]}.pdf",
        mimetype="application/pdf",
    )


# ─────────────────────────── Pipeline ─────────────────────────────────────

def _run_pipeline(audio_path: str, job_id: str) -> dict:
    """Full analysis pipeline → returns JSON-serialisable result dict."""

    # 1. Load audio
    processor = AudioProcessor(audio_path, frame_ms=30, hop_ms=20)
    processor.load()
    global_stats = processor.global_stats()

    # 2. Batch psychoacoustic analysis (vectorized — no Python loop)
    sr        = processor.sr
    frame_len = int(sr * processor.frame_ms / 1000)
    hop_len   = int(sr * processor.hop_ms / 1000)
    frame_results = batch_psychoacoustic_analysis(
        processor.audio, sr, frame_len, hop_len
    )

    # 3. Spike detection
    detector = SpikeDetector()
    report   = detector.analyze(frame_results, global_stats, processor.metadata)

    # 4. Generate charts (base64 PNG)
    timeline_b64 = build_timeline_chart(report)
    band_b64     = build_band_chart(report)

    # 5. Generate PDF
    pdf_path = str(REPORT_DIR / f"{job_id}.pdf")
    generate_pdf_report(report, pdf_path)
    jobs[job_id] = {"pdf_path": pdf_path}

    # 6. Build JSON response
    json_report = generate_json_report(report)
    json_report["job_id"]             = job_id
    json_report["timeline_chart"]     = timeline_b64
    json_report["band_chart"]         = band_b64
    json_report["loudness_timeline"]  = report.loudness_timeline
    json_report["timestamp_timeline"] = report.timestamp_timeline

    return json_report


# ─────────────────────────── Entry Point ──────────────────────────────────

if __name__ == "__main__":
    print("\n🎬  Psychoacoustic Audio Spike Detection System")
    print("━" * 50)
    print("   Open http://127.0.0.1:5000 in your browser")
    print("━" * 50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
