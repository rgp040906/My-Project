"""
Spike Detector Module
=====================
Processes per-frame psychoacoustic results and classifies detected spikes
into three categories:
  1. Cinematic Effect  – intentional dramatic loudness change
  2. Editing Error     – abrupt discontinuity with no artistic context
  3. Clipping Artifact – waveform clipping / digital distortion
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────── Data Types ───────────────────────────────

@dataclass
class FrameResult:
    timestamp: float          # seconds from start
    raw_rms_db: float
    a_weighted_db: float
    k_weighted_lufs: float
    perceived_score: float    # 0-100
    frequency_profile: dict
    is_spike: bool = False
    spike_type: Optional[str] = None
    severity: Optional[str] = None   # Low / Medium / High / Critical
    severity_score: float = 0.0      # 0-100
    recommendation: Optional[str] = None


@dataclass
class SpikeReport:
    total_frames: int
    spike_frames: List[FrameResult]
    global_stats: dict
    metadata: dict
    loudness_timeline: List[float]   # perceived_score per frame
    timestamp_timeline: List[float]  # seconds per frame
    summary: dict = field(default_factory=dict)


# ─────────────────────────── Thresholds ───────────────────────────────────

DEFAULT_THRESHOLDS = {
    "spike_percentile":         95.0,
    "min_above_median":          8.0,
    "absolute_floor":           30.0,
    "perceived_score_medium":   45.0,
    "perceived_score_high":     62.0,
    "perceived_score_critical": 78.0,
    "raw_db_clip_warn":         -3.0,
    "min_spike_gap_sec":         1.5,
    "delta_score_error":        20.0,
    "delta_score_cinematic":    10.0,
    "sustained_neighbor_count":  3,
}


# ─────────────────────────── Spike Detector ───────────────────────────────

class SpikeDetector:
    """
    Runs the full spike-detection pipeline over psychoacoustic frame results.
    """

    def __init__(self, thresholds: dict | None = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    # ──────────────────────────── Public API ──────────────────────────────

    def analyze(
        self,
        frame_results: List[dict],
        global_stats: dict,
        metadata: dict,
    ) -> SpikeReport:
        """
        Parameters
        ----------
        frame_results : list of dicts from psychoacoustic_model.calculate_perceived_loudness
                        with 'timestamp' key injected by the pipeline.
        global_stats  : dict from AudioProcessor.global_stats()
        metadata      : dict from AudioProcessor.metadata

        Returns
        -------
        SpikeReport
        """
        import numpy as np

        scores     = [f["perceived_score"] for f in frame_results]
        timestamps = [f["timestamp"] for f in frame_results]
        scores_arr = np.array(scores)

        t = self.thresholds

        # ── Percentile-based adaptive threshold ──────────────────────────
        track_median = float(np.median(scores_arr))
        track_mean   = float(np.mean(scores_arr))
        track_std    = float(np.std(scores_arr))
        pct_thresh   = float(np.percentile(scores_arr, t["spike_percentile"]))
        spike_thresh = max(
            pct_thresh,
            track_median + t["min_above_median"],
            t["absolute_floor"],
        )

        # ── Boolean mask: which frames are above threshold ────────────────
        above_thresh = scores_arr >= spike_thresh    # shape (n_frames,)

        # ── Candidate pass ────────────────────────────────────────────────
        processed: list[FrameResult] = []
        n = len(frame_results)
        for i, fr in enumerate(frame_results):
            prev_score = scores[i - 1] if i > 0 else fr["perceived_score"]
            delta = fr["perceived_score"] - prev_score

            # Count how many neighboring frames are ALSO above threshold
            # (used by _classify to detect sustained loud sections)
            radius = t["sustained_neighbor_count"]
            lo = max(0, i - radius)
            hi = min(n,  i + radius + 1)
            neighbor_above = int(above_thresh[lo:hi].sum()) - int(above_thresh[i])

            result = FrameResult(
                timestamp=fr["timestamp"],
                raw_rms_db=fr["raw_rms_db"],
                a_weighted_db=fr["a_weighted_db"],
                k_weighted_lufs=fr["k_weighted_lufs"],
                perceived_score=fr["perceived_score"],
                frequency_profile=fr["frequency_profile"],
            )

            if self._is_spike(fr, spike_thresh, t["raw_db_clip_warn"]):
                result.is_spike   = True
                result.spike_type = self._classify(fr, delta, neighbor_above)
                result.severity, result.severity_score = self._severity(fr)
                result.recommendation = self._recommend(
                    result.spike_type, result.severity, fr
                )

            processed.append(result)

        # ── Temporal deduplication (1.5 s window) ─────────────────────────
        raw_spikes   = [f for f in processed if f.is_spike]
        spike_frames = self._dedup_spikes(raw_spikes, t["min_spike_gap_sec"])

        summary = self._build_summary(spike_frames, metadata)
        summary["track_mean_loudness"]   = round(track_mean, 1)
        summary["track_median_loudness"] = round(track_median, 1)
        summary["track_std_loudness"]    = round(track_std,   1)
        summary["spike_threshold"]       = round(spike_thresh, 1)

        return SpikeReport(
            total_frames=len(processed),
            spike_frames=spike_frames,
            global_stats=global_stats,
            metadata=metadata,
            loudness_timeline=scores,
            timestamp_timeline=timestamps,
            summary=summary,
        )

    # ──────────────────────────── Internals ───────────────────────────────

    def _is_spike(self, fr: dict,
                  spike_thresh: float, clip_thresh: float) -> bool:
        """A frame is a spike if it clips OR exceeds the adaptive threshold."""
        if fr["raw_rms_db"] >= clip_thresh:
            return True
        if fr["perceived_score"] >= spike_thresh:
            return True
        return False

    @staticmethod
    def _dedup_spikes(spikes: list, min_gap: float) -> list:
        """Keep only the peak spike within each min_gap-second window."""
        if not spikes:
            return []
        out = []
        window_start = spikes[0].timestamp
        window_best  = spikes[0]
        for sp in spikes[1:]:
            if sp.timestamp - window_start < min_gap:
                # Same window — keep the louder spike
                if sp.perceived_score > window_best.perceived_score:
                    window_best = sp
            else:
                out.append(window_best)
                window_start = sp.timestamp
                window_best  = sp
        out.append(window_best)
        return out

    def _classify(self, fr: dict, delta: float, neighbor_above: int) -> str:
        """
        Classify a spike frame using three signals:
          1. raw_rms_db  — is the waveform clipping?
          2. neighbor_above  — how many surrounding frames are also loud?
             If many neighbors are above threshold → SUSTAINED → Cinematic
          3. delta  — how abruptly did loudness change?
             Only use delta when neighbors are NOT above threshold (isolated spike)
        """
        t = self.thresholds

        # ── Rule 1: Clipping always wins ──────────────────────────────────
        if fr["raw_rms_db"] >= t["raw_db_clip_warn"]:
            return "Clipping Artifact"

        # ── Rule 2: Sustained loud section → Cinematic Effect ─────────────
        # If ≥ 3 neighboring frames are ALSO above threshold, this is part
        # of a continuous loud section (music swell, explosion sequence, etc.)
        # It cannot be an editing error — real errors are ISOLATED spikes.
        if neighbor_above >= t["sustained_neighbor_count"]:
            return "Cinematic Effect"

        # ── Rule 3: Isolated spike — use delta to classify ─────────────────
        # Only reaches here when the spike is surrounded by quieter frames.
        if abs(delta) >= t["delta_score_error"]:   # truly abrupt jump
            return "Editing Error"

        if abs(delta) < t["delta_score_cinematic"]:  # gentle rise
            return "Cinematic Effect"

        # ── Rule 4: Moderate delta, isolated → Editing Error ──────────────
        return "Editing Error"

    def _severity(self, fr: dict) -> tuple[str, float]:
        score = fr["perceived_score"]
        t = self.thresholds
        if score >= t["perceived_score_critical"]:
            return "Critical", score
        if score >= t["perceived_score_high"]:
            return "High", score
        if score >= t["perceived_score_medium"]:
            return "Medium", score
        return "Low", score

    @staticmethod
    def _recommend(spike_type: str, severity: str, fr: dict) -> str:
        if spike_type == "Clipping Artifact":
            return (
                "URGENT: Digital clipping detected. Apply brick-wall limiter at -0.5 dBFS, "
                "then re-render the affected section. Check upstream gain staging."
            )
        if spike_type == "Editing Error":
            if severity in ("Critical", "High"):
                return (
                    "Abrupt loudness discontinuity detected. Review the edit point for "
                    "missing crossfade or misaligned audio layers. "
                    "Apply 5–10 ms fade-in/out around the cut."
                )
            return (
                "Minor edit discontinuity. Consider a short crossfade (2–5 ms) "
                "or level-match surrounding frames."
            )
        # Cinematic Effect
        if severity == "Critical":
            return (
                "Intentional effect but perceived loudness exceeds cinema safety limits. "
                "Apply dynamic range compression or lower peak gain by 3–6 dB."
            )
        if severity == "High":
            return (
                "Loud cinematic moment. Verify against SMPTE ST 202 cinema loudness spec "
                "(≤ 85 dB SPL peak). Apply gentle limiting if needed."
            )
        return "Acceptable cinematic effect. No immediate action required."

    @staticmethod
    def _build_summary(spikes: List[FrameResult], metadata: dict) -> dict:
        if not spikes:
            return {
                "total_spikes": 0,
                "cinematic_effects": 0,
                "editing_errors": 0,
                "clipping_artifacts": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "safety_verdict": "PASS",
                "safety_message": "No abnormal audio spikes detected. Audio is safe for cinema release.",
            }

        type_counts = {"Cinematic Effect": 0, "Editing Error": 0, "Clipping Artifact": 0}
        sev_counts  = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}

        for s in spikes:
            type_counts[s.spike_type] = type_counts.get(s.spike_type, 0) + 1
            sev_counts[s.severity]    = sev_counts.get(s.severity, 0) + 1

        clips     = type_counts["Clipping Artifact"]
        cinematic = type_counts["Cinematic Effect"]
        errors    = type_counts["Editing Error"]
        critical  = sev_counts["Critical"]
        high      = sev_counts["High"]

        # FAIL: waveform clipping (always dangerous) OR 3+ critical non-cinematic spikes
        critical_non_cinematic = sum(
            1 for s in spikes
            if s.severity == "Critical" and s.spike_type != "Cinematic Effect"
        )
        if clips > 0 or critical_non_cinematic >= 3:
            verdict = "FAIL"
            msg = (
                f"{clips} clipping artifact(s) and {critical_non_cinematic} critical "
                "non-cinematic spike(s) detected. Audio MUST be corrected before cinema release."
            )
        elif critical > 3 or (high + critical) > 6:
            verdict = "REVIEW"
            msg = (
                f"{critical} critical and {high} high-severity spike(s) detected. "
                "Engineering review recommended — verify against SMPTE ST 202 limits."
            )
        elif errors > 3 or critical > 1:
            verdict = "PASS WITH NOTES"
            msg = (
                f"{errors} editing discontinuity(ies) and {critical} critical cinematic spike(s) found. "
                "Recommend review before release, but not blocking."
            )
        else:
            verdict = "PASS WITH NOTES"
            msg = "Minor spikes found. Review recommended but audio is acceptable for release."

        return {
            "total_spikes":       len(spikes),
            "cinematic_effects":  type_counts["Cinematic Effect"],
            "editing_errors":     errors,
            "clipping_artifacts": clips,
            "critical_count":     critical,
            "high_count":         high,
            "medium_count":       sev_counts["Medium"],
            "low_count":          sev_counts["Low"],
            "safety_verdict":     verdict,
            "safety_message":     msg,
        }
