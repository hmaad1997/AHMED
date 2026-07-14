from __future__ import annotations
import hashlib,os,random,tempfile,threading,time,traceback,requests
MP3='https://mp3quran.net/api/v3/reciters?language=ar';SURAHS='https://mp3quran.net/api/v3/suwar?language=ar'
REST_MINUTES=int(os.environ.get('FP_REST_MINUTES','60'));MAX_PER_CYCLE=int(os.environ.get('FP_MAX_PER_CYCLE','3'));MAX_DURATION_SEC=int(os.environ.get('FP_MAX_DURATION','1800'))
AUTO_ENABLED=os.environ.get('AUTO_FINGERPRINT_ENABLED','true').lower() not in {'0','false','no'}
try:from .fingerprint_db import upsert_reciter_sync,recitation_exists_sync,insert_recitation_sync,bulk_insert_fingerprints_sync,stats_sync
except Exception:from app.fingerprint_db import upsert_reciter_sync,recitation_exists_sync,insert_recitation_sync,bulk_insert_fingerprints_sync,stats_sync
_STATE={'enabled':AUTO_ENABLED,'running':False,'total_reciters':0,'processed':0,'current_reciter':None,'current_surah':None,'last_run':None,'last_error':None,'db':{}}
def generate_fingerprints(audio_path:str):
 import numpy as np,subprocess
 from scipy.io import wavfile
 from scipy.signal import spectrogram
 wav=audio_path+'.wav';subprocess.run(['ffmpeg','-y','-i',audio_path,'-ac','1','-ar','11025',wav],check=True,capture_output=True,timeout=300)
 sr,s=wavfile.read(wav);os.unlink(wav)
 if getattr(s,'ndim',1)>1:s=s.mean(axis=1)
 s=s.astype(np.float32);dur=len(s)/float(sr);_,t,S=spectrogram(s,fs=sr,nperseg=4096,noverlap=2048);L=np.log1p(S);peaks=[]
 for ti in range(1,L.shape[1]-1):
  col=L[:,ti];thr=col.mean()+1.2*col.std()
  for fi in range(20,len(col)-1):
   v=col[fi]
   if v>thr and v>col[fi-1] and v>col[fi+1] and v>L[fi,ti-1] and v>L[fi,ti+1]:peaks.append((fi,int(t[ti]*1000)))
 out=[]
 for i,(f1,t1) in enumerate(peaks):
  for j in range(1,9):
   if i+j>=len(peaks):break
   f2,t2=peaks[i+j];dt=t2-t1
   if 20<dt<3000:out.append((int.from_bytes(hashlib.sha1(f'{f1}|{f2}|{dt}'.encode()).digest()[:6],'big')&0x7FFFFFFFFFFFFFFF,t1))
 return out,dur
def _download(url):
 f=tempfile.NamedTemporaryFile(suffix='.mp3',delete=False)
 try:
  with requests.get(url,stream=True,timeout=120) as r:
   if r.status_code!=200:return None
   for ch in r.iter_content(65536):
    f.write(ch)
    if f.tell()>55*1024*1024:break
  f.close();return f.name
 except Exception:
  try:os.unlink(f.name)
  except Exception:pass
  return None
def _one(reciter,surah):
 ext=str(reciter.get('id'));name=reciter.get('name') or 'قارئ غير معروف';sn=int(surah.get('id',0))
 if not 1<=sn<=114:return False
 rid=upsert_reciter_sync(name_ar=name,external_id=ext);server=((reciter.get('moshaf') or [{}])[0].get('server','')).rstrip('/')
 if not server:return False
 url=f'{server}/{sn:03d}.mp3'
 if recitation_exists_sync(rid,sn,'mp3quran',url):return False
 _STATE['current_reciter']=name;_STATE['current_surah']=surah.get('name') or str(sn);print(f'[AutoFP] → {name} — {sn}',flush=True)
 p=_download(url)
 if not p:return False
 try:
  hashes,dur=generate_fingerprints(p)
  if dur>MAX_DURATION_SEC or len(hashes)<100:return False
  recid=insert_recitation_sync(rid,sn,surah.get('name',f'سورة {sn}'),'mp3quran',(reciter.get('moshaf') or [{}])[0].get('name',''),url,int(dur))
  bulk_insert_fingerprints_sync(recid,hashes);_STATE['processed']+=1;_STATE['db']=stats_sync();print(f'[AutoFP] ✓ {len(hashes)} fingerprints',flush=True);return True
 finally:
  try:os.unlink(p)
  except Exception:pass
def _cycle():
 _STATE['running']=True
 try:
  reciters=requests.get(MP3,timeout=30).json().get('reciters',[]);surahs=requests.get(SURAHS,timeout=30).json().get('suwar',[]);_STATE['total_reciters']=len(reciters);random.shuffle(reciters);done=0
  for r in reciters:
   if done>=MAX_PER_CYCLE:break
   for s in random.sample(surahs,min(6,len(surahs))):
    try:
     if _one(r,s):done+=1;break
    except Exception as e:print(f'[AutoFP] ✗ {e}',flush=True)
  _STATE['last_run']=time.time();_STATE['last_error']=None;_STATE['db']=stats_sync()
 except Exception as e:_STATE['last_error']=str(e);traceback.print_exc()
 finally:_STATE['running']=False;_STATE['current_reciter']=None;_STATE['current_surah']=None
def worker_loop():
 print('[AutoFP] worker started — local SQLite mode',flush=True)
 while True:_cycle();time.sleep(REST_MINUTES*60)
def start_worker_thread():
 if not AUTO_ENABLED:print('[AutoFP] disabled',flush=True);return
 threading.Thread(target=worker_loop,daemon=True,name='auto-fp-worker').start();print('[AutoFP] launched ✓',flush=True)
def get_state():
 s=dict(_STATE)
 try:s['db']=stats_sync()
 except Exception as e:s['db_error']=str(e)
 return s
if __name__=='__main__':_cycle();print(get_state())
