"""من القارئ - أداة توليد البصمات (نسخة محسّنة مع فحص تلقائي للمتطلبات)"""
import os, sys, json, time, hashlib, shutil, threading, queue, subprocess, urllib.request, zipfile, tempfile
from pathlib import Path
from datetime import timedelta
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ProcessPoolExecutor, as_completed

APP_TITLE = "من القارئ — مولّد البصمات"
DEFAULT_SERVER = "https://your-app.onrender.com"
UPLOAD_EP = "/upload-fingerprints"
BATCH = 10
CFG = Path.home() / ".mn_alqari.json"
FFMPEG_DIR = Path.home() / ".mn_alqari_ffmpeg"
SR = 22050; NFFT = 4096; OL = 0.5; NBH = 20; MINA = 10; FAN = 15; MAXDT = 200

# ============================================================
# فحص المتطلبات وتثبيتها تلقائياً
# ============================================================

REQUIRED_PKGS = [
    ("yt_dlp", "yt-dlp"),
    ("librosa", "librosa"),
    ("scipy", "scipy"),
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("openpyxl", "openpyxl"),
    ("requests", "requests"),
]

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"


def find_ffmpeg():
    """يبحث عن ffmpeg في PATH ثم في مجلد التطبيق."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    local = FFMPEG_DIR / "bin" / "ffmpeg.exe"
    if local.exists():
        # أضفه للـ PATH للعملية الحالية والأبناء
        os.environ["PATH"] = str(local.parent) + os.pathsep + os.environ.get("PATH", "")
        return str(local)
    return None


def install_ffmpeg_windows(log_cb):
    """ينزّل ffmpeg ويفكّه في مجلد المستخدم — لا يحتاج صلاحيات مسؤول."""
    try:
        FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = FFMPEG_DIR / "ffmpeg.zip"
        log_cb(f"⬇ تنزيل ffmpeg من BtbN ({FFMPEG_URL[:60]}...)")
        with urllib.request.urlopen(FFMPEG_URL, timeout=120) as r, open(zip_path, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = r.read(1024 * 256)
                if not chunk: break
                f.write(chunk); got += len(chunk)
                if total:
                    log_cb(f"  … {got / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB")
        log_cb("📦 فكّ الضغط…")
        with zipfile.ZipFile(zip_path) as z:
            # الملفات داخل مجلد فرعي — ننقل bin/
            names = z.namelist()
            root = names[0].split("/")[0]
            z.extractall(FFMPEG_DIR)
        # نقل bin للمستوى العلوي
        src_bin = FFMPEG_DIR / root / "bin"
        dst_bin = FFMPEG_DIR / "bin"
        if src_bin.exists():
            if dst_bin.exists(): shutil.rmtree(dst_bin)
            shutil.move(str(src_bin), str(dst_bin))
            shutil.rmtree(FFMPEG_DIR / root, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        exe = FFMPEG_DIR / "bin" / "ffmpeg.exe"
        if exe.exists():
            os.environ["PATH"] = str(exe.parent) + os.pathsep + os.environ.get("PATH", "")
            log_cb(f"✅ ffmpeg جاهز: {exe}")
            return True
        log_cb("❌ فشل التنزيل — ملف ffmpeg.exe غير موجود بعد الفك")
        return False
    except Exception as e:
        log_cb(f"❌ خطأ في تنزيل ffmpeg: {type(e).__name__}: {e}")
        return False


def pip_install(pkg, log_cb):
    """تثبيت حزمة عبر pip بنافذة cmd منفصلة يشوفها المستخدم."""
    log_cb(f"📦 تثبيت {pkg} …")
    try:
        # على ويندوز: نافذة cmd منفصلة
        if os.name == "nt":
            cmd = f'"{sys.executable}" -m pip install --upgrade "{pkg}"'
            # نافذة مرئية + انتظار الإنهاء
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        else:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", pkg],
                               capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            log_cb(f"✅ {pkg}")
            return True
        log_cb(f"❌ {pkg}: {r.stderr[-200:]}")
        return False
    except Exception as e:
        log_cb(f"❌ {pkg}: {e}")
        return False


def check_and_install_all(log_cb):
    """يفحص كل المتطلبات ويثبت الناقص. يعيد True إذا كل شي جاهز."""
    log_cb("🔍 فحص المتطلبات…")
    ok = True

    # 1) حزم بايثون
    missing = []
    for mod, pkg in REQUIRED_PKGS:
        try:
            __import__(mod)
            log_cb(f"  ✅ {pkg}")
        except ImportError:
            log_cb(f"  ⚠ {pkg} ناقص")
            missing.append(pkg)

    if missing:
        log_cb(f"📦 تثبيت {len(missing)} حزمة…")
        for pkg in missing:
            if not pip_install(pkg, log_cb):
                ok = False

    # 2) تحديث yt-dlp دائماً (يوتيوب يغيّر باستمرار)
    log_cb("🔄 تحديث yt-dlp لآخر إصدار (مهم جداً)…")
    pip_install("yt-dlp", log_cb)

    # 3) ffmpeg
    ffm = find_ffmpeg()
    if ffm:
        log_cb(f"  ✅ ffmpeg: {ffm}")
    else:
        log_cb("  ⚠ ffmpeg غير موجود — سيتم التنزيل التلقائي")
        if os.name == "nt":
            if not install_ffmpeg_windows(log_cb):
                ok = False
        else:
            log_cb("  ❌ ثبّت ffmpeg يدوياً على نظامك")
            ok = False

    log_cb("✅ كل المتطلبات جاهزة" if ok else "⚠ بعض المتطلبات فشلت — راجع السجل")
    return ok


# ============================================================
# البصمات
# ============================================================

def _peaks(spec):
    import numpy as np
    from scipy.ndimage import maximum_filter, generate_binary_structure, iterate_structure
    nb = iterate_structure(generate_binary_structure(2, 1), NBH)
    lm = maximum_filter(spec, footprint=nb) == spec
    bg = spec == 0
    eroded = maximum_filter(bg, footprint=nb) == bg
    det = lm & ~eroded
    amps = spec[det]
    f, t = np.where(det)
    k = np.where(amps > MINA)
    return list(zip(f[k], t[k]))


def _hashes(peaks):
    peaks = sorted(peaks, key=lambda p: p[1])
    out = []
    for i, (f1, t1) in enumerate(peaks):
        for j in range(1, FAN):
            if i + j >= len(peaks): break
            f2, t2 = peaks[i + j]
            dt = t2 - t1
            if 0 <= dt <= MAXDT:
                h = hashlib.sha1(f"{f1}|{f2}|{dt}".encode()).digest()
                out.append((int.from_bytes(h[:8], "big", signed=True), int(t1)))
    return out


def fingerprint(path):
    import librosa, numpy as np
    y, _ = librosa.load(path, sr=SR, mono=True)
    if len(y) < SR * 5: return None
    hop = NFFT - int(NFFT * OL)
    S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=hop))
    Sdb = np.clip(librosa.amplitude_to_db(S, ref=np.max, top_db=80) + 80, 0, None)
    hs = _hashes(_peaks(Sdb))
    return [(h, int(t * hop * 1000 / SR)) for h, t in hs], float(len(y) / SR)


# ============================================================
# يوتيوب — تدوير عملاء متعددين للتحايل على الحجب
# ============================================================

# ترتيب العملاء حسب موثوقيتها في 2025 (android محجوب حالياً غالباً)
YT_CLIENTS = ["tv_embedded", "ios", "web_safari", "mweb", "android", "web"]

# صيغ بحث متعددة — لو الأولى ما رجّعت نتائج نجرّب البدائل
def _query_variants(name):
    n = name.strip()
    return [
        f"{n} تلاوة قرآن",
        f"القارئ {n} تلاوة",
        f"{n} قرآن كريم",
        n,
    ]


def _yt_opts(client, out_dir, have_ff):
    cookies_file = CFG.parent / ".mn_alqari_cookies.txt"
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "socket_timeout": 45, "retries": 5, "fragment_retries": 5,
        "extractor_retries": 5,
        "extractor_args": {"youtube": {"player_client": [client]}},
        "geo_bypass": True,
        "nocheckcertificate": True,
        "source_address": "0.0.0.0",
    }
    # User-Agent مناسب لكل عميل
    if client == "ios":
        opts["http_headers"] = {"User-Agent": "com.google.ios.youtube/19.09.3 (iPhone; U; CPU iOS 17_5_1 like Mac OS X)"}
    elif client == "android":
        opts["http_headers"] = {"User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 14) gzip"}
    elif client in ("web", "web_safari", "mweb"):
        opts["http_headers"] = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"}
    if cookies_file.exists():
        opts["cookiefile"] = str(cookies_file)
    if have_ff:
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}]
    return opts


def yt_dl(query, count, out_dir):
    """يجرّب عدة عملاء × عدة صيغ بحث حتى ينجح."""
    import yt_dlp
    have_ff = find_ffmpeg() is not None
    variants = _query_variants(query)
    errors = []
    for client in YT_CLIENTS:
        for q in variants:
            try:
                with yt_dlp.YoutubeDL(_yt_opts(client, out_dir, have_ff)) as ydl:
                    info = ydl.extract_info(f"ytsearch{count}:{q}", download=True)
                    files = []
                    for e in (info or {}).get("entries", []) or []:
                        if not e: continue
                        vid = e.get("id", "")
                        cand = list(out_dir.glob(f"{vid}.*"))
                        if cand:
                            files.append((str(cand[0]), e.get("webpage_url", "")))
                    if files:
                        return files, None
                    errors.append(f"[{client}|{q[:20]}] 0 نتائج")
            except Exception as e:
                errors.append(f"[{client}] {type(e).__name__}: {str(e)[:80]}")
                # عند 403 نجرّب العميل التالي مباشرة
                if "403" in str(e) or "Forbidden" in str(e):
                    break
    return [], " | ".join(errors[-3:])  # آخر 3 أخطاء


def process_reciter(args):
    name, per, root = args
    out = {"reciter": name, "items": [], "hashes": 0}
    wd = Path(root) / hashlib.md5(name.encode()).hexdigest()[:12]
    wd.mkdir(parents=True, exist_ok=True)
    try:
        files, yerr = yt_dl(name, per, wd)
        if yerr and not files:
            out["error"] = yerr
        for path, url in files:
            try:
                r = fingerprint(path)
                if not r: continue
                hs, dur = r
                if not hs: continue
                out["items"].append({"reciter_name": name, "surah_number": 0, "surah_name_ar": "",
                    "source": "youtube", "source_url": url, "duration_sec": int(dur), "hashes": hs})
                out["hashes"] += len(hs)
            finally:
                try: os.remove(path)
                except: pass
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    return out


def upload(server, token, items):
    import requests
    try:
        r = requests.post(f"{server.rstrip('/')}{UPLOAD_EP}",
            headers={"Authorization": f"Bearer {token}"}, json={"items": items}, timeout=180)
        return r.ok
    except Exception: return False


# ============================================================
# نسخ / لصق
# ============================================================

def enable_clipboard(root):
    KC = {67: "<<Copy>>", 86: "<<Paste>>", 88: "<<Cut>>", 65: "select_all"}
    def on_key(event):
        if not (event.state & 0x4): return
        action = KC.get(event.keycode)
        if not action: return
        w = event.widget
        try:
            if action == "select_all":
                if isinstance(w, tk.Text): w.tag_add("sel", "1.0", "end-1c")
                else: w.select_range(0, "end"); w.icursor("end")
            else:
                w.event_generate(action)
        except Exception: pass
        return "break"
    for cls in ("TEntry", "Entry", "Text", "TCombobox", "Spinbox", "TSpinbox"):
        root.bind_class(cls, "<Control-KeyPress>", on_key, add="+")
        root.bind_class(cls, "<Button-3>", _show_ctx_menu, add="+")


def _show_ctx_menu(event):
    w = event.widget
    m = tk.Menu(w, tearoff=0, bg="#0f2b27", fg="#e5e7eb",
                activebackground="#d4af37", activeforeground="#0a1f1c")
    try:
        m.add_command(label="قص", command=lambda: w.event_generate("<<Cut>>"))
        m.add_command(label="نسخ", command=lambda: w.event_generate("<<Copy>>"))
        m.add_command(label="لصق", command=lambda: w.event_generate("<<Paste>>"))
        m.add_separator()
        m.add_command(label="تحديد الكل", command=lambda: (
            w.tag_add("sel", "1.0", "end-1c") if isinstance(w, tk.Text)
            else (w.select_range(0, "end"), w.icursor("end"))
        ))
        m.tk_popup(event.x_root, event.y_root)
    finally:
        m.grab_release()


# ============================================================
# الواجهة
# ============================================================

class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE); root.geometry("900x760"); root.configure(bg="#0a1f1c")
        cfg = json.loads(CFG.read_text(encoding="utf-8")) if CFG.exists() else {}
        self.excel = tk.StringVar(value=cfg.get("excel", ""))
        self.server = tk.StringVar(value=cfg.get("server", DEFAULT_SERVER))
        self.token = tk.StringVar(value=cfg.get("token", ""))
        self.workers = tk.IntVar(value=cfg.get("workers", min(8, os.cpu_count() or 4)))
        self.per = tk.IntVar(value=cfg.get("per", 3))
        self.running = False; self.paused = False; self.stopped = False
        self.ready = False
        self.q = queue.Queue(); self.done = self.ok = self.fail = self.hs = 0
        self.t0 = None; self.names = []
        self._ui(); root.after(200, self._poll)
        root.protocol("WM_DELETE_WINDOW", self._close)
        enable_clipboard(root)
        # فحص المتطلبات تلقائياً عند البدء
        root.after(500, self._preflight)

    def _preflight(self):
        self._log("═════════ فحص متطلبات التشغيل ═════════", "info")
        self.b_start.configure(state="disabled")
        threading.Thread(target=self._preflight_worker, daemon=True).start()

    def _preflight_worker(self):
        try:
            ok = check_and_install_all(lambda m: self.q.put(("log", m, "info")))
            self.ready = ok
            self.q.put(("ready", ok, None))
        except Exception as e:
            self.q.put(("log", f"❌ فشل الفحص: {e}", "fail"))
            self.q.put(("ready", False, None))

    def _ui(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("TLabel", background="#0a1f1c", foreground="#e5e7eb", font=("Segoe UI", 10))
        s.configure("H.TLabel", font=("Segoe UI", 18, "bold"), foreground="#d4af37")
        s.configure("S.TLabel", foreground="#94a3b8")
        s.configure("TFrame", background="#0a1f1c")
        s.configure("C.TFrame", background="#0f2b27")
        s.configure("TEntry", fieldbackground="#0f2b27", foreground="#e5e7eb", insertcolor="#d4af37")
        s.configure("TButton", background="#d4af37", foreground="#0a1f1c", font=("Segoe UI", 10, "bold"), padding=8)
        s.map("TButton", background=[("active", "#e8c56a")])
        s.configure("G.TButton", background="#1a3d38", foreground="#e5e7eb")
        s.map("G.TButton", background=[("active", "#255049")])
        s.configure("Horizontal.TProgressbar", background="#d4af37", troughcolor="#0f2b27")

        h = ttk.Frame(self.root); h.pack(fill="x", padx=20, pady=(20, 8))
        ttk.Label(h, text="🎙️  من القارئ", style="H.TLabel").pack(anchor="w")
        ttk.Label(h, text="مولّد بصمات القرّاء الصوتية — تشغيل محلي فائق السرعة", style="S.TLabel").pack(anchor="w")

        c = ttk.Frame(self.root, style="C.TFrame"); c.pack(fill="x", padx=20, pady=10)
        c.columnconfigure(1, weight=1)
        pad = {"padx": 16, "pady": 8}

        ttk.Label(c, text="🔑 التوكن:").grid(row=0, column=0, sticky="w", **pad)
        te = ttk.Entry(c, textvariable=self.token, show="•"); te.grid(row=0, column=1, sticky="ew", **pad)
        sv = tk.BooleanVar()
        ttk.Checkbutton(c, text="إظهار", variable=sv,
            command=lambda: te.configure(show="" if sv.get() else "•")).grid(row=0, column=2, **pad)

        ttk.Label(c, text="🌐 السيرفر:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=self.server).grid(row=1, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(c, text="📄 ملف Excel:").grid(row=2, column=0, sticky="w", **pad)
        fp = ttk.Frame(c, style="C.TFrame"); fp.grid(row=2, column=1, columnspan=2, sticky="ew", **pad)
        fp.columnconfigure(0, weight=1)
        ttk.Entry(fp, textvariable=self.excel).grid(row=0, column=0, sticky="ew")
        ttk.Button(fp, text="اختر…", style="G.TButton",
            command=lambda: self._pick()).grid(row=0, column=1, padx=(8, 0))

        o = ttk.Frame(c, style="C.TFrame"); o.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Label(o, text="⚙️ Workers:").pack(side="left", padx=(0, 6))
        ttk.Spinbox(o, from_=1, to=32, textvariable=self.workers, width=5).pack(side="left", padx=(0, 20))
        ttk.Label(o, text="🎬 فيديو/قارئ:").pack(side="left", padx=(0, 6))
        ttk.Spinbox(o, from_=1, to=10, textvariable=self.per, width=5).pack(side="left")

        ct = ttk.Frame(self.root); ct.pack(fill="x", padx=20, pady=(4, 10))
        self.b_start = ttk.Button(ct, text="▶  ابدأ", command=self._start); self.b_start.pack(side="left", padx=(0, 8))
        self.b_pause = ttk.Button(ct, text="⏸  إيقاف مؤقت", style="G.TButton",
            command=self._pause, state="disabled"); self.b_pause.pack(side="left", padx=(0, 8))
        self.b_stop = ttk.Button(ct, text="⏹  إيقاف", style="G.TButton",
            command=self._stop, state="disabled"); self.b_stop.pack(side="left")
        self.b_recheck = ttk.Button(ct, text="🔄  إعادة فحص المتطلبات", style="G.TButton",
            command=self._preflight); self.b_recheck.pack(side="right")

        p = ttk.Frame(self.root, style="C.TFrame"); p.pack(fill="x", padx=20, pady=8)
        self.pb = ttk.Progressbar(p, orient="horizontal", mode="determinate", length=100)
        self.pb.pack(fill="x", padx=16, pady=(16, 8))
        st = ttk.Frame(p, style="C.TFrame"); st.pack(fill="x", padx=16, pady=(0, 16))
        self.l_cnt = ttk.Label(st, text="0 / 0"); self.l_cnt.pack(side="left")
        self.l_ok = ttk.Label(st, text="✅ 0", foreground="#4ade80"); self.l_ok.pack(side="left", padx=(20, 0))
        self.l_fail = ttk.Label(st, text="❌ 0", foreground="#f87171"); self.l_fail.pack(side="left", padx=(20, 0))
        self.l_hs = ttk.Label(st, text="🎵 0", foreground="#d4af37"); self.l_hs.pack(side="left", padx=(20, 0))
        self.l_rate = ttk.Label(st, text="⚡ 0.0/دق"); self.l_rate.pack(side="right", padx=(20, 0))
        self.l_eta = ttk.Label(st, text="⏳ ETA: —"); self.l_eta.pack(side="right", padx=(20, 0))
        self.l_el = ttk.Label(st, text="⏱ 0:00:00"); self.l_el.pack(side="right")

        lf = ttk.Frame(self.root, style="C.TFrame"); lf.pack(fill="both", expand=True, padx=20, pady=(4, 20))
        ttk.Label(lf, text="📋 السجل الحي", foreground="#d4af37").pack(anchor="w", padx=16, pady=(12, 4))
        self.log = tk.Text(lf, bg="#0a1f1c", fg="#e5e7eb", insertbackground="#d4af37",
            font=("Consolas", 9), relief="flat", padx=12, pady=8, height=14)
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.log.tag_configure("rtl", justify="right")
        self.log.tag_configure("ok", foreground="#4ade80", justify="right")
        self.log.tag_configure("fail", foreground="#f87171", justify="right")
        self.log.tag_configure("info", foreground="#d4af37", justify="right")

    def _pick(self):
        p = filedialog.askopenfilename(title="اختر ملف Excel",
            filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv")])
        if p: self.excel.set(p)

    def _save(self):
        try:
            CFG.write_text(json.dumps({"token": self.token.get(), "server": self.server.get(),
                "excel": self.excel.get(), "workers": self.workers.get(), "per": self.per.get()},
                ensure_ascii=False, indent=2), encoding="utf-8")
        except: pass

    def _log(self, t, tag=None):
        self.log.insert("end", t + "\n", tag or "rtl")
        self.log.see("end")

    def _start(self):
        if self.running: return
        if not self.ready:
            if not messagebox.askyesno("تحذير", "المتطلبات لم تكتمل — قد تفشل معظم العمليات. متابعة؟"):
                return
        if not self.excel.get() or not Path(self.excel.get()).exists():
            messagebox.showerror("خطأ", "اختر ملف Excel صحيح"); return
        if not self.token.get():
            messagebox.showerror("خطأ", "أدخل التوكن"); return
        try:
            import pandas as pd
            df = pd.read_excel(self.excel.get())
            names = df[df.columns[0]].dropna().astype(str).str.strip().unique().tolist()
        except Exception as e:
            messagebox.showerror("خطأ في قراءة الملف", str(e)); return
        if not names:
            messagebox.showerror("خطأ", "الملف فارغ"); return
        self._save()
        self.names = names
        self.done = self.ok = self.fail = self.hs = 0
        self.t0 = time.time(); self.stopped = False; self.paused = False; self.running = True
        self.pb["maximum"] = len(names); self.pb["value"] = 0
        self._log(f"▶ بدء التشغيل — {len(names):,} قارئ • {self.workers.get()} workers", "info")
        self.b_start.configure(state="disabled")
        self.b_pause.configure(state="normal")
        self.b_stop.configure(state="normal")
        threading.Thread(target=self._loop, daemon=True).start()
        self._tick()

    def _pause(self):
        self.paused = not self.paused
        self.b_pause.configure(text="▶  متابعة" if self.paused else "⏸  إيقاف مؤقت")
        self._log("⏸ متوقف مؤقتاً" if self.paused else "▶ استكمال", "info")

    def _stop(self):
        self.stopped = True; self.running = False
        self._log("⏹ تم الإيقاف", "info")
        self.b_start.configure(state="normal")
        self.b_pause.configure(state="disabled", text="⏸  إيقاف مؤقت")
        self.b_stop.configure(state="disabled")

    def _loop(self):
        tmp = tempfile.mkdtemp(prefix="mnq_")
        batch = []
        try:
            with ProcessPoolExecutor(max_workers=self.workers.get()) as ex:
                futs = {ex.submit(process_reciter, (n, self.per.get(), tmp)): n for n in self.names}
                for f in as_completed(futs):
                    while self.paused and not self.stopped: time.sleep(0.5)
                    if self.stopped:
                        for x in futs: x.cancel()
                        break
                    n = futs[f]
                    try:
                        r = f.result()
                        if r.get("items"):
                            batch.extend(r["items"])
                            self.q.put(("ok", n, r["hashes"]))
                        else:
                            self.q.put(("fail", n, r.get("error", "no items")))
                        if len(batch) >= BATCH:
                            success = upload(self.server.get(), self.token.get(), batch)
                            self.q.put(("upload", len(batch), success))
                            batch = []
                    except Exception as e:
                        self.q.put(("fail", n, str(e)))
            if batch:
                success = upload(self.server.get(), self.token.get(), batch)
                self.q.put(("upload", len(batch), success))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            self.q.put(("finish", None, None))

    def _poll(self):
        try:
            while True:
                kind, a, b = self.q.get_nowait()
                if kind == "log":
                    self._log(a, b or "info")
                elif kind == "ready":
                    self.ready = a
                    self.b_start.configure(state="normal")
                    self._log("═══════════════════════════════════", "info")
                elif kind == "ok":
                    self.ok += 1; self.done += 1; self.hs += b
                    self._log(f"✅ {a}  •  {b:,} بصمة", "ok")
                elif kind == "fail":
                    self.fail += 1; self.done += 1
                    self._log(f"❌ {a}  •  {b}", "fail")
                elif kind == "upload":
                    tag = "ok" if b else "fail"
                    self._log(f"📤 رفع دفعة {a} عنصر — {'نجح' if b else 'فشل'}", tag)
                elif kind == "finish":
                    self.running = False
                    self._log("🎉 انتهى!", "info")
                    self.b_start.configure(state="normal")
                    self.b_pause.configure(state="disabled")
                    self.b_stop.configure(state="disabled")
                if kind in ("ok", "fail"):
                    self.pb["value"] = self.done
                    self.l_cnt.configure(text=f"{self.done:,} / {len(self.names):,}")
                    self.l_ok.configure(text=f"✅ {self.ok:,}")
                    self.l_fail.configure(text=f"❌ {self.fail:,}")
                    self.l_hs.configure(text=f"🎵 {self.hs:,}")
        except queue.Empty: pass
        self.root.after(200, self._poll)

    def _tick(self):
        if not self.running: return
        el = time.time() - self.t0
        self.l_el.configure(text=f"⏱ {timedelta(seconds=int(el))}")
        if self.done > 0:
            rate = self.done / el * 60
            self.l_rate.configure(text=f"⚡ {rate:.1f}/دق")
            left = len(self.names) - self.done
            if rate > 0:
                eta = int(left / (rate / 60))
                self.l_eta.configure(text=f"⏳ ETA: {timedelta(seconds=eta)}")
        self.root.after(1000, self._tick)

    def _close(self):
        self._save(); self.stopped = True; self.root.destroy()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    root = tk.Tk()
    App(root)
    root.mainloop()
