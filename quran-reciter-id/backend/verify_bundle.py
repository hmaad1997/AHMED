"""CI guard: refuse to build an EXE without a usable bundled fingerprint DB."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

DB_PATH = Path("data/embeddings/reciter_database.json")
META_PATH = Path("data/reciters_metadata.json")


def main() -> int:
    if not DB_PATH.exists():
        raise SystemExit("reciter_database.json is missing — refusing to build empty EXE")

    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    reciters = db.get("reciters", [])
    if not isinstance(reciters, list):
        raise SystemExit("reciter_database.json schema must be {reciters: [...]}" )
    if len(reciters) < 100:
        raise SystemExit(f"Only {len(reciters)} fingerprints found — refusing to build weak/empty EXE")

    bad = [idx for idx, r in enumerate(reciters[:50]) if not r.get("reciter_name") or not r.get("embedding")]
    if bad:
        raise SystemExit(f"Invalid reciter rows at indexes: {bad[:10]}")

    dims = sorted({len(r.get("embedding", [])) for r in reciters[: min(50, len(reciters))]})
    if not dims or min(dims) < 128:
        raise SystemExit(f"Invalid embedding dimensions: {dims}")

    # Exercise app-side scoring with a larger query vector. This catches the old
    # bug where an Ensemble query vector crashed against ECAPA-only DB vectors.
    from app.main import _score_all

    sample_vecs = {r["reciter_name"]: np.array(r["embedding"], dtype=np.float32) for r in reciters[:20]}
    query_dim = max(max(dims), 192) + 192
    query = np.ones(query_dim, dtype=np.float32)
    ranked = _score_all(query, sample_vecs)
    if not ranked or not np.isfinite(ranked[0][1]):
        raise SystemExit("Scoring guard failed: no finite similarity produced")

    print(f"OK bundled DB: {len(reciters)} fingerprints, sample dims={dims}")
    print(f"OK scoring compatibility: query_dim={query_dim}, top={ranked[0][0]}:{ranked[0][1]:.4f}")

    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8")).get("reciters", [])
        print(f"OK metadata: {len(meta)} reciters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
