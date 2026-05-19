"""
Ví dụ 05 — Văn phòng ảo (Web UI)

Chạy: python examples/05_virtual_office_web.py
Browser tự mở http://localhost:8000
Thoát: Ctrl+C
"""

import sys
import threading
import time
import webbrowser
from pathlib import Path

# Đảm bảo project root nằm trong sys.path để uvicorn import được package `web`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn  # noqa: E402


def _open_browser_after_delay() -> None:
    time.sleep(1.0)  # đợi uvicorn bind port xong
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    threading.Thread(target=_open_browser_after_delay, daemon=True).start()
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=False)
