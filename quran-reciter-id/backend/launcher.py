"""GUI launcher for Quran Reciter ID - hides console, opens webview window."""
import sys, threading, time, socket
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
import webview

def wait_for_port(port, host="127.0.0.1", timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False

def run_server():
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    wait_for_port(8000)
    webview.create_window("Quran Reciter ID", "http://127.0.0.1:8000/docs", width=1100, height=780)
    webview.start()
