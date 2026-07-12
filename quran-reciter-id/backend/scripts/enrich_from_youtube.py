"""dl + main for youtube enrichment with auto-retry on failures."""
import json, os, sys, tempfile, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _yt_helpers import DB, MT, RJ, RC, norm, bases, excel_names, save

PER = int(os.environ.get("YT_PER_RECITER","3"))
SEC = int(os.environ.get("YT_CLIP_SECONDS","60"))
DL_RETRIES = int(os.environ.get("YT_DL_RETRIES","3"))
FP_RETRIES = int(os.environ.get("YT_FP_RETRIES","2"))

# search variations tried in order until one yields downloads
QUERY_VARIANTS = [
    "{name} قرآن",
    "{name} تلاوة",
    "{name} تلاوات",
    "{name} سورة",
    "{name} recitation quran",
]

def _dl_once(query, per, out):
    from yt_dlp import YoutubeDL
    info = {}
    def hook(d):
        i = d.get("info_dict") or {}
        v = i.get("id")
        if v and v not in info:
            info[v] = {"url": f"https://www.youtube.com/watch?v={v}",
                       "title": i.get("title") or "", "uploader": i.get("uploader") or ""}
    opts = {"quiet":True,"no_warnings":True,"format":"bestaudio/best",
        "outtmpl":str(out/"%(id)s.%(ext)s"),"noplaylist":True,"max_downloads":per*2,
        "postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"wav","preferredquality":"0"}],
        "postprocessor_args":["-ac","1","-ar","16000","-ss","10","-t",str(SEC)],
        "socket_timeout":30,"retries":3,"fragment_retries":3,
        "progress_hooks":[hook]}
    with YoutubeDL(opts) as y:
        y.download([f"ytsearch{per*2}:{query}"])
    return sorted(out.glob("*.wav"))[:per], info

def dl_with_retry(name, per, out, log):
    """Try each query variant; if a variant yields wavs, return. Else retry with backoff."""
    last_err = ""
    tried = []
    for attempt in range(1, DL_RETRIES + 1):
        variant = QUERY_VARIANTS[(attempt - 1) % len(QUERY_VARIANTS)]
        q = variant.format(name=name)
        tried.append(q)
        try:
            # clean previous partial files between attempts
            for f in out.glob("*"):
                try: f.unlink()
                except OSError: pass
            wavs, info = _dl_once(q, per, out)
            if wavs:
                log(f"  [dl ok] attempt {attempt} query='{q}' -> {len(wavs)} clip(s)")
                return wavs, info, tried, ""
            log(f"  [dl empty] attempt {attempt} query='{q}'")
        except Exception as e:
            last_err = str(e)
            log(f"  [dl err] attempt {attempt} query='{q}': {e}")
        time.sleep(2 + random.random() * 3 * attempt)  # backoff
    return [], {}, tried, last_err or "no downloads across variants"

def fingerprint_with_retry(engine, wav, log):
    """Retry embedding extraction on transient errors (CUDA/OOM/decoding blips)."""
    last = ""
    for attempt in range(1, FP_RETRIES + 1):
        try:
            if not engine.validate_audio_duration(wav, min_duration_sec=15):
                return None, "too_short"
            return engine.process_audio_file(wav), ""
        except Exception as ex:
            last = str(ex)
            log(f"    [fp err] attempt {attempt}: {ex}")
            time.sleep(1.5 * attempt)
    return None, f"error: {last}"

def main():
    print("="*70, flush=True)
    print("YouTube enrichment + report (auto-retry enabled)", flush=True)
    print(f"DL_RETRIES={DL_RETRIES} FP_RETRIES={FP_RETRIES} PER={PER} SEC={SEC}", flush=True)
    print("="*70, flush=True)
    names = excel_names()
    if not names: print("[exit] no excel", flush=True); return
    existing = bases()
    missing = [n for n in names if norm(n) not in existing]
    print(f"Excel:{len(names)} DB:{len(existing)} Missing:{len(missing)}", flush=True)
    if not missing: return
    from app.ai_engine import VoiceRecognitionEngine
    eng = VoiceRecognitionEngine()
    db = json.load(open(DB, encoding="utf-8")) if DB.exists() else {"version":"3.0-ensemble","reciters":[]}
    meta = json.load(open(MT, encoding="utf-8")) if MT.exists() else {"reciters":[]}
    rep = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "excel_total":len(names), "already_in_db":len(existing), "missing_targeted":len(missing),
        "config":{"dl_retries":DL_RETRIES,"fp_retries":FP_RETRIES,"per_reciter":PER,"clip_seconds":SEC},
        "reciters":[]}
    tot = 0
    for i, name in enumerate(missing, 1):
        print(f"\n[{i}/{len(missing)}] {name}", flush=True)
        def log(m): print(m, flush=True)
        e = {"name":name,"status":"no_download","fingerprints_added":0,"videos":[],
             "attempts":0,"queries_tried":[],"error":""}
        try:
            with tempfile.TemporaryDirectory() as td:
                wavs, info, tried, err = dl_with_retry(name, PER, Path(td), log)
                e["queries_tried"] = tried
                e["attempts"] = len(tried)
                if not wavs:
                    e["error"] = err or "no downloads"
                    rep["reciters"].append(e); continue
                added = 0
                for j, wav in enumerate(wavs):
                    vid = wav.stem
                    vi = {**info.get(vid, {"url":f"https://www.youtube.com/watch?v={vid}","title":"","uploader":""}), "id":vid}
                    emb, err = fingerprint_with_retry(eng, wav, log)
                    if emb is None:
                        vi["status"] = err
                    else:
                        db["reciters"].append({"reciter_name":f"{name}#{j}","embedding":emb.tolist(),
                            "source":"youtube","video_id":vid,"video_url":vi["url"]})
                        added += 1; vi["status"] = "fingerprinted"
                    e["videos"].append(vi)
                if added:
                    meta["reciters"].append({"name":name,"name_english":name,"country":"-",
                        "bio":f"YouTube - {added} samples","birth_year":"-","death_year":None,
                        "image_url":"","recitation_style":"murattal"})
                    tot += added; e["status"]="success"; e["fingerprints_added"]=added
                    print(f"  ok +{added}", flush=True)
                else:
                    e["status"]="downloaded_but_no_valid_audio"
        except Exception as ex:
            e["status"]="exception"; e["error"]=str(ex)
        rep["reciters"].append(e)
        if i % 5 == 0: save(db, meta, rep)
        time.sleep(1)
    rep["summary"] = {"success":sum(1 for r in rep["reciters"] if r["status"]=="success"),
        "failed":sum(1 for r in rep["reciters"] if r["status"]!="success"),
        "total_fingerprints_added":tot,
        "avg_dl_attempts": round(sum(r.get("attempts",0) for r in rep["reciters"])/max(1,len(rep["reciters"])), 2)}
    save(db, meta, rep)
    print(f"\nSUMMARY ok:{rep['summary']['success']} fail:{rep['summary']['failed']} +fps:{tot} avg_attempts:{rep['summary']['avg_dl_attempts']}", flush=True)
    print(f"report: {RJ.name} / {RC.name}", flush=True)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("interrupted")
