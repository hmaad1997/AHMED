"""FastAPI Backend Server for Quran Reciter ID — with user reciters + UI."""
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging, tempfile, sys
from typing import Optional, List

from .models import IdentificationResult, ReciterListResponse, ErrorResponse, ReciterInfo
from .ai_engine import VoiceRecognitionEngine
from .database import ReciterDatabase
from .user_db import UserReciterDB
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Quran Reciter ID API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ai_engine: Optional[VoiceRecognitionEngine] = None
database: Optional[ReciterDatabase] = None
user_db: Optional[UserReciterDB] = None

# Paths — support PyInstaller bundle
_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
EMBEDDINGS_PATH = _BASE / "data" / "embeddings" / "reciter_database.json"
METADATA_PATH = _BASE / "data" / "reciters_metadata.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = _BASE / "app" / "static"


@app.on_event("startup")
async def startup_event():
    global ai_engine, database, user_db
    logger.info("=== STARTING QURAN RECITER ID SERVER ===")
    ai_engine = VoiceRecognitionEngine()
    try:
        database = ReciterDatabase(EMBEDDINGS_PATH, METADATA_PATH)
    except FileNotFoundError:
        logger.warning("Built-in database not found — running with user reciters only")
        database = None
    user_db = UserReciterDB()
    logger.info(f"✓ Data folder: {user_db.get_data_path()}")
    logger.info("✓ SERVER READY")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"service": "Quran Reciter ID API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "ai": ai_engine is not None,
            "builtin_reciters": len(database.reciter_vectors) if database else 0,
            "user_reciters": len(user_db.data) if user_db else 0,
            "data_path": user_db.get_data_path() if user_db else ""}


def _all_vectors():
    """Merge built-in + user embeddings."""
    vecs = {}
    if database:
        vecs.update(database.reciter_vectors)
    if user_db:
        vecs.update(user_db.vectors())
    return vecs


def _get_info(name: str):
    if user_db and name in user_db.data:
        r = user_db.data[name]
        return {"name": r["name"], "name_english": r.get("name_english", name),
                "country": r.get("country", "مخصّص"), "bio": r.get("bio", ""),
                "birth_year": r.get("birth_year", "-"), "death_year": r.get("death_year"),
                "image_url": r.get("image_url", ""), "recitation_style": r.get("recitation_style", "مخصّص")}
    if database:
        return database.get_reciter_info(name)
    return None


@app.post("/identify-reciter", response_model=IdentificationResult)
async def identify_reciter(audio_file: UploadFile = File(...)):
    if ai_engine is None:
        raise HTTPException(503, "Service not initialized")
    vecs = _all_vectors()
    if not vecs:
        raise HTTPException(400, "لا يوجد قرّاء في قاعدة البيانات — أضف قارئاً أولاً")

    audio_bytes = await audio_file.read()
    with tempfile.NamedTemporaryFile(suffix=Path(audio_file.filename or "a.wav").suffix or ".wav", delete=False) as tmp:
        tmp.write(audio_bytes); tmp_path = Path(tmp.name)
    try:
        if not ai_engine.validate_audio_duration(tmp_path, min_duration_sec=3.0):
            raise HTTPException(400, "الملف قصير جداً — يجب أن يكون 3 ثوانٍ على الأقل")
        q = ai_engine.process_audio_file(tmp_path).reshape(1, -1)
        scored = sorted(
            ((n, float(cosine_similarity(q, v.reshape(1, -1))[0][0])) for n, v in vecs.items()),
            key=lambda x: x[1], reverse=True
        )
        name, sim = scored[0]
        info = _get_info(name) or {"name": name, "name_english": name, "country": "-",
                                    "bio": "", "birth_year": "-", "death_year": None,
                                    "image_url": "", "recitation_style": "-"}
        confidence = min(sim * 1.1, 1.0)
        result = IdentificationResult(
            success=True, reciter_name=info["name"], reciter_name_english=info["name_english"],
            confidence=confidence, country=info["country"], bio=info["bio"],
            birth_year=info["birth_year"], death_year=info.get("death_year"),
            image_url=info["image_url"], recitation_style=info["recitation_style"],
            similarity_score=sim,
        )
        if user_db:
            user_db.log_identification({
                "reciter": name, "confidence": confidence, "similarity": sim,
                "filename": audio_file.filename,
                "top3": [{"name": n, "score": s} for n, s in scored[:3]],
            })
        return result
    finally:
        try: tmp_path.unlink()
        except Exception: pass


@app.post("/reciters/add")
async def add_reciter(
    name: str = Form(...),
    country: str = Form(""),
    bio: str = Form(""),
    audio_files: List[UploadFile] = File(...),
):
    """أضف قارئاً جديداً بصوته — يمكن رفع عدة عينات لدقة أعلى."""
    if ai_engine is None or user_db is None:
        raise HTTPException(503, "Service not initialized")
    blobs, names = [], []
    for f in audio_files:
        blobs.append(await f.read())
        names.append(f.filename or "audio.wav")
    try:
        res = user_db.add_reciter(name, blobs, names, ai_engine, country=country, bio=bio)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "message": f"تم حفظ القارئ «{res['name']}» مع {res['samples']} عيّنة", **res}


@app.delete("/reciters/{name}")
async def delete_reciter(name: str):
    if user_db is None:
        raise HTTPException(503, "Service not initialized")
    ok = user_db.delete_reciter(name)
    if not ok:
        raise HTTPException(404, "القارئ غير موجود في قائمة المستخدم")
    return {"success": True, "message": f"تم حذف «{name}»"}


@app.get("/list-reciters", response_model=ReciterListResponse)
async def list_reciters():
    combined = []
    idx = 1
    if database:
        for r in database.get_all_reciters():
            combined.append(ReciterInfo(id=r.get("id", idx), name=r["name"],
                name_english=r["name_english"], country=r["country"], bio=r["bio"],
                birth_year=r["birth_year"], death_year=r.get("death_year"),
                image_url=r["image_url"], recitation_style=r["recitation_style"]))
            idx += 1
    if user_db:
        for r in user_db.list_reciters():
            combined.append(ReciterInfo(id=idx, name=r["name"], name_english=r["name_english"],
                country=r["country"], bio=r["bio"], birth_year=r["birth_year"],
                death_year=r.get("death_year"), image_url=r["image_url"],
                recitation_style=r["recitation_style"]))
            idx += 1
    return ReciterListResponse(success=True, total_reciters=len(combined), reciters=combined)


@app.get("/history")
async def history(limit: int = 100):
    if user_db is None:
        return {"items": []}
    return {"items": user_db.list_history(limit=limit), "data_path": user_db.get_data_path()}


@app.exception_handler(Exception)
async def gxh(request, exc):
    logger.exception("unhandled")
    return JSONResponse(status_code=500, content={"success": False, "error": "Internal", "detail": str(exc)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
