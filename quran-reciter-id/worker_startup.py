"""Starts Auto-Fingerprint worker + registers /fingerprint-worker + /youtube-enrich endpoints."""
try:
    try:
        from .auto_fingerprint_worker import start_worker_thread, get_state
    except Exception:
        from auto_fingerprint_worker import start_worker_thread, get_state  # type: ignore

    start_worker_thread()

    try:
        from .main import app
        from fastapi import APIRouter
        from pydantic import BaseModel
        from typing import List, Optional

        try:
            from .youtube_enricher import enrich_reciter, enrich_batch_async, get_state as yt_state
        except Exception:
            from app.youtube_enricher import enrich_reciter, enrich_batch_async, get_state as yt_state

        router = APIRouter()

        @router.get("/fingerprint-worker/status")
        def _fp_status():
            return get_state()

        class YTReq(BaseModel):
            reciter: str
            max_videos: Optional[int] = 2

        class YTBatchReq(BaseModel):
            reciters: List[str]
            max_videos: Optional[int] = 1

        @router.post("/youtube-enrich")
        def _yt_enrich(req: YTReq):
            """يبحث بيوتيوب عن قارئ وينزّل حتى max_videos تلاوة ويحفظها كبصمة."""
            return enrich_reciter(req.reciter, max_videos=req.max_videos or 2)

        @router.post("/youtube-enrich-batch")
        def _yt_batch(req: YTBatchReq):
            """يشغّل قائمة قراء بالخلفية."""
            return enrich_batch_async(req.reciters, max_videos=req.max_videos or 1)

        @router.get("/youtube-enrich/status")
        def _yt_status():
            return yt_state()

        app.include_router(router)
        print("[AutoFP] endpoints ready: /fingerprint-worker/status /youtube-enrich /youtube-enrich-batch", flush=True)
    except Exception as exc:
        print(f"[AutoFP] register endpoints failed: {exc}", flush=True)
except Exception as exc:
    print(f"[AutoFP] load failed: {exc}", flush=True)
