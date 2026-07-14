"""
🎙️ من القارئ - أداة البصمات المحلية
=====================================
تقرأ ملف Excel فيه أسماء القراء، تحمل من YouTube، تستخرج البصمات، وترفعها للسيرفر.

الاستخدام:
    python local_fingerprint_tool.py القراء.xlsx
"""
import sys, os, json, hashlib, time, subprocess, tempfile
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
    import librosa
    import requests
    from tqdm import tqdm
except ImportError:
    print("❌ ناقص مكتبات. شغّل:")
    print("   pip install pandas openpyxl librosa numpy requests tqdm yt-dlp")
    sys.exit(1)

# ===== إعدادات =====
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://sjeekqasnjyaaxkjpvud.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")  # ضروري - service role key
MAX_PER_RECITER = 3     # كم فيديو لكل قارئ
MAX_DURATION = 600      # ثواني - تجاهل الفيديوهات الأطول من 10 دقايق
SAMPLE_RATE = 22050
TARGET_ZONE_SIZE = 5
FAN_VALUE = 5

def search_youtube(query, max_results=3):
    """يبحث في YouTube ويرجع روابط الفيديوهات"""
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings",
           "--playlist-end", str(max_results), f"ytsearch{max_results}:{query}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        videos = []
        for line in result.stdout.strip().split("\n"):
            if line:
                v = json.loads(line)
                if v.get("duration", 999999) < MAX_DURATION:
                    videos.append({"id": v["id"], "title": v.get("title", ""),
                                   "url": f"https://youtube.com/watch?v={v['id']}",
                                   "duration": v.get("duration", 0)})
        return videos
    except Exception as e:
        print(f"  ⚠️ فشل البحث: {e}")
        return []

def download_audio(url, output_path):
    """يحمل صوت الفيديو كـ WAV"""
    cmd = ["yt-dlp", "-x", "--audio-format", "wav", "--audio-quality", "0",
           "-o", output_path, "--no-warnings", "--quiet", url]
    try:
        subprocess.run(cmd, check=True, timeout=300, capture_output=True)
        return True
    except Exception as e:
        print(f"  ⚠️ فشل التحميل: {e}")
        return False

def extract_fingerprints(audio_path):
    """يستخرج البصمات - نفس خوارزمية السيرفر"""
    try:
        y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
        # Spectrogram
        S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
        S_db = librosa.amplitude_to_db(S, ref=np.max)
        # Peak picking
        from scipy.ndimage import maximum_filter
        neighborhood = maximum_filter(S_db, size=(20, 20))
        peaks = (S_db == neighborhood) & (S_db > -60)
        peak_coords = np.argwhere(peaks)
        # Sort by time
        peak_coords = peak_coords[peak_coords[:, 1].argsort()]
        # Generate hashes (anchor + target pairs)
        hashes = []
        for i, (f1, t1) in enumerate(peak_coords):
            for j in range(1, min(FAN_VALUE + 1, len(peak_coords) - i)):
                f2, t2 = peak_coords[i + j]
                dt = t2 - t1
                if 0 < dt <= 200:
                    h_str = f"{f1}|{f2}|{dt}"
                    h = int(hashlib.sha1(h_str.encode()).hexdigest()[:15], 16)
                    hashes.append({"hash": h, "offset_ms": int(t1 * 512 * 1000 / sr)})
        return hashes, len(y) / sr
    except Exception as e:
        print(f"  ⚠️ فشل استخراج البصمات: {e}")
        return [], 0

def get_or_create_reciter(name_ar):
    """يجيب أو ينشئ قارئ في السيرفر"""
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
               "Content-Type": "application/json"}
    # ابحث أول
    r = requests.get(f"{SUPABASE_URL}/rest/v1/reciters",
                     params={"name_ar": f"eq.{name_ar}", "select": "id"}, headers=headers)
    if r.ok and r.json():
        return r.json()[0]["id"]
    # أنشئ
    r = requests.post(f"{SUPABASE_URL}/rest/v1/reciters",
                      json={"name_ar": name_ar}, headers={**headers, "Prefer": "return=representation"})
    if r.ok:
        return r.json()[0]["id"]
    print(f"  ⚠️ فشل إنشاء القارئ: {r.text}")
    return None

def upload_recitation(reciter_id, video_info, hashes, duration):
    """يرفع تلاوة + بصماتها للسيرفر"""
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
               "Content-Type": "application/json", "Prefer": "return=representation"}
    # أنشئ تلاوة
    rec_data = {"reciter_id": reciter_id, "surah_number": 0,
                "surah_name_ar": video_info["title"][:200], "source": "youtube",
                "source_url": video_info["url"], "duration_sec": int(duration),
                "sample_rate": SAMPLE_RATE, "fingerprint_count": len(hashes)}
    r = requests.post(f"{SUPABASE_URL}/rest/v1/recitations", json=rec_data, headers=headers)
    if not r.ok:
        print(f"  ⚠️ فشل رفع التلاوة: {r.text}")
        return False
    recitation_id = r.json()[0]["id"]
    # ارفع البصمات (دفعات 1000)
    for i in range(0, len(hashes), 1000):
        batch = [{"hash": h["hash"], "offset_ms": h["offset_ms"], "recitation_id": recitation_id}
                 for h in hashes[i:i+1000]]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/fingerprints", json=batch,
                          headers={**headers, "Prefer": "return=minimal"})
        if not r.ok:
            print(f"  ⚠️ فشل رفع دفعة: {r.text[:100]}")
    return True

def process_reciter(name_ar):
    """يعالج قارئ واحد كامل"""
    print(f"\n🎤 {name_ar}")
    videos = search_youtube(f"القارئ {name_ar} قرآن", MAX_PER_RECITER)
    if not videos:
        print("  ❌ ما لقيت فيديوهات")
        return 0
    reciter_id = get_or_create_reciter(name_ar)
    if not reciter_id:
        return 0
    success = 0
    for v in videos:
        print(f"  📹 {v['title'][:60]}...")
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "audio.wav")
            if not download_audio(v["url"], audio_path):
                continue
            if not os.path.exists(audio_path):
                continue
            print(f"     🔍 استخراج البصمات...")
            hashes, duration = extract_fingerprints(audio_path)
            if len(hashes) < 100:
                print(f"     ⚠️ بصمات قليلة ({len(hashes)}), تخطي")
                continue
            print(f"     ⬆️  رفع {len(hashes)} بصمة...")
            if upload_recitation(reciter_id, v, hashes, duration):
                success += 1
                print(f"     ✅ تم!")
    return success

def main():
    if len(sys.argv) < 2:
        print("الاستخدام: python local_fingerprint_tool.py القراء.xlsx")
        sys.exit(1)
    if not SUPABASE_KEY:
        print("❌ محتاج SUPABASE_SERVICE_KEY في environment")
        print("   Windows: set SUPABASE_SERVICE_KEY=eyJ...")
        print("   Linux/Mac: export SUPABASE_SERVICE_KEY=eyJ...")
        sys.exit(1)
    excel_path = sys.argv[1]
    df = pd.read_excel(excel_path)
    # جد عمود الأسماء
    name_col = None
    for col in df.columns:
        if any(k in str(col).lower() for k in ["اسم", "name", "قارئ", "reciter"]):
            name_col = col
            break
    if not name_col:
        name_col = df.columns[0]
    reciters = df[name_col].dropna().unique().tolist()
    print(f"📚 وجدت {len(reciters)} قارئ في {excel_path}")
    print(f"🎯 السيرفر: {SUPABASE_URL}")
    print(f"⚙️  {MAX_PER_RECITER} فيديوهات لكل قارئ، حد أقصى {MAX_DURATION} ثانية\n")
    input("اضغط Enter للبدء...")
    total_success = 0
    for i, name in enumerate(reciters, 1):
        print(f"\n{'='*60}\n[{i}/{len(reciters)}]", end=" ")
        try:
            n = process_reciter(str(name).strip())
            total_success += n
        except KeyboardInterrupt:
            print("\n\n⏸️  توقف بأمر المستخدم")
            break
        except Exception as e:
            print(f"  💥 خطأ: {e}")
    print(f"\n\n🎉 انتهى! رفعت {total_success} تلاوة بنجاح.")

if __name__ == "__main__":
    main()
