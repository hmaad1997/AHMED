"""
Enrich reciter fingerprint database using open-source audio from mp3quran.net.

For every reciter listed in the Excel file that is NOT already in the
pre-trained ECAPA database, this script:
  1. Fetches the reciter's audio server from https://mp3quran.net/api/v3/
  2. Downloads 3 short surah recordings (Al-Fatiha, Al-Ikhlas, Al-Kafirun)
  3. Trims each clip to ~10s to keep memory low
  4. Extracts an ECAPA-TDNN embedding per clip
  5. Stores the mean embedding as a fingerprint in reciter_database.json
  6. Appends the Arabic display name to arabic_names.json

Runs inside the GitHub Actions build job — no user interaction required.
Skips gracefully on network errors so a partial DB is always shipped.
"""
from __future__ import annotations
import json, os, sys, io, tempfile, time, re, unicodedata
from pathlib import Path
import requests
import numpy as np
import torch
import torchaudio
from difflib import SequenceMatcher

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
DB_PATH = DATA / "reciter_database.json"
NAMES_PATH = DATA / "arabic_names.json"
EXCEL_PATH = DATA / "reciters.xlsx"  # committed alongside build

MP3Q_API = "https://mp3quran.net/api/v3/reciters?language=ar"
SURAHS = [1, 112, 109]  # Fatiha, Ikhlas, Kafirun — short & universally recorded
MAX_SECONDS = 12
SAMPLE_RATE = 16000


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", s)  # remove diacritics/tatweel
    s = re.sub(r"[إأآا]", "ا", s)
    s = re.sub(r"[ى]", "ي", s)
    s = re.sub(r"[ة]", "ه", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip().lower()


def load_excel_names() -> list[str]:
    if not EXCEL_PATH.exists():
        return []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True)
        ws = wb.active
        names = []
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str) and cell.strip():
                    names.append(cell.strip())
        return list(dict.fromkeys(names))
    except Exception as e:
        print(f"[enrich] excel read failed: {e}")
        return []


def fetch_mp3quran() -> list[dict]:
    try:
        r = requests.get(MP3Q_API, timeout=30)
        r.raise_for_status()
        return r.json().get("reciters", [])
    except Exception as e:
        print(f"[enrich] mp3quran api failed: {e}")
        return []


def best_match(name: str, reciters: list[dict]) -> dict | None:
    n = norm(name)
    best, score = None, 0.0
    for r in reciters:
        for candidate in [r.get("name", "")] + [m.get("name", "") for m in r.get("moshaf", [])]:
            s = SequenceMatcher(None, n, norm(candidate)).ratio()
            if s > score:
                score, best = s, r
    return best if score >= 0.72 else None


def load_ecapa():
    from speechbrain.inference.speaker import EncoderClassifier
    model = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(BACKEND / "pretrained_models" / "ecapa"),
        run_opts={"device": "cpu"},
    )
    return model


def load_audio(url: str) -> torch.Tensor | None:
    try:
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            for chunk in r.iter_content(1 << 15):
                f.write(chunk)
                if f.tell() > 3_000_000:  # ~3 MB cap
                    break
            path = f.name
        wav, sr = torchaudio.load(path)
        os.unlink(path)
        if wav.shape[0] > 1:
            wav = wav.mean(0, keepdim=True)
        if sr != SAMPLE_RATE:
            wav = torchaudio.functional.resample(wav, sr, SAMPLE_RATE)
        max_len = MAX_SECONDS * SAMPLE_RATE
        # skip first 2s (intro/basmala) if possible
        start = min(2 * SAMPLE_RATE, wav.shape[1] // 4)
        wav = wav[:, start : start + max_len]
        if wav.shape[1] < SAMPLE_RATE:
            return None
        return wav
    except Exception as e:
        print(f"[enrich]   audio fail {url[:60]}: {e}")
        return None


def embed(model, wav: torch.Tensor) -> np.ndarray | None:
    try:
        with torch.no_grad():
            emb = model.encode_batch(wav).squeeze().cpu().numpy()
        return emb / (np.linalg.norm(emb) + 1e-9)
    except Exception as e:
        print(f"[enrich]   embed fail: {e}")
        return None


def main():
    db = json.loads(DB_PATH.read_text(encoding="utf-8")) if DB_PATH.exists() else {}
    names = json.loads(NAMES_PATH.read_text(encoding="utf-8")) if NAMES_PATH.exists() else {}
    existing_ar = {v for v in names.values()}

    excel = load_excel_names()
    print(f"[enrich] excel names: {len(excel)}  existing db keys: {len(db)}")

    missing = [n for n in excel if norm(n) not in {norm(v) for v in existing_ar}]
    print(f"[enrich] missing to enrich: {len(missing)}")
    if not missing:
        return

    reciters = fetch_mp3quran()
    print(f"[enrich] mp3quran reciters listed: {len(reciters)}")
    if not reciters:
        return

    model = load_ecapa()
    added = 0

    for arabic_name in missing:
        match = best_match(arabic_name, reciters)
        if not match:
            continue
        moshaf = (match.get("moshaf") or [{}])[0]
        base = (moshaf.get("server") or "").rstrip("/")
        if not base:
            continue
        embs = []
        for s in SURAHS:
            url = f"{base}/{s:03d}.mp3"
            wav = load_audio(url)
            if wav is None:
                continue
            e = embed(model, wav)
            if e is not None:
                embs.append(e)
            time.sleep(0.3)
        if len(embs) < 2:
            print(f"[enrich] skip {arabic_name}: only {len(embs)} embeddings")
            continue
        centroid = np.mean(embs, axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-9)
        key = f"mp3q_{re.sub(r'[^A-Za-z0-9]+', '_', match.get('name', arabic_name))}"
        db[key] = {"centroid": centroid.tolist(), "sub_centroids": [e.tolist() for e in embs]}
        names[key] = arabic_name
        added += 1
        print(f"[enrich] +++ {arabic_name}  ({len(embs)} samples)")

    DB_PATH.write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
    NAMES_PATH.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[enrich] done. added {added}. total reciters in DB: {len(db)}")


if __name__ == "__main__":
    main()
