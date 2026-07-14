"""Starts the Auto-Fingerprint worker when Uvicorn imports the app package."""
try:
    try:
        from .auto_fingerprint_worker import start_worker_thread, get_state
    except Exception:
        from auto_fingerprint_worker import start_worker_thread, get_state  # type: ignore

    start_worker_thread()

    try:
        from .main import app
        from fastapi import APIRouter

        router = APIRouter()

        @router.get("/fingerprint-worker/status")
        def _fp_status():
            return get_state()

        app.include_router(router)
        print("[AutoFP] endpoint /fingerprint-worker/status جاهز", flush=True)
    except Exception as exc:
        print(f"[AutoFP] تعذر تسجيل endpoint: {exc}", flush=True)
except Exception as exc:
    print(f"[AutoFP] فشل التحميل: {exc}", flush=True)
