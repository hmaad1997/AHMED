"""Multi-source reciter enrichment.

Pulls voice samples from several open sources (mp3quran.net, everyayah.com,
quranapi.pages.dev) for every reciter that is NOT already fingerprinted in
reciter_database.json, extracts ECAPA-TDNN embeddings, and merges them in.

Runs during the GitHub Actions build after build_pretrained_db.py.
"""
from __future__ import annotations
import io
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

import requests
import torch
import torchaudio
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "reciter_database.json"
NAMES_PATH = DATA_DIR / "arabic_names.json"

MP3QURAN_API = "https://mp3quran.net/api/v3/reciters?language=ar"
EVERYAYAH_INDEX = "https://everyayah.com/data/recitations.js"
QURANAPI_RECITERS = "https://quranapi.pages.dev/api/reciters.json"

SAMPLE_SURAHS = [112, 113, 114, 108, 103]  # short surahs
HEADERS = {"User-Agent": "QuranReciterID/1.0 (+github.com/hmaad1997/AHMED)"}
TIMEOUT = 30


def log(msg: str) -> None:
    print(f"[enrich] {msg}", flush=True)


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize(text: str) -> str:
    text = re.sub(r"[\u064B-\u0652\u0670]", "", text or "")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def load_encoder():
    from speechbrain.pretrained import EncoderClassifier
    log("Loading ECAPA-TDNN encoder…")
    return EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(ROOT / ".models" / "ecapa"),
        run_opts={"device": "cpu"},
    )


def embed_audio(encoder, wav_bytes: bytes) -> list[float] | None:
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(wav_bytes)
            tmp = f.name
        wav, sr = torchaudio.load(tmp)
        os.unlink(tmp)
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        # Trim to first 20 seconds
        if wav.shape[1] > 16000 * 20:
            wav = wav[:, : 16000 * 20]
        emb = encoder.encode_batch(wav).squeeze().detach().cpu().numpy()
        return emb.tolist()
    except Exception as e:
        log(f"  embed error: {e}")
        return None


def download(url: str, max_bytes: int = 8_000_000) -> bytes | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if r.status_code != 200:
            return None
        buf = io.BytesIO()
        for chunk in r.iter_content(65536):
            buf.write(chunk)
            if buf.tell() > max_bytes:
                break
        return buf.getvalue()
    except Exception:
        return None


# ---------- Source: mp3quran.net ----------

def mp3quran_reciters() -> list[dict]:
    try:
        data = requests.get(MP3QURAN_API, headers=HEADERS, timeout=TIMEOUT).json()
        return data.get("reciters", [])
    except Exception as e:
        log(f"mp3quran fetch failed: {e}")
        return []


def mp3quran_samples(reciter: dict) -> Iterable[tuple[str, str]]:
    for moshaf in reciter.get("moshaf", [])[:1]:
        server = moshaf.get("server", "").rstrip("/")
        surahs = str(moshaf.get("surah_list", ""))
        available = {int(s) for s in surahs.split(",") if s.isdigit()}
        for sn in SAMPLE_SURAHS:
            if sn in available:
                yield f"{server}/{sn:03d}.mp3", f"mp3quran_{sn}"


# ---------- Source: everyayah.com ----------

def everyayah_reciters() -> list[dict]:
    try:
        txt = requests.get(EVERYAYAH_INDEX, headers=HEADERS, timeout=TIMEOUT).text
        # File is a JS assignment: var Recitations = [ {...}, ... ];
        m = re.search(r"\[(.*)\]", txt, re.S)
        if not m:
            return []
        raw = "[" + m.group(1) + "]"
        # Convert JS-ish to JSON: quote keys, single->double quotes
        raw = re.sub(r"([{,]\s*)([A-Za-z_][\w]*)\s*:", r'\1"\2":', raw)
        raw = raw.replace("'", '"')
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        try:
            return json.loads(raw)
        except Exception:
            return []
    except Exception as e:
        log(f"everyayah fetch failed: {e}")
        return []


def everyayah_samples(reciter: dict) -> Iterable[tuple[str, str]]:
    subfolder = reciter.get("subfolder") or reciter.get("folder")
    if not subfolder:
        return
    base = f"https://everyayah.com/data/{subfolder}"
    for sn in SAMPLE_SURAHS:
        # everyayah format: SSSAAA.mp3  (surah 112 ayah 001 -> 112001.mp3)
        yield f"{base}/{sn:03d}001.mp3", f"everyayah_{sn}"


# ---------- Source: quranapi.pages.dev ----------

def quranapi_reciters() -> list[dict]:
    try:
        d = requests.get(QURANAPI_RECITERS, headers=HEADERS, timeout=TIMEOUT).json()
        return d if isinstance(d, list) else d.get("reciters", [])
    except Exception:
        return []


# ---------- Matching ----------

def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def already_have(name: str, existing_names: dict[str, str]) -> bool:
    n = normalize(name)
    for rid, ar in existing_names.items():
        if similar(name, ar) > 0.75 or similar(name, rid.replace("_", " ")) > 0.75:
            return True
    return False


def main() -> int:
    if not DB_PATH.exists():
        log("reciter_database.json missing — run build_pretrained_db.py first")
        return 0
    db = load_json(DB_PATH, {"reciters": {}})
    names = load_json(NAMES_PATH, {})
    existing = dict(names)

    encoder = load_encoder()

    added = 0
    tried = 0

    def process(name_ar: str, name_id: str, samples: Iterable[tuple[str, str]], source: str):
        nonlocal added, tried
        if already_have(name_ar, existing) or name_id in db["reciters"]:
            return
        tried += 1
        embeddings = []
        for url, tag in samples:
            audio = download(url)
            if not audio:
                continue
            emb = embed_audio(encoder, audio)
            if emb:
                embeddings.append(emb)
            if len(embeddings) >= 3:
                break
        if len(embeddings) >= 2:
            db["reciters"][name_id] = {
                "name_ar": name_ar,
                "source": source,
                "embeddings": embeddings,
            }
            existing[name_id] = name_ar
            names[name_id] = name_ar
            added += 1
            log(f"  ✅ {name_ar}  ({len(embeddings)} embeddings, {source})")
            if added % 5 == 0:
                save_json(DB_PATH, db)
                save_json(NAMES_PATH, names)

    # 1) mp3quran
    log("Source: mp3quran.net")
    for r in mp3quran_reciters():
        name_ar = r.get("name", "").strip()
        rid = f"mp3q_{r.get('id')}"
        process(name_ar, rid, mp3quran_samples(r), "mp3quran.net")

    # 2) everyayah
    log("Source: everyayah.com")
    for r in everyayah_reciters():
        name_ar = r.get("ename") or r.get("name") or ""
        rid = f"eay_{normalize(name_ar).replace(' ', '_')}"[:60]
        process(name_ar, rid, everyayah_samples(r), "everyayah.com")

    save_json(DB_PATH, db)
    save_json(NAMES_PATH, names)
    log(f"Done. Tried {tried} new reciters, added {added}. Total DB: {len(db['reciters'])}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(0)  # never fail the build
