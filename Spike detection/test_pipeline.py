"""Quick local test of the batch pipeline without Flask."""
import numpy as np
import soundfile as sf
import tempfile, os

from psychoacoustic_model import batch_psychoacoustic_analysis

sr  = 22050
dur = 20
t   = np.linspace(0, dur, sr * dur, endpoint=False)

audio  = 0.02 * np.sin(2 * np.pi * 60  * t)
audio += 0.03 * np.sin(2 * np.pi * 440 * t)
audio += 0.02 * np.sin(2 * np.pi * 800 * t)

# Add spike
idx = int(3.0 * sr)
w   = int(0.06 * sr)
env = np.hanning(w * 2)
audio[idx:idx+w] += 0.98 * env[:w]

audio = np.clip(audio, -1.0, 1.0).astype(np.float32)

print(f"Audio shape: {audio.shape}, max: {audio.max():.3f}, dtype: {audio.dtype}")

frame_len = int(sr * 30 / 1000)   # 30 ms
hop_len   = int(sr * 20 / 1000)   # 20 ms hop
print(f"frame_len={frame_len}, hop_len={hop_len}")

results = batch_psychoacoustic_analysis(audio, sr, frame_len, hop_len)
print(f"Frames returned: {len(results)}")
if results:
    scores = [r['perceived_score'] for r in results]
    import numpy as np
    arr = np.array(scores)
    print(f"Max score: {arr.max():.1f}  Mean: {arr.mean():.1f}  Min: {arr.min():.1f}")
    print("Top 5 scores:", sorted(scores, reverse=True)[:5])
