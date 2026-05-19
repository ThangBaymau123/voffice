"""Uvicorn launcher for `voffice web` — boots server + opens browser."""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

# Direct invocation (`python voffice/launcher.py`) means uvicorn's
# `voffice.server:app` import string won't resolve unless we put the
# project root on sys.path first.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn


def _open_browser_after_delay() -> None:
    time.sleep(1.0)  # wait for uvicorn to bind the port
    webbrowser.open("http://localhost:8000")


def run_web() -> None:
    threading.Thread(target=_open_browser_after_delay, daemon=True).start()
    uvicorn.run("voffice.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    run_web()
