"""Multi-source auto fingerprint enricher for "من القارئ".
Sources: MP3Quran, EveryAyah, Al-Quran Cloud, Archive.org, YouTube (fallback).
"""
from __future__ import annotations
import os, re, tempfile, logging, urllib.parse
from typing import List, Optional
import httpx
from rapidfuzz import fuzz
from .ai_engine import extract_embedding
from .fingerprint_db import save_fingerprint, reciter_exists

log = logging.getLogger("multi_enricher")
UA = {"User-Agent": "MinAlQari/1.0"}
T = httpx.Timeout(30.0, connect=10.0)

def _n(s): 
    s = re.sub(r"[إأآا]","ا",s or ""); s = re.sub(r"[ىي]","ي",s)
    s = re.sub(r"[ةه]","ه",s); return re.sub(r"\s+"," ",s).strip()
def _m(a,b,t=82): return fuzz.token_set_ratio(_n(a),_n(b))>=t

def src_mp3quran(name, limit=3):
    urls=[]
    try:
        with httpx.Client(timeout=T,headers=UA) as c:
            for r in c.get("https://mp3quran.net/api/v3/reciters",params={"language":"ar"}).json().get("reciters",[]):
                if _m(name,r.get("name","")):
                    for mo in r.get("moshaf",[])[:1]:
                        srv=mo.get("server","").rstrip("/")
                        for s in (mo.get("surah_list") or "").split(",")[:limit]:
                            if s.strip().isdigit(): urls.append(f"{srv}/{int(s):03d}.mp3")
                    if urls: break
    except Exception as e: log.warning("mp3quran %s: %s",name,e)
    return urls

EA={"الحصري":"Husary_128kbps","المنشاوي":"Minshawy_Murattal_128kbps",
    "عبد الباسط":"Abdul_Basit_Murattal_192kbps","السديس":"Abdurrahmaan_As-Sudais_192kbps",
    "الشريم":"Saood_ash-Shuraym_128kbps","العجمي":"Ahmed_ibn_Ali_al-Ajamy_128kbps",
    "الغامدي":"Ghamadi_40kbps","المعيقلي":"MaherAlMuaiqly128kbps"}
def src_everyayah(name, limit=3):
    for k,f in EA.items():
        if _m(name,k,78):
            return [f"https://everyayah.com/data/{f}/{n}.mp3" for n in ("001001","002001","112001")][:limit]
    return []

AC={"الأفاسي":"ar.alafasy","العفاسي":"ar.alafasy","الحصري":"ar.husary",
    "المنشاوي":"ar.minshawi","عبد الباسط":"ar.abdulbasitmurattal",
    "السديس":"ar.abdurrahmaansudais","الشريم":"ar.saoodshuraym",
    "أيوب":"ar.muhammadayyoub","الجهني":"ar.hanirifai"}
def src_alquran(name, limit=3):
    for k,i in AC.items():
        if _m(name,k,78):
            return [f"https://cdn.islamic.network/quran/audio-surah/128/{i}/{n}.mp3" for n in (1,36,55)][:limit]
    return []

def src_archive(name, limit=2):
    urls=[]
    try:
        q=f'({name}) AND mediatype:(audio) AND (subject:quran OR subject:قرآن)'
        with httpx.Client(timeout=T,headers=UA) as c:
            r=c.get("https://archive.org/advancedsearch.php",params={"q":q,"fl[]":"identifier","rows":limit,"output":"json"})
            for d in r.json().get("response",{}).get("docs",[]):
                i=d.get("identifier")
                for fi in c.get(f"https://archive.org/metadata/{i}").json().get("files",[]):
                    if fi.get("format","").lower() in ("vbr mp3","mp3","128kbps mp3"):
                        urls.append(f"https://archive.org/download/{i}/{urllib.parse.quote(fi['name'])}"); break
                if len(urls)>=limit: break
    except Exception as e: log.warning("archive %s: %s",name,e)
    return urls

def src_youtube(name, limit=2):
    try: import yt_dlp
    except ImportError: return []
    urls=[]
    try:
        with yt_dlp.YoutubeDL({"quiet":True,"skip_download":True,"extract_flat":True,
                               "default_search":f"ytsearch{limit}"}) as y:
            info=y.extract_info(f"القارئ {name} تلاوة",download=False)
            for e in (info.get("entries") or [])[:limit]:
                if e and e.get("id"): urls.append(f"https://www.youtube.com/watch?v={e['id']}")
    except Exception as e: log.warning("yt %s: %s",name,e)
    return urls

SOURCES=[("mp3quran",src_mp3quran),("everyayah",src_everyayah),
         ("alquran_cloud",src_alquran),("archive",src_archive),("youtube",src_youtube)]

def _dl(url):
    tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".audio"); tmp.close()
    try:
        if "youtube.com" in url or "youtu.be" in url:
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet":True,"format":"bestaudio/best","outtmpl":tmp.name+".%(ext)s",
                "postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}]}) as y:
                y.download([url])
            return tmp.name+".mp3"
        with httpx.stream("GET",url,timeout=T,headers=UA,follow_redirects=True) as r:
            r.raise_for_status()
            with open(tmp.name,"wb") as f:
                for ch in r.iter_bytes(65536): f.write(ch)
        return tmp.name
    except Exception as e: log.warning("dl %s: %s",url,e); return None

def enrich_reciter(name, max_per_source=2, skip_existing=True):
    if skip_existing and reciter_exists(name):
        return {"reciter":name,"status":"already_exists","added":0}
    added=0; tried=[]; errs=[]
    for sn,fn in SOURCES:
        try: urls=fn(name,limit=max_per_source)
        except Exception as e: errs.append(f"{sn}:{e}"); continue
        for u in urls:
            tried.append({"source":sn,"url":u})
            p=_dl(u)
            if not p: continue
            try:
                save_fingerprint(name,extract_embedding(p),source=sn,url=u); added+=1
            except Exception as e: errs.append(f"{sn}-emb:{e}")
            finally:
                try: os.remove(p)
                except: pass
        if added>=max_per_source: break
    return {"reciter":name,"status":"ok" if added else "no_audio_found",
            "added":added,"tried":len(tried),"errors":errs[:5]}

def enrich_batch(names, max_per_source=2):
    res=[enrich_reciter(n,max_per_source) for n in names]
    return {"total":len(res),
            "succeeded":sum(1 for r in res if r["added"]>0),
            "skipped":sum(1 for r in res if r["status"]=="already_exists"),
            "failed":sum(1 for r in res if r["status"]=="no_audio_found"),
            "results":res}
