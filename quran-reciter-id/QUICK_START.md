# ⚡ دليل البدء السريع - Quran Reciter ID

## 🚀 5 خطوات للبدء

### الخطوة 1: تثبيت Backend (5 دقائق)

```bash
cd backend
pip install -r requirements.txt
```

---

### الخطوة 2: إضافة بيانات القراء (يدوي)

```bash
# ضع 50 فيديو في:
backend/data/raw_videos/

# مثال:
# عبد_الباسط_عبد_الصمد.mp4
# محمد_صديق_المنشاوي.mp4
# ...
```

---

### الخطوة 3: معالجة البيانات (2 ساعة)

```bash
python scripts/process_data.py
```

**انتظر حتى ترى:**
```
✓ Successfully processed: 50/50 reciters
```

---

### الخطوة 4: تشغيل Backend (30 ثانية)

```bash
python run_server.py
```

**انتظر:**
```
✓ SERVER READY
```

**اختبر:**
```
افتح: http://localhost:8000/docs
```

---

### الخطوة 5: تشغيل Flutter (3 دقائق)

#### A. تثبيت المكتبات:
```bash
cd ../flutter_app
flutter pub get
```

#### B. تعديل API URL:

افتح: `lib/services/api_service.dart`

**للـ Emulator:**
```dart
static const String baseUrl = 'http://10.0.2.2:8000';
```

**لجهاز حقيقي:**
```dart
static const String baseUrl = 'http://YOUR_PC_IP:8000';
```

#### C. تشغيل:
```bash
flutter run
```

---

## ✅ تحقق من النجاح

### Backend:
- [ ] السيرفر يعمل على `http://localhost:8000`
- [ ] صفحة `/docs` تفتح بنجاح
- [ ] ملف `reciter_database.json` موجود

### Flutter:
- [ ] التطبيق يفتح بدون أخطاء
- [ ] نقطة خضراء في الـ AppBar
- [ ] تبويب "مكتبة القراء" يعرض 50 قارئ

---

## 🧪 اختبار سريع

### 1. اختبر Backend (من Terminal):
```bash
cd backend
python test_api.py
```

**النتيجة المتوقعة:**
```
✓ Health Check: PASSED
✓ Stats: PASSED
✓ List Reciters: PASSED
```

---

### 2. اختبر Flutter (من التطبيق):
1. افتح التطبيق
2. اضغط على الميكروفون 🎤
3. سجّل 5 ثواني من تلاوة
4. اضغط "إيقاف وتحليل"
5. انتظر النتيجة (2-5 ثواني)

**النتيجة المتوقعة:**
- شاشة تعرض اسم القارئ
- نسبة التطابق
- معلومات القارئ

---

## ⚠️ مشكلة شائعة وحل سريع

### "الخادم غير متصل"

**الحل:**
```bash
# 1. تأكد أن Backend يعمل
cd backend
python run_server.py

# 2. في Flutter، تحقق من baseUrl
# lib/services/api_service.dart
```

---

## 📁 الملفات المهمة

```
quran-reciter-id/
├── backend/
│   ├── run_server.py              ← شغّل هذا أولاً
│   ├── scripts/process_data.py    ← معالجة البيانات
│   └── data/raw_videos/           ← ضع الفيديوهات هنا
│
└── flutter_app/
    ├── lib/services/api_service.dart  ← عدّل baseUrl هنا
    └── README.md                      ← دليل Flutter كامل
```

---

## 🎯 الأوامر الأساسية

### Backend:
```bash
# تشغيل السيرفر
python run_server.py

# اختبار API
python test_api.py

# معالجة البيانات
python scripts/process_data.py
```

### Flutter:
```bash
# تثبيت المكتبات
flutter pub get

# تشغيل التطبيق
flutter run

# بناء APK
flutter build apk --release
```

---

## 📚 الأدلة الكاملة

للتفاصيل الكاملة، راجع:
- `SETUP_GUIDE.md` - دليل التثبيت المفصل
- `COMPLETE_PROJECT_GUIDE.md` - دليل المشروع الشامل
- `backend/PHASE3_GUIDE.md` - دليل Backend
- `flutter_app/README.md` - دليل Flutter
- `docs/API_CONTRACT.md` - توثيق الـ API

---

## 🎉 خلاص!

**وقت التشغيل الإجمالي:**
- التثبيت: ~10 دقائق
- معالجة البيانات: ~2 ساعة (مرة واحدة فقط)
- التشغيل بعد ذلك: ~1 دقيقة

**الآن جاهز للاستخدام!** 🚀
