"""
PostgreSQL storage layer for the fingerprint engine.
Uses Supabase (Lovable Cloud) via psycopg2 with the service_role key.

Environment variables required:
  SUPABASE_URL              e.g. https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY (only used for direct connection; you can use
                              Supabase REST API alternatively)

For simplicity we use the Supabase REST API here (no direct pg connection).
"""
from __future__ import annotations
import os
from collections import Counter
from typing import Optional
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

MATCH_THRESHOLD = 30  # minimum aligned hashes required for a valid match


def _rest(path: str) -> str:
    return f"{SUPABASE_URL}/rest/v1{path}"


async def insert_recitation(
    reciter_id: str,
    surah_number: int,
    surah_name_ar: str,
    source: str,
    riwayah: str | None = None,
    source_url: str | None = None,
    duration_sec: int | None = None,
) -> str:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            _rest("/recitations"),
            headers=_HEADERS,
            json={
                "reciter_id": reciter_id,
                "surah_number": surah_number,
                "surah_name_ar": surah_name_ar,
                "source": source,
                "riwayah": riwayah,
                "source_url": source_url,
                "duration_sec": duration_sec,
            },
        )
        r.raise_for_status()
        return r.json()[0]["id"]


async def bulk_insert_fingerprints(recitation_id: str, hashes: list[tuple[int, int]]):
    """Batches of 5000 rows."""
    rows = [{"recitation_id": recitation_id, "hash": h, "offset_ms": off} for h, off in hashes]
    async with httpx.AsyncClient(timeout=60) as c:
        for i in range(0, len(rows), 5000):
            batch = rows[i : i + 5000]
            r = await c.post(_rest("/fingerprints"), headers={**_HEADERS, "Prefer": "return=minimal"}, json=batch)
            r.raise_for_status()
    # update count
    async with httpx.AsyncClient(timeout=15) as c:
        await c.patch(
            _rest(f"/recitations?id=eq.{recitation_id}"),
            headers=_HEADERS,
            json={"fingerprint_count": len(rows)},
        )


async def match_fingerprints(query_hashes: list[tuple[int, int]]) -> Optional[dict]:
    """Query the DB for matching hashes and align them by time.
    Returns the best-matched recitation with metadata, or None if under threshold.
    """
    if not query_hashes:
        return None

    # Query in chunks (Postgres IN clause limit ~1000)
    hash_to_query_offset = {h: off for h, off in query_hashes}
    hashes = list(hash_to_query_offset.keys())

    matched_rows = []
    async with httpx.AsyncClient(timeout=30) as c:
        for i in range(0, len(hashes), 500):
            chunk = hashes[i : i + 500]
            in_clause = ",".join(str(h) for h in chunk)
            r = await c.get(
                _rest(f"/fingerprints?hash=in.({in_clause})&select=recitation_id,hash,offset_ms"),
                headers=_HEADERS,
            )
            r.raise_for_status()
            matched_rows.extend(r.json())

    if not matched_rows:
        return None

    # Time-alignment histogram: for each (recitation_id), count how many hashes
    # agree on the same (db_offset - query_offset) delta. Peak = true match.
    alignment_counter: Counter = Counter()
    for row in matched_rows:
        q_off = hash_to_query_offset.get(row["hash"])
        if q_off is None:
            continue
        delta = row["offset_ms"] - q_off
        alignment_counter[(row["recitation_id"], delta)] += 1

    if not alignment_counter:
        return None

    (best_rec_id, best_delta), best_count = alignment_counter.most_common(1)[0]
    if best_count < MATCH_THRESHOLD:
        return None

    # Fetch recitation + reciter details
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            _rest(
                f"/recitations?id=eq.{best_rec_id}"
                "&select=id,surah_number,surah_name_ar,riwayah,source,fingerprint_count,"
                "reciter:reciters(id,name_ar,name_en,country,image_url,bio)"
            ),
            headers=_HEADERS,
        )
        r.raise_for_status()
        rec = r.json()[0]

    match_score = min(1.0, best_count / max(50, len(query_hashes) * 0.1))
    return {
        "recitation_id": rec["id"],
        "surah_number": rec["surah_number"],
        "surah_name_ar": rec["surah_name_ar"],
        "riwayah": rec.get("riwayah"),
        "source": rec.get("source"),
        "offset_ms": max(0, best_delta),
        "match_score": match_score,
        "aligned_hashes": best_count,
        "reciter": rec.get("reciter"),
    }
