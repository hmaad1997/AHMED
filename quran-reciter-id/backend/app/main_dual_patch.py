"""
Patch to add to your existing backend/app/main.py

Add these imports at the top:
    import asyncio, tempfile
    from .fingerprint_engine import fingerprint_audio, frames_to_ms
    from .fingerprint_db import match_fingerprints

Then add this endpoint (paste anywhere after your FastAPI `app = FastAPI(...)`):
"""

# --- Paste from here ---
@app.post("/identify-dual")
async def identify_dual(audio_file: UploadFile = File(...)):
    """
    Dual-engine identification:
      1) Speaker Recognition (existing engine) → who is the reciter
      2) Audio Fingerprint (Shazam-style)      → which recitation & position
    Merges both results into a single response.
    """
    # Save upload to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp:
        tmp.write(await audio_file.read())
        tmp_path = tmp.name

    # Run both engines in parallel
    async def run_speaker():
        # Reuse your existing engine.identify() or equivalent function
        return await asyncio.to_thread(engine.identify_from_path, tmp_path)

    async def run_fingerprint():
        hashes_frames = await asyncio.to_thread(fingerprint_audio, tmp_path)
        hashes_ms = [(h, frames_to_ms(off)) for h, off in hashes_frames]
        return await match_fingerprints(hashes_ms)

    speaker_result, fp_result = await asyncio.gather(
        run_speaker(), run_fingerprint(), return_exceptions=True
    )

    # Handle exceptions gracefully — one engine failing shouldn't kill the response
    if isinstance(speaker_result, Exception):
        speaker_result = {"is_unknown": True, "reciter_name": "غير معروف", "confidence": 0.0, "top_matches": []}
    if isinstance(fp_result, Exception):
        fp_result = None

    # Merge: if fingerprint matched, boost the reciter identification confidence
    response = dict(speaker_result) if isinstance(speaker_result, dict) else {}
    if fp_result:
        response["recitation"] = {
            "recitation_id": fp_result["recitation_id"],
            "surah_number":  fp_result["surah_number"],
            "surah_name_ar": fp_result["surah_name_ar"],
            "riwayah":       fp_result.get("riwayah"),
            "source":        fp_result.get("source"),
            "offset_ms":     fp_result["offset_ms"],
            "match_score":   fp_result["match_score"],
        }
        response["method"] = "combined"
        # If fingerprint says one reciter and speaker agrees → boost confidence
        fp_reciter = (fp_result.get("reciter") or {}).get("name_ar")
        if fp_reciter and fp_reciter == response.get("reciter_name"):
            response["confidence"] = min(1.0, response.get("confidence", 0) + 0.15)
        elif fp_reciter:
            # Fingerprint is more authoritative (exact match) — override
            response["reciter_name"] = fp_reciter
            response["confidence"] = fp_result["match_score"]
            response["is_unknown"] = False
    else:
        response["method"] = "speaker"
        response["recitation"] = None

    return response
# --- End paste ---
