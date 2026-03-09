"""
Psychoacoustic Model Module — Vectorized Batch Edition
========================================================
Computes all frame metrics in one pass using batched NumPy FFT.
This is 10-20× faster than frame-by-frame processing.
"""

import numpy as np
from scipy.signal import lfilter


# ─────────────────────────── Pre-computed Weights ─────────────────────────

def _build_weight_vectors(n_fft: int, sr: int):
    """Return (freqs, a_gains, el_weights) – computed once per unique n_fft/sr."""
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)

    # A-Weighting gains
    f  = freqs.astype(float)
    f2 = f ** 2
    num = (12194.0 ** 2) * (f2 ** 2)
    den = (
        (f2 + 20.6  ** 2)
        * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2))
        * (f2 + 12194.0 ** 2)
    )
    Ra = np.where(f > 0, num / (den + 1e-30), 0.0)
    A_db = 2.0 + 20.0 * np.log10(Ra + 1e-12)
    a_gains = 10.0 ** (A_db / 20.0)         # (n_fft//2+1,)

    # Equal-loudness weights (ISO 226 approximation)
    el = np.ones_like(f)
    el[(f >= 2000) & (f <= 5000)] = 1.5
    mask_lo = f < 200
    el[mask_lo] = 0.4 + 0.6 * (f[mask_lo] / 200.0)
    mask_hi = f > 8000
    el[mask_hi] = np.exp(-((f[mask_hi] - 8000) / 4000.0) ** 2)

    return freqs, a_gains, el


# Simple cache so we don't rebuild on every call
_WEIGHT_CACHE: dict = {}


def _get_weights(n_fft: int, sr: int):
    key = (n_fft, sr)
    if key not in _WEIGHT_CACHE:
        _WEIGHT_CACHE[key] = _build_weight_vectors(n_fft, sr)
    return _WEIGHT_CACHE[key]


# ─────────────────────────── K-Weighting (once on full signal) ────────────

def k_weighting_filter(audio: np.ndarray, _sr: int) -> np.ndarray:
    """Apply K-weighting filter (pre-filter + RLB) to 1-D audio."""
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


# ─────────────────────────── Batch Processor ──────────────────────────────

def batch_psychoacoustic_analysis(
    audio: np.ndarray,
    sr: int,
    frame_len: int,
    hop_len: int,
    n_fft: int = 2048,
) -> list[dict]:
    """
    Analyse ALL frames in one vectorized pass.

    Parameters
    ----------
    audio     : 1-D float32/64 mono audio array
    sr        : sample rate
    frame_len : samples per frame
    hop_len   : hop size in samples
    n_fft     : FFT size (≥ frame_len recommended)

    Returns
    -------
    List of per-frame dicts (same schema as old calculate_perceived_loudness)
    with 'timestamp' key included.
    """
    eps = 1e-12

    # ── Ensure float64 throughout (lfilter always returns float64) ────────
    audio   = np.asarray(audio,   dtype=np.float64)
    k_audio = k_weighting_filter(audio, sr)   # already float64 from lfilter

    # ── Build frame start indices ─────────────────────────────────────────
    starts = np.arange(0, len(audio) - frame_len + 1, hop_len)
    n_frames = len(starts)
    if n_frames == 0:
        return []

    # ── Hann window ───────────────────────────────────────────────────────
    window = np.hanning(frame_len)                             # (frame_len,)

    # ── Slice all frames into a 2-D matrix (n_frames × frame_len) ─────────
    # Both arrays are now float64 (8 bytes), so itemsize is consistent.
    from numpy.lib.stride_tricks import as_strided
    itemsize = audio.itemsize   # always 8 for float64

    frames = as_strided(
        audio,
        shape=(n_frames, frame_len),
        strides=(hop_len * itemsize, itemsize),
    ).copy()                                                   # copy to own the data
    frames *= window[np.newaxis, :]

    k_frames = as_strided(
        k_audio,
        shape=(n_frames, frame_len),
        strides=(hop_len * itemsize, itemsize),
    ).copy()

    # ── Batch FFT ─────────────────────────────────────────────────────────
    spectra    = np.fft.rfft(frames, n=n_fft, axis=1)         # (n_frames, n_bins)
    magnitudes = np.abs(spectra)                               # (n_frames, n_bins)

    freqs, a_gains, el_weights = _get_weights(n_fft, sr)

    # ── Raw RMS ───────────────────────────────────────────────────────────
    rms        = np.sqrt(np.mean(frames ** 2, axis=1) + eps)
    raw_rms_db = 20.0 * np.log10(rms)                         # (n_frames,)

    # ── A-Weighted loudness ───────────────────────────────────────────────
    a_mag      = magnitudes * a_gains[np.newaxis, :]           # (n_frames, n_bins)
    a_rms      = np.sqrt(np.mean(a_mag ** 2, axis=1) + eps) / (n_fft / 2)
    a_db       = 20.0 * np.log10(a_rms)                       # (n_frames,)

    # ── K-Weighted LUFS ───────────────────────────────────────────────────
    k_mean_sq  = np.mean(k_frames ** 2, axis=1) + eps
    k_lufs     = -0.691 + 10.0 * np.log10(k_mean_sq)         # (n_frames,)

    # ── Equal-loudness perceived score ────────────────────────────────────
    combo_w    = (el_weights * a_gains)[np.newaxis, :]
    el_mag     = magnitudes * combo_w
    el_energy  = np.sum(el_mag ** 2, axis=1) + eps
    perc_db    = 20.0 * np.log10(np.sqrt(el_energy / (n_fft ** 2) + eps))
    perc_score = np.clip((perc_db + 90.0) * (100.0 / 90.0), 0, 100)   # (n_frames,)

    # ── Band energies (computed per band, vectorized over frames) ─────────
    band_energies: list[np.ndarray] = []
    for _, flo, fhi in BAND_DEFS:
        mask = (freqs >= flo) & (freqs < fhi)
        if mask.any():
            be = np.mean(magnitudes[:, mask] ** 2, axis=1)
            band_energies.append(20.0 * np.log10(np.sqrt(be + eps)))
        else:
            band_energies.append(np.full(n_frames, -120.0))

    # ── Assemble result list ──────────────────────────────────────────────
    results = []
    for i in range(n_frames):
        fp = {BAND_DEFS[b][0]: float(band_energies[b][i]) for b in range(len(BAND_DEFS))}
        results.append({
            "timestamp":       float(starts[i] / sr),
            "raw_rms_db":      float(raw_rms_db[i]),
            "a_weighted_db":   float(a_db[i]),
            "k_weighted_lufs": float(k_lufs[i]),
            "perceived_score": float(perc_score[i]),
            "frequency_profile": fp,
        })
    return results


# ─────────────────────────── Legacy single-frame API ──────────────────────
# (kept for backwards compatibility)

def calculate_perceived_loudness(frame: np.ndarray, sr: int, n_fft: int = 2048) -> dict:
    results = batch_psychoacoustic_analysis(frame, sr, len(frame), len(frame), n_fft)
    return results[0] if results else {}
