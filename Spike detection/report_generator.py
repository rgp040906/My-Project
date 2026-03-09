"""
Report Generator Module
=======================
Produces:
  • JSON summary (machine-readable)
  • PDF correction report with loudness timeline chart
"""

import json
import io
import base64
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

if TYPE_CHECKING:
    from spike_detector import SpikeReport


# ────────────────────────── Colour Palette ────────────────────────────────

COLORS = {
    "bg":       "#0d1117",
    "panel":    "#161b22",
    "accent":   "#58a6ff",
    "green":    "#3fb950",
    "yellow":   "#d29922",
    "orange":   "#f78166",
    "red":      "#ff4444",
    "text":     "#c9d1d9",
    "grid":     "#21262d",
}

SEVERITY_COLORS = {
    "Low":      COLORS["green"],
    "Medium":   COLORS["yellow"],
    "High":     COLORS["orange"],
    "Critical": COLORS["red"],
}

TYPE_COLORS = {
    "Cinematic Effect":  COLORS["accent"],
    "Editing Error":     COLORS["orange"],
    "Clipping Artifact": COLORS["red"],
}


# ─────────────────────────── Chart Builder ────────────────────────────────

def build_timeline_chart(report: "SpikeReport", width_px: int = 1200) -> str:
    """
    Generate a base64-encoded PNG of the loudness timeline with spike markers.
    """
    dpi = 100
    fig_w = width_px / dpi
    fig_h = 5.0

    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=COLORS["bg"])
    ax = fig.add_subplot(111, facecolor=COLORS["panel"])

    times  = np.array(report.timestamp_timeline)
    scores = np.array(report.loudness_timeline)

    # Fill area under curve
    ax.fill_between(times, scores, alpha=0.18, color=COLORS["accent"])
    ax.plot(times, scores, color=COLORS["accent"], linewidth=1.2, label="Perceived Loudness")

    # Threshold zones
    ax.axhspan(90, 100, alpha=0.08, color=COLORS["red"],    label="Critical (>90)")
    ax.axhspan(82,  90, alpha=0.08, color=COLORS["orange"], label="High (82-90)")
    ax.axhspan(72,  82, alpha=0.06, color=COLORS["yellow"], label="Medium (72-82)")
    ax.axhline(60, color=COLORS["green"], linewidth=0.7, linestyle="--", alpha=0.6)

    # Spike markers
    for sp in report.spike_frames:
        col = TYPE_COLORS.get(sp.spike_type, COLORS["red"])
        ax.axvline(sp.timestamp, color=col, linewidth=0.8, alpha=0.7)
        ax.scatter([sp.timestamp], [sp.perceived_score], color=col, s=30, zorder=5)

    ax.set_xlim(times[0] if len(times) else 0, times[-1] if len(times) else 1)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Time (seconds)", color=COLORS["text"], fontsize=9)
    ax.set_ylabel("Perceived Loudness Score", color=COLORS["text"], fontsize=9)
    ax.set_title("Psychoacoustic Loudness Timeline", color=COLORS["text"],
                 fontsize=11, fontweight="bold", pad=10)

    ax.tick_params(colors=COLORS["text"])
    for spine in ax.spines.values():
        spine.set_edgecolor(COLORS["grid"])
    ax.grid(True, color=COLORS["grid"], linewidth=0.5, alpha=0.8)

    legend = ax.legend(loc="upper right", fontsize=7,
                       facecolor=COLORS["panel"], edgecolor=COLORS["grid"],
                       labelcolor=COLORS["text"])

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=COLORS["bg"])
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def build_band_chart(report: "SpikeReport") -> str:
    """Bar chart showing average energy across frequency bands for spike frames."""
    if not report.spike_frames:
        return ""

    band_labels = list(report.spike_frames[0].frequency_profile.keys())
    avg_energies = []
    for band in band_labels:
        vals = [s.frequency_profile.get(band, -120) for s in report.spike_frames]
        avg_energies.append(float(np.mean(vals)))

    fig, ax = plt.subplots(figsize=(9, 3.5), facecolor=COLORS["bg"])
    ax.set_facecolor(COLORS["panel"])

    bar_colors = [
        COLORS["accent"] if e > -30 else COLORS["grid"]
        for e in avg_energies
    ]
    bars = ax.bar(range(len(band_labels)), avg_energies, color=bar_colors, width=0.6)

    ax.set_xticks(range(len(band_labels)))
    ax.set_xticklabels([b.split("(")[0].strip() for b in band_labels],
                       rotation=25, ha="right", fontsize=8, color=COLORS["text"])
    ax.set_ylabel("Avg Energy (dB)", color=COLORS["text"], fontsize=9)
    ax.set_title("Average Frequency Band Energy at Spike Frames",
                 color=COLORS["text"], fontsize=10, fontweight="bold")
    ax.tick_params(colors=COLORS["text"])
    for spine in ax.spines.values():
        spine.set_edgecolor(COLORS["grid"])
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.5)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=COLORS["bg"])
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ──────────────────────────── JSON Export ─────────────────────────────────

def generate_json_report(report: "SpikeReport") -> dict:
    """Return a serialisable dict of the full analysis report."""

    def _spike_to_dict(sp):
        return {
            "timestamp_sec":   round(sp.timestamp, 3),
            "timestamp_hms":   _fmt_time(sp.timestamp),
            "raw_rms_db":      round(sp.raw_rms_db, 2),
            "a_weighted_db":   round(sp.a_weighted_db, 2),
            "k_weighted_lufs": round(sp.k_weighted_lufs, 2),
            "perceived_score": round(sp.perceived_score, 2),
            "spike_type":      sp.spike_type,
            "severity":        sp.severity,
            "severity_score":  round(sp.severity_score, 2),
            "recommendation":  sp.recommendation,
            "frequency_profile": {k: round(v, 2) for k, v in sp.frequency_profile.items()},
        }

    return {
        "generated_at":  datetime.now().isoformat(),
        "metadata":      report.metadata,
        "global_stats":  report.global_stats,
        "summary":       report.summary,
        "total_frames":  report.total_frames,
        "spikes":        [_spike_to_dict(s) for s in report.spike_frames],
    }


# ──────────────────────────── PDF Export ──────────────────────────────────

def generate_pdf_report(report: "SpikeReport", output_path: str) -> str:
    """Generate a professional PDF report and return the file path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, Image, HRFlowable)
    from reportlab.lib.units import cm

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style  = ParagraphStyle("Title2", parent=styles["Title"],
                                  fontSize=18, textColor=colors.HexColor("#1a73e8"),
                                  spaceAfter=6)
    h2_style     = ParagraphStyle("H2", parent=styles["Heading2"],
                                  fontSize=13, textColor=colors.HexColor("#1a73e8"),
                                  spaceBefore=14, spaceAfter=4)
    body_style   = ParagraphStyle("Body2", parent=styles["Normal"],
                                  fontSize=9, leading=13)
    verdict_ok   = ParagraphStyle("VerdictOK", parent=styles["Normal"],
                                  fontSize=14, textColor=colors.green, fontName="Helvetica-Bold")
    verdict_warn = ParagraphStyle("VerdictWarn", parent=styles["Normal"],
                                  fontSize=14, textColor=colors.orange, fontName="Helvetica-Bold")
    verdict_fail = ParagraphStyle("VerdictFail", parent=styles["Normal"],
                                  fontSize=14, textColor=colors.red, fontName="Helvetica-Bold")

    story = []
    meta = report.metadata
    summ = report.summary

    # ── Title ──
    story.append(Paragraph("Psychoacoustic Audio Safety Report", title_style))
    story.append(Paragraph(f"Cinema Audio Spike Detection — {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 10))

    # ── Metadata Table ──
    story.append(Paragraph("File Information", h2_style))
    rows = [
        ["File", meta.get("file", "—")],
        ["Duration", f"{meta.get('duration_sec', 0):.1f} s"],
        ["Sample Rate", f"{meta.get('sample_rate', '—')} Hz"],
        ["Channels", str(meta.get("channels", "—"))],
        ["Total Frames Analysed", str(report.total_frames)],
    ]
    t = Table(rows, colWidths=[5 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f0fe")),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # ── Safety Verdict ──
    verdict = summ.get("safety_verdict", "—")
    vstyle = verdict_ok if verdict == "PASS" else (
        verdict_fail if verdict == "FAIL" else verdict_warn)
    story.append(Paragraph("Safety Verdict", h2_style))
    story.append(Paragraph(f"▶ {verdict}", vstyle))
    story.append(Paragraph(summ.get("safety_message", ""), body_style))
    story.append(Spacer(1, 10))

    # ── Summary Stats ──
    story.append(Paragraph("Spike Summary", h2_style))
    sum_rows = [
        ["Category", "Count"],
        ["Total Spikes",       str(summ.get("total_spikes", 0))],
        ["Cinematic Effects",  str(summ.get("cinematic_effects", 0))],
        ["Editing Errors",     str(summ.get("editing_errors", 0))],
        ["Clipping Artifacts", str(summ.get("clipping_artifacts", 0))],
        ["Critical",           str(summ.get("critical_count", 0))],
        ["High",               str(summ.get("high_count", 0))],
        ["Medium",             str(summ.get("medium_count", 0))],
        ["Low",                str(summ.get("low_count", 0))],
    ]
    t2 = Table(sum_rows, colWidths=[8 * cm, 9 * cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    story.append(t2)
    story.append(Spacer(1, 14))

    # ── Spike Detail Table ──
    if report.spike_frames:
        story.append(Paragraph("Spike Detail — Correction Log", h2_style))
        detail_rows = [["Time", "Type", "Severity", "Score", "Recommendation (truncated)"]]
        for sp in report.spike_frames[:50]:   # cap at 50 rows
            rec = (sp.recommendation or "")[:80] + ("…" if len(sp.recommendation or "") > 80 else "")
            detail_rows.append([
                _fmt_time(sp.timestamp),
                sp.spike_type,
                sp.severity,
                f"{sp.perceived_score:.1f}",
                rec,
            ])
        t3 = Table(detail_rows, colWidths=[2.2*cm, 3.5*cm, 2*cm, 1.5*cm, 7.8*cm])
        sev_color_map = {"Critical": "#ff4444", "High": "#f78166",
                         "Medium":   "#d29922",  "Low":  "#3fb950"}
        ts = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f9f9f9")]),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ])
        for row_i, sp in enumerate(report.spike_frames[:50], start=1):
            hex_c = sev_color_map.get(sp.severity, "#888888")
            ts.add("TEXTCOLOR", (2, row_i), (2, row_i), colors.HexColor(hex_c))
            ts.add("FONTNAME",  (2, row_i), (2, row_i), "Helvetica-Bold")
        t3.setStyle(ts)
        story.append(t3)

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Generated by Psychoacoustic Audio Safety Verification System — Cinema Edition",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontSize=7, textColor=colors.grey)
    ))

    doc.build(story)
    return output_path


# ─────────────────────────── Helpers ──────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"
