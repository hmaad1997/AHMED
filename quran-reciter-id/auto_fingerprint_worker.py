"""
Auto-Fingerprint Worker — من القارئ
====================================
يعمل تلقائياً 24/7 على Render:
  1. يجيب قائمة القراء من MP3Quran API
  2. يختار قارئ/سورة لم تُبصم بعد من Supabase
  3. يحمّل الصوت → يولّد بصمات (Shazam-style) → يرفعها Supabase
  4. كل 10 بصمات، يتحقّق بواسطة Gemini (Lovable AI) من صحة قارئ العينة
  5. يعيد كل REST_MINUTES دقيقة

يعمل كـ background thread داخل نفس عملية FastAPI.
"""
from __future__ import annotations

import os, sys, time, json, random, tempfile, traceback, threading, hashlib
from pathlib import Path
from typing import Optional
import requests

# ---- إعدادات ----
MP3QURAN_API   = "https://mp3quran.net/api/v3/reciters?language=ar"
SURAHS_API     = "https://mp3quran.net/api/v3/suwar?language=ar"
SUPABASE_URL   = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY   = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
LOVABLE_KEY    = os.environ.get("LOVABLE_API_KEY", "")
LOVABLE_AI_URL = "https://ai.gateway.lovable.dev/v1/chat/completions"

REST_MINUTES        = int(os.environ.get("FP_REST_MINUTES", "60"))
MAX_PER_CYCLE       = int(os.environ.get("FP_MAX_PER_CYCLE", "3"))    # سور في كل دورة
VERIFY_EVERY_N      = int(os.environ.get("FP_VERIFY_EVERY_N", "10"))  # 10% ≈ كل 10 عمليات
MAX_DURATION_SEC    = int(os.environ.get("FP_MAX_DURATION", "1800"))  # 30د كحد أقصى
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# ---------- Supabase helpers ----------
def sb_get(table: str, params: dict) -> list:
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def sb_insert(table: str, row: dict) -> Optional[dict]:
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, json=row, timeout=30)
    if r.status_code >= 400:
        print(f"[sb_insert:{table}] {r.status_code} {r.text[:200]}", flush=True)
        return None
    data = r.json()
    return data[0] if isinstance(data, list) and data else None

def sb_upsert_reciter(name_ar: str, name_en: str, external_id: str) -> Optional[str]:
    existing = sb_get("reciters", {"external_id": f"eq.{external_id}", "select": "id"})
    if existing:
        return existing[0]["id"]
    row = sb_insert("reciters", {"name_ar": name_ar, "name_en": name_en, "external_id": external_id})
    return row["id"] if row else None

def sb_recitation_exists(reciter_id: str, surah: int) -> bool:
    r = sb_get("recitations", {
        "reciter_id": f"eq.{reciter_id}", "surah_number": f"eq.{surah}", "select": "id", "limit": "1"
    })
    return bool(r)

# ---------- Fingerprint engine (خفيف — Shazam-style) ----------
def generate_fingerprints(audio_path: str) -> tuple[list[tuple[int, int]], float]:
    """يرجّع [(hash, offset_ms), ...] + المدة بالثواني."""
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import spectrogram
    import subprocess

    wav_path = audio_path + ".wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", audio_path, "-ac", "1", "-ar", "11025", wav_path],
        check=True, capture_output=True, timeout=300,
    )
    sr, samples = wavfile.read(wav_path)
    os.unlink(wav_path)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    samples = samples.astype(np.float32)
    duration = len(samples) / sr

    f, t, Sxx = spectrogram(samples, fs=sr, nperseg=4096, noverlap=2048)
    Sxx_log = np.log1p(Sxx)

    # ذروات محلية
    peaks: list[tuple[int, int]] = []
    for ti in range(1, Sxx_log.shape[1] - 1):
        col = Sxx_log[:, ti]
        thresh = col.mean() + 1.2 * col.std()
        for fi in range(20, len(col) - 1):
            v = col[fi]
            if v > thresh and v > col[fi-1] and v > col[fi+1] \
               and v > Sxx_log[fi, ti-1] and v > Sxx_log[fi, ti+1]:
                peaks.append((fi, int(t[ti] * 1000)))

    # combinatorial hashing
    hashes: list[tuple[int, int]] = []
    FAN = 8
    for i, (f1, t1) in enumerate(peaks):
        for j in range(1, FAN + 1):
            if i + j >= len(peaks):
                break
            f2, t2 = peaks[i + j]
            dt = t2 - t1
            if 20 < dt < 3000:
                key = f"{f1}|{f2}|{dt}".encode()
                h = int.from_bytes(hashlib.sha1(key).digest()[:6], "big") & 0x7FFFFFFFFFFFFFFF
                hashes.append((h, t1))
    return hashes, duration

# ---------- Gemini verification ----------
def verify_with_gemini(reciter_name_ar: str, surah_ar: str, source_url: str) -> dict:
    """يفحص منطقياً إذا هذا القارئ معروف بهذه التلاوة."""
    if not LOVABLE_KEY:
        return {"verified": None, "reason": "no_lovable_key"}
    prompt = (
        f"هل القارئ '{reciter_name_ar}' معروف بتلاوة سورة '{surah_ar}'؟ "
        f"المصدر: {source_url}. "
        "أجب فقط بـ JSON: {\"verified\": true|false, \"confidence\": 0-1, \"note\": \"...\"}"
    )
    try:
        r = requests.post(LOVABLE_AI_URL,
            headers={"Authorization": f"Bearer {LOVABLE_KEY}", "Content-Type": "application/json"},
            json={
                "model": "google/gemini-3.5-flash",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }, timeout=30)
        if r.status_code == 429:
            return {"verified": None, "reason": "rate_limited"}
        if r.status_code == 402:
            return {"verified": None, "reason": "credits_exhausted"}
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        return {"verified": None, "reason": f"error:{e}"}

# ---------- الدورة الرئيسية ----------
_STATE = {"total_reciters": 0, "processed": 0, "verified": 0, "rejected": 0,
          "last_run": None, "last_error": None, "running": False}

def _process_one_surah(reciter: dict, surah: dict, cycle_idx: int) -> bool:
    ext_id = str(reciter.get("id"))
    name_ar = reciter.get("name", "غير معروف")
    surah_num = int(surah.get("id", 0))
    if not (1 <= surah_num <= 114):
        return False

    reciter_id = sb_upsert_reciter(name_ar, "", ext_id)
    if not reciter_id or sb_recitation_exists(reciter_id, surah_num):
        return False

    server = reciter.get("moshaf", [{}])[0].get("server", "").rstrip("/")
    if not server:
        return False
    audio_url = f"{server}/{surah_num:03d}.mp3"

    print(f"  ↓ {name_ar} — سورة {surah_num} — {audio_url}", flush=True)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        try:
            with requests.get(audio_url, stream=True, timeout=120) as r:
                if r.status_code != 200:
                    return False
                for chunk in r.iter_content(1024 * 64):
                    tmp.write(chunk)
                    if tmp.tell() > 50 * 1024 * 1024:
                        break
            tmp.flush()
            hashes, duration = generate_fingerprints(tmp.name)
            if duration > MAX_DURATION_SEC or len(hashes) < 100:
                return False

            rec = sb_insert("recitations", {
                "reciter_id": reciter_id,
                "surah_number": surah_num,
                "surah_name_ar": surah.get("name", f"سورة {surah_num}"),
                "riwayah": reciter.get("moshaf", [{}])[0].get("name", ""),
                "source_url": audio_url,
                "source": "mp3quran",
                "duration_sec": int(duration),
                "sample_rate": 11025,
                "fingerprint_count": len(hashes),
            })
            if not rec:
                return False

            # bulk insert للبصمات (على دفعات)
            batch, BATCH = [], 500
            for h, off in hashes:
                batch.append({"hash": h, "offset_ms": off, "recitation_id": rec["id"]})
                if len(batch) >= BATCH:
                    requests.post(f"{SUPABASE_URL}/rest/v1/fingerprints",
                                  headers=SB_HEADERS, json=batch, timeout=60)
                    batch = []
            if batch:
                requests.post(f"{SUPABASE_URL}/rest/v1/fingerprints",
                              headers=SB_HEADERS, json=batch, timeout=60)

            _STATE["processed"] += 1
            print(f"    ✓ {len(hashes)} بصمة محفوظة", flush=True)

            # تحقّق 10%
            if cycle_idx % VERIFY_EVERY_N == 0:
                v = verify_with_gemini(name_ar, surah.get("name", ""), audio_url)
                if v.get("verified") is True:
                    _STATE["verified"] += 1
                    print(f"    🤖 Gemini: موثّق ({v.get('confidence', 0)})", flush=True)
                elif v.get("verified") is False:
                    _STATE["rejected"] += 1
                    print(f"    ⚠ Gemini رفض: {v.get('note', '')}", flush=True)
            return True
        finally:
            try: os.unlink(tmp.name)
            except: pass

def _run_cycle():
    _STATE["running"] = True
    try:
        print("[AutoFP] جلب القراء والسور...", flush=True)
        reciters = requests.get(MP3QURAN_API, timeout=30).json().get("reciters", [])
        surahs   = requests.get(SURAHS_API, timeout=30).json().get("suwar", [])
        _STATE["total_reciters"] = len(reciters)
        random.shuffle(reciters)

        done = 0
        for reciter in reciters:
            if done >= MAX_PER_CYCLE:
                break
            for surah in random.sample(surahs, min(5, len(surahs))):
                try:
                    if _process_one_surah(reciter, surah, _STATE["processed"] + 1):
                        done += 1
                        break
                except Exception as e:
                    print(f"    ✗ {e}", flush=True)
        _STATE["last_run"] = time.time()
        _STATE["last_error"] = None
    except Exception as e:
        _STATE["last_error"] = str(e)
        traceback.print_exc()
    finally:
        _STATE["running"] = False

def worker_loop():
    print("[AutoFP] بدء Worker التلقائي...", flush=True)
    while True:
        try:
            _run_cycle()
        except Exception:
            traceback.print_exc()
        print(f"[AutoFP] استراحة {REST_MINUTES}د | حالة: {_STATE}", flush=True)
        time.sleep(REST_MINUTES * 60)

def start_worker_thread():
    if not (SUPABASE_URL and SUPABASE_KEY):
        print("[AutoFP] معطّل — متغيرات Supabase مفقودة", flush=True)
        return
    t = threading.Thread(target=worker_loop, daemon=True, name="auto-fp-worker")
    t.start()
    print("[AutoFP] Worker يعمل في الخلفية ✓", flush=True)

def get_state() -> dict:
    return dict(_STATE)

# لو تشغلته يدوياً
if __name__ == "__main__":
    _run_cycle()
    print(json.dumps(_STATE, ensure_ascii=False, indent=2))
