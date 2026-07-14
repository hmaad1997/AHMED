from __future__ import annotations
import asyncio, os, sqlite3, uuid
from collections import Counter
from pathlib import Path
from typing import Optional
MATCH_THRESHOLD=int(os.environ.get('FP_MATCH_THRESHOLD','30'))
def _db():
 p=Path(os.environ.get('FINGERPRINT_DB_PATH','/home/user/app/data/fingerprints.sqlite3'))
 try:p.parent.mkdir(parents=True,exist_ok=True);(p.parent/'.t').write_text('x');(p.parent/'.t').unlink()
 except Exception:p=Path('/tmp/fingerprints.sqlite3')
 return p
DB_PATH=_db()
def _conn():
 DB_PATH.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(str(DB_PATH),timeout=60,check_same_thread=False);c.row_factory=sqlite3.Row
 c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=NORMAL')
 c.executescript('''CREATE TABLE IF NOT EXISTS reciters(id TEXT PRIMARY KEY,external_id TEXT UNIQUE,name_ar TEXT NOT NULL,name_en TEXT DEFAULT '',country TEXT DEFAULT '',image_url TEXT DEFAULT '',bio TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS recitations(id TEXT PRIMARY KEY,reciter_id TEXT NOT NULL,surah_number INTEGER NOT NULL,surah_name_ar TEXT NOT NULL,riwayah TEXT,source TEXT NOT NULL,source_url TEXT,duration_sec INTEGER,fingerprint_count INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(reciter_id,surah_number,source,source_url));
CREATE TABLE IF NOT EXISTS fingerprints(hash INTEGER NOT NULL,offset_ms INTEGER NOT NULL,recitation_id TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_fp_hash ON fingerprints(hash);CREATE INDEX IF NOT EXISTS idx_fp_rec ON fingerprints(recitation_id);''');c.commit();return c
def upsert_reciter_sync(name_ar:str,name_en:str='',external_id:str|None=None,country:str='',image_url:str='',bio:str='')->str:
 external_id=external_id or name_ar
 with _conn() as c:
  r=c.execute('SELECT id FROM reciters WHERE external_id=?',(external_id,)).fetchone()
  if r:return r['id']
  rid=str(uuid.uuid4());c.execute('INSERT INTO reciters(id,external_id,name_ar,name_en,country,image_url,bio) VALUES(?,?,?,?,?,?,?)',(rid,external_id,name_ar,name_en,country,image_url,bio));c.commit();return rid
def recitation_exists_sync(reciter_id:str,surah_number:int,source:str='mp3quran',source_url:str|None=None)->bool:
 with _conn() as c:
  if source_url:r=c.execute('SELECT 1 FROM recitations WHERE reciter_id=? AND surah_number=? AND source=? AND source_url=? LIMIT 1',(reciter_id,surah_number,source,source_url)).fetchone()
  else:r=c.execute('SELECT 1 FROM recitations WHERE reciter_id=? AND surah_number=? AND source=? LIMIT 1',(reciter_id,surah_number,source)).fetchone()
  return bool(r)
def insert_recitation_sync(reciter_id:str,surah_number:int,surah_name_ar:str,source:str,riwayah:str|None=None,source_url:str|None=None,duration_sec:int|None=None)->str:
 with _conn() as c:
  old=c.execute('SELECT id FROM recitations WHERE reciter_id=? AND surah_number=? AND source=? AND source_url=?',(reciter_id,surah_number,source,source_url)).fetchone()
  if old:return old['id']
  rid=str(uuid.uuid4());c.execute('INSERT INTO recitations(id,reciter_id,surah_number,surah_name_ar,riwayah,source,source_url,duration_sec) VALUES(?,?,?,?,?,?,?,?)',(rid,reciter_id,surah_number,surah_name_ar,riwayah,source,source_url,duration_sec));c.commit();return rid
def bulk_insert_fingerprints_sync(recitation_id:str,hashes:list[tuple[int,int]]):
 if not hashes:return
 with _conn() as c:
  c.executemany('INSERT INTO fingerprints(hash,offset_ms,recitation_id) VALUES(?,?,?)',[(int(h),int(o),recitation_id) for h,o in hashes]);c.execute('UPDATE recitations SET fingerprint_count=? WHERE id=?',(len(hashes),recitation_id));c.commit()
def match_fingerprints_sync(query_hashes:list[tuple[int,int]])->Optional[dict]:
 if not query_hashes:return None
 q={int(h):int(o) for h,o in query_hashes};rows=[]
 with _conn() as c:
  hs=list(q.keys())
  for i in range(0,len(hs),500):
   ch=hs[i:i+500];rows+=c.execute(f"SELECT recitation_id,hash,offset_ms FROM fingerprints WHERE hash IN ({','.join('?' for _ in ch)})",ch).fetchall()
  if not rows:return None
  cnt=Counter((r['recitation_id'],int(r['offset_ms'])-q.get(int(r['hash']),0)) for r in rows if int(r['hash']) in q)
  if not cnt:return None
  (rid,delta),best=cnt.most_common(1)[0]
  if best<MATCH_THRESHOLD:return None
  rec=c.execute('''SELECT r.id recitation_id,r.surah_number,r.surah_name_ar,r.riwayah,r.source,r.fingerprint_count,c.id reciter_id,c.name_ar,c.name_en,c.country,c.image_url,c.bio FROM recitations r JOIN reciters c ON c.id=r.reciter_id WHERE r.id=?''',(rid,)).fetchone()
  if not rec:return None
  score=min(1.0,best/max(50,len(query_hashes)*.1))
  return {'recitation_id':rec['recitation_id'],'surah_number':rec['surah_number'],'surah_name_ar':rec['surah_name_ar'],'riwayah':rec['riwayah'],'source':rec['source'],'offset_ms':max(0,int(delta)),'match_score':score,'aligned_hashes':int(best),'reciter':{'id':rec['reciter_id'],'name_ar':rec['name_ar'],'name_en':rec['name_en'] or '','country':rec['country'] or '','image_url':rec['image_url'] or '','bio':rec['bio'] or ''}}
def stats_sync()->dict:
 with _conn() as c:return {'db_path':str(DB_PATH),'reciters':c.execute('SELECT COUNT(*) c FROM reciters').fetchone()['c'],'recitations':c.execute('SELECT COUNT(*) c FROM recitations').fetchone()['c'],'fingerprints':c.execute('SELECT COUNT(*) c FROM fingerprints').fetchone()['c'],'match_threshold':MATCH_THRESHOLD}
async def insert_recitation(*a,**k):return await asyncio.to_thread(insert_recitation_sync,*a,**k)
async def bulk_insert_fingerprints(*a,**k):return await asyncio.to_thread(bulk_insert_fingerprints_sync,*a,**k)
async def match_fingerprints(*a,**k):return await asyncio.to_thread(match_fingerprints_sync,*a,**k)
