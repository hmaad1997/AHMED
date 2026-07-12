"""
Audio Fingerprint Engine (Shazam-style) for Quran recitation identification.
Uses the classic constellation-map + combinatorial hashing algorithm.

Dependencies: numpy, scipy, librosa
"""
from __future__ import annotations
import hashlib
import numpy as np
from scipy.ndimage import maximum_filter, generate_binary_structure, iterate_structure
from typing import List, Tuple
import librosa

# --- Algorithm parameters (tuned for Quran recitation, mostly vocal content) ---
SAMPLE_RATE = 22050
FFT_WINDOW_SIZE = 4096
OVERLAP_RATIO = 0.5
PEAK_NEIGHBORHOOD_SIZE = 20
MIN_AMPLITUDE = 10
FAN_VALUE = 15          # how many target peaks each anchor pairs with
MIN_HASH_TIME_DELTA = 0
MAX_HASH_TIME_DELTA = 200


def _get_2d_peaks(spectrogram: np.ndarray, amp_min: float = MIN_AMPLITUDE):
    struct = generate_binary_structure(2, 1)
    neighborhood = iterate_structure(struct, PEAK_NEIGHBORHOOD_SIZE)
    local_max = maximum_filter(spectrogram, footprint=neighborhood) == spectrogram
    background = spectrogram == 0
    eroded_background = maximum_filter(background, footprint=neighborhood) == background
    detected_peaks = local_max & ~eroded_background
    amps = spectrogram[detected_peaks]
    freqs, times = np.where(detected_peaks)
    filter_idxs = np.where(amps > amp_min)
    freqs_filter = freqs[filter_idxs]
    times_filter = times[filter_idxs]
    return list(zip(freqs_filter, times_filter))


def _generate_hashes(peaks: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Combinatorial hashing → (hash_int64, absolute_time_offset)."""
    peaks = sorted(peaks, key=lambda p: p[1])  # sort by time
    hashes = []
    for i, (f1, t1) in enumerate(peaks):
        for j in range(1, FAN_VALUE):
            if i + j >= len(peaks):
                break
            f2, t2 = peaks[i + j]
            dt = t2 - t1
            if MIN_HASH_TIME_DELTA <= dt <= MAX_HASH_TIME_DELTA:
                h = hashlib.sha1(f"{f1}|{f2}|{dt}".encode()).digest()
                # take 8 bytes → int64 (Postgres BIGINT)
                hash_int = int.from_bytes(h[:8], "big", signed=True)
                hashes.append((hash_int, int(t1)))
    return hashes


def fingerprint_audio(path_or_bytes, sr: int = SAMPLE_RATE) -> List[Tuple[int, int]]:
    """Load audio → compute spectrogram → detect peaks → generate hashes.
    Returns list of (hash_bigint, offset_frames). offset_frames * hop = ms.
    """
    y, _ = librosa.load(path_or_bytes, sr=sr, mono=True)
    hop = FFT_WINDOW_SIZE - int(FFT_WINDOW_SIZE * OVERLAP_RATIO)
    S = np.abs(librosa.stft(y, n_fft=FFT_WINDOW_SIZE, hop_length=hop))
    S_db = librosa.amplitude_to_db(S, ref=np.max, top_db=80)
    S_db = np.clip(S_db + 80, 0, None)  # shift to non-negative
    peaks = _get_2d_peaks(S_db)
    return _generate_hashes(peaks)


def frames_to_ms(offset_frames: int) -> int:
    hop = FFT_WINDOW_SIZE - int(FFT_WINDOW_SIZE * OVERLAP_RATIO)
    return int(offset_frames * hop * 1000 / SAMPLE_RATE)
