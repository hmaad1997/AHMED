import sys, threading, time, socket, traceback
from pathlib import Path
sys.path.insert(0, str(Path(getattr(sys, "_MEIPASS", Path(__file__).parent))))
import uvicorn, webview

E = {"e": None}
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
LOGO = (BASE / "app" / "static" / "logo.jpg").as_uri()

def wait_port(port, timeout=900):
    start = time.time()
    while time.time() - start < timeout:
        if E["e"]:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False

def run_server():
    try:
        from app.main import app
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
    except Exception:
        E["e"] = traceback.format_exc()

def on_start(window):
    if wait_port(8000):
        window.load_url("http://127.0.0.1:8000/")
    else:
        import html as _html
        msg = _html.escape(E["e"] or "Server did not start in time")
        window.load_html(
            "<body style='background:#2a1414;color:#fff;font-family:Segoe UI;padding:20px'>"
            "<h2>خطأ في تشغيل الخادم</h2><pre style='white-space:pre-wrap'>" + msg + "</pre></body>"
        )

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    splash = f"""<body style='margin:0;background:radial-gradient(1000px 700px at 80% -10%,#0f5349 0,#021a19 70%);
    color:#eef4ea;font-family:"Segoe UI",Tahoma,sans-serif;display:flex;align-items:center;
    justify-content:center;height:100vh;direction:rtl'>
    <div style='text-align:center'>
    <img src='{LOGO}' style='width:120px;height:120px;border-radius:50%;object-fit:cover;
    box-shadow:0 0 0 3px #d9b35c,0 0 40px #d9b35c66;margin-bottom:22px'>
    <h1 style='color:#f0d78c;margin:0 0 6px;font-size:38px;font-family:"Traditional Arabic",serif'>من القارئ</h1>
    <p style='color:#a9b8b6;margin:0 0 22px'>جارٍ تحميل النموذج الذكي…</p>
    <div style='margin:0 auto;width:44px;height:44px;border:3px solid #083c39;
    border-top-color:#d9b35c;border-radius:50%;animation:s 1s linear infinite'></div>
    </div><style>@keyframes s{{to{{transform:rotate(360deg)}}}}</style></body>"""
    win = webview.create_window("من القارئ", html=splash,
        width=1200, height=820, min_size=(900, 640))
    webview.start(on_start, win)
