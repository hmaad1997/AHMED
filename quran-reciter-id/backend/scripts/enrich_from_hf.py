"""Enrich reciter DB from Hugging Face large audio datasets — stream via
datasets-server API (no 26GB parquet download).

Source:
  abdu-l7hman/quran-reciters-8sec-dataset
    106,128 clips × 8s, labeled with reciter name.
    We uniformly sample the dataset (strided offsets) to hit every reciter
    cluster, then download up to N clips per new reciter and embed.

Runtime budget:
  ~300 API calls (100 rows each) + ~1500 tiny WAV downloads.
  Total ≈ 25-40 min on GitHub Actions. Adds ~500 new reciters typically.
"""
from __future__ import annotations
import io, json, os, re, sys, tempfile, time, random
from pathlib import Path
from collections import defaultdict

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "embeddings" / "reciter_database.json"
NAMES_PATH = DATA_DIR / "arabic_names.json"

DATASET = "abdu-l7hman/quran-reciters-8sec-dataset"
TOTAL_ROWS = 106128
BATCH = 100
MAX_API_CALLS = 320                # ~32,000 rows scanned (30% of dataset)
MAX_SAMPLES_PER_RECITER = 3
MIN_SAMPLES_PER_RECITER = 1
DOWNLOAD_TIMEOUT = 30
API_TIMEOUT = 60

HEADERS = {"User-Agent": "QuranReciterID/2.0 (+github.com/hmaad1997/AHMED)"}


def _norm(s: str) -> str:
    return re.sub(r"[^\w\u0600-\u06FF]+", "", (s or "").lower())


def _load_json(p: Path, default):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_db(db: dict):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_rows(offset: int) -> list[dict]:
    url = (
        f"https://datasets-server.huggingface.co/rows?dataset={DATASET}"
        f"&config=default&split=train&offset={offset}&length={BATCH}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=API_TIMEOUT)
        if r.status_code != 200:
            print(f"[api] offset={offset} status={r.status_code}", flush=True)
            return []
        return r.json().get("rows", [])
    except Exception as e:
        print(f"[api] offset={offset} err={e}", flush=True)
        return []


def _embed_url(engine, url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=DOWNLOAD_TIMEOUT)
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
            t.write(r.content)
            p = Path(t.name)
        try:
            return engine.process_audio_file(p)
        finally:
            try: p.unlink()
            except Exception: pass
    except Exception as e:
        print(f"[embed] fail: {e}", flush=True)
        return None


def main():
    sys.path.insert(0, str(ROOT))
    print("=" * 60, flush=True)
    print("HF DATASET ENRICHMENT — abdu-l7hman/quran-reciters-8sec-dataset", flush=True)
    print("=" * 60, flush=True)

    from app.ai_engine import VoiceRecognitionEngine
    print("[init] loading SpeechBrain model...", flush=True)
    engine = VoiceRecognitionEngine()
    print("[init] ✓ model ready", flush=True)

    db = _load_json(DB_PATH, {})
    have_norm = {_norm(k) for k in db.keys()}
    # Also normalize known english aliases to skip duplicates
    for v in db.values():
        if isinstance(v, dict):
            en = v.get("name_english") or ""
            if en: have_norm.add(_norm(en))
    arabic_names = _load_json(NAMES_PATH, {})
    print(f"[init] existing DB: {len(db)} reciters", flush=True)

    # ── Phase 1: strided scan to collect audio URLs per reciter ─────────
    step = max(1, TOTAL_ROWS // MAX_API_CALLS)
    offsets = list(range(0, TOTAL_ROWS, step))[:MAX_API_CALLS]
    random.Random(42).shuffle(offsets)  # spread network load

    per_reciter: dict[str, list[str]] = defaultdict(list)
    scanned = 0
    for i, off in enumerate(offsets, 1):
        rows = _fetch_rows(off)
        scanned += len(rows)
        for item in rows:
            row = item.get("row", {})
            name = (row.get("reciter") or "").strip()
            if not name:
                continue
            if _norm(name) in have_norm:
                continue
            if len(per_reciter[name]) >= MAX_SAMPLES_PER_RECITER:
                continue
            audio = row.get("audio") or []
            if audio and isinstance(audio, list):
                src = audio[0].get("src") if isinstance(audio[0], dict) else None
                if src:
                    per_reciter[name].append(src)
        if i % 20 == 0:
            ready = sum(1 for v in per_reciter.values() if len(v) >= MIN_SAMPLES_PER_RECITER)
            print(f"[scan] {i}/{len(offsets)} calls | {scanned} rows | "
                  f"{len(per_reciter)} new reciters | {ready} embeddable", flush=True)
        time.sleep(0.1)  # gentle on API

    print(f"[scan] done — {scanned} rows scanned, "
          f"{len(per_reciter)} candidate reciters", flush=True)

    # ── Phase 2: download + embed ───────────────────────────────────────
    added = 0
    skipped = 0
    for idx, (name, urls) in enumerate(per_reciter.items(), 1):
        if not urls:
            skipped += 1
            continue
        embs = []
        for u in urls[:MAX_SAMPLES_PER_RECITER]:
            e = _embed_url(engine, u)
            if e is not None:
                embs.append(e)
        if not embs:
            skipped += 1
            continue
        mean = np.mean(np.stack(embs, axis=0), axis=0).tolist()
        display = arabic_names.get(_norm(name), name)
        db[display] = {
            "name": display,
            "name_english": name,
            "country": "-",
            "bio": "قارئ من قاعدة بيانات HF (106k clips) — تم استخراج البصمة من عيّنات حقيقية.",
            "birth_year": "-",
            "death_year": None,
            "image_url": "",
            "recitation_style": "-",
            "embedding": mean,
            "samples": len(embs),
            "source": "abdu-l7hman/quran-reciters-8sec-dataset",
        }
        added += 1
        if added % 25 == 0:
            _save_db(db)
            print(f"[save] checkpoint @ +{added} (skipped {skipped}) "
                  f"| total DB = {len(db)}", flush=True)

    _save_db(db)
    print("=" * 60, flush=True)
    print(f"[done] +{added} new reciters | skipped {skipped} | "
          f"TOTAL DB = {len(db)}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[abort] interrupted", flush=True)
        sys.exit(0)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(0)  # never fail the build
