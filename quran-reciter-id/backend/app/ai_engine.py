"""
AI Engine for Voice Recognition using SpeechBrain
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
    """Return absolute path to bundled SpeechBrain model (works in PyInstaller EXE and dev)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    d = base / "pretrained_models" / "spkrec-ecapa-voxceleb"
    if not d.exists():
        # fallback: writable cache in user home so first-run download still works
        d = Path.home() / ".quran_reciter_id" / "spkrec-ecapa-voxceleb"
        d.mkdir(parents=True, exist_ok=True)
    return d


class VoiceRecognitionEngine:
    """Handle voice embedding generation using SpeechBrain ECAPA-TDNN"""
    
    def __init__(self):
        """Initialize the SpeechBrain model"""
        logger.info("Loading SpeechBrain ECAPA-TDNN model...")
        
        try:
            self.encoder = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(_model_dir())
            )
            logger.info("✓ Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise
        
        self.sample_rate = 16000  # Required by the model
    
    def process_audio_file(self, audio_path: Path) -> np.ndarray:
        """
        Process an audio file and generate its voice embedding
        
        Args:
            audio_path: Path to the audio file (WAV, MP3, etc.)
        
        Returns:
            numpy array containing the voice embedding
        """
        try:
            logger.info(f"Processing audio file: {audio_path.name}")
            
            # Load audio
            signal, fs = torchaudio.load(str(audio_path))
            
            # Convert to mono if stereo
            if signal.shape[0] > 1:
                signal = torch.mean(signal, dim=0, keepdim=True)
            
            # Resample if needed
            if fs != self.sample_rate:
                logger.info(f"Resampling from {fs}Hz to {self.sample_rate}Hz")
                resampler = torchaudio.transforms.Resample(fs, self.sample_rate)
                signal = resampler(signal)
            
            # Generate embedding
            with torch.no_grad():
                embedding = self.encoder.encode_batch(signal)
            
            # Convert to numpy
            embedding_np = embedding.squeeze().cpu().numpy()
            
            logger.info(f"✓ Generated embedding with shape: {embedding_np.shape}")
            return embedding_np
            
        except Exception as e:
            logger.error(f"Failed to process audio: {str(e)}")
            raise
    
    def process_audio_bytes(self, audio_bytes: bytes) -> np.ndarray:
        """
        Process audio from bytes (useful for API uploads)
        
        Args:
            audio_bytes: Raw audio file bytes
        
        Returns:
            numpy array containing the voice embedding
        """
        try:
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = Path(tmp_file.name)
            
            # Process the temp file
            embedding = self.process_audio_file(tmp_path)
            
            # Clean up
            tmp_path.unlink()
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to process audio bytes: {str(e)}")
            raise
    
    def validate_audio_duration(self, audio_path: Path, min_duration_sec: float = 3.0) -> bool:
        """
        Check if audio is long enough for reliable identification
        
        Args:
            audio_path: Path to audio file
            min_duration_sec: Minimum required duration in seconds
        
        Returns:
            True if audio is long enough, False otherwise
        """
        try:
            info = torchaudio.info(str(audio_path))
            duration = info.num_frames / info.sample_rate
            
            if duration < min_duration_sec:
                logger.warning(f"Audio too short: {duration:.2f}s (minimum: {min_duration_sec}s)")
                return False
            
            logger.info(f"Audio duration: {duration:.2f}s ✓")
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate audio: {str(e)}")
            return False
