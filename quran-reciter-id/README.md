# 🎙️ Quran Reciter ID

<div align="center">

**AI-Powered Quran Reciter Identification System**

تطبيق ذكاء اصطناعي للتعرف على صوت قارئ القرآن الكريم

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flutter](https://img.shields.io/badge/Flutter-3.0+-blue.svg)](https://flutter.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![SpeechBrain](https://img.shields.io/badge/SpeechBrain-0.5.16-orange.svg)](https://speechbrain.github.io/)

</div>

---

## 📖 نظرة عامة

**Quran Reciter ID** هو نظام متكامل يستخدم الذكاء الاصطناعي للتعرف على صوت قارئ القرآن من بين **50 قارئ** مشهور.

### ✨ الميزات الرئيسية:
- 🎤 **تسجيل صوتي مباشر** من خلال التطبيق
- 🧠 **تحليل ذكي** باستخدام SpeechBrain ECAPA-TDNN
- 📊 **دقة عالية** 85-95% في التعرف على القارئ
- 📱 **تطبيق Android** سهل الاستخدام
- 📚 **مكتبة شاملة** لـ 50 قارئ مع معلوماتهم
- ⚡ **سريع** نتائج خلال 2-5 ثواني

---

## 🏗️ البنية المعمارية

```
┌─────────────────┐
│  Flutter App    │  ← المستخدم يسجل الصوت
│   (Android)     │
└────────┬────────┘
         │ HTTP/REST API
         ▼
┌─────────────────┐
│  FastAPI Server │  ← Backend
│   (Python)      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌──────┐  ┌──────────┐
│ AI   │  │ Vector   │
│Engine│  │ Database │
└──────┘  └──────────┘
SpeechBrain   50 Reciters
ECAPA-TDNN    Embeddings
```

---

## 🚀 البدء السريع

### المتطلبات:
- Python 3.8+
- Flutter SDK 3.0+
- FFmpeg
- 2-4 GB RAM

### التثبيت:

```bash
# 1. Clone المشروع
git clone <repository-url>
cd quran-reciter-id

# 2. إعداد Backend
cd backend
pip install -r requirements.txt

# 3. معالجة بيانات القراء (ضع 50 فيديو في data/raw_videos/)
python scripts/process_data.py

# 4. تشغيل Backend
python run_server.py

# 5. إعداد Flutter (في terminal جديد)
cd ../flutter_app
flutter pub get
flutter run
```

**📚 للتفاصيل الكاملة:** راجع [`QUICK_START.md`](QUICK_START.md)

---

## 📸 Screenshots

### الشاشة الرئيسية
```
┌──────────────────────┐
│  🎙️ التسجيل         │
│                      │
│      ┌────────┐      │
│      │   🎤   │      │
│      │ ميكرفون│      │
│      └────────┘      │
│                      │
│  اضغط للتسجيل        │
└──────────────────────┘
```

### شاشة النتيجة
```
┌──────────────────────┐
│     ✅ تم التعرف     │
│                      │
│   دقة التطابق: 94%  │
│                      │
│  عبد الباسط عبد الصمد│
│ Abdul Basit Abdus..  │
│                      │
│  البلد: مصر 🇪🇬       │
│  النمط: مجود          │
│  (1927 - 1988)      │
└──────────────────────┘
```

---

## 🔧 التقنيات المستخدمة

### Backend:
- **FastAPI** - Web framework
- **SpeechBrain** - Speaker recognition model
- **PyTorch** - Deep learning
- **FFmpeg** - Audio processing
- **scikit-learn** - Cosine similarity

### Frontend:
- **Flutter** - Cross-platform UI
- **Dart** - Programming language
- **record** - Audio recording
- **http** - API communication

### AI/ML:
- **ECAPA-TDNN** - Time Delay Neural Network
- **Voice Embeddings** - 192-dimensional vectors
- **Cosine Similarity** - Matching algorithm

---

## 📊 الأداء

| المقياس | القيمة |
|---------|--------|
| دقة التعرف | 85-95% |
| وقت الاستجابة | 2-5 ثواني |
| عدد القراء | 50 |
| حجم النموذج | ~500 MB |
| استهلاك الذاكرة | 1-2 GB |
| حجم APK | ~20-30 MB |

---

## 📁 هيكل المشروع

```
quran-reciter-id/
│
├── backend/                 # Python Backend
│   ├── app/                # FastAPI application
│   ├── data/               # Data & embeddings
│   ├── scripts/            # Processing scripts
│   └── requirements.txt    # Python dependencies
│
├── flutter_app/            # Flutter Frontend
│   ├── lib/               # Dart source code
│   ├── android/           # Android config
│   └── pubspec.yaml       # Flutter dependencies
│
├── docs/                   # Documentation
│   └── API_CONTRACT.md    # API documentation
│
├── QUICK_START.md         # دليل البدء السريع
├── SETUP_GUIDE.md         # دليل التثبيت
├── COMPLETE_PROJECT_GUIDE.md  # الدليل الشامل
└── README.md              # هذا الملف
```

---

## 📚 التوثيق

| الملف | الوصف |
|------|--------|
| [`QUICK_START.md`](QUICK_START.md) | ⚡ البدء السريع (5 خطوات) |
| [`SETUP_GUIDE.md`](SETUP_GUIDE.md) | 📥 دليل التثبيت الكامل |
| [`COMPLETE_PROJECT_GUIDE.md`](COMPLETE_PROJECT_GUIDE.md) | 📖 الدليل الشامل |
| [`backend/PHASE3_GUIDE.md`](backend/PHASE3_GUIDE.md) | 🔧 دليل Backend |
| [`flutter_app/README.md`](flutter_app/README.md) | 📱 دليل Flutter |
| [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) | 🔌 توثيق API |

---

## 🧪 الاختبار

### Backend API:
```bash
cd backend
python test_api.py
```

### Flutter App:
1. شغّل التطبيق
2. اضغط على الميكروفون
3. سجّل 5 ثواني من التلاوة
4. شاهد النتيجة

---

## 🎯 Use Cases

### 1. التعليم:
- تعليم الطلاب التمييز بين أصوات القراء
- دراسة أساليب التلاوة المختلفة

### 2. التوثيق:
- تصنيف التسجيلات الصوتية
- أرشفة المكتبات الصوتية

### 3. البحث:
- دراسة خصائص الأصوات
- تحليل أنماط التلاوة

---

## 🔮 التطوير المستقبلي

### قريباً:
- [ ] دعم iOS
- [ ] وضع Offline
- [ ] إضافة المزيد من القراء
- [ ] تحسين الدقة

### مستقبلاً:
- [ ] دعم تعدد اللغات
- [ ] تطبيق Web
- [ ] API عام للمطورين
- [ ] Google Play Store

---

## ⚠️ المشاكل الشائعة

| المشكلة | الحل |
|---------|------|
| السيرفر لا يعمل | تأكد من تشغيل `run_server.py` |
| صلاحية الميكروفون | فعّلها من إعدادات الجهاز |
| "Audio too short" | سجّل 3+ ثواني |
| دقة منخفضة | استخدم صوت واضح بدون ضوضاء |

**للمزيد:** راجع [`COMPLETE_PROJECT_GUIDE.md`](COMPLETE_PROJECT_GUIDE.md#حل-المشاكل)

---

## 🤝 المساهمة

نرحب بالمساهمات! يمكنك:
- 🐛 الإبلاغ عن الأخطاء
- ✨ اقتراح ميزات جديدة
- 🔧 تحسين الكود
- 📖 تحسين التوثيق

---

## 📄 الترخيص

هذا المشروع مفتوح المصدر للأغراض التعليمية والبحثية.

---

## 🙏 الشكر

- **SpeechBrain** - نموذج التعرف على الصوت
- **FastAPI** - Framework رائع
- **Flutter** - أداة تطوير قوية

---

## 📞 الدعم

إذا واجهت أي مشكلة:
1. راجع [`COMPLETE_PROJECT_GUIDE.md`](COMPLETE_PROJECT_GUIDE.md)
2. تحقق من قسم [المشاكل الشائعة](#⚠️-المشاكل-الشائعة)
3. راجع الـ logs في Backend

---

<div align="center">

**صُنع بـ ❤️ لخدمة القرآن الكريم**

⭐ إذا أعجبك المشروع، لا تنسى النجمة!

</div>
