import sys,threading,time,socket,traceback
from pathlib import Path
sys.path.insert(0,str(Path(getattr(sys,"_MEIPASS",Path(__file__).parent))))
import uvicorn,webview
E={"e":None}
def W(p,t=180):
 s=time.time()
 while time.time()-s<t:
  if E["e"]:return False
  try:
   with socket.create_connection(("127.0.0.1",p),timeout=1):return True
  except OSError:time.sleep(0.4)
 return False
def R():
 try:
  from app.main import app
  uvicorn.run(app,host="127.0.0.1",port=8000,log_level="warning")
 except Exception:E["e"]=traceback.format_exc()
def P(w):
 if W(8000):w.load_url("http://127.0.0.1:8000/docs")
 else:
  import html
  w.load_html("<body style='background:#7f1d1d;color:#fff;font-family:Segoe UI;padding:20px'><h2>Server failed</h2><pre>"+html.escape(E["e"] or "Timeout")+"</pre></body>")
if __name__=="__main__":
 threading.Thread(target=R,daemon=True).start()
 w=webview.create_window("Quran Reciter ID",html="<body style='background:#0f172a;color:#e2e8f0;font-family:Segoe UI;display:flex;align-items:center;justify-content:center;height:100vh'><div style=text-align:center><h1 style=color:#38bdf8>Quran Reciter ID</h1><p>Loading models...</p></div></body>",width=1100,height=780)
 webview.start(P,w)
