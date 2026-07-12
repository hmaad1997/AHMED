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
DB_PATH = DATA_DIR / "embeddings" / "reciter_database.json"
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




# ---------- Source: alquran.cloud (via cdn.islamic.network) ----------

ALQURAN_EDITIONS = "https://api.alquran.cloud/v1/edition?format=audio&type=versebyverse"

def alquran_reciters() -> list[dict]:
    try:
        d = requests.get(ALQURAN_EDITIONS, headers=HEADERS, timeout=TIMEOUT).json()
        return d.get("data", []) if isinstance(d, dict) else []
    except Exception:
        return []

def alquran_samples(reciter: dict) -> Iterable[tuple[str, str]]:
    ident = reciter.get("identifier")
    if not ident:
        return
    # ayah numbers 1 (Al-Fatiha 1), 8 (Al-Fatiha), 293 (Al-Baqarah 286 end -> ~286), varied
    for ayah in (1, 8, 293, 1000, 2000):
        for br in (128, 64):
            yield f"https://cdn.islamic.network/quran/audio/{br}/{ident}/{ayah}.mp3", f"alquran_{ident}_{ayah}"

# ---------- Source: quranicaudio.com ----------

QURANICAUDIO_API = "https://quranicaudio.com/api/qaris"

def quranicaudio_reciters() -> list[dict]:
    try:
        d = requests.get(QURANICAUDIO_API, headers=HEADERS, timeout=TIMEOUT).json()
        return d if isinstance(d, list) else []
    except Exception:
        return []

def quranicaudio_samples(reciter: dict) -> Iterable[tuple[str, str]]:
    rel = reciter.get("relative_path") or ""
    if not rel:
        return
    rel = rel.rstrip("/") + "/"
    for surah in (1, 36, 55, 67, 112):
        yield f"https://download.quranicaudio.com/quran/{rel}{surah:03d}.mp3", f"qa_{surah}"

# ---------- Source: islamic.network mirror aliases ----------
# Many extra reciters are keyed as ar.<slug> on cdn.islamic.network but not in alquran.cloud editions.
# Try a curated list of well-known identifiers not always returned by /edition.
EXTRA_ISLAMIC_NETWORK = [
    ("ar.abdurrahmaansudais", "عبد الرحمن السديس"),
    ("ar.saudalshuraim", "سعود الشريم"),
    ("ar.mahermuaiqly", "ماهر المعيقلي"),
    ("ar.hanirifai", "هاني الرفاعي"),
    ("ar.abdulsamad", "عبد الباسط عبد الصمد"),
    ("ar.minshawi", "محمد صديق المنشاوي"),
    ("ar.husary", "محمود خليل الحصري"),
    ("ar.husarymujawwad", "محمود خليل الحصري (مجود)"),
    ("ar.aymanswoaid", "أيمن سويد"),
    ("ar.hudhaify", "علي بن عبد الرحمن الحذيفي"),
    ("ar.ibrahimakhbar", "إبراهيم الأخضر"),
    ("ar.mohammadayyoub", "محمد أيوب"),
    ("ar.muhammadjibreel", "محمد جبريل"),
    ("ar.parhizgar", "شهریار پرهیزگار"),
    ("ar.shaatree", "أبو بكر الشاطري"),
    ("ar.ahmedajamy", "أحمد بن علي العجمي"),
    ("ar.aymansweid", "أيمن سويد"),
    ("ar.abdulbasitmurattal", "عبد الباسط عبد الصمد (مرتل)"),
]

def extra_islamic_network_reciters() -> list[dict]:
    return [{"identifier": ident, "name_ar": ar} for ident, ar in EXTRA_ISLAMIC_NETWORK]

def extra_islamic_network_samples(reciter: dict) -> Iterable[tuple[str, str]]:
    ident = reciter["identifier"]
    for ayah in (1, 8, 293, 1000, 2000):
        yield f"https://cdn.islamic.network/quran/audio/128/{ident}/{ayah}.mp3", f"in_{ayah}"


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


    # 3) alquran.cloud (verse-by-verse editions, served via cdn.islamic.network)
    log("Source: alquran.cloud / cdn.islamic.network")
    for r in alquran_reciters():
        name_ar = r.get("name") or r.get("englishName") or ""
        rid = f"aq_{r.get('identifier','').replace('.', '_')}"
        process(name_ar, rid, alquran_samples(r), "alquran.cloud")

    # 4) quranicaudio.com
    log("Source: quranicaudio.com")
    for r in quranicaudio_reciters():
        name_ar = r.get("arabic_name") or r.get("name") or ""
        rid = f"qa_{normalize(r.get('name','')).replace(' ', '_')}"[:60]
        process(name_ar, rid, quranicaudio_samples(r), "quranicaudio.com")

    # 5) Extra curated islamic.network identifiers
    log("Source: islamic.network (curated extras)")
    for r in extra_islamic_network_reciters():
        rid = f"in_{r['identifier'].replace('.', '_')}"
        process(r["name_ar"], rid, extra_islamic_network_samples(r), "islamic.network")

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

