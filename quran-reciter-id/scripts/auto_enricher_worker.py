"""GitHub Actions worker — runs every 6h to auto-add fingerprints.

Reads the reciters list, splits into chunks, and posts to the running
Render backend `/batch-parallel` endpoint. No secrets required: uses
the public backend URL.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib import request, error

BACKEND = os.environ.get("BACKEND_URL", "https://ahmed-aew3.onrender.com").rstrip("/")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "4"))
MAX_BATCHES = int(os.environ.get("MAX_BATCHES", "3"))  # 3 * 10 = 30 reciters per run
MAX_PER_SOURCE = int(os.environ.get("MAX_PER_SOURCE", "2"))
STATE_PATH = Path(os.environ.get("STATE_PATH", ".enrich_state.json"))
RECITERS_PATH = Path(os.environ.get("RECITERS_PATH", "quran-reciter-id/data/reciters.json"))


def _load_reciters() -> list[str]:
    if not RECITERS_PATH.exists():
        print(f"[warn] reciters file not found: {RECITERS_PATH}", flush=True)
        return []
    raw = json.loads(RECITERS_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [r if isinstance(r, str) else r.get("name", "") for r in raw if r]
    return []


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"cursor": 0}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _post(path: str, body: dict, timeout: int = 900) -> dict:
    req = request.Request(
        f"{BACKEND}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, timeout: int = 30) -> dict:
    with request.urlopen(f"{BACKEND}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    reciters = _load_reciters()
    if not reciters:
        print("[error] no reciters", flush=True)
        return 1
    state = _load_state()
    cursor = int(state.get("cursor", 0)) % len(reciters)

    print(f"[info] {len(reciters)} reciters total, starting at cursor={cursor}", flush=True)
    try:
        health = _get("/health")
        print(f"[info] backend health: ai={health.get('ai')} db={health.get('db_status')}", flush=True)
    except error.URLError as exc:
        print(f"[error] backend unreachable: {exc}", flush=True)
        return 2

    grand_added = 0
    for i in range(MAX_BATCHES):
        chunk = []
        for _ in range(BATCH_SIZE):
            chunk.append(reciters[cursor % len(reciters)])
            cursor += 1
        print(f"[batch {i + 1}/{MAX_BATCHES}] {chunk}", flush=True)
        try:
            res = _post(
                "/batch-parallel",
                {"names": chunk, "concurrency": CONCURRENCY, "max_per_source": MAX_PER_SOURCE},
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] batch failed: {exc}", flush=True)
            time.sleep(30)
            continue
        added = int(res.get("added", 0) or 0)
        grand_added += added
        print(f"[batch {i + 1}] added={added} in {res.get('seconds')}s", flush=True)
        time.sleep(5)

    state["cursor"] = cursor % len(reciters)
    state["last_run"] = int(time.time())
    state["last_added"] = grand_added
    _save_state(state)
    print(f"[done] total fingerprints added this run: {grand_added}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
