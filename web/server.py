"""FastAPI app: serves the static UI and one WebSocket per session."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Make examples/ importable as a flat module path (matches pytest.ini pythonpath)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "examples"))

from office_engine import build_office, run_turn  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Thư mục lưu deliverable: ưu tiên biến môi trường WORKSPACE_DIR, mặc định project_root/workspace
WORKSPACE_DIR = Path(
    os.environ.get("WORKSPACE_DIR", PROJECT_ROOT / "workspace")
).resolve()

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/roster")
async def roster() -> dict:
    """Used by the page to render sidebar avatars."""
    return {
        "members": [
            {"name": "Manager", "title": "Manager",            "color": "#5865f2"},
            {"name": "Lan",     "title": "Product Manager",    "color": "#f1c40f"},
            {"name": "Minh",    "title": "Backend Developer",  "color": "#2ecc71"},
            {"name": "Hà",      "title": "Frontend Developer", "color": "#e91e63"},
            {"name": "Tú",      "title": "QA Tester",          "color": "#3498db"},
        ],
    }


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        office = build_office(WORKSPACE_DIR)
    except KeyError as e:
        await websocket.send_json({"error": f"Missing env var: {e.args[0]}"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("text", "").strip()
            if not user_text:
                continue
            try:
                async for ev in run_turn(office, user_text):
                    await websocket.send_json({
                        "speaker": ev.speaker,
                        "text": ev.text_chunk,
                        "final": ev.is_final,
                    })
                await websocket.send_json({"turn_complete": True})
            except Exception as e:  # noqa: BLE001
                await websocket.send_json({"error": str(e)})
    except WebSocketDisconnect:
        return
