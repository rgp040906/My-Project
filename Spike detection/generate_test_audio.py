"""
Test Audio Generator for CinemaGuard
=====================================
Generates three WAV files to test the spike detection pipeline:

  1. test_no_spike.wav       – Clean dialogue/music bed, no dangerous spikes
  2. test_partial_spike.wav  – Mix of quiet sections + a few moderate spikes
  3. test_full_spike.wav     – Heavy clipping + multiple critical spikes

Run with: python generate_test_audio.py
"""

import numpy as np
import soundfile as sf
from pathlib import Path

SR   = 44100   # 44.1 kHz standard cinema
OUT  = Path(__file__).parent / "test_audio"
OUT.mkdir(exist_ok=True)

rng = np.random.default_rng(42)

def sine(freq, dur, amp=1.0):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return amp * np.sin(2 * np.pi * freq * t)

def noise(dur, amp=1.0):
    return amp * rng.uniform(-1, 1, int(SR * dur))

def hann_burst(freq, amp, dur_s, total_len):
    """A short hann-windowed burst, zero-padded to total_len samples."""
    n = int(SR * dur_s)
    t = np.linspace(0, dur_s, n, endpoint=False)
    burst = amp * np.sin(2 * np.pi * freq * t) * np.hanning(n)
    out = np.zeros(total_len)
    out[:n] = burst
    return out

def inject_spike(audio, at_sec, amp, dur_s=0.05, freq=220):
    """Inject a hann-windowed spike into audio at position at_sec."""
    idx   = int(at_sec * SR)
    n     = int(SR * dur_s)
    if idx + n > len(audio):
        n = len(audio) - idx
    t   = np.linspace(0, dur_s, n, endpoint=False)
    env = np.hanning(n)
    audio[idx:idx+n] += amp * np.sin(2 * np.pi * freq * t) * env
    return audio

def inject_clip(audio, at_sec, amp=2.0, dur_s=0.04):
    """Inject raw clipping noise (saturated) to simulate digital clip."""
    idx = int(at_sec * SR)
    n   = int(SR * dur_s)
    if idx + n > len(audio):
        n = len(audio) - idx
    audio[idx:idx+n] += amp   # amp > 1.0 intentionally causes clipping after np.clip
    return audio

def save(audio, fname, desc):
    audio = np.clip(audio, -1.0, 1.0)
    path  = OUT / fname
    sf.write(str(path), audio.astype(np.float32), SR)
    peak_db = 20 * np.log10(np.max(np.abs(audio)) + 1e-12)
    rms_db  = 20 * np.log10(np.sqrt(np.mean(audio ** 2)) + 1e-12)
    print(f"  ✅  {fname:35s}  peak={peak_db:+.1f} dBFS  rms={rms_db:+.1f} dBFS  →  {path}")
    return str(path)


print("\n🎬  CinemaGuard — Test Audio Generator")
print("=" * 55)

# ══════════════════════════════════════════════════════════════
# 1.  NO SPIKE — Clean cinema bed (30 s)
#     Soft dialogue + gentle music, well below safety limits
# ══════════════════════════════════════════════════════════════
print("\n[1/3]  Generating: test_no_spike.wav")
dur = 30.0
audio = np.zeros(int(SR * dur))

# Soft ambient bed
audio += sine(80,  dur, amp=0.04)   # sub-bass rumble
audio += sine(220, dur, amp=0.06)   # bass note
audio += sine(440, dur, amp=0.05)   # A4 musical tone
audio += sine(880, dur, amp=0.03)   # octave
audio += sine(1200,dur, amp=0.02)   # upper harmonic
audio += noise(dur, amp=0.015)      # gentle room noise

# Very soft, gradual swells (natural dynamics, not spikes)
for t in [5, 12, 20]:
    audio = inject_spike(audio, t, amp=0.18, dur_s=1.2, freq=220)

save(audio, "test_no_spike.wav",
     "Clean dialogue/music bed — should PASS")


# ══════════════════════════════════════════════════════════════
# 2.  PARTIAL SPIKE — Mix of quiet + a few moderate events (30 s)
#     Cinematic dynamics: quiet dialogue then a couple of bangs
# ══════════════════════════════════════════════════════════════
print("\n[2/3]  Generating: test_partial_spike.wav")
dur = 30.0
audio = np.zeros(int(SR * dur))

# Same ambient bed
audio += sine(80,  dur, amp=0.04)
audio += sine(440, dur, amp=0.06)
audio += noise(dur, amp=0.012)

# Moderate cinematic moments (not clipping, but notable)
audio = inject_spike(audio,  6.0, amp=0.55, dur_s=0.20, freq=120)   # medium boom
audio = inject_spike(audio, 14.0, amp=0.65, dur_s=0.15, freq=80)    # louder boom
audio = inject_spike(audio, 22.0, amp=0.50, dur_s=0.25, freq=200)   # sustained hit
# One abrupt edit discontinuity (editing error simulation)
audio = inject_spike(audio, 18.3, amp=0.72, dur_s=0.02, freq=1000)  # short harsh click

save(audio, "test_partial_spike.wav",
     "Moderate spikes — should PASS WITH NOTES or REVIEW")


# ══════════════════════════════════════════════════════════════
# 3.  FULL / HEAVY SPIKE — Clipping + many critical events (30 s)
#     Multiple digital clips + abrupt loud transients
# ══════════════════════════════════════════════════════════════
print("\n[3/3]  Generating: test_full_spike.wav")
dur = 30.0
audio = np.zeros(int(SR * dur))

# Loud base bed
audio += sine(80,  dur, amp=0.15)
audio += sine(440, dur, amp=0.20)
audio += noise(dur, amp=0.05)

# Digital clipping injections (amp > 1.0 before np.clip → true clip)
for t in [2.0, 8.5, 16.0, 23.5]:
    audio = inject_clip(audio, t,  amp=2.5, dur_s=0.04)

# Multiple very loud cinematic spikes
audio = inject_spike(audio,  4.0, amp=0.95, dur_s=0.30, freq=60)    # sub-bass explosion
audio = inject_spike(audio,  9.5, amp=0.92, dur_s=0.25, freq=120)   # bass slam
audio = inject_spike(audio, 13.0, amp=0.90, dur_s=0.20, freq=80)    # another explosion
audio = inject_spike(audio, 19.0, amp=0.88, dur_s=0.35, freq=100)   # sustained boom

# Abrupt editing errors (rapid harsh transitions)
for t in [6.2, 11.7, 21.3]:
    audio = inject_spike(audio, t, amp=0.85, dur_s=0.015, freq=4000)

save(audio, "test_full_spike.wav",
     "Heavy clipping + critical spikes — should FAIL")


print("\n" + "=" * 55)
print(f"📁  All files saved to:  {OUT}")
print("""
Upload to CinemaGuard at http://127.0.0.1:5000

Expected verdicts:
  test_no_spike.wav      → ✅  PASS
  test_partial_spike.wav → ⚠️  PASS WITH NOTES / REVIEW
  test_full_spike.wav    → ❌  FAIL
""")
