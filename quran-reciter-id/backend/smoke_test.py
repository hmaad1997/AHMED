"""Smoke test: extract a fingerprint for one reciter and validate the pipeline.

Downloads a small known clip (Al-Fatiha by Alafasy from everyayah — public, tiny),
runs the ensemble embedding, and checks the vector shape and L2 norm.
Exits non-zero on any failure so the CI step fails loudly.
"""
import sys, os, urllib.request, tempfile
from pathlib import Path
import numpy as np

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

SAMPLE_URL = "https://everyayah.com/data/Alafasy_128kbps/001001.mp3"

def main():
    tmp = Path(tempfile.mkdtemp()) / "sample.mp3"
    print(f"[smoke] downloading {SAMPLE_URL}", flush=True)
    urllib.request.urlretrieve(SAMPLE_URL, tmp)
    assert tmp.stat().st_size > 5_000, "sample too small"
    print(f"[smoke] downloaded {tmp.stat().st_size} bytes", flush=True)

    from app.ai_engine import VoiceRecognitionEngine
    print("[smoke] loading engine (ECAPA + X-Vector)…", flush=True)
    eng = VoiceRecognitionEngine()

    print("[smoke] extracting fingerprint…", flush=True)
    emb = eng.process_audio_file(tmp)

    assert isinstance(emb, np.ndarray), f"embedding not ndarray: {type(emb)}"
    assert emb.ndim == 1 and emb.size >= 192, f"unexpected shape: {emb.shape}"
    norm = float(np.linalg.norm(emb))
    assert 0.9 < norm < 1.1, f"embedding not L2-normalised: norm={norm}"
    assert np.isfinite(emb).all(), "embedding has NaN/Inf"

    print(f"[smoke] OK  dim={emb.size}  norm={norm:.4f}  head={emb[:4].tolist()}", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[smoke] FAILED: {e}", flush=True)
        raise
