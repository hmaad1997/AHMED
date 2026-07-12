"""
AI Engine for Voice Recognition using SpeechBrain
- GPU auto-detection (CUDA)
- VAD (Silero) to strip silence/music before embedding
- Multi-segment averaging for robust embeddings & spoof detection
"""

import sys, os
import torch
import torchaudio
import numpy as np
from pathlib import Path
from speechbrain.pretrained import EncoderClassifier
import logging
import tempfile

logger = logging.getLogger(__name__)


def _model_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    d = base / "pretrained_models" / "spkrec-ecapa-voxceleb"
    if not d.exists():
        d = Path.home() / ".quran_reciter_id" / "spkrec-ecapa-voxceleb"
        d.mkdir(parents=True, exist_ok=True)
    return d


def _pick_device() -> str:
    """CUDA if available, else CPU."""
    if torch.cuda.is_available():
        try:
            name = torch.cuda.get_device_name(0)
            logger.info(f"🚀 GPU detected: {name} — using CUDA")
            return "cuda"
        except Exception:
            pass
    logger.info("💻 No GPU — using CPU")
    return "cpu"


class VoiceRecognitionEngine:
    """SpeechBrain ECAPA-TDNN with VAD + multi-segment averaging."""

    SAMPLE_RATE = 16000
    SEGMENT_SEC = 5           # length of each analysis window
    MAX_SEGMENTS = 8          # 8 × 5s = 40s deep analysis
    TARGET_ANALYSIS_SEC = 40  # trim speech to ~40s before segmenting
    VAD_MIN_SPEECH_MS = 500   # min speech chunk length

    def __init__(self):
        self.device = _pick_device()
        logger.info("Loading SpeechBrain ECAPA-TDNN model...")
        try:
            self.encoder = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(_model_dir()),
                run_opts={"device": self.device},
            )
            logger.info("✓ Speaker model loaded")
        except Exception as e:
            logger.error(f"Failed to load speaker model: {e}")
            raise

        # Silero VAD — optional, gracefully degrade if not installed
        self.vad = None
        self._vad_get_ts = None
        try:
            from silero_vad import load_silero_vad, get_speech_timestamps
            self.vad = load_silero_vad()
            self._vad_get_ts = get_speech_timestamps
            logger.info("✓ Silero VAD loaded")
        except Exception as e:
            logger.warning(f"Silero VAD not available — will skip VAD ({e})")

        self.sample_rate = self.SAMPLE_RATE

    # ---------- audio loading ----------
    def _load_mono_16k(self, audio_path: Path) -> torch.Tensor:
        signal, fs = torchaudio.load(str(audio_path))
        if signal.shape[0] > 1:
            signal = torch.mean(signal, dim=0, keepdim=True)
        if fs != self.SAMPLE_RATE:
            signal = torchaudio.transforms.Resample(fs, self.SAMPLE_RATE)(signal)
        return signal  # shape [1, N]

    # ---------- VAD ----------
    def _apply_vad(self, signal: torch.Tensor) -> torch.Tensor:
        """Return speech-only concatenated tensor. Falls back to input if VAD unavailable."""
        if self.vad is None or self._vad_get_ts is None:
            return signal
        try:
            wav = signal.squeeze(0)
            ts = self._vad_get_ts(
                wav, self.vad, sampling_rate=self.SAMPLE_RATE,
                min_speech_duration_ms=self.VAD_MIN_SPEECH_MS,
            )
            if not ts:
                logger.warning("VAD: no speech detected — using raw audio")
                return signal
            chunks = [wav[t["start"]:t["end"]] for t in ts]
            speech = torch.cat(chunks).unsqueeze(0)
            total_s = speech.shape[1] / self.SAMPLE_RATE
            logger.info(f"VAD kept {total_s:.1f}s of speech across {len(ts)} chunk(s)")
            return speech
        except Exception as e:
            logger.warning(f"VAD failed, using raw audio: {e}")
            return signal

    # ---------- embedding ----------
    def _embed(self, signal: torch.Tensor) -> np.ndarray:
        with torch.no_grad():
            emb = self.encoder.encode_batch(signal.to(self.device))
        return emb.squeeze().cpu().numpy()

    def process_audio_file(self, audio_path: Path) -> np.ndarray:
        """Single-shot embedding — kept for backward compatibility (add-reciter path)."""
        signal = self._load_mono_16k(audio_path)
        signal = self._apply_vad(signal)
        emb = self._embed(signal)
        logger.info(f"Embedding shape: {emb.shape}")
        return emb

    def process_audio_bytes(self, audio_bytes: bytes) -> np.ndarray:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes); p = Path(tmp.name)
        try:
            return self.process_audio_file(p)
        finally:
            try: p.unlink()
            except Exception: pass

    def process_audio_segments(self, audio_path: Path):
        """
        Deep 40-second analysis:
          1. Load audio → VAD (remove silence/music)
          2. Trim/pad speech to ~40s
          3. Split into 8 segments × 5s
          4. Embed each segment + compute mean
        Returns (mean_embedding, per_segment_embeddings, analyzed_sec).
        """
        signal = self._load_mono_16k(audio_path)
        signal = self._apply_vad(signal)
        target_len = self.TARGET_ANALYSIS_SEC * self.SAMPLE_RATE
        seg_len = self.SEGMENT_SEC * self.SAMPLE_RATE
        total = signal.shape[1]

        # Trim to the middle 40s if speech is longer (most representative)
        if total > target_len:
            start = (total - target_len) // 2
            signal = signal[:, start:start + target_len]
            total = target_len
            logger.info(f"Trimmed to central {self.TARGET_ANALYSIS_SEC}s of speech")

        analyzed_sec = total / self.SAMPLE_RATE

        if total < seg_len:
            emb = self._embed(signal)
            return emb, [emb], analyzed_sec

        n_segs = min(self.MAX_SEGMENTS, max(1, total // seg_len))
        stride = (total - seg_len) // max(1, n_segs - 1) if n_segs > 1 else 0
        embeddings = []
        for i in range(n_segs):
            start = i * stride if n_segs > 1 else 0
            chunk = signal[:, start:start + seg_len]
            embeddings.append(self._embed(chunk))
        embeddings = np.stack(embeddings, axis=0)
        mean = embeddings.mean(axis=0)
        logger.info(f"Deep analysis: {n_segs} segments over {analyzed_sec:.1f}s")
        return mean, [e for e in embeddings], analyzed_sec

    def validate_audio_duration(self, audio_path: Path, min_duration_sec: float = 3.0) -> bool:
        try:
            info = torchaudio.info(str(audio_path))
            duration = info.num_frames / info.sample_rate
            if duration < min_duration_sec:
                logger.warning(f"Audio too short: {duration:.2f}s")
                return False
            return True
        except Exception as e:
            logger.error(f"validate_audio_duration: {e}")
            return False
