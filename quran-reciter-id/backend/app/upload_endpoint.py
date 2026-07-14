import os, logging
from typing import Any, Dict, Optional
from fastapi import HTTPException, Header
log = logging.getLogger(__name__)
def register(app):
    from . import fingerprint_db as db
    TOK = os.environ.get("UPLOAD_TOKEN", "")
    @app.post("/upload-fingerprints")
    async def up(payload: Dict[str, Any], authorization: Optional[str] = Header(default=None)):
        if not TOK: raise HTTPException(500, "UPLOAD_TOKEN not set")
        if (authorization or "").replace("Bearer ", "").strip() != TOK:
            raise HTTPException(401, "invalid token")
        items = payload.get("items") or []
        if not isinstance(items, list) or not items:
            raise HTTPException(400, "items required")
        ar = af = sk = 0
        for it in items:
            try:
                n = (it.get("reciter_name") or "").strip()
                h = it.get("hashes") or []
                if not n or not h: sk += 1; continue
                rid = db.upsert_reciter_sync(name_ar=n)
                rc = db.insert_recitation_sync(reciter_id=rid,
                    surah_number=int(it.get("surah_number") or 0),
                    surah_name_ar=it.get("surah_name_ar") or "",
                    source=it.get("source") or "local",
                    source_url=it.get("source_url"),
                    duration_sec=it.get("duration_sec"))
                db.bulk_insert_fingerprints_sync(rc, [(int(a), int(b)) for a, b in h])
                ar += 1; af += len(h)
            except Exception as e:
                log.warning("skip: %s", e); sk += 1
        return {"ok": True, "recitations_added": ar, "hashes_added": af, "skipped": sk, **db.stats_sync()}
    @app.get("/upload-fingerprints/stats")
    async def st(): return db.stats_sync()
    log.info("/upload-fingerprints registered")
