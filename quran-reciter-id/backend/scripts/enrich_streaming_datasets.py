"""
Streaming enrichment from large HuggingFace Quran datasets.

Datasets:
  - tarteel-ai/everyayah   (~200 reciters, studio quality)
  - Wider-Community/quranic-universal-audio  (multi-reciter, community)

Uses the HF datasets-server API to sample rows without downloading full data.
Downloads only up to N samples per NEW reciter, computes ensemble embeddings,
and stores as multi-fingerprints (`Name#i`).
"""
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

import requests

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

DB_PATH = BACKEND / "data" / "embeddings" / "reciter_database.json"
META_PATH = BACKEND / "data" / "reciters_metadata.json"

DATASETS = [
    {
        "name": "tarteel-ai/everyayah",
        "config": "default",
        "split": "train",
        "reciter_col": "reciter",
        "audio_col": "audio",
    },
    {
        "name": "Wider-Community/quranic-universal-audio",
        "config": "default",
        "split": "train",
        "reciter_col": "reciter",
        "audio_col": "audio",
    },
]

SAMPLES_PER_RECITER = int(os.environ.get("HF_SAMPLES", "3"))
MAX_ROWS_PER_DS = int(os.environ.get("HF_MAX_ROWS", "8000"))
BATCH = 100


def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"[إأآا]", "ا", s)
    s = re.sub(r"[ىي]", "ي", s)
    s = re.sub(r"ة", "ه", s)
    s = re.sub(r"[ًٌٍَُِّْـ]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _load_bases() -> set:
    if not DB_PATH.exists():
        return set()
    with open(DB_PATH, encoding="utf-8") as f:
        db = json.load(f)
    return {_norm(r["reciter_name"].split("#")[0]) for r in db.get("reciters", [])}


def _iter_rows(ds_name: str, config: str, split: str, max_rows: int):
    """Stride-sample rows via datasets-server."""
    # First get row count
    try:
        info = requests.get(
            "https://datasets-server.huggingface.co/info",
            params={"dataset": ds_name, "config": config},
            timeout=30,
        ).json()
        total = info.get("dataset_info", {}).get(config, {}).get("splits", {}).get(split, {}).get("num_examples", 0)
    except Exception as e:
        print(f"  [warn] info failed for {ds_name}: {e}", flush=True)
        total = max_rows * 2
    if total == 0:
        total = max_rows * 2
    stride = max(1, total // max_rows)
    print(f"  dataset rows: {total}, sampling every {stride}", flush=True)

    offset = 0
    fetched = 0
    while fetched < max_rows:
        try:
            r = requests.get(
                "https://datasets-server.huggingface.co/rows",
                params={"dataset": ds_name, "config": config, "split": split,
                        "offset": offset, "length": BATCH},
                timeout=60,
            )
            if r.status_code != 200:
                print(f"  [warn] rows {offset}: HTTP {r.status_code}", flush=True)
                offset += BATCH * stride
                continue
            data = r.json()
            rows = data.get("rows", [])
            if not rows:
                break
            for item in rows:
                yield item.get("row", {})
                fetched += 1
                if fetched >= max_rows:
                    return
            offset += BATCH * stride
        except Exception as e:
            print(f"  [warn] fetch err: {e}", flush=True)
            offset += BATCH * stride


def _download_audio(url: str, out: Path) -> bool:
    try:
        r = requests.get(url, timeout=60, stream=True)
        if r.status_code != 200:
            return False
        with open(out, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        return out.stat().st_size > 5000
    except Exception:
        return False


def main():
    print("=" * 70, flush=True)
    print("Streaming enrichment: tarteel-ai + Wider-Community", flush=True)
    print("=" * 70, flush=True)

    existing = _load_bases()
    print(f"DB currently covers: {len(existing)} unique reciters", flush=True)

    from app.ai_engine import VoiceRecognitionEngine
    print("Loading AI engine...", flush=True)
    eng = VoiceRecognitionEngine()

    if DB_PATH.exists():
        db = json.load(open(DB_PATH, encoding="utf-8"))
    else:
        db = {"version": "3.0-ensemble", "reciters": []}
    meta = json.load(open(META_PATH, encoding="utf-8")) if META_PATH.exists() else {"reciters": []}

    per_reciter_count = {}
    total_added = 0

    for ds in DATASETS:
        print(f"\n=== {ds['name']} ===", flush=True)
        try:
            for row in _iter_rows(ds["name"], ds["config"], ds["split"], MAX_ROWS_PER_DS):
                reciter = row.get(ds["reciter_col"]) or row.get("speaker") or row.get("qari")
                if not reciter:
                    continue
                key = _norm(reciter)
                if not key or key in existing:
                    continue
                if per_reciter_count.get(key, 0) >= SAMPLES_PER_RECITER:
                    continue
                audio = row.get(ds["audio_col"], {})
                url = audio.get("src") if isinstance(audio, dict) else None
                if not url:
                    continue
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tp = Path(tmp.name)
                try:
                    if not _download_audio(url, tp):
                        continue
                    if not eng.validate_audio_duration(tp, min_duration_sec=4):
                        continue
                    emb = eng.process_audio_file(tp)
                    idx = per_reciter_count.get(key, 0)
                    db["reciters"].append({
                        "reciter_name": f"{reciter}#{idx+100}",  # offset to avoid clash
                        "embedding": emb.tolist(),
                        "source": ds["name"],
                    })
                    per_reciter_count[key] = idx + 1
                    total_added += 1
                    if per_reciter_count[key] == 1:
                        meta["reciters"].append({
                            "name": reciter, "name_english": reciter, "country": "-",
                            "bio": f"مضاف من {ds['name']}", "birth_year": "-",
                            "death_year": None, "image_url": "", "recitation_style": "-",
                        })
                    if total_added % 25 == 0:
                        _save(db, meta)
                        print(f"  progress: +{total_added} fingerprints", flush=True)
                finally:
                    try: tp.unlink()
                    except Exception: pass
        except Exception as e:
            print(f"  [ds error] {e}", flush=True)

    _save(db, meta)
    print(f"\n{'='*70}\nDONE — added {total_added} fingerprints", flush=True)


def _save(db, meta):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    json.dump(db, open(DB_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(meta, open(META_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("interrupted")
