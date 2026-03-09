"""
Audio Processor Module
======================
Handles loading, channel mixing, frame segmentation and spectral analysis
of cinema audio files for the spike detection pipeline.
"""

import numpy as np
import librosa
import soundfile as sf
from pathlib import Path
from typing import Generator, Tuple


SUPPORTED_EXTENSIONS = {".wav", ".flac", ".aac", ".mp3", ".ogg", ".m4a", ".aiff"}


class AudioProcessor:
    """Load and segment a cinema audio file into overlapping frames."""

    def __init__(
        self,
        file_path: str,
        frame_ms: int = 30,
        hop_ms: int = 10,
        target_sr: int = 44100,
    ):
        self.file_path = Path(file_path)
        self.frame_ms = frame_ms
        self.hop_ms = hop_ms
        self.target_sr = target_sr

        self.audio: np.ndarray | None = None
        self.sr: int | None = None
        self.duration: float | None = None
        self.num_channels: int | None = None
        self.metadata: dict = {}

    # ─────────────────────────────── Loading ──────────────────────────────

    def load(self) -> "AudioProcessor":
        """Load file, convert to mono, and resample to target_sr."""
        suffix = self.file_path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported format: {suffix}")

        # librosa handles all formats (mp3 via audioread, etc.)
        audio, sr = librosa.load(
            str(self.file_path),
            sr=self.target_sr,
            mono=False,   # keep channels so we know original count
        )

        if audio.ndim == 1:
            self.num_channels = 1
            self.audio = audio
        else:
            self.num_channels = audio.shape[0]
            # Downmix to mono for analysis
            self.audio = np.mean(audio, axis=0)

        self.sr = sr
        self.duration = len(self.audio) / sr

        # Store basic metadata
        self.metadata = {
            "file": self.file_path.name,
            "format": suffix,
            "sample_rate": sr,
            "channels": self.num_channels,
            "duration_sec": round(self.duration, 3),
            "total_samples": len(self.audio),
        }
        return self

    # ─────────────────────────────── Framing ──────────────────────────────

    def frame_generator(self) -> Generator[Tuple[float, np.ndarray], None, None]:
        """
        Yields (timestamp_sec, frame_array) for each overlapping frame.
        Frame length = frame_ms ms; hop = hop_ms ms.
        """
        frame_len = int(self.sr * self.frame_ms / 1000)
        hop_len = int(self.sr * self.hop_ms / 1000)

        start = 0
        while start + frame_len <= len(self.audio):
            timestamp = start / self.sr
            frame = self.audio[start: start + frame_len]
            # Apply Hann window to reduce spectral leakage
            window = np.hanning(len(frame))
            yield timestamp, frame * window
            start += hop_len

    # ──────────────────────────── Quick Stats ─────────────────────────────

    def global_stats(self) -> dict:
        """Compute global statistics (peak, RMS, crest factor) on the whole track."""
        if self.audio is None:
            raise RuntimeError("Call .load() first.")
        eps = 1e-12
        peak = float(np.max(np.abs(self.audio)))
        rms = float(np.sqrt(np.mean(self.audio ** 2) + eps))
        peak_db = 20 * np.log10(peak + eps)
        rms_db = 20 * np.log10(rms)
        crest_factor_db = peak_db - rms_db
        return {
            "peak_linear": round(peak, 6),
            "peak_db":     round(peak_db, 2),
            "rms_db":      round(rms_db, 2),
            "crest_factor_db": round(crest_factor_db, 2),
            "dynamic_range_estimate_db": round(crest_factor_db, 2),
        }
