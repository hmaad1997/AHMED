# 🚀 رفع المشروع على GitHub وبناء EXE تلقائياً

## 🎯 نظرة عامة

هذا الدليل يشرح كيفية:
1. ✅ رفع المشروع على GitHub
2. ✅ بناء EXE تلقائياً عند كل push
3. ✅ تحميل EXE جاهز للاستخدام

---

## 📋 الخطوة 1: تحضير المشروع للرفع

### 1.1 تحديث `.gitignore`

الملف موجود بالفعل وجاهز! ✅

تأكد من أنه يتجاهل:
- ✅ `backend/data/raw_videos/*` (الفيديوهات كبيرة)
- ✅ `backend/data/embeddings/*` (ستُبنى محلياً)
- ✅ `backend/pretrained_models/` (سيُحمّل تلقائياً)
- ✅ `flutter_app/build/` (ملفات البناء)

### 1.2 تحقق من الملفات

تأكد من وجود:
```
quran-reciter-id/
├── .github/
│   └── workflows/
│       ├── build-windows.yml        ✅ NEW!
│       ├── build-backend.yml        ✅ NEW!
│       └── build-complete.yml       ✅ NEW!
├── backend/
├── flutter_app/
├── README.md
└── .gitignore
```

---

## 📦 الخطوة 2: إنشاء Repository على GitHub

### 2.1 من موقع GitHub:

1. اذهب إلى: https://github.com/new
2. **Repository name:** `quran-reciter-id`
3. **Description:** `AI-powered Quran Reciter Identification System`
4. **Visibility:** Public أو Private (اختر ما تريد)
5. ❌ **لا تختر** "Add a README" (عندنا واحد)
6. ❌ **لا تختر** "Add .gitignore" (عندنا واحد)
7. اضغط **Create repository**

---

## 🔧 الخطوة 3: ربط المشروع المحلي بـ GitHub

### 3.1 افتح Terminal/CMD في مجلد المشروع:

```bash
cd "C:\Users\user\Downloads\تطبيق الصوت\quran-reciter-id"
```

### 3.2 تهيئة Git (إذا لم يكن مهيأ):

```bash
# تهيئة Git
git init

# إضافة جميع الملفات
git add .

# أول commit
git commit -m "Initial commit: Complete Quran Reciter ID project"
```

### 3.3 ربط بـ GitHub:

**استبدل `YOUR-USERNAME` باسم المستخدم الخاص بك:**

```bash
# ربط بـ GitHub
git remote add origin https://github.com/YOUR-USERNAME/quran-reciter-id.git

# رفع الكود
git branch -M main
git push -u origin main
```

**سيطلب منك اسم المستخدم وكلمة المرور (أو Personal Access Token)**

---

## ⚡ الخطوة 4: GitHub Actions سيبني تلقائياً!

### 4.1 ما سيحدث تلقائياً:

بمجرد الـ push، GitHub Actions سيبدأ البناء:

```
Your Push → GitHub → GitHub Actions → Build EXE → Download Ready!
```

### 4.2 مراقبة البناء:

1. اذهب إلى repository على GitHub
2. اضغط على تبويب **Actions**
3. سترى 3 workflows تعمل:
   - ✅ **Build Windows Desktop App**
   - ✅ **Build Backend Executable**
   - ✅ **Build Complete Package**

### 4.3 الوقت المتوقع:

- **Flutter Build:** ~10-15 دقيقة
- **Backend Build:** ~5-10 دقيقة
- **Complete Package:** ~20 دقيقة

---

## 📥 الخطوة 5: تحميل EXE الجاهز

### طريقة 1: من Artifacts

1. اذهب إلى **Actions** tab
2. اضغط على آخر workflow ناجح (✅ علامة خضراء)
3. scroll للأسفل لـ "Artifacts"
4. حمّل:
   - `QuranReciterID-Windows` (التطبيق فقط)
   - `QuranReciterID-Backend` (Backend فقط)
   - `QuranReciterID-Complete-Package` (كل شيء معاً) ⭐

### طريقة 2: من Releases (للنسخ المستقرة)

**إنشاء Release:**

```bash
# محلياً، أنشئ tag:
git tag -a v1.0.0 -m "First stable release"
git push origin v1.0.0
```

**سيبني تلقائياً ويضيف في Releases!**

1. اذهب لـ repository
2. اضغط **Releases**
3. سترى `v1.0.0`
4. حمّل `QuranReciterID-Windows-Complete.zip`

---

## 🎁 الخطوة 6: استخدام EXE

### ما ستحصل عليه:

```
QuranReciterID-Windows-Complete.zip
└── QuranReciterID/
    ├── app/
    │   └── quran_reciter_id.exe
    ├── backend/
    │   ├── backend-server.exe
    │   └── data/
    ├── START.bat              ⭐ شغّل هذا!
    └── README.txt
```

### كيفية الاستخدام:

1. فك ضغط الملف
2. شغّل `START.bat`
3. انتهى! 🎉

**START.bat سيشغل:**
- ✅ Backend Server
- ✅ Flutter Desktop App
- ✅ كل شيء تلقائياً!

---

## 🔄 تحديث المشروع

### عند إضافة تعديلات:

```bash
# إضافة التعديلات
git add .

# commit
git commit -m "Added new features"

# رفع
git push

# GitHub Actions سيبني تلقائياً!
```

**بعد 20 دقيقة، EXE جديد جاهز للتحميل!**

---

## 🏷️ إنشاء نسخة مستقرة (Release)

```bash
# أنشئ tag للنسخة
git tag -a v1.0.1 -m "Bug fixes and improvements"

# ارفع الـ tag
git push origin v1.0.1

# سيظهر في Releases تلقائياً!
```

---

## 📊 الـ Workflows المتاحة

### 1. **build-windows.yml** (Flutter App فقط)
```yaml
Trigger: كل push للـ main
Output: Flutter Desktop EXE
Time: ~10-15 دقيقة
```

### 2. **build-backend.yml** (Backend فقط)
```yaml
Trigger: كل push للـ main
Output: Backend Server EXE
Time: ~5-10 دقائق
```

### 3. **build-complete.yml** ⭐ (الحزمة الكاملة)
```yaml
Trigger: عند إنشاء tag (v*)
Output: حزمة ZIP كاملة جاهزة للتوزيع
Time: ~20 دقيقة
```

---

## 🎯 استراتيجية التطوير

### Development Workflow:

```
1. عدّل الكود محلياً
2. اختبر محلياً
3. git add . && git commit -m "..."
4. git push
5. انتظر GitHub Actions
6. حمّل EXE من Artifacts
7. اختبر
8. كرر!
```

### Release Workflow:

```
1. كل شيء يعمل؟ ✅
2. git tag -a v1.0.0 -m "Stable release"
3. git push origin v1.0.0
4. انتظر 20 دقيقة
5. تحقق من Releases
6. شارك الرابط مع المستخدمين!
```

---

## 🔒 Personal Access Token (إذا طُلب)

إذا طلب GitHub كلمة مرور:

1. اذهب إلى: https://github.com/settings/tokens
2. اضغط **Generate new token (classic)**
3. اختر scope: `repo`
4. انسخ الـ token
5. استخدمه بدلاً من كلمة المرور

---

## 📱 مشاركة التطبيق

### للمستخدمين النهائيين:

أرسل لهم:
```
https://github.com/YOUR-USERNAME/quran-reciter-id/releases/latest
```

**التعليمات:**
1. حمّل `QuranReciterID-Windows-Complete.zip`
2. فك الضغط
3. شغّل `START.bat`

**لا حاجة لتثبيت أي شيء!** ✅

---

## 🎨 Badge للـ README

أضف في `README.md`:

```markdown
![Build Status](https://github.com/YOUR-USERNAME/quran-reciter-id/workflows/Build%20Complete%20Package/badge.svg)

[![Download Latest Release](https://img.shields.io/github/v/release/YOUR-USERNAME/quran-reciter-id)](https://github.com/YOUR-USERNAME/quran-reciter-id/releases/latest)
```

---

## ⚠️ ملاحظات مهمة

### 1. حجم الـ Artifacts
GitHub يحفظ Artifacts لمدة 90 يوم.

### 2. حجم Repository
- لا ترفع الفيديوهات (`.gitignore` يتجاهلها)
- لا ترفع الـ embeddings (تُبنى محلياً)

### 3. GitHub Actions Minutes
- Free: 2000 دقيقة/شهر
- كل build: ~20 دقيقة
- يكفي لـ ~100 build شهرياً

### 4. Backend Data
المستخدم يحتاج:
- وضع الفيديوهات في `backend/data/raw_videos/`
- تشغيل `process_data.py` محلياً
- أو توزيع `reciter_database.json` جاهز

---

## 🚀 البناء المحلي (اختياري)

إذا تريد بناء محلياً بدون GitHub:

### Flutter:
```bash
cd flutter_app
flutter build windows --release
```

### Backend:
```bash
cd backend
pip install pyinstaller
pyinstaller --onefile run_server.py
```

---

## 📋 Checklist النهائي

قبل الرفع على GitHub:

- [ ] `.gitignore` موجود
- [ ] `.github/workflows/` موجود
- [ ] `README.md` محدّث
- [ ] كل الملفات المهمة موجودة
- [ ] الفيديوهات/Embeddings غير مرفوعة

بعد الرفع:

- [ ] Repository created على GitHub
- [ ] الكود مرفوع (`git push`)
- [ ] GitHub Actions تعمل (تحقق من Actions tab)
- [ ] Build ناجح (✅ علامة خضراء)
- [ ] Artifacts متاحة للتحميل

للـ Release:

- [ ] Tag created (`git tag v1.0.0`)
- [ ] Tag pushed (`git push origin v1.0.0`)
- [ ] Release ظهر في Releases tab
- [ ] ZIP متاح للتحميل

---

## 🎉 الخلاصة

**بهذه الطريقة:**

1. ✅ الكود آمن على GitHub
2. ✅ EXE يُبنى تلقائياً
3. ✅ التوزيع سهل (رابط واحد)
4. ✅ التحديثات سريعة (push → 20 دقيقة → EXE جديد)
5. ✅ احترافي 100%

---

<div align="center">

**🚀 الآن جاهز للرفع على GitHub!**

**كل push = EXE جديد تلقائياً!**

</div>
