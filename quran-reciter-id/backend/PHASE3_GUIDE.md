# 🚀 PHASE 3 - تشغيل Backend Server

## المتطلبات الأساسية

قبل تشغيل السيرفر، تأكد من:

✅ إتمام PHASE 2 بنجاح (وجود ملف `data/embeddings/reciter_database.json`)
✅ تثبيت جميع المكتبات من `requirements.txt`

---

## خطوات التشغيل

### الخطوة 1: تحقق من قاعدة البيانات

```bash
# تأكد من وجود الملف
ls data/embeddings/reciter_database.json
```

**يجب أن يحتوي على:**
- 50 قارئ مع embeddings خاصة بهم

---

### الخطوة 2: شغّل السيرفر

```bash
cd backend
python run_server.py
```

**ما الذي سيحدث؟**

1. تحميل نموذج SpeechBrain
2. تحميل قاعدة بيانات الـ 50 قارئ
3. تشغيل FastAPI على المنفذ `8000`

**الوقت المتوقع:** 30-60 ثانية (أول مرة فقط)

**Output المتوقع:**
```
============================================================
STARTING QURAN RECITER ID SERVER
============================================================
INFO:     Loading SpeechBrain ECAPA-TDNN model...
INFO:     ✓ Model loaded successfully
INFO:     Loading reciter database...
INFO:     ✓ Database loaded: 50 reciters
INFO:     ✓ Embedding dimension: 192
============================================================
✓ SERVER READY
============================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### الخطوة 3: اختبر السيرفر

**افتح المتصفح:**
```
http://localhost:8000/docs
```

**ستظهر واجهة Swagger UI** حيث يمكنك:
- رؤية جميع الـ endpoints
- اختبار الـ API مباشرة من المتصفح
- رفع ملف صوتي وتجربة التعرف على القارئ

---

### الخطوة 4: اختبار الـ API بالكود

في terminal جديد (اترك السيرفر يعمل):

```bash
# اختبار أساسي (بدون رفع ملف)
python test_api.py
```

**سيختبر:**
1. ✅ Health check
2. ✅ Database stats
3. ✅ List all reciters

**لاختبار التعرف على القارئ:**
```bash
python test_api.py path/to/test_audio.wav
```

---

## الـ Endpoints المتاحة

### 1️⃣ **Health Check**
```bash
curl http://localhost:8000/health
```

### 2️⃣ **List All Reciters**
```bash
curl http://localhost:8000/list-reciters
```

### 3️⃣ **Identify Reciter**
```bash
curl -X POST http://localhost:8000/identify-reciter \
  -F "audio_file=@recitation.wav"
```

### 4️⃣ **Database Stats**
```bash
curl http://localhost:8000/stats
```

---

## اختبار يدوي (Swagger UI)

1. افتح: `http://localhost:8000/docs`
2. اضغط على `/identify-reciter`
3. اضغط "Try it out"
4. ارفع ملف صوتي (WAV/MP3)
5. اضغط "Execute"
6. شاهد النتيجة!

---

## حل المشاكل الشائعة

### ❌ خطأ: `reciter_database.json not found`
**الحل:** شغّل `python scripts/process_data.py` أولاً

### ❌ خطأ: `Port 8000 already in use`
**الحل:**
```bash
# غيّر المنفذ في run_server.py
port=8001  # بدلاً من 8000
```

### ❌ خطأ: `Model failed to load`
**الحل:**
- تحقق من الإنترنت (يحمّل النموذج أول مرة)
- امسح مجلد `pretrained_models/` وحاول مرة أخرى

### ❌ خطأ: `Audio too short`
**الحل:** ارفع ملف صوتي مدته 3 ثواني على الأقل

---

## مثال عملي كامل

### استخدام Python:
```python
import requests

# رفع ملف صوتي
with open('test_recitation.wav', 'rb') as f:
    files = {'audio_file': f}
    response = requests.post(
        'http://localhost:8000/identify-reciter',
        files=files
    )

result = response.json()

print(f"القارئ: {result['reciter_name']}")
print(f"الثقة: {result['confidence']:.2%}")
print(f"البلد: {result['country']}")
```

### النتيجة المتوقعة:
```json
{
  "success": true,
  "reciter_name": "عبد الباسط عبد الصمد",
  "reciter_name_english": "Abdul Basit Abdus Samad",
  "confidence": 0.94,
  "country": "مصر",
  "bio": "قارئ مصري شهير...",
  "similarity_score": 0.892
}
```

---

## الخطوات التالية

بعد نجاح اختبار السيرفر:

✅ **PHASE 3 مكتمل!**

🎨 **جاهز للمرحلة 4:** بناء Flutter UI

---

## ملاحظات مهمة

1. **السيرفر يجب أن يبقى مشتغل** طوال فترة استخدام التطبيق
2. للإنتاج، استخدم **Gunicorn** أو **Docker** بدلاً من `uvicorn`
3. فعّل **HTTPS** في الإنتاج
4. أضف **Authentication** قبل النشر العام

---

## 📊 مؤشرات الأداء المتوقعة

- **وقت الاستجابة:** 2-5 ثواني للتعرف على القارئ
- **دقة التعرف:** 85-95% (حسب جودة الصوت)
- **حجم الذاكرة:** ~1-2 GB (بسبب PyTorch)
- **استهلاك CPU:** متوسط أثناء المعالجة

---

**عندما تكون جاهز لبناء Flutter App، قل "PROCEED"** 🎨
