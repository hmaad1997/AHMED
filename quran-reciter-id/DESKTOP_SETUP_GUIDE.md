# 🖥️ دليل تشغيل التطبيق على Windows Desktop

## 📋 الحالة الحالية

المشروع جاهز 100%، لكن تحتاج تثبيت Flutter لتشغيله على Desktop.

---

## ✅ **الخطوة 1: تثبيت Flutter**

### **طريقة 1: التثبيت السريع (موصى به)**

1. **تحميل Flutter SDK:**
   - اذهب إلى: https://docs.flutter.dev/get-started/install/windows
   - أو مباشرة: https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.16.0-stable.zip

2. **فك الضغط:**
   ```
   C:\src\flutter\
   ```
   (أو أي مكان تريده، تجنب `C:\Program Files\`)

3. **إضافة Flutter للـ PATH:**
   - افتح: **System Properties → Environment Variables**
   - تحت "System variables"، اختر `Path`
   - اضغط **Edit → New**
   - أضف: `C:\src\flutter\bin`
   - اضغط **OK**

4. **تحقق من التثبيت:**
   ```bash
   # افتح CMD جديد أو PowerShell
   flutter --version
   ```

   يجب أن ترى:
   ```
   Flutter 3.16.0 • channel stable
   ```

---

## ✅ **الخطوة 2: تثبيت متطلبات Windows Desktop**

### **تثبيت Visual Studio 2022 (مطلوب):**

1. حمّل **Visual Studio 2022 Community** (مجاني):
   https://visualstudio.microsoft.com/downloads/

2. أثناء التثبيت، اختر:
   - ✅ **Desktop development with C++**
   - ✅ **Windows 10 SDK** أو أحدث

3. أكمل التثبيت (قد يستغرق 30-60 دقيقة)

### **تحقق من البيئة:**
```bash
flutter doctor
```

يجب أن ترى:
```
[✓] Flutter (Channel stable, 3.16.0)
[✓] Windows Version (Windows 10 or later)
[✓] Visual Studio - develop for Windows (Visual Studio Community 2022)
[✓] VS Code (version 1.x)
```

---

## ✅ **الخطوة 3: تفعيل Windows Desktop Support**

```bash
# تفعيل Windows Desktop
flutter config --enable-windows-desktop

# تحقق من الأجهزة المتاحة
flutter devices
```

يجب أن ترى:
```
Windows (desktop) • windows • windows-x64 • Microsoft Windows
```

---

## ✅ **الخطوة 4: إضافة Windows Support للمشروع**

```bash
# اذهب لمجلد Flutter App
cd "C:\Users\user\Downloads\تطبيق الصوت\quran-reciter-id\flutter_app"

# أضف Windows support
flutter create --platforms=windows .

# انتظر حتى ينتهي...
```

هذا سينشئ مجلد `windows/` جديد في المشروع.

---

## ✅ **الخطوة 5: تحديث API URL**

**مهم!** عدّل هذا الملف:

`flutter_app/lib/services/api_service.dart`

**ابحث عن:**
```dart
static const String baseUrl = 'http://localhost:8000';
```

**تأكد أنه كذلك** (أو غيّره إذا كان مختلف):
```dart
static const String baseUrl = 'http://localhost:8000';
```

هذا لأن Desktop سيستخدم localhost مباشرة.

---

## ✅ **الخطوة 6: تثبيت المكتبات**

```bash
cd "C:\Users\user\Downloads\تطبيق الصوت\quran-reciter-id\flutter_app"

# تثبيت المكتبات
flutter pub get
```

---

## ✅ **الخطوة 7: تشغيل Backend Server**

**في terminal/cmd منفصل:**

```bash
cd "C:\Users\user\Downloads\تطبيق الصوت\quran-reciter-id\backend"

# تأكد من تثبيت المكتبات (إذا لم تكن مثبتة)
pip install -r requirements.txt

# شغّل السيرفر
python run_server.py
```

**انتظر حتى ترى:**
```
✓ SERVER READY
Uvicorn running on http://0.0.0.0:8000
```

**اترك هذا Terminal مفتوح!**

---

## ✅ **الخطوة 8: تشغيل التطبيق على Windows**

**في terminal/cmd آخر:**

```bash
cd "C:\Users\user\Downloads\تطبيق الصوت\quran-reciter-id\flutter_app"

# تشغيل على Windows Desktop
flutter run -d windows
```

**انتظر البناء (أول مرة: 5-10 دقائق)**

بعدها سيفتح التطبيق كنافذة Windows! 🎉

---

## 🎨 **الخطوة 9: بناء EXE للتوزيع**

بعد التأكد من أن كل شيء يعمل:

```bash
cd "C:\Users\user\Downloads\تطبيق الصوت\quran-reciter-id\flutter_app"

# بناء للإنتاج
flutter build windows --release
```

**الملف النهائي:**
```
flutter_app\build\windows\runner\Release\quran_reciter_id.exe
```

**حجم التطبيق:** ~50-70 MB

---

## 📦 **الخطوة 10: حزم التطبيق للتوزيع**

### **ما تحتاجه لتشغيل التطبيق:**

1. ✅ `quran_reciter_id.exe`
2. ✅ ملفات DLL المرافقة (في نفس المجلد)
3. ✅ مجلد `data/` (البيانات)
4. ✅ Backend Server

### **طريقة الحزم:**

انسخ المجلد بالكامل:
```
build\windows\runner\Release\
```

إلى:
```
QuranReciterID_Windows\
├── quran_reciter_id.exe
├── flutter_windows.dll
├── [ملفات DLL أخرى]
└── data\
```

---

## 🚀 **البديل الأسهل: VS Code**

إذا عندك VS Code:

1. افتح VS Code
2. File → Open Folder → `flutter_app/`
3. اضغط `F5` أو Run → Start Debugging
4. اختر "Windows" من القائمة
5. سيشتغل تلقائياً!

---

## ⚠️ **المشاكل الشائعة**

### ❌ "flutter: command not found"
**الحل:** Flutter غير مثبت أو غير مضاف للـ PATH
- أعد الخطوة 1

### ❌ "Visual Studio not found"
**الحل:** ثبّت Visual Studio 2022
- أعد الخطوة 2

### ❌ "Failed to build Windows"
**الحل:** 
```bash
flutter clean
flutter pub get
flutter build windows --release
```

### ❌ "Backend غير متصل"
**الحل:** 
- تأكد من Backend يعمل على port 8000
- تحقق من baseUrl في api_service.dart

### ❌ "Microphone permission"
**الحل:** Windows سيطلب الصلاحية تلقائياً أول مرة

---

## 📊 **الملخص السريع**

| الخطوة | الوقت | الحالة |
|--------|-------|--------|
| 1. تثبيت Flutter | 5 دقائق | ⏳ |
| 2. تثبيت VS 2022 | 30-60 دقيقة | ⏳ |
| 3. تفعيل Windows | 1 دقيقة | ⏳ |
| 4. إضافة Windows Support | 2 دقيقة | ⏳ |
| 5. تحديث API URL | 1 دقيقة | ⏳ |
| 6. تثبيت المكتبات | 2 دقيقة | ⏳ |
| 7. تشغيل Backend | 1 دقيقة | ⏳ |
| 8. تشغيل Flutter | 5-10 دقائق | ⏳ |
| **المجموع** | **~1 ساعة** | |

**بعدها:** التطبيق يعمل على Windows! ✅

---

## 🎯 **الخطوات التالية:**

بعد التشغيل بنجاح:

1. ✅ اختبر التسجيل الصوتي
2. ✅ جرّب التعرف على القراء
3. ✅ اختبر مكتبة القراء
4. ✅ ابنِ EXE للتوزيع

---

## 💡 **نصيحة احترافية:**

### **للتطوير السريع:**
استخدم Hot Reload في Flutter:
- عدّل الكود
- احفظ (`Ctrl+S`)
- التطبيق يتحدث تلقائياً! ⚡

### **للأداء الأفضل:**
بناء Release بدلاً من Debug:
```bash
flutter run -d windows --release
```

---

## 📞 **تحتاج مساعدة؟**

إذا واجهت أي مشكلة:

1. ✅ شغّل `flutter doctor` وأرسل النتيجة
2. ✅ تحقق من الـ logs في Terminal
3. ✅ تأكد من Backend يعمل
4. ✅ جرّب `flutter clean` ثم أعد المحاولة

---

<div align="center">

## 🎉 **مبروك مقدماً!**

بعد ساعة واحدة، التطبيق سيعمل على Windows Desktop! 🚀

**صُنع بـ ❤️ لخدمة القرآن الكريم**

</div>
