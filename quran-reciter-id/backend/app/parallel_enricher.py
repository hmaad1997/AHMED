"""Parallel batch enricher — process many reciters concurrently.

Wraps `multi_source_enricher` with an asyncio semaphore so we can push
5-10x more reciters per hour on a single Render worker.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

from .multi_source_enricher import enrich_reciter

logger = logging.getLogger(__name__)

# Global run stats (in-memory; resets on restart)
STATS: Dict[str, Any] = {
    "total_runs": 0,
    "total_reciters": 0,
    "total_fingerprints_added": 0,
    "last_run_at": None,
    "last_run_seconds": 0.0,
    "last_batch": [],
    "running": False,
}


async def _one(name: str, max_per_source: int, sem: asyncio.Semaphore) -> Dict[str, Any]:
    async with sem:
        loop = asyncio.get_running_loop()
        try:
            res = await loop.run_in_executor(
                None, lambda: enrich_reciter(name, max_per_source, True)
            )
            return {"name": name, "ok": True, **res}
        except Exception as exc:  # noqa: BLE001
            logger.exception("enrich failed for %s", name)
            return {"name": name, "ok": False, "error": str(exc)}


async def enrich_parallel(
    names: List[str],
    concurrency: int = 4,
    max_per_source: int = 2,
) -> Dict[str, Any]:
    """Enrich a batch of reciters in parallel with a concurrency cap."""
    if STATS["running"]:
        return {"ok": False, "error": "another batch is already running", "stats": STATS}

    STATS["running"] = True
    started = time.time()
    sem = asyncio.Semaphore(max(1, concurrency))
    try:
        results = await asyncio.gather(
            *(_one(n, max_per_source, sem) for n in names)
        )
        added = sum(int(r.get("added", 0) or 0) for r in results if r.get("ok"))
        elapsed = time.time() - started
        STATS["total_runs"] += 1
        STATS["total_reciters"] += len(names)
        STATS["total_fingerprints_added"] += added
        STATS["last_run_at"] = started
        STATS["last_run_seconds"] = round(elapsed, 2)
        STATS["last_batch"] = results[-20:]
        return {
            "ok": True,
            "count": len(names),
            "added": added,
            "seconds": round(elapsed, 2),
            "results": results,
        }
    finally:
        STATS["running"] = False


def get_stats() -> Dict[str, Any]:
    return dict(STATS)
