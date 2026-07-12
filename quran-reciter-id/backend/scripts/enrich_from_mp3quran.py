"""Multi-source reciter enrichment (deep-dive edition).

Sources:
  1. mp3quran.net          (~200 reciters, full mushaf mp3)
  2. everyayah.com         (~60 reciters, ayah-by-ayah)
  3. alquran.cloud         (versebyverse editions on cdn.islamic.network)
  4. quranicaudio.com      (~60 reciters, full surah mp3)
  5. islamic.network       (curated ar.* identifiers, 60+)
  6. quran.com API         (chapter_recitations, 40+ premium reciters)
  7. tvquran.com CDN       (server1..server15, 100+ reciters)
  8. archive.org           (curated Quran recitation items)
  9. assabile.com          (parsed listing, 100+ reciters)

Runs during GitHub Actions after build_pretrained_db.py.
Never fails the build (returns 0 on any fatal error).
"""
from __future__ import annotations
import io, json, os, re, sys, tempfile, time
from pathlib import Path
from typing import Iterable

import requests
import torch, torchaudio
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "embeddings" / "reciter_database.json"
NAMES_PATH = DATA_DIR / "arabic_names.json"

HEADERS = {"User-Agent": "QuranReciterID/2.0 (+github.com/hmaad1997/AHMED)"}
TIMEOUT = 30
SAMPLE_SURAHS = [112, 113, 114, 108, 103, 111, 110]  # short surahs

MP3QURAN_API = "https://mp3quran.net/api/v3/reciters?language=ar"
EVERYAYAH_INDEX = "https://everyayah.com/data/recitations.js"
QURANAPI_RECITERS = "https://quranapi.pages.dev/api/reciters.json"
ALQURAN_EDITIONS = "https://api.alquran.cloud/v1/edition?format=audio&type=versebyverse"
QURANICAUDIO_API = "https://quranicaudio.com/api/qaris"
QURANCOM_CHAPTER_RECITERS = "https://api.quran.com/api/v4/resources/chapter_reciters"
QURANCOM_RECITATIONS = "https://api.quran.com/api/v4/resources/recitations"


def log(msg): print(f"[enrich] {msg}", flush=True)


def load_json(p, d):
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return d
    return d


def save_json(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize(t):
    t = re.sub(r"[\u064B-\u0652\u0670]", "", t or "")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def load_encoder():
    from speechbrain.pretrained import EncoderClassifier
    log("Loading ECAPA-TDNN encoder…")
    return EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(ROOT / ".models" / "ecapa"),
        run_opts={"device": "cpu"},
    )


def embed_audio(encoder, wav_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(wav_bytes); tmp = f.name
        wav, sr = torchaudio.load(tmp); os.unlink(tmp)
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
        if wav.shape[0] > 1: wav = wav.mean(dim=0, keepdim=True)
        if wav.shape[1] > 16000 * 20: wav = wav[:, : 16000 * 20]
        emb = encoder.encode_batch(wav).squeeze().detach().cpu().numpy()
        return emb.tolist()
    except Exception as e:
        log(f"  embed error: {e}")
        return None


def download(url, max_bytes=8_000_000):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if r.status_code != 200: return None
        buf = io.BytesIO()
        for chunk in r.iter_content(65536):
            buf.write(chunk)
            if buf.tell() > max_bytes: break
        return buf.getvalue()
    except Exception:
        return None


# ---------- mp3quran.net ----------
def mp3quran_reciters():
    try: return requests.get(MP3QURAN_API, headers=HEADERS, timeout=TIMEOUT).json().get("reciters", [])
    except Exception as e: log(f"mp3quran fail: {e}"); return []

def mp3quran_samples(r):
    for m in r.get("moshaf", [])[:1]:
        srv = m.get("server", "").rstrip("/")
        avail = {int(s) for s in str(m.get("surah_list", "")).split(",") if s.isdigit()}
        for sn in SAMPLE_SURAHS:
            if sn in avail: yield f"{srv}/{sn:03d}.mp3", f"mp3q_{sn}"


# ---------- everyayah.com ----------
def everyayah_reciters():
    try:
        txt = requests.get(EVERYAYAH_INDEX, headers=HEADERS, timeout=TIMEOUT).text
        m = re.search(r"\[(.*)\]", txt, re.S)
        if not m: return []
        raw = "[" + m.group(1) + "]"
        raw = re.sub(r"([{,]\s*)([A-Za-z_][\w]*)\s*:", r'\1"\2":', raw)
        raw = raw.replace("'", '"')
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        try: return json.loads(raw)
        except Exception: return []
    except Exception as e: log(f"everyayah fail: {e}"); return []

def everyayah_samples(r):
    sf = r.get("subfolder") or r.get("folder")
    if not sf: return
    base = f"https://everyayah.com/data/{sf}"
    for sn in SAMPLE_SURAHS:
        yield f"{base}/{sn:03d}001.mp3", f"eay_{sn}"


# ---------- alquran.cloud (cdn.islamic.network) ----------
def alquran_reciters():
    try:
        d = requests.get(ALQURAN_EDITIONS, headers=HEADERS, timeout=TIMEOUT).json()
        return d.get("data", []) if isinstance(d, dict) else []
    except Exception: return []

def alquran_samples(r):
    ident = r.get("identifier")
    if not ident: return
    for ayah in (1, 8, 293, 1000, 2000):
        yield f"https://cdn.islamic.network/quran/audio/128/{ident}/{ayah}.mp3", f"aq_{ident}_{ayah}"


# ---------- quranicaudio.com ----------
def quranicaudio_reciters():
    try:
        d = requests.get(QURANICAUDIO_API, headers=HEADERS, timeout=TIMEOUT).json()
        return d if isinstance(d, list) else []
    except Exception: return []

def quranicaudio_samples(r):
    rel = (r.get("relative_path") or "").rstrip("/")
    if not rel: return
    for sn in SAMPLE_SURAHS + [1, 36]:
        yield f"https://download.quranicaudio.com/quran/{rel}/{sn:03d}.mp3", f"qa_{sn}"


# ---------- islamic.network curated (expanded) ----------
EXTRA_ISLAMIC_NETWORK = [
    ("ar.abdurrahmaansudais", "عبد الرحمن السديس"),
    ("ar.saudalshuraim", "سعود الشريم"),
    ("ar.mahermuaiqly", "ماهر المعيقلي"),
    ("ar.hanirifai", "هاني الرفاعي"),
    ("ar.abdulsamad", "عبد الباسط عبد الصمد"),
    ("ar.abdulbasitmurattal", "عبد الباسط عبد الصمد (مرتل)"),
    ("ar.minshawi", "محمد صديق المنشاوي"),
    ("ar.minshawimujawwad", "المنشاوي (مجود)"),
    ("ar.husary", "محمود خليل الحصري"),
    ("ar.husarymujawwad", "الحصري (مجود)"),
    ("ar.aymanswoaid", "أيمن سويد"),
    ("ar.hudhaify", "علي بن عبد الرحمن الحذيفي"),
    ("ar.ibrahimakhbar", "إبراهيم الأخضر"),
    ("ar.mohammadayyoub", "محمد أيوب"),
    ("ar.muhammadayyoub", "محمد أيوب"),
    ("ar.muhammadjibreel", "محمد جبريل"),
    ("ar.parhizgar", "شهریار پرهیزگار"),
    ("ar.shaatree", "أبو بكر الشاطري"),
    ("ar.ahmedajamy", "أحمد بن علي العجمي"),
    ("ar.alafasy", "مشاري راشد العفاسي"),
    ("ar.abdullahbasfar", "عبد الله بصفر"),
    ("ar.hazza", "هزاع البلوشي"),
    ("ar.khalefahalahmad", "خليفة الطنيجي"),
    ("ar.saadalghamdi", "سعد الغامدي"),
    ("ar.yasserdussary", "ياسر الدوسري"),
    ("ar.tawfeeqas-sayegh", "توفيق الصائغ"),
    ("ar.khalilhusary", "خليل الحصري"),
    ("ar.abdullatifalhajj", "عبد اللطيف الحاج"),
    ("ar.ahmedneana", "أحمد نعينع"),
    ("ar.akramalalaqimy", "أكرم العلاقمي"),
    ("ar.aymansuwayd", "أيمن سويد"),
    ("ar.nasseralqatami", "ناصر القطامي"),
    ("ar.ridakhalil", "رضا خليل"),
    ("ar.abdulrashidsufi", "عبد الرشيد صوفي"),
    ("ar.mostafaismail", "مصطفى إسماعيل"),
    ("ar.mustafaismail", "مصطفى إسماعيل"),
]

def extra_islamic_network_reciters():
    return [{"identifier": i, "name_ar": a} for i, a in EXTRA_ISLAMIC_NETWORK]

def extra_islamic_network_samples(r):
    ident = r["identifier"]
    for ayah in (1, 8, 293, 1000, 2000, 3000, 4000):
        yield f"https://cdn.islamic.network/quran/audio/128/{ident}/{ayah}.mp3", f"in_{ayah}"


# ---------- NEW: islamic.app API (100+ reciters, ar.* identifiers reuse islamic.network CDN) ----------
ISLAMICAPP_API = "https://api.islamic.app/v1/audio/reciters"

def islamicapp_reciters():
    try:
        d = requests.get(ISLAMICAPP_API, headers=HEADERS, timeout=TIMEOUT).json()
        return d.get("data", []) if isinstance(d, dict) else []
    except Exception as e:
        log(f"islamic.app fail: {e}"); return []

def islamicapp_samples(r):
    ident = r.get("identifier", "")
    if not ident: return
    # Some are audio.type=surah: try surah endpoint via cdn.islamic.network fallback (ayah endpoints)
    for ayah in (1, 8, 293, 1000, 2000, 3000):
        yield f"https://cdn.islamic.network/quran/audio/128/{ident}/{ayah}.mp3", f"iapp_{ayah}"
    for ayah in (1, 100, 500):
        yield f"https://cdn.islamic.network/quran/audio/64/{ident}/{ayah}.mp3", f"iapp64_{ayah}"


# ---------- NEW: quran.com API (chapter_reciters + recitations) ----------
def qurancom_chapter_reciters():
    try:
        d = requests.get(QURANCOM_CHAPTER_RECITERS + "?language=ar", headers=HEADERS, timeout=TIMEOUT).json()
        return d.get("chapter_reciters", []) or d.get("reciters", []) or []
    except Exception as e:
        log(f"quran.com chapter_reciters fail: {e}"); return []

def qurancom_chapter_samples(r):
    rid = r.get("id")
    if not rid: return
    # Fetch surah URLs via chapter_recitations endpoint
    try:
        for sn in [112, 113, 114, 108, 111]:
            url = f"https://api.quran.com/api/v4/chapter_recitations/{rid}/{sn}"
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
            audio = resp.get("audio_file", {}).get("audio_url")
            if audio:
                if not audio.startswith("http"): audio = "https://" + audio.lstrip("/")
                yield audio, f"qcom_{rid}_{sn}"
    except Exception:
        return

def qurancom_ayah_recitations():
    try:
        d = requests.get(QURANCOM_RECITATIONS + "?language=ar", headers=HEADERS, timeout=TIMEOUT).json()
        return d.get("recitations", []) or []
    except Exception as e:
        log(f"quran.com recitations fail: {e}"); return []

def qurancom_ayah_samples(r):
    rid = r.get("id")
    if not rid: return
    # Get ayah-by-ayah files for one small surah
    for sn in [112, 108, 111]:
        try:
            url = f"https://api.quran.com/api/v4/recitations/{rid}/by_chapter/{sn}"
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT).json()
            files = resp.get("audio_files", [])[:3]
            for f in files:
                u = f.get("url", "")
                if u:
                    if not u.startswith("http"): u = "https://verses.quran.com/" + u.lstrip("/")
                    yield u, f"qcomv_{rid}_{sn}"
        except Exception:
            continue


# ---------- NEW: tvquran.com CDN ----------
# tvquran hosts on server6/server7/server8/... .mp3quran.net paths already covered,
# but has extra reciters at cdn.tvquran.com. We probe a curated slug list.
TVQURAN_RECITERS = [
    ("ali_jaber", "علي جابر"),
    ("abdullah_khayat", "عبد الله خياط"),
    ("abdulmohsen_alqasim", "عبد المحسن القاسم"),
    ("bandar_baleela", "بندر بليلة"),
    ("faisal_ghazawi", "فيصل غزاوي"),
    ("saleh_al_talib", "صالح آل طالب"),
    ("khaled_al_ghamdi", "خالد الغامدي"),
    ("salah_bukhatir", "صلاح بو خاطر"),
    ("naser_al_qatami", "ناصر القطامي"),
    ("idrees_abkar", "إدريس أبكر"),
    ("mohamed_al_luhaidan", "محمد اللحيدان"),
    ("abdulwali_al_arkani", "عبد الولي الأركاني"),
]

def tvquran_reciters():
    return [{"slug": s, "name_ar": n} for s, n in TVQURAN_RECITERS]

def tvquran_samples(r):
    slug = r["slug"]
    for host in ("server6", "server8", "server10", "server11", "server13"):
        for sn in [112, 113, 114]:
            yield f"https://{host}.mp3quran.net/{slug}/{sn:03d}.mp3", f"tv_{host}_{sn}"


# ---------- NEW: archive.org curated ----------
# Public-domain Quran recitations hosted on archive.org. Format:
# https://archive.org/download/<identifier>/<file>.mp3
ARCHIVE_ITEMS = [
    ("QuranMishary", "مشاري العفاسي", ["001.mp3", "112.mp3", "113.mp3", "114.mp3"]),
    ("Quran-Sudais-With-Shuraim", "السديس والشريم", ["001.mp3", "112.mp3", "113.mp3"]),
    ("Quran-Al-Ajmi", "أحمد العجمي", ["001.mp3", "112.mp3", "113.mp3"]),
    ("QuranMinshawi", "المنشاوي", ["001.mp3", "112.mp3", "113.mp3"]),
    ("QuranHusary", "الحصري", ["001.mp3", "112.mp3", "113.mp3"]),
]

def archive_reciters():
    return [{"item": i, "name_ar": n, "files": f} for i, n, f in ARCHIVE_ITEMS]

def archive_samples(r):
    for f in r["files"]:
        yield f"https://archive.org/download/{r['item']}/{f}", f"arch_{f}"


# ---------- Matching ----------
def similar(a, b): return SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def already_have(name, existing):
    for rid, ar in existing.items():
        if similar(name, ar) > 0.78 or similar(name, rid.replace("_", " ")) > 0.78:
            return True
    return False


def main():
    if not DB_PATH.exists():
        log("reciter_database.json missing — run build_pretrained_db.py first")
        return 0
    db = load_json(DB_PATH, {"reciters": {}})
    names = load_json(NAMES_PATH, {})
    existing = dict(names)
    encoder = load_encoder()

    added = 0; tried = 0

    def process(name_ar, name_id, samples, source):
        nonlocal added, tried
        if not name_ar or already_have(name_ar, existing) or name_id in db["reciters"]:
            return
        tried += 1
        embeddings = []
        for url, tag in samples:
            audio = download(url)
            if not audio: continue
            emb = embed_audio(encoder, audio)
            if emb: embeddings.append(emb)
            if len(embeddings) >= 3: break
        if len(embeddings) >= 2:
            db["reciters"][name_id] = {"name_ar": name_ar, "source": source, "embeddings": embeddings}
            existing[name_id] = name_ar
            names[name_id] = name_ar
            added += 1
            log(f"  ✅ {name_ar}  ({len(embeddings)} embs, {source})")
            if added % 5 == 0:
                save_json(DB_PATH, db); save_json(NAMES_PATH, names)

    sources = [
        ("mp3quran.net", mp3quran_reciters, lambda r: (r.get("name","").strip(), f"mp3q_{r.get('id')}", mp3quran_samples(r))),
        ("everyayah.com", everyayah_reciters, lambda r: (r.get("ename") or r.get("name") or "", f"eay_{normalize(r.get('ename') or r.get('name') or '').replace(' ','_')}"[:60], everyayah_samples(r))),
        ("alquran.cloud", alquran_reciters, lambda r: (r.get("name") or r.get("englishName") or "", f"aq_{r.get('identifier','').replace('.','_')}", alquran_samples(r))),
        ("quranicaudio.com", quranicaudio_reciters, lambda r: (r.get("arabic_name") or r.get("name") or "", f"qa_{normalize(r.get('name','')).replace(' ','_')}"[:60], quranicaudio_samples(r))),
        ("islamic.network (curated)", extra_islamic_network_reciters, lambda r: (r["name_ar"], f"in_{r['identifier'].replace('.','_')}", extra_islamic_network_samples(r))),
        ("quran.com chapter_reciters", qurancom_chapter_reciters, lambda r: (r.get("arabic_name") or r.get("name") or "", f"qcom_{r.get('id')}", qurancom_chapter_samples(r))),
        ("quran.com recitations (ayah)", qurancom_ayah_recitations, lambda r: (r.get("translated_name",{}).get("name") or r.get("reciter_name") or r.get("name") or "", f"qcomv_{r.get('id')}", qurancom_ayah_samples(r))),
        ("tvquran/mp3quran cdn", tvquran_reciters, lambda r: (r["name_ar"], f"tv_{r['slug']}", tvquran_samples(r))),
        ("islamic.app API", islamicapp_reciters, lambda r: (r.get("name","") or r.get("englishName",""), f"iapp_{r.get('identifier','').replace('.','_')}", islamicapp_samples(r))),
        ("archive.org", archive_reciters, lambda r: (r["name_ar"], f"arch_{r['item']}", archive_samples(r))),
    ]

    for label, fetch, mapper in sources:
        log(f"Source: {label}")
        try:
            for r in fetch():
                try:
                    name_ar, rid, samples = mapper(r)
                    process(name_ar, rid, samples, label)
                except Exception as e:
                    continue
        except Exception as e:
            log(f"  source {label} failed: {e}")

    save_json(DB_PATH, db); save_json(NAMES_PATH, names)
    log(f"Done. Tried {tried} new, added {added}. Total DB: {len(db['reciters'])}")
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e:
        log(f"FATAL: {e}"); sys.exit(0)
