"""يُستورد عند إقلاع Uvicorn لتشغيل Auto-Fingerprint Worker في الخلفية."""
try:
    from auto_fingerprint_worker import start_worker_thread, get_state
    start_worker_thread()

    # تسجيل endpoint للحالة على نفس تطبيق FastAPI
    try:
        from main import app  # type: ignore
        from fastapi import APIRouter
        r = APIRouter()

        @r.get("/fingerprint-worker/status")
        def _fp_status():
            return get_state()

        app.include_router(r)
        print("[AutoFP] endpoint /fingerprint-worker/status جاهز", flush=True)
    except Exception as e:
        print(f"[AutoFP] تعذّر تسجيل endpoint: {e}", flush=True)
except Exception as e:
    print(f"[AutoFP] فشل التحميل: {e}", flush=True)
