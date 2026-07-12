"""
Build the initial fingerprint database from MP3Quran.net.
Downloads each surah for each selected reciter, computes fingerprints,
uploads them to Lovable Cloud (PostgreSQL).

Usage:
    export SUPABASE_URL=https://xxx.supabase.co
    export SUPABASE_SERVICE_ROLE_KEY=eyJ...
    python scripts/build_fingerprint_seed.py --reciters mishary,husary,abdelbasit
    python scripts/build_fingerprint_seed.py --reciters all --surahs 1,36,55,67,112
"""
from __future__ import annotations
import argparse, asyncio, os, sys, tempfile
from pathlib import Path
import httpx

# Add backend/app to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from app.fingerprint_engine import fingerprint_audio, frames_to_ms
from app.fingerprint_db import _rest, _HEADERS, insert_recitation, bulk_insert_fingerprints

# --- Selected famous reciters (mp3quran.net API IDs) ---
FAMOUS = {
    "mishary":     {"id": "7",   "name_ar": "مشاري راشد العفاسي", "country": "الكويت"},
    "husary":      {"id": "11",  "name_ar": "محمود خليل الحصري", "country": "مصر"},
    "abdelbasit":  {"id": "3",   "name_ar": "عبد الباسط عبد الصمد", "country": "مصر"},
    "minshawi":    {"id": "10",  "name_ar": "محمد صديق المنشاوي", "country": "مصر"},
    "sudais":      {"id": "5",   "name_ar": "عبد الرحمن السديس",   "country": "السعودية"},
    "shuraim":     {"id": "6",   "name_ar": "سعود الشريم",          "country": "السعودية"},
    "ghamdi":      {"id": "16",  "name_ar": "سعد الغامدي",           "country": "السعودية"},
    "ajmi":        {"id": "23",  "name_ar": "أحمد بن علي العجمي",   "country": "السعودية"},
}

SURAH_NAMES = ["", "الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام", "الأعراف",
               "الأنفال", "التوبة", "يونس", "هود", "يوسف", "الرعد", "إبراهيم", "الحجر", "النحل",
               "الإسراء", "الكهف", "مريم", "طه", "الأنبياء", "الحج", "المؤمنون", "النور", "الفرقان",
               "الشعراء", "النمل", "القصص", "العنكبوت", "الروم", "لقمان", "السجدة", "الأحزاب",
               "سبأ", "فاطر", "يس", "الصافات", "ص", "الزمر", "غافر", "فصلت", "الشورى", "الزخرف",
               "الدخان", "الجاثية", "الأحقاف", "محمد", "الفتح", "الحجرات", "ق", "الذاريات",
               "الطور", "النجم", "القمر", "الرحمن", "الواقعة", "الحديد", "المجادلة", "الحشر",
               "الممتحنة", "الصف", "الجمعة", "المنافقون", "التغابن", "الطلاق", "التحريم", "الملك",
               "القلم", "الحاقة", "المعارج", "نوح", "الجن", "المزمل", "المدثر", "القيامة", "الإنسان",
               "المرسلات", "النبأ", "النازعات", "عبس", "التكوير", "الانفطار", "المطففين", "الانشقاق",
               "البروج", "الطارق", "الأعلى", "الغاشية", "الفجر", "البلد", "الشمس", "الليل", "الضحى",
               "الشرح", "التين", "العلق", "القدر", "البينة", "الزلزلة", "العاديات", "القارعة",
               "التكاثر", "العصر", "الهمزة", "الفيل", "قريش", "الماعون", "الكوثر", "الكافرون",
               "النصر", "المسد", "الإخلاص", "الفلق", "الناس"]


async def ensure_reciter(key: str, meta: dict) -> str:
    """Upsert reciter and return its UUID."""
    async with httpx.AsyncClient(timeout=15) as c:
        # Try to find existing
        r = await c.get(_rest(f"/reciters?external_id=eq.mp3quran_{meta['id']}&select=id"), headers=_HEADERS)
        r.raise_for_status()
        rows = r.json()
        if rows:
            return rows[0]["id"]
        # Insert
        r = await c.post(_rest("/reciters"), headers=_HEADERS, json={
            "name_ar": meta["name_ar"],
            "country": meta["country"],
            "external_id": f"mp3quran_{meta['id']}",
        })
        r.raise_for_status()
        return r.json()[0]["id"]


async def process_surah(reciter_uuid: str, reciter_key: str, meta: dict, surah_num: int):
    """Download surah MP3, fingerprint, upload."""
    # mp3quran url pattern: server_url + zero-padded surah + .mp3
    # Fetch server URL from mp3quran API
    async with httpx.AsyncClient(timeout=30) as c:
        idx = await c.get(f"https://mp3quran.net/api/v3/reciters?reciter={meta['id']}")
        idx.raise_for_status()
        data = idx.json()
        server = data["reciters"][0]["moshaf"][0]["server"]

    url = f"{server}{surah_num:03d}.mp3"
    print(f"  ⬇  {reciter_key} surah {surah_num} ← {url}")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        async with httpx.AsyncClient(timeout=120) as c:
            async with c.stream("GET", url) as resp:
                if resp.status_code != 200:
                    print(f"  ✗  HTTP {resp.status_code}")
                    return
                async for chunk in resp.aiter_bytes():
                    tmp.write(chunk)
        tmp_path = tmp.name

    try:
        # Fingerprint
        hashes_frames = fingerprint_audio(tmp_path)
        hashes_ms = [(h, frames_to_ms(off)) for h, off in hashes_frames]
        if not hashes_ms:
            print("  ✗  no fingerprints extracted")
            return
        # Insert
        rec_id = await insert_recitation(
            reciter_id=reciter_uuid,
            surah_number=surah_num,
            surah_name_ar=SURAH_NAMES[surah_num],
            source=f"mp3quran/{meta['id']}",
            source_url=url,
        )
        await bulk_insert_fingerprints(rec_id, hashes_ms)
        print(f"  ✓  {len(hashes_ms):,} hashes uploaded")
    finally:
        os.unlink(tmp_path)


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reciters", default="mishary,husary,abdelbasit",
                   help="comma-separated keys, or 'all'")
    p.add_argument("--surahs", default="1,36,55,67,112",
                   help="comma-separated surah numbers, or 'all'")
    args = p.parse_args()

    reciters = list(FAMOUS.keys()) if args.reciters == "all" else args.reciters.split(",")
    surahs = list(range(1, 115)) if args.surahs == "all" else [int(s) for s in args.surahs.split(",")]

    for key in reciters:
        meta = FAMOUS.get(key)
        if not meta:
            print(f"skip unknown reciter: {key}")
            continue
        print(f"\n=== {meta['name_ar']} ===")
        uuid = await ensure_reciter(key, meta)
        for s in surahs:
            try:
                await process_surah(uuid, key, meta, s)
            except Exception as e:
                print(f"  ✗ error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
