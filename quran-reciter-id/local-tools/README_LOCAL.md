# 🎙️ أداة البصمات المحلية - من القارئ

سكريبت بيشتغل على لابتوبك، بيقرأ ملف Excel فيه أسماء القراء، بينزل صوتياتهم من YouTube، بيستخرج البصمات، وبيرفعها مباشرة على سيرفرنا.

## 📋 المتطلبات

### 1. Python 3.9+
حمّل من: https://python.org

### 2. FFmpeg
- **Windows:** حمّل من https://ffmpeg.org/download.html وأضفه للـ PATH
- **Mac:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

### 3. مكتبات Python
```bash
pip install pandas openpyxl librosa numpy scipy requests tqdm yt-dlp
```

## 🔑 المفتاح السري (SUPABASE_SERVICE_KEY)

محتاج مفتاح service_role من Lovable Cloud. إذا مش عندك، اطلبه مني ورح أعطيك خطوة بخطوة.

**Windows (PowerShell):**
```powershell
$env:SUPABASE_SERVICE_KEY="eyJhbGc..."
```

**Windows (CMD):**
```cmd
set SUPABASE_SERVICE_KEY=eyJhbGc...
```

**Mac/Linux:**
```bash
export SUPABASE_SERVICE_KEY="eyJhbGc..."
```

## 🚀 التشغيل

```bash
python local_fingerprint_tool.py القراء.xlsx
```

## ⚙️ الإعدادات (داخل السكريبت)

- `MAX_PER_RECITER = 3` — كم فيديو تحمل لكل قارئ
- `MAX_DURATION = 600` — تجاهل الفيديوهات الأطول من 10 دقايق
- `SAMPLE_RATE = 22050` — نفس السيرفر

## 📊 شو بيصير؟

لكل قارئ:
1. 🔍 يبحث في YouTube (أول 3 نتائج قصيرة)
2. 📥 ينزل الصوت (WAV)
3. 🧠 يستخرج البصمات (نفس خوارزمية السيرفر — SHA1 hashing على spectrogram peaks)
4. ☁️ يرفع القارئ + التلاوة + البصمات على قاعدة البيانات

## 🛑 إيقاف

اضغط `Ctrl+C` بأي وقت — بيوقف بأمان بدون فقدان اللي تم رفعه.

## 💡 نصائح

- شغّله بالليل قبل النوم — 100 قارئ × 3 فيديوهات = ساعتين تقريباً على انترنت عادي
- إذا YouTube حظرك مؤقتاً، استنى ساعة وكمّل من نفس الملف (السكريبت بيتخطى القراء اللي عندهم بصمات بأتوماتيك — قريباً)
- الملفات ما بتنحفظ على لابتوبك، بس مؤقتاً بمجلد temp
