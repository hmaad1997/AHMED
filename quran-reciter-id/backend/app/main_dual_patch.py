"""/identify-dual endpoint. Import to register on app.main.app."""
import asyncio,logging,tempfile
from io import BytesIO
from pathlib import Path
from fastapi import File,HTTPException,UploadFile
from starlette.datastructures import UploadFile as SUF
from .main import app,_prepare_audio,_model_not_ready_message
from . import main as _m
log=logging.getLogger(__name__)
try:
 from .fingerprint_engine import fingerprint_audio,frames_to_ms
 from .fingerprint_db import match_fingerprints
 _FP=True
except Exception as e:
 _FP=False;log.warning(f"FP off:{e}")
@app.post("/identify-dual")
async def identify_dual(audio_file:UploadFile=File(...)):
 if _m.ai_engine is None:raise HTTPException(503,_model_not_ready_message())
 b=await audio_file.read();fn=audio_file.filename or "a.wav";sfx=Path(fn).suffix or ".wav"
 with tempfile.NamedTemporaryFile(suffix=sfx,delete=False) as t:t.write(b);tp=Path(t.name)
 async def sp():return await _m.identify_reciter(SUF(filename=fn,file=BytesIO(b)))
 async def fp():
  if not _FP:return None
  ap=_prepare_audio(tp,fn)
  hf=await asyncio.to_thread(fingerprint_audio,str(ap))
  return await match_fingerprints([(h,frames_to_ms(o)) for h,o in hf])
 try:sr,fr=await asyncio.gather(sp(),fp(),return_exceptions=True)
 finally:
  try:tp.unlink()
  except Exception:pass
 if isinstance(sr,Exception):sd={"success":False,"reciter_name":"Unknown","confidence":0.0,"is_unknown":True,"top_matches":[]}
 else:sd=sr.model_dump() if hasattr(sr,"model_dump") else dict(sr)
 if isinstance(fr,Exception):fr=None
 r=dict(sd)
 if fr:
  r["recitation"]={k:fr.get(k) for k in ("recitation_id","surah_number","surah_name_ar","riwayah","source","offset_ms","match_score")}
  r["method"]="combined"
  fpn=(fr.get("reciter") or {}).get("name_ar")
  if fpn and fpn==r.get("reciter_name"):r["confidence"]=min(1.0,float(r.get("confidence",0))+0.15)
  elif fpn:r["reciter_name"]=fpn;r["confidence"]=float(fr.get("match_score",0));r["is_unknown"]=False
 else:r["method"]="speaker";r["recitation"]=None
 return r
