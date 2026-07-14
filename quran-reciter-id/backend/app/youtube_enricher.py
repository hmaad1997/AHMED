"""YouTube Auto-Enricher: يبحث بيوتيوب عن قارئ، ينزّل الصوت، ويحفظه كبصمة."""
from __future__ import annotations
import os, json, tempfile, subprocess, traceback, threading, time
try:
    from .fingerprint_db import upsert_reciter_sync, recitation_exists_sync, insert_recitation_sync, bulk_insert_fingerprints_sync, stats_sync
    from .auto_fingerprint_worker import generate_fingerprints
except Exception:
    from app.fingerprint_db import upsert_reciter_sync, recitation_exists_sync, insert_recitation_sync, bulk_insert_fingerprints_sync, stats_sync
    from app.auto_fingerprint_worker import generate_fingerprints

MAX_DURATION = int(os.environ.get('YT_MAX_DURATION', '1800'))  # 30 min
MIN_DURATION = int(os.environ.get('YT_MIN_DURATION', '120'))   # 2 min
MAX_FILESIZE = int(os.environ.get('YT_MAX_FILESIZE_MB', '60')) * 1024 * 1024

_STATE = {'running': False, 'processed': 0, 'failed': 0, 'current': None, 'last_error': None, 'last_run': None}


def _yt_search(query: str, max_results: int = 3):
    """يبحث بيوتيوب ويرجّع قائمة (video_id, title, duration)."""
    try:
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--no-warnings',
               '--default-search', 'ytsearch', f'ytsearch{max_results}:{query} تلاوة قرآن']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = []
        for line in r.stdout.strip().split('\n'):
            if not line.strip(): continue
            try:
                j = json.loads(line)
                out.append({
                    'id': j.get('id'),
                    'title': j.get('title', ''),
                    'url': j.get('url') or f"https://youtube.com/watch?v={j.get('id')}",
                    'duration': j.get('duration') or 0
                })
            except Exception: continue
        return out
    except Exception as e:
        print(f'[YT] search failed: {e}', flush=True); return []


def _yt_download_audio(video_url: str) -> str | None:
    """ينزّل الصوت كـ mp3."""
    tmp = tempfile.mkdtemp(prefix='yt_')
    out_tpl = os.path.join(tmp, '%(id)s.%(ext)s')
    try:
        cmd = ['yt-dlp', '-x', '--audio-format', 'mp3', '--audio-quality', '5',
               '--max-filesize', f'{MAX_FILESIZE}', '--no-playlist', '--no-warnings',
               '-o', out_tpl, video_url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            print(f'[YT] download failed: {r.stderr[:200]}', flush=True); return None
        for f in os.listdir(tmp):
            if f.endswith('.mp3'): return os.path.join(tmp, f)
    except Exception as e:
        print(f'[YT] download error: {e}', flush=True)
    return None


def enrich_reciter(reciter_name: str, max_videos: int = 2) -> dict:
    """يبحث عن قارئ ويضيف حتى max_videos تلاوة."""
    _STATE['current'] = reciter_name
    added, failed, details = 0, 0, []
    try:
        rid = upsert_reciter_sync(name_ar=reciter_name, external_id=f'yt:{reciter_name}')
        results = _yt_search(reciter_name, max_results=max_videos * 2)
        for v in results[:max_videos * 2]:
            if added >= max_videos: break
            dur = v.get('duration') or 0
            if dur and (dur < MIN_DURATION or dur > MAX_DURATION):
                details.append({'title': v['title'], 'skip': f'duration {dur}s'}); continue
            if recitation_exists_sync(rid, 0, 'youtube', v['url']):
                details.append({'title': v['title'], 'skip': 'exists'}); continue
            path = _yt_download_audio(v['url'])
            if not path:
                failed += 1; details.append({'title': v['title'], 'skip': 'download failed'}); continue
            try:
                hashes, actual_dur = generate_fingerprints(path)
                if len(hashes) < 100:
                    failed += 1; details.append({'title': v['title'], 'skip': f'too few hashes ({len(hashes)})'}); continue
                recid = insert_recitation_sync(rid, 0, v['title'][:200], 'youtube', 'YouTube', v['url'], int(actual_dur))
                bulk_insert_fingerprints_sync(recid, hashes)
                added += 1; _STATE['processed'] += 1
                details.append({'title': v['title'], 'ok': True, 'fingerprints': len(hashes), 'duration': int(actual_dur)})
                print(f'[YT] ✓ {reciter_name} — {v["title"][:60]} ({len(hashes)} fp)', flush=True)
            finally:
                try: os.unlink(path); os.rmdir(os.path.dirname(path))
                except Exception: pass
    except Exception as e:
        _STATE['last_error'] = str(e); traceback.print_exc()
        return {'ok': False, 'error': str(e), 'added': added}
    finally:
        _STATE['current'] = None; _STATE['last_run'] = time.time()
    return {'ok': True, 'reciter': reciter_name, 'added': added, 'failed': failed, 'details': details, 'db': stats_sync()}


def enrich_batch_async(names: list[str], max_videos: int = 1):
    """يشغّل قائمة قراء بالخلفية."""
    def _run():
        _STATE['running'] = True
        try:
            for n in names:
                if not n or not n.strip(): continue
                try: enrich_reciter(n.strip(), max_videos=max_videos)
                except Exception as e: print(f'[YT] batch err {n}: {e}', flush=True)
                time.sleep(3)
        finally: _STATE['running'] = False
    threading.Thread(target=_run, daemon=True, name='yt-enricher').start()
    return {'ok': True, 'started': len(names)}


def get_state(): return dict(_STATE)
