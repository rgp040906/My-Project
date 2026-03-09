"""
Debug: print perceived_score statistics for each test audio.
Run: python debug_scores.py
"""
import numpy as np
import soundfile as sf
from pathlib import Path

from audio_processor import AudioProcessor
from psychoacoustic_model import batch_psychoacoustic_analysis
from spike_detector import SpikeDetector, DEFAULT_THRESHOLDS

FILES = [
    "test_audio/test_no_spike.wav",
    "test_audio/test_partial_spike.wav",
    "test_audio/test_full_spike.wav",
]

print("\n🔬  CinemaGuard — Score Diagnostics")
print("=" * 65)

for fpath in FILES:
    p = Path(__file__).parent / fpath
    if not p.exists():
        print(f"  ⚠  File not found: {p}"); continue

    proc = AudioProcessor(str(p), frame_ms=30, hop_ms=20)
    proc.load()
    sr       = proc.sr
    frame_len = int(sr * proc.frame_ms / 1000)
    hop_len   = int(sr * proc.hop_ms  / 1000)

    frames = batch_psychoacoustic_analysis(proc.audio, sr, frame_len, hop_len)
    scores = np.array([f["perceived_score"] for f in frames])
    rms_db = np.array([f["raw_rms_db"]      for f in frames])

    t = DEFAULT_THRESHOLDS
    pct_thresh   = float(np.percentile(scores, t["spike_percentile"]))
    spike_thresh = max(pct_thresh,
                       float(np.median(scores)) + t["min_above_median"],
                       t["absolute_floor"])

    print(f"\n📄  {p.name}")
    print(f"    Frames          : {len(scores)}")
    print(f"    Score  min/mean/median/max : "
          f"{scores.min():.1f} / {scores.mean():.1f} / "
          f"{np.median(scores):.1f} / {scores.max():.1f}")
    print(f"    RMS dB min/max  : {rms_db.min():.1f} / {rms_db.max():.1f}")
    print(f"    spike_thresh    : {spike_thresh:.1f}  "
          f"(pct97={pct_thresh:.1f}, abs_floor={t['absolute_floor']})")
    print(f"    Frames >= thresh: {(scores >= spike_thresh).sum()}")
    print(f"    Frames >= 0 dB clip ({t['raw_db_clip_warn']} dBFS): "
          f"{(rms_db >= t['raw_db_clip_warn']).sum()}")

    # Also run the full detector
    detector = SpikeDetector()
    report   = detector.analyze(frames, proc.global_stats(), proc.metadata)
    summ     = report.summary
    print(f"    ── Verdict: {summ['safety_verdict']}  "
          f"| spikes={summ['total_spikes']}  "
          f"critical={summ['critical_count']}  "
          f"clips={summ['clipping_artifacts']}")

print("\n" + "=" * 65 + "\n")
