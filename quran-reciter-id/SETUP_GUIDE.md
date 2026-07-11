# 🎯 دليل التثبيت السريع - Quran Reciter ID

## المتطلبات الأساسية

### 1. Python (3.8 أو أحدث)
تأكد من تثبيت Python:
```bash
python --version
```

### 2. FFmpeg
**ضروري لاستخراج الصوت من الفيديوهات**

#### تثبيت FFmpeg على Windows:
1. حمّل FFmpeg من: https://ffmpeg.org/download.html
2. فك الضغط في مجلد (مثلاً `C:\ffmpeg`)
3. أضف `C:\ffmpeg\bin` إلى متغيرات النظام (PATH)
4. تحقق من التثبيت:
```bash
ffmpeg -version
```

---

## خطوات التثبيت

### الخطوة 1: تثبيت مكتبات Python

```bash
cd quran-reciter-id/backend
pip install -r requirements.txt
```

**ملاحظة:** قد يستغرق التثبيت 5-10 دقائق بسبب PyTorch و SpeechBrain.

---

### الخطوة 2: إضافة ملفات القراء

ضع الـ **50 فيديو** في المجلد:
```
backend/data/raw_videos/
```

**تنسيق أسماء الملفات:**
- استخدم اسم القارئ كاسم للملف
- مثال: `عبد_الباسط_عبد_الصمد.mp4`
- `محمد_صديق_المنشاوي.mp4`

**الصيغ المدعومة:**
- MP4, AVI, MKV, MOV, FLV, WMV

---

### الخطوة 3: اختبار المعالجة (اختياري)

قبل معالجة الـ 50 فيديو، اختبر واحد فقط:

```bash
python scripts/test_processing.py data/raw_videos/your_test_video.mp4
```

**ما الذي سيحدث؟**
1. تحميل نموذج SpeechBrain (أول مرة فقط)
2. استخراج الصوت
3. توليد الـ embeddings
4. عرض النتيجة

**الوقت المتوقع:** 2-3 دقائق لفيديو واحد

---

### الخطوة 4: معالجة جميع الفيديوهات

```bash
python scripts/process_data.py
```

**ما الذي سيحدث؟**
1. استخراج الصوت من كل فيديو → `data/processed_audio/`
2. تقسيم الصوت إلى مقاطع 10 ثواني
3. توليد "بصمة صوتية" لكل قارئ باستخدام AI
4. حفظ قاعدة البيانات في: `data/embeddings/reciter_database.json`

**الوقت المتوقع:** 
- حوالي 2-3 دقائق لكل قارئ
- المجموع: ~1.5 - 2.5 ساعة للـ 50 قارئ

---

## التحقق من النجاح

بعد انتهاء المعالجة، يجب أن ترى:

✅ **الملف:** `backend/data/embeddings/reciter_database.json`

✅ **محتوى الملف:**
```json
{
  "version": "1.0",
  "num_reciters": 50,
  "embedding_dim": 192,
  "reciters": [...]
}
```

✅ **الرسالة في Terminal:**
```
✓ Successfully processed: 50/50 reciters
✓ Database location: data/embeddings/reciter_database.json
```

---

## حل المشاكل الشائعة

### ❌ خطأ: `ffmpeg: command not found`
**الحل:** تأكد من تثبيت FFmpeg وإضافته لـ PATH

### ❌ خطأ: `Out of memory`
**الحل:** 
- أغلق البرامج الأخرى
- أو عالج الفيديوهات على دفعات (25 فيديو في المرة)

### ❌ خطأ: `Some videos fail to process`
**الحل:**
- تحقق من سلامة ملف الفيديو
- تأكد من الصيغة المدعومة
- حاول تحويل الفيديو لـ MP4

### ❌ خطأ: `Model download fails`
**الحل:**
- تحقق من اتصال الإنترنت
- النموذج سيتم تحميله تلقائياً في أول تشغيل

---

## الخطوات التالية

بعد نجاح المعالجة:

✅ **CHECKPOINT 2 مكتمل!**

🚀 **جاهز للمرحلة 3:** بناء FastAPI Server

انتظر التأكيد للانتقال للمرحلة التالية 👍
