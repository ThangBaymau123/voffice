"""
Ví dụ 05 — Văn phòng ảo (Web UI)

Chạy: python examples/05_virtual_office_web.py
Browser tự mở http://localhost:8000
Thoát: Ctrl+C
"""

import threading
import time
import webbrowser

import uvicorn


def _open_browser_after_delay() -> None:
    time.sleep(1.0)  # đợi uvicorn bind port xong
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    threading.Thread(target=_open_browser_after_delay, daemon=True).start()
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=False)
