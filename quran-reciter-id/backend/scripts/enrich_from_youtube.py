"""dl + main for youtube enrichment (kept small)."""
import json, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _yt_helpers import DB, MT, RJ, RC, norm, bases, excel_names, save
PER = int(os.environ.get("YT_PER_RECITER","3"))
SEC = int(os.environ.get("YT_CLIP_SECONDS","60"))

def dl(name, per, out):
    from yt_dlp import YoutubeDL
    info = {}
    def hook(d):
        i = d.get("info_dict") or {}
        v = i.get("id")
        if v and v not in info:
            info[v] = {"url":f"https://www.youtube.com/watch?v={v}","title":i.get("title") or "","uploader":i.get("uploader") or ""}
    opts = {"quiet":True,"no_warnings":True,"format":"bestaudio/best",
        "outtmpl":str(out/"%(id)s.%(ext)s"),"noplaylist":True,"max_downloads":per*2,
        "postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"wav","preferredquality":"0"}],
        "postprocessor_args":["-ac","1","-ar","16000","-ss","10","-t",str(SEC)],
        "socket_timeout":30,"retries":2,"progress_hooks":[hook]}
    try:
        with YoutubeDL(opts) as y: y.download([f"ytsearch{per*2}:{name} \u0642\u0631\u0622\u0646"])
    except Exception as e: print(f"  [yt] {name}: {e}", flush=True)
    return sorted(out.glob("*.wav"))[:per], info

def main():
    print("="*70, flush=True); print("YouTube enrichment + report", flush=True); print("="*70, flush=True)
    names = excel_names()
    if not names: print("[exit] no excel", flush=True); return
    existing = bases()
    missing = [n for n in names if norm(n) not in existing]
    print(f"Excel:{len(names)} DB:{len(existing)} Missing:{len(missing)}", flush=True)
    if not missing: return
    from app.ai_engine import VoiceRecognitionEngine
    eng = VoiceRecognitionEngine()
    db = json.load(open(DB,encoding="utf-8")) if DB.exists() else {"version":"3.0-ensemble","reciters":[]}
    meta = json.load(open(MT,encoding="utf-8")) if MT.exists() else {"reciters":[]}
    rep = {"generated_at":time.strftime("%Y-%m-%d %H:%M:%S UTC",time.gmtime()),
        "excel_total":len(names),"already_in_db":len(existing),"missing_targeted":len(missing),"reciters":[]}
    tot = 0
    for i, name in enumerate(missing, 1):
        print(f"\n[{i}/{len(missing)}] {name}", flush=True)
        e = {"name":name,"status":"no_download","fingerprints_added":0,"videos":[],"error":""}
        try:
            with tempfile.TemporaryDirectory() as td:
                wavs, info = dl(name, PER, Path(td))
                if not wavs:
                    e["error"]="no downloads"; rep["reciters"].append(e); continue
                added = 0
                for j, wav in enumerate(wavs):
                    vid = wav.stem
                    vi = {**info.get(vid, {"url":f"https://www.youtube.com/watch?v={vid}","title":"","uploader":""}), "id":vid}
                    try:
                        if not eng.validate_audio_duration(wav, min_duration_sec=15):
                            vi["status"]="too_short"; e["videos"].append(vi); continue
                        emb = eng.process_audio_file(wav)
                        db["reciters"].append({"reciter_name":f"{name}#{j}","embedding":emb.tolist(),
                            "source":"youtube","video_id":vid,"video_url":vi["url"]})
                        added += 1; vi["status"]="fingerprinted"; e["videos"].append(vi)
                    except Exception as ex:
                        vi["status"]=f"error: {ex}"; e["videos"].append(vi)
                if added:
                    meta["reciters"].append({"name":name,"name_english":name,"country":"-",
                        "bio":f"YouTube - {added} samples","birth_year":"-","death_year":None,
                        "image_url":"","recitation_style":"murattal"})
                    tot += added; e["status"]="success"; e["fingerprints_added"]=added
                    print(f"  ok +{added}", flush=True)
                else: e["status"]="downloaded_but_no_valid_audio"
        except Exception as ex:
            e["status"]="exception"; e["error"]=str(ex)
        rep["reciters"].append(e)
        if i % 5 == 0: save(db, meta, rep)
        time.sleep(1)
    rep["summary"] = {"success":sum(1 for r in rep["reciters"] if r["status"]=="success"),
        "failed":sum(1 for r in rep["reciters"] if r["status"]!="success"),"total_fingerprints_added":tot}
    save(db, meta, rep)
    print(f"\nSUMMARY ok:{rep['summary']['success']} fail:{rep['summary']['failed']} +fps:{tot}", flush=True)
    print(f"report: {RJ.name} / {RC.name}", flush=True)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("interrupted")
