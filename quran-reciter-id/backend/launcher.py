import sys, threading, time, socket, traceback
from pathlib import Path
sys.path.insert(0, str(Path(getattr(sys, "_MEIPASS", Path(__file__).parent))))
import uvicorn, webview

E = {"e": None}

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
            "<body style='background:#7f1d1d;color:#fff;font-family:Segoe UI;padding:20px'>"
            "<h2>Server failed</h2><pre style='white-space:pre-wrap'>" + msg + "</pre></body>"
        )

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    win = webview.create_window(
        "Quran Reciter ID",
        html="""<body style='margin:0;background:#0b1220;color:#e6ecf7;font-family:Segoe UI,sans-serif;
             display:flex;align-items:center;justify-content:center;height:100vh'>
             <div style='text-align:center'>
             <div style='width:70px;height:70px;margin:0 auto 20px;border-radius:18px;
             background:linear-gradient(135deg,#d4af37,#f0d78c);display:grid;place-items:center;
             color:#1a1204;font-weight:900;font-size:34px;font-family:serif'>ق</div>
             <h1 style='color:#f0d78c;margin:0 0 8px'>Quran Reciter ID</h1>
             <p style='color:#8ea0c2'>جارٍ تحميل النموذج الذكي…</p>
             <p style='color:#8ea0c2;font-size:12px'>(أول تشغيل يستغرق دقيقة)</p>
             <div style='margin:20px auto;width:40px;height:40px;border:3px solid #1f2b47;
             border-top-color:#d4af37;border-radius:50%;animation:s 1s linear infinite'></div>
             </div>
             <style>@keyframes s{to{transform:rotate(360deg)}}</style></body>""",
        width=1200, height=820, min_size=(900, 640),
    )
    webview.start(on_start, win)
