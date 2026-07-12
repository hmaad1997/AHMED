import os,sys,time,threading,traceback,faulthandler,webbrowser,urllib.request
from pathlib import Path
A=Path(os.environ.get("APPDATA") or Path.home())/"QuranReciterID";A.mkdir(parents=True,exist_ok=True)
L=A/"launcher.log"
try:
    _f=open(L,"a",buffering=1,encoding="utf-8");sys.stdout=_f;sys.stderr=_f
except Exception:
    _f=None
faulthandler.enable(file=_f or sys.__stderr__)
print(f"[boot] {time.strftime('%F %T')} frozen={getattr(sys,'frozen',0)} meipass={getattr(sys,'_MEIPASS','-')}",flush=True)
B=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent));sys.path.insert(0,str(B))
E={"e":None};P=8000
def wait(t=900):
    s=time.time()
    while time.time()-s<t:
        if E["e"]:return False
        try:
            r=urllib.request.urlopen(f"http://127.0.0.1:{P}/health",timeout=2)
            if r.status==200:return True
        except Exception:time.sleep(0.5)
    return False
def srv():
    try:
        import uvicorn
        from app.main import app
        uvicorn.run(app,host="127.0.0.1",port=P,log_level="info",log_config=None)
    except SystemExit:raise
    except BaseException:
        E["e"]=traceback.format_exc();print("[CRASH]\n"+E["e"],flush=True)
def ui():
    u=f"http://127.0.0.1:{P}/"
    try:
        import webview
        LOGO=(B/"app"/"static"/"logo.jpg").as_uri()
        s=f"<body style='margin:0;background:#021a19;color:#f0d78c;display:flex;align-items:center;justify-content:center;height:100vh;direction:rtl;font-family:Segoe UI'><div style='text-align:center'><img src='{LOGO}' style='width:120px;height:120px;border-radius:50%;box-shadow:0 0 0 3px #d9b35c'><h1>من القارئ</h1><p style='color:#a9b8b6'>جارٍ التحميل…</p></div></body>"
        w=webview.create_window("من القارئ",html=s,width=1200,height=820,min_size=(900,640))
        def on(win):
            if wait():win.load_url(u)
            else:
                import html;m=html.escape(E["e"] or "الخادم لم يستجب")
                win.load_html(f"<body style='background:#2a1414;color:#fff;padding:20px;direction:rtl'><h2>خطأ</h2><p>Log: {L}</p><pre>{m}</pre></body>")
        webview.start(on,w);print("[exit] webview closed",flush=True);os._exit(0)
    except Exception as e:
        print(f"[warn] webview: {e} → browser fallback",flush=True)
        if wait():
            try:webbrowser.open(u)
            except Exception:pass
        while True:time.sleep(3600)
if __name__=="__main__":
    try:
        import multiprocessing;multiprocessing.freeze_support()
    except Exception:pass
    if os.environ.get("QRI_HEADLESS")=="1":
        print("[headless] server in main thread",flush=True);srv();raise SystemExit(1 if E["e"] else 0)
    threading.Thread(target=srv,name="uvicorn",daemon=False).start()
    ui()
