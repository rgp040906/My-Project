"""Debug scores v3 - read error too"""
import traceback, pathlib

output_lines = []
def log(s=""): output_lines.append(s)

try:
    import numpy as np
    from audio_processor import AudioProcessor
    from psychoacoustic_model import batch_psychoacoustic_analysis
    from spike_detector import SpikeDetector, DEFAULT_THRESHOLDS

    FILES = [
        "test_audio/test_no_spike.wav",
        "test_audio/test_partial_spike.wav",
        "test_audio/test_full_spike.wav",
    ]

    log("CinemaGuard - Score Diagnostics v3")
    log("=" * 65)

    for fpath in FILES:
        p = pathlib.Path(__file__).parent / fpath
        if not p.exists():
            log(f"  FILE NOT FOUND: {p}"); continue

        try:
            proc = AudioProcessor(str(p), frame_ms=30, hop_ms=20)
            proc.load()
            sr        = proc.sr
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

            log(f"\nFILE: {p.name}")
            log(f"  Frames total    : {len(scores)}")
            log(f"  Score min       : {scores.min():.2f}")
            log(f"  Score mean      : {scores.mean():.2f}")
            log(f"  Score median    : {float(np.median(scores)):.2f}")
            log(f"  Score max       : {scores.max():.2f}")
            log(f"  Score pct95     : {pct_thresh:.2f}")
            log(f"  spike_thresh    : {spike_thresh:.2f}  (abs_floor={t['absolute_floor']})")
            log(f"  Frames>=thresh  : {int((scores >= spike_thresh).sum())}")
            log(f"  RMS dB min      : {rms_db.min():.2f}")
            log(f"  RMS dB max      : {rms_db.max():.2f}")
            log(f"  Clip frames (>={t['raw_db_clip_warn']} dBFS): {int((rms_db >= t['raw_db_clip_warn']).sum())}")
            log(f"  Thresholds med/high/crit: {t['perceived_score_medium']}/{t['perceived_score_high']}/{t['perceived_score_critical']}")

            try:
                detector = SpikeDetector()
                report   = detector.analyze(frames, proc.global_stats(), proc.metadata)
                summ     = report.summary
                log(f"  >> VERDICT: {summ['safety_verdict']}")
                log(f"     spikes={summ['total_spikes']} critical={summ['critical_count']} "
                    f"high={summ['high_count']} clips={summ['clipping_artifacts']}")
                log(f"     msg: {summ['safety_message']}")
            except Exception as e2:
                log(f"  >> DETECTOR ERROR: {e2}")
                log(traceback.format_exc())

        except Exception as e:
            log(f"  FILE ERROR: {e}")
            log(traceback.format_exc())

    log("\n" + "=" * 65)

except Exception as top_err:
    log(f"TOP-LEVEL ERROR: {top_err}")
    log(traceback.format_exc())

result = "\n".join(output_lines)
print(result)
out = pathlib.Path(__file__).parent / "debug_out.txt"
out.write_text(result, encoding="utf-8")
print(f"\nWritten to {out}")
