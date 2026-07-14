"""FastAPI Backend — Multi-Stage Verification Pipeline → ONE final answer."""
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging, tempfile, sys, threading, time, re, os
from typing import Optional, List, Any, Dict

from .models import IdentificationResult, ReciterListResponse, ErrorResponse, ReciterInfo
from .database import ReciterDatabase
from .user_db import UserReciterDB
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Quran Reciter ID API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ai_engine: Optional[Any] = None
database: Optional[ReciterDatabase] = None
user_db: Optional[UserReciterDB] = None

_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
EMBEDDINGS_PATH = _BASE / "data" / "embeddings" / "reciter_database.json"
METADATA_PATH = _BASE / "data" / "reciters_metadata.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = _BASE / "app" / "static"

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".3gp", ".ts", ".mpeg", ".mpg"}
CLIP_SECONDS = 40
CLIP_OFFSET = 5


def _ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _prepare_audio(src: Path, filename: str = "") -> Path:
    ext = Path(filename or src.name).suffix.lower()
    if ext not in VIDEO_EXTS:
        return src
    import subprocess
    out = src.with_suffix(".extracted.wav")
    for cmd in (
        [_ffmpeg_bin(), "-y", "-ss", str(CLIP_OFFSET), "-t", str(CLIP_SECONDS), "-i", str(src),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(out)],
        [_ffmpeg_bin(), "-y", "-t", str(CLIP_SECONDS), "-i", str(src),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(out)],
    ):
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            return out
        except subprocess.CalledProcessError:
            continue
    raise HTTPException(400, "تعذّر استخراج الصوت من الفيديو")


model_state = {"status": "starting", "error": "", "started_at": None, "ready_at": None}
database_state = {"status": "starting", "error": "", "started_at": None, "ready_at": None}


def _load_database_background():
    global database
    database_state.update({"status": "loading", "error": "", "started_at": time.time(), "ready_at": None})
    try:
        if os.environ.get("QRI_SKIP_DB") == "1":
            logger.warning("Built-in database load skipped by QRI_SKIP_DB")
            database = None
            database_state.update({"status": "skipped", "error": "", "ready_at": time.time()})
            return
        database = ReciterDatabase(EMBEDDINGS_PATH, METADATA_PATH)
        database_state.update({"status": "ready", "error": "", "ready_at": time.time()})
        logger.info("✓ BUILT-IN DATABASE READY")
    except FileNotFoundError:
        logger.warning("Built-in database not found — running with user reciters only")
        database = None
        database_state.update({"status": "missing", "error": "", "ready_at": time.time()})
    except Exception as exc:
        logger.exception("Built-in database failed to load")
        database = None
        database_state.update({"status": "error", "error": str(exc), "ready_at": time.time()})


def _load_ai_engine_background():
    global ai_engine
    model_state.update({"status": "loading", "error": "", "started_at": time.time(), "ready_at": None})
    try:
        if os.environ.get("QRI_SKIP_AI") == "1":
            logger.warning("AI model load skipped by QRI_SKIP_AI")
            ai_engine = None
            model_state.update({"status": "skipped", "error": "", "ready_at": time.time()})
            return
        from .ai_engine import VoiceRecognitionEngine
        ai_engine = VoiceRecognitionEngine()
        model_state.update({"status": "ready", "error": "", "ready_at": time.time()})
        logger.info("✓ AI MODEL READY")
    except Exception as exc:
        logger.exception("AI model failed to load")
        ai_engine = None
        model_state.update({"status": "error", "error": str(exc), "ready_at": time.time()})


def _model_not_ready_message() -> str:
    if model_state.get("status") == "error":
        return "فشل تحميل نموذج الذكاء. أعد تشغيل التطبيق أو تأكد من اتصال الإنترنت أول مرة."
    return "نموذج التعرف الصوتي ما زال يحمّل. انتظر قليلاً ثم جرّب مرة أخرى."


@app.on_event("startup")
async def startup_event():
    global user_db
    logger.info("=== STARTING QURAN RECITER ID SERVER v3.0 (multi-stage) ===")
    user_db = UserReciterDB()
    logger.info(f"✓ Data folder: {user_db.get_data_path()}")
    threading.Thread(target=_load_database_background, daemon=True).start()
    threading.Thread(target=_load_ai_engine_background, daemon=True).start()
    logger.info("✓ SERVER READY — database and model are loading in background")


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
            "ai_status": model_state.get("status", "unknown"),
            "ai_error": model_state.get("error", ""),
            "db_status": database_state.get("status", "unknown"),
            "db_error": database_state.get("error", ""),
            "builtin_reciters": _unique_reciter_count() if database else 0,
            "user_reciters": len(user_db.data) if user_db else 0,
            "data_path": user_db.get_data_path() if user_db else ""}


@app.get("/model-status")
async def model_status():
    return {"ready": ai_engine is not None, **model_state}


# ============================================================================
#   MULTI-FINGERPRINT SUPPORT
#   Storage: each reciter can have multiple samples keyed as "Name#0", "Name#1"...
#   The base reciter name is recovered by stripping "#<int>".
# ============================================================================

_FP_SUFFIX = re.compile(r"#\d+$")

def _base_name(key: str) -> str:
    return _FP_SUFFIX.sub("", key)


def _unique_reciter_count() -> int:
    if not database:
        return 0
    return len({_base_name(k) for k in database.reciter_vectors.keys()})


def _all_vectors() -> Dict[str, np.ndarray]:
    vecs = {}
    if database:
        vecs.update(database.reciter_vectors)
    if user_db:
        vecs.update(user_db.vectors())
    return vecs


def _get_info(name: str):
    base = _base_name(name)
    if user_db and base in user_db.data:
        r = user_db.data[base]
        return {"name": r["name"], "name_english": r.get("name_english", base),
                "country": r.get("country", "مخصّص"), "bio": r.get("bio", ""),
                "birth_year": r.get("birth_year", "-"), "death_year": r.get("death_year"),
                "image_url": r.get("image_url", ""),
                "recitation_style": r.get("recitation_style", "مخصّص")}
    if database:
        info = database.get_reciter_info(base)
        if info:
            return info
    return {"name": base, "name_english": base, "country": "-", "bio": "",
            "birth_year": "-", "death_year": None, "image_url": "", "recitation_style": "-"}


# ============================================================================
#   MULTI-STAGE VERIFICATION PIPELINE
# ============================================================================
#   Stage 1: Fast broad match — cosine sim against ALL fingerprints → top 30
#   Stage 2: Multi-fingerprint aggregation — max score per BASE reciter name
#   Stage 3: Segment agreement — 8 × 5s segments must vote consistently
#   Stage 4: S-Norm — z-score against cohort of top-100 impostor mean/std
#   Stage 5: Margin gate — winner must beat #2 by a margin
#   Stage 6: Absolute similarity gate — winner sim ≥ MIN_SIM
#   → All gates pass ⇒ ONE reciter. Any gate fails ⇒ "غير معروف".
# ============================================================================

MIN_SIM = 0.58           # absolute cosine threshold
MIN_MARGIN = 0.04        # winner must beat #2 by this margin (base names)
MIN_AGREEMENT = 0.60     # ≥60% segments must vote the winner
MIN_SEG_MEAN = 0.50      # mean per-segment top-1 similarity
MIN_ZSCORE = 2.0         # S-Norm z-score threshold (winner vs cohort)


def _unit(v: np.ndarray) -> np.ndarray:
    arr = np.asarray(v, dtype=np.float32).reshape(-1)
    return arr / (float(np.linalg.norm(arr)) + 1e-9)


def _compatible_vectors(query_vec: np.ndarray, db_vec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return same-length normalized vectors.

    The bundled pretrained database is ECAPA-only (192 dims). New/user fingerprints
    can be Ensemble ECAPA+XVector (larger dims). When dimensions differ, compare
    the shared ECAPA prefix instead of crashing or mixing incompatible vectors.
    """
    q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    d = np.asarray(db_vec, dtype=np.float32).reshape(-1)
    n = min(q.size, d.size)
    if n <= 0:
        raise ValueError("empty embedding vector")
    return _unit(q[:n]), _unit(d[:n])


def _score_all(query_vec: np.ndarray, vecs: Dict[str, np.ndarray]) -> List[tuple]:
    """Return sorted list of (fingerprint_key, similarity), supporting mixed DB dimensions."""
    similarities = []
    for name, reciter_vec in vecs.items():
        try:
            q, r = _compatible_vectors(query_vec, reciter_vec)
            similarities.append((name, float(np.dot(q, r))))
        except Exception as exc:
            logger.warning(f"Skipping incompatible fingerprint {name}: {exc}")
    if not similarities:
        raise ValueError("No compatible fingerprints in database")
    return sorted(similarities, key=lambda x: x[1], reverse=True)


def _aggregate_by_base(scored: List[tuple]) -> List[tuple]:
    """Group fingerprints by base reciter name; take the MAX score per reciter."""
    best: Dict[str, float] = {}
    for key, s in scored:
        b = _base_name(key)
        if s > best.get(b, -1.0):
            best[b] = s
    return sorted(best.items(), key=lambda x: x[1], reverse=True)


def _snorm_zscore(winner_sim: float, all_scores: List[float]) -> float:
    """Compute S-Norm z-score of winner against cohort (all others)."""
    if len(all_scores) < 20:
        return 99.0  # too few → skip normalization
    others = np.array(sorted(all_scores, reverse=True)[1:101])  # top-100 impostors
    mu, sigma = float(others.mean()), float(others.std() + 1e-6)
    return (winner_sim - mu) / sigma


@app.post("/identify-reciter", response_model=IdentificationResult)
async def identify_reciter(audio_file: UploadFile = File(...)):
    if ai_engine is None:
        raise HTTPException(503, _model_not_ready_message())
    vecs = _all_vectors()
    if not vecs:
        if database_state.get("status") == "loading":
            raise HTTPException(503, "قاعدة البصمات ما زالت تُحمّل. انتظر قليلاً ثم جرّب مرة أخرى.")
        raise HTTPException(400, "لا يوجد قرّاء في قاعدة البيانات — أضف قارئاً أولاً")

    audio_bytes = await audio_file.read()
    with tempfile.NamedTemporaryFile(suffix=Path(audio_file.filename or "a.wav").suffix or ".wav", delete=False) as tmp:
        tmp.write(audio_bytes); tmp_path = Path(tmp.name)
    extracted_path: Optional[Path] = None
    try:
        analysis_path = _prepare_audio(tmp_path, audio_file.filename or "")
        if analysis_path != tmp_path:
            extracted_path = analysis_path
        if not ai_engine.validate_audio_duration(analysis_path, min_duration_sec=8.0):
            raise HTTPException(400, "الملف قصير جداً — التحليل العميق يحتاج 8 ثوانٍ على الأقل (يُفضّل 40 ثانية)")

        # ═══ Deep analysis: VAD → 40s → 8 × 5s ensemble embeddings ═══
        mean_emb, seg_embs, analyzed_sec = ai_engine.process_audio_segments(analysis_path)

        # ─── Stage 1: broad score across all fingerprints ───
        scored_all = _score_all(mean_emb, vecs)

        # ─── Stage 2: aggregate multi-fingerprints by base name ───
        base_ranked = _aggregate_by_base(scored_all)
        winner_name, winner_sim = base_ranked[0]
        second_sim = base_ranked[1][1] if len(base_ranked) > 1 else 0.0
        margin = winner_sim - second_sim

        # ─── Stage 3: per-segment agreement (each segment votes a base name) ───
        seg_top_bases, seg_top_scores = [], []
        for e in seg_embs:
            s_scored = _score_all(e, vecs)
            s_agg = _aggregate_by_base(s_scored)
            seg_top_bases.append(s_agg[0][0])
            seg_top_scores.append(s_agg[0][1])
        agreement = seg_top_bases.count(winner_name) / max(1, len(seg_top_bases))
        seg_mean_score = float(np.mean(seg_top_scores)) if seg_top_scores else 0.0

        # ─── Stage 4: S-Norm z-score against impostor cohort ───
        z = _snorm_zscore(winner_sim, [s for _, s in base_ranked])

        # ─── Stages 5+6: gates ───
        gates = {
            "similarity":  winner_sim >= MIN_SIM,
            "margin":      margin >= MIN_MARGIN,
            "agreement":   agreement >= MIN_AGREEMENT,
            "seg_mean":    seg_mean_score >= MIN_SEG_MEAN,
            "zscore":      z >= MIN_ZSCORE,
        }
        passed = sum(gates.values())
        # Require at least 4/5 gates (zscore may fail on small DBs)
        is_unknown = passed < 4 or not gates["similarity"]

        confidence = float(np.clip(
            0.25 * min(max((winner_sim - 0.4) / 0.35, 0), 1) +
            0.20 * min(max(margin / 0.10, 0), 1) +
            0.25 * agreement +
            0.15 * min(max((seg_mean_score - 0.4) / 0.30, 0), 1) +
            0.15 * min(max((z - 1.5) / 2.0, 0), 1),
            0.0, 1.0
        ))

        logger.info(
            f"[PIPELINE] winner={winner_name} sim={winner_sim:.3f} margin={margin:.3f} "
            f"agree={agreement:.2f} seg_mean={seg_mean_score:.3f} z={z:.2f} "
            f"gates={passed}/5 → {'UNKNOWN' if is_unknown else 'MATCH'}"
        )

        if is_unknown:
            result = IdentificationResult(
                success=True, reciter_name="غير معروف", reciter_name_english="Unknown",
                confidence=round(confidence, 3), country="-",
                bio="لم يتم التعرّف على القارئ بثقة كافية. جرّب عيّنة أطول أو أوضح، أو أضف القارئ إلى قاعدة البيانات.",
                birth_year="-", death_year=None, image_url="",
                recitation_style="-", similarity_score=round(winner_sim, 4),
                is_unknown=True, top_matches=[],
            )
        else:
            info = _get_info(winner_name)
            result = IdentificationResult(
                success=True, reciter_name=info["name"], reciter_name_english=info["name_english"],
                confidence=round(confidence, 3), country=info["country"], bio=info["bio"],
                birth_year=info["birth_year"], death_year=info.get("death_year"),
                image_url=info["image_url"], recitation_style=info["recitation_style"],
                similarity_score=round(winner_sim, 4),
                is_unknown=False,
                # Return ONLY the winner — no top-3 list to the user
                top_matches=[{"name": info["name"], "similarity": round(winner_sim, 4),
                              "confidence": round(confidence, 3)}],
            )
        if user_db:
            user_db.log_identification({
                "reciter": winner_name, "confidence": confidence, "similarity": winner_sim,
                "filename": audio_file.filename,
                "gates_passed": passed, "gates": gates,
                "margin": round(margin, 3), "agreement": round(agreement, 2),
                "seg_mean": round(seg_mean_score, 3), "zscore": round(z, 2),
                "analyzed_sec": round(analyzed_sec, 1),
            })
        return result
    finally:
        for p in (tmp_path, extracted_path):
            if p:
                try: p.unlink()
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
        raise HTTPException(503, _model_not_ready_message())
    blobs, names = [], []
    for f in audio_files:
        raw = await f.read()
        fname = f.filename or "audio.wav"
        ext = Path(fname).suffix.lower()
        if ext in VIDEO_EXTS:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as vtmp:
                vtmp.write(raw); vpath = Path(vtmp.name)
            try:
                apath = _prepare_audio(vpath, fname)
                blobs.append(apath.read_bytes())
                names.append(Path(fname).stem + ".wav")
                try: apath.unlink()
                except Exception: pass
            finally:
                try: vpath.unlink()
                except Exception: pass
        else:
            blobs.append(raw); names.append(fname)
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
    seen = set()
    if database:
        for r in database.get_all_reciters():
            base = _base_name(r.get("name", ""))
            if base in seen:
                continue
            seen.add(base)
            combined.append(ReciterInfo(id=r.get("id", idx), name=base,
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



# ==================== Multi-source auto enrichment ====================
try:
    from .multi_source_enricher import enrich_reciter as _mse_one, enrich_batch as _mse_batch
    from pydantic import BaseModel as _BM
    class _EnrichReq(_BM):
        name: str
        max_per_source: int = 2
        skip_existing: bool = True
    class _EnrichBatchReq(_BM):
        names: List[str]
        max_per_source: int = 2

    @app.post("/multi-enrich")
    async def multi_enrich(req: _EnrichReq):
        return _mse_one(req.name, req.max_per_source, req.skip_existing)

    @app.post("/multi-enrich-batch")
    async def multi_enrich_batch(req: _EnrichBatchReq):
        return _mse_batch(req.names, req.max_per_source)

    @app.get("/multi-enrich/status")
    async def multi_enrich_status():
        return {"ok": True, "sources": ["mp3quran","everyayah","alquran_cloud","archive","youtube"]}
    logger.info("multi_source_enricher endpoints registered")
except Exception as _e:
    logging.getLogger(__name__).warning("multi_source_enricher not loaded: %s", _e)
# ======================================================================

@app.exception_handler(Exception)
async def gxh(request, exc):
    logger.exception("unhandled")
    return JSONResponse(status_code=500, content={"success": False, "error": "Internal", "detail": str(exc)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
