"""
Psychoacoustic Model Module — Vectorized Batch Edition
========================================================
Computes per-frame metrics in one vectorized NumPy pass.

Score mapping (perceived_score, 0-100):
  Directly tied to RMS dBFS of the frame, boosted by A-weighting above 1kHz.
  -60 dBFS -> score   0  (silence/background)
  -40 dBFS -> score  35  (quiet background)
  -20 dBFS -> score  70  (moderate / dialogue)
   -6 dBFS -> score  94  (very loud / cinematic)
   -1 dBFS -> score 100  (near-clip / dangerous)
"""

import numpy as np
from scipy.signal import lfilter


# ─────────────────────────── Pre-computed Weights ─────────────────────────

def _build_weight_vectors(n_fft: int, sr: int):
    """Return (freqs, a_gains, el_weights)."""
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    f  = freqs.astype(float)
    f2 = f ** 2

    # A-Weighting (standard IEC 61672)
    num = (12194.0 ** 2) * (f2 ** 2)
    den = (
        (f2 + 20.6  ** 2)
        * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2))
        * (f2 + 12194.0 ** 2)
    )
    Ra   = np.where(f > 0, num / (den + 1e-30), 0.0)
    A_db = 2.0 + 20.0 * np.log10(Ra + 1e-12)
    a_gains = 10.0 ** (A_db / 20.0)

    # Equal-loudness / ISO 226 approximation
    el = np.ones_like(f)
    el[(f >= 2000) & (f <= 5000)] = 1.5
    mask_lo = f < 200
    el[mask_lo] = 0.4 + 0.6 * (f[mask_lo] / 200.0)
    mask_hi = f > 8000
    el[mask_hi] = np.exp(-((f[mask_hi] - 8000) / 4000.0) ** 2)

    return freqs, a_gains, el


_WEIGHT_CACHE: dict = {}

def _get_weights(n_fft: int, sr: int):
    key = (n_fft, sr)
    if key not in _WEIGHT_CACHE:
        _WEIGHT_CACHE[key] = _build_weight_vectors(n_fft, sr)
    return _WEIGHT_CACHE[key]


# ─────────────────────────── K-Weighting ──────────────────────────────────

def k_weighting_filter(audio: np.ndarray, _sr: int) -> np.ndarray:
    b1 = np.array([1.53512485958697, -2.69169618940638, 1.19839281085285])
    a1 = np.array([1.0, -1.69065929318241, 0.73248077421585])
    y  = lfilter(b1, a1, audio)
    b2 = np.array([1.0, -2.0, 1.0])
    a2 = np.array([1.0, -1.99004745483398, 0.99007225036621])
    return lfilter(b2, a2, y)


# ─────────────────────────── Band Definitions ─────────────────────────────

BAND_DEFS = [
    ("sub_bass (20-60 Hz)",    20,    60),
    ("bass (60-250 Hz)",       60,   250),
    ("low_mid (250-500 Hz)",  250,   500),
    ("mid (500-2k Hz)",       500,  2000),
    ("upper_mid (2k-5k Hz)", 2000,  5000),
    ("presence (5k-8k Hz)",  5000,  8000),
    ("brilliance (8k-20k Hz)",8000, 20000),
]

# Score calibration: map raw_rms_db (dBFS) -> perceived_score (0-100)
# Anchored on physically meaningful dBFS values:
SCORE_LOW_DB  = -60.0   # silence  -> score   0
SCORE_HIGH_DB =  -1.0   # near-clip-> score 100

def _rms_db_to_score(rms_db: np.ndarray) -> np.ndarray:
    """Map dBFS values linearly to 0-100 score."""
    return np.clip(
        (rms_db - SCORE_LOW_DB) / (SCORE_HIGH_DB - SCORE_LOW_DB) * 100.0,
        0.0, 100.0
    )


# ─────────────────────────── Batch Processor ──────────────────────────────

def batch_psychoacoustic_analysis(
    audio: np.ndarray,
    sr: int,
    frame_len: int,
    hop_len: int,
    n_fft: int = 2048,
) -> list[dict]:
    eps = 1e-12

    audio   = np.asarray(audio, dtype=np.float64)
    k_audio = k_weighting_filter(audio, sr)

    starts   = np.arange(0, len(audio) - frame_len + 1, hop_len)
    n_frames = len(starts)
    if n_frames == 0:
        return []

    window = np.hanning(frame_len)

    from numpy.lib.stride_tricks import as_strided
    itemsize = audio.itemsize

    frames = as_strided(
        audio,
        shape=(n_frames, frame_len),
        strides=(hop_len * itemsize, itemsize),
    ).copy()
    frames *= window[np.newaxis, :]

    k_frames = as_strided(
        k_audio,
        shape=(n_frames, frame_len),
        strides=(hop_len * itemsize, itemsize),
    ).copy()

    # ── Batch FFT (normalised magnitudes) ─────────────────────────────────
    spectra    = np.fft.rfft(frames, n=n_fft, axis=1)
    magnitudes = np.abs(spectra) / (frame_len + eps)           # per-sample amplitude

    freqs, a_gains, el_weights = _get_weights(n_fft, sr)

    # ── Raw RMS (dBFS) ────────────────────────────────────────────────────
    rms_lin    = np.sqrt(np.mean(frames ** 2, axis=1) + eps)
    raw_rms_db = 20.0 * np.log10(rms_lin + eps)               # (n_frames,)

    # ── A-Weighted RMS (dBFS) ─────────────────────────────────────────────
    a_mag = magnitudes * a_gains[np.newaxis, :]
    a_rms = np.sqrt(np.mean(a_mag ** 2, axis=1) + eps)
    a_db  = 20.0 * np.log10(a_rms + eps)                      # (n_frames,)

    # ── K-Weighted LUFS ───────────────────────────────────────────────────
    k_mean_sq = np.mean(k_frames ** 2, axis=1) + eps
    k_lufs    = -0.691 + 10.0 * np.log10(k_mean_sq)

    # ── Perceived Score (0-100) ───────────────────────────────────────────
    # Base on raw RMS dBFS — this is the most direct measure of signal power
    # and works correctly for ALL frequency content (low-freq bass, broadband
    # noise, clipped signals etc.). A-weighting was killing low-freq energy,
    # causing very low scores for bass-heavy cinema audio.
    #
    # Add a small equal-loudness "presence boost" for high-freq content
    # (2–5 kHz is most perceptually annoying for humans):
    presence_mask = (freqs >= 2000) & (freqs <= 5000)
    if presence_mask.any():
        presence_energy = np.mean(magnitudes[:, presence_mask] ** 2, axis=1)
        presence_db     = 10.0 * np.log10(presence_energy + eps)
        # Boost score by up to 10 pts if there's significant presence content
        presence_boost  = np.clip((presence_db - (-60.0)) / 40.0 * 10.0, 0.0, 10.0)
    else:
        presence_boost = np.zeros(n_frames)

    perc_db    = raw_rms_db                                    # base = raw RMS
    base_score = _rms_db_to_score(perc_db)
    perc_score = np.clip(base_score + presence_boost, 0.0, 100.0)

    # ── Band energies (dBFS) ──────────────────────────────────────────────
    band_energies: list[np.ndarray] = []
    for _, flo, fhi in BAND_DEFS:
        mask = (freqs >= flo) & (freqs < fhi)
        if mask.any():
            be = np.mean(magnitudes[:, mask] ** 2, axis=1)
            band_energies.append(20.0 * np.log10(np.sqrt(be + eps)))
        else:
            band_energies.append(np.full(n_frames, -120.0))

    # ── Assemble ──────────────────────────────────────────────────────────
    results = []
    for i in range(n_frames):
        fp = {BAND_DEFS[b][0]: float(band_energies[b][i]) for b in range(len(BAND_DEFS))}
        results.append({
            "timestamp":         float(starts[i] / sr),
            "raw_rms_db":        float(raw_rms_db[i]),
            "a_weighted_db":     float(a_db[i]),
            "k_weighted_lufs":   float(k_lufs[i]),
            "perceived_score":   float(perc_score[i]),
            "frequency_profile": fp,
        })
    return results


# ─────────────────────────── Legacy single-frame API ──────────────────────

def calculate_perceived_loudness(frame: np.ndarray, sr: int, n_fft: int = 2048) -> dict:
    results = batch_psychoacoustic_analysis(frame, sr, len(frame), len(frame), n_fft)
    return results[0] if results else {}
