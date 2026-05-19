# Virtual Office Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vietnamese virtual software office chat — Manager + 4 employees (PM, Backend, Frontend, QA) — usable via CLI and a Slack-style web UI, sharing one engine that streams turn-by-turn events.

**Architecture:** Three layers. Layer 1 = `office_engine.py` exposes `build_office()` and async generator `run_turn()` yielding `TurnEvent(speaker, text_chunk, is_final)`. Layer 2 = two entry points (`04_virtual_office_cli.py`, `05_virtual_office_web.py`) consume the same generator. Layer 3 = AgentScope `MsgHub` + `fanout_pipeline` with 5 `AnthropicChatModel` instances pointing at AWS gateway (regions vary per agent).

**Tech Stack:** Python 3.10, AgentScope 1.0.20, Anthropic SDK (via AgentScope), FastAPI, uvicorn, websockets, colorama (CLI), pytest + pytest-asyncio (tests), vanilla HTML/CSS/JS (no build).

---

## File Structure

```
agentscope/
├── examples/
│   ├── _common.py                   # MODIFY: make_model accepts per-agent config
│   ├── office_engine.py             # NEW: build_office, run_turn, dataclasses
│   ├── 04_virtual_office_cli.py     # NEW: terminal REPL
│   └── 05_virtual_office_web.py     # NEW: uvicorn launcher
├── web/
│   ├── __init__.py                  # NEW: empty (makes it a package)
│   ├── server.py                    # NEW: FastAPI app + websocket
│   └── static/
│       ├── index.html               # NEW
│       ├── style.css                # NEW
│       └── app.js                   # NEW
├── tests/
│   └── test_office_engine.py        # NEW: unit tests for engine
├── .env.example                     # MODIFY: add 5 employee key placeholders
├── requirements.txt                 # MODIFY: + fastapi, uvicorn, colorama, pytest-asyncio
└── README.md                        # MODIFY: section for examples 4 & 5
```

Each file has one responsibility:
- `_common.py` → model factory only
- `office_engine.py` → no I/O, pure orchestration of agents
- `04_*.py` → CLI rendering only (no business logic)
- `05_*.py` → uvicorn launcher only (5 lines)
- `web/server.py` → HTTP + WS routing only
- `web/static/*` → presentation only

---

## Task 1: Install dependencies + set up pytest

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py` (empty)
- Create: `pytest.ini`

- [ ] **Step 1: Update requirements.txt**

Replace contents with:

```
agentscope>=1.0.20
anthropic>=0.40.0
python-dotenv>=1.0.0
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
colorama>=0.4.6
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Install deps**

Run: `pip install -r requirements.txt`
Expected: all packages install (or already satisfied).

- [ ] **Step 3: Create tests/__init__.py**

Empty file. `touch tests/__init__.py` on Unix, or create blank file on Windows.

- [ ] **Step 4: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = examples
```

- [ ] **Step 5: Verify pytest works**

Run: `pytest --collect-only`
Expected: `no tests ran` (no errors, just nothing to collect).

- [ ] **Step 6: Commit**

```bash
git init  # if not already a repo
git add requirements.txt tests/__init__.py pytest.ini
git commit -m "chore: add fastapi, uvicorn, colorama, pytest deps"
```

---

## Task 2: Extend `make_model()` with optional per-agent config (TDD)

**Files:**
- Test: `tests/test_office_engine.py`
- Modify: `examples/_common.py`

- [ ] **Step 1: Write failing test for explicit-args path**

Create `tests/test_office_engine.py`:

```python
import os
import pytest
from _common import make_model


def test_make_model_uses_explicit_args(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AWS_API_KEY", "fallback")
    monkeypatch.setenv("ANTHROPIC_AWS_WORKSPACE_ID", "fallback_ws")
    monkeypatch.setenv("ANTHROPIC_AWS_BASE_URL", "https://fallback.example")

    model = make_model(
        api_key="explicit_key",
        workspace_id="explicit_ws",
        base_url="https://explicit.example",
    )
    assert str(model.client.base_url).rstrip("/") == "https://explicit.example"
    assert model.client.default_headers.get("anthropic-workspace-id") == "explicit_ws"


def test_make_model_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AWS_API_KEY", "fallback_key")
    monkeypatch.setenv("ANTHROPIC_AWS_WORKSPACE_ID", "fallback_ws")
    monkeypatch.setenv("ANTHROPIC_AWS_BASE_URL", "https://fallback.example")

    model = make_model()
    assert str(model.client.base_url).rstrip("/") == "https://fallback.example"
    assert model.client.default_headers.get("anthropic-workspace-id") == "fallback_ws"
```

- [ ] **Step 2: Run tests to see them fail**

Run: `pytest tests/test_office_engine.py -v`
Expected: FAIL — `make_model()` currently takes no args; `TypeError: make_model() got an unexpected keyword argument 'api_key'`.

- [ ] **Step 3: Replace `examples/_common.py`**

```python
"""
Helpers dùng chung cho mọi ví dụ.

`make_model()` xây dựng `AnthropicChatModel` của AgentScope trỏ vào Anthropic
gateway. Mỗi tham số có thể truyền tường minh (cho từng agent dùng key/region
riêng) hoặc fallback sang biến môi trường `ANTHROPIC_AWS_*`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from agentscope.model import AnthropicChatModel

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-4-5"


def make_model(
    api_key: str | None = None,
    workspace_id: str | None = None,
    base_url: str | None = None,
    *,
    model_name: str = DEFAULT_MODEL,
    stream: bool = True,
) -> AnthropicChatModel:
    api_key = api_key or os.environ["ANTHROPIC_AWS_API_KEY"]
    workspace_id = workspace_id or os.environ["ANTHROPIC_AWS_WORKSPACE_ID"]
    base_url = base_url or os.environ["ANTHROPIC_AWS_BASE_URL"]

    return AnthropicChatModel(
        model_name=model_name,
        api_key=api_key,
        stream=stream,
        client_kwargs={
            "base_url": base_url,
            "default_headers": {"anthropic-workspace-id": workspace_id},
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_office_engine.py -v`
Expected: 2 passed.

- [ ] **Step 5: Verify older examples still import cleanly**

Run: `python -c "from examples._common import make_model; m = make_model(); print('OK:', m.__class__.__name__)"`
Expected: `OK: AnthropicChatModel`.

- [ ] **Step 6: Commit**

```bash
git add examples/_common.py tests/test_office_engine.py
git commit -m "feat(common): make_model accepts per-agent api_key/workspace_id/base_url"
```

---

## Task 3: Define `RoleSpec`, `ROLES`, `Office`, `TurnEvent` (TDD)

**Files:**
- Test: `tests/test_office_engine.py` (append)
- Create: `examples/office_engine.py`

- [ ] **Step 1: Append failing tests for data structures**

Append to `tests/test_office_engine.py`:

```python
from office_engine import ROLES, RoleSpec, TurnEvent


def test_roles_has_5_entries():
    expected = {"Manager", "Lan", "Minh", "Hà", "Tú"}
    assert set(ROLES.keys()) == expected


def test_each_role_has_required_fields():
    for name, spec in ROLES.items():
        assert isinstance(spec, RoleSpec)
        assert spec.title, f"{name} missing title"
        assert spec.sys_prompt, f"{name} missing sys_prompt"
        assert spec.env_prefix, f"{name} missing env_prefix"


def test_employee_sys_prompts_contain_skip_rule():
    employee_names = ["Lan", "Minh", "Hà", "Tú"]
    for name in employee_names:
        assert "[skip]" in ROLES[name].sys_prompt, (
            f"{name}'s sys_prompt must instruct to return [skip] when silent"
        )


def test_turn_event_dataclass_shape():
    ev = TurnEvent(speaker="Lan", text_chunk="xin chào", is_final=False)
    assert ev.speaker == "Lan"
    assert ev.text_chunk == "xin chào"
    assert ev.is_final is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_office_engine.py -v -k "roles or turn"`
Expected: FAIL — `ModuleNotFoundError: No module named 'office_engine'`.

- [ ] **Step 3: Create `examples/office_engine.py`**

```python
"""
Văn phòng ảo — logic chung cho CLI và Web.

Kiến trúc: 1 Manager + 4 employees ngồi chung MsgHub (auto-broadcast).
- build_office() — đọc env, dựng 5 ReActAgent.
- run_turn() — async generator phát TurnEvent từng chunk khi stream.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleSpec:
    title: str
    sys_prompt: str
    env_prefix: str  # ví dụ "MANAGER" → MANAGER_KEY, MANAGER_WORKSPACE, MANAGER_BASE_URL


@dataclass
class TurnEvent:
    speaker: str
    text_chunk: str   # delta — KHÔNG phải cumulative
    is_final: bool


_EMPLOYEE_TEMPLATE = """\
Bạn là {name}, {title} trong văn phòng phần mềm.

QUY TẮC NÓI:
- Nếu Manager nhắc tên bạn → trả lời chi tiết theo chuyên môn.
- Nếu Manager giao cho người khác nhưng bạn thấy LỖI KỸ THUẬT NGHIÊM TRỌNG
  trong cách tiếp cận, hãy chen ngắn 1-2 câu phản biện.
- Nếu không có gì để góp, trả lời CHÍNH XÁC chuỗi: [skip]

Trả lời tiếng Việt, 2-4 câu, từ góc nhìn chuyên môn ({title}) của bạn.
"""


def _emp(name: str, title: str, env_prefix: str) -> RoleSpec:
    return RoleSpec(
        title=title,
        sys_prompt=_EMPLOYEE_TEMPLATE.format(name=name, title=title),
        env_prefix=env_prefix,
    )


ROLES: dict[str, RoleSpec] = {
    "Manager": RoleSpec(
        title="Manager",
        sys_prompt=(
            "Bạn là Manager của một văn phòng phần mềm 4 người: "
            "Lan (PM), Minh (Backend), Hà (Frontend), Tú (QA). "
            "Khi user đăng việc:\n"
            "  1. Phân tích yêu cầu.\n"
            "  2. Giao việc CỤ THỂ cho từng người liên quan, gọi đích danh.\n"
            "  3. Không tự làm thay — chỉ điều phối.\n"
            "Trả lời ngắn (2-5 câu), tiếng Việt."
        ),
        env_prefix="MANAGER",
    ),
    "Lan":  _emp("Lan",  "Product Manager",   "EMPLOYEE_1"),
    "Minh": _emp("Minh", "Backend Developer", "EMPLOYEE_2"),
    "Hà":   _emp("Hà",   "Frontend Developer", "EMPLOYEE_3"),
    "Tú":   _emp("Tú",   "QA Tester",         "EMPLOYEE_4"),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_office_engine.py -v`
Expected: All previous tests + 4 new tests = 6 passed.

- [ ] **Step 5: Commit**

```bash
git add examples/office_engine.py tests/test_office_engine.py
git commit -m "feat(engine): define RoleSpec, ROLES dict, TurnEvent dataclass"
```

---

## Task 4: Implement `build_office()` (TDD with stubbed env)

**Files:**
- Test: `tests/test_office_engine.py` (append)
- Modify: `examples/office_engine.py`

- [ ] **Step 1: Append failing test**

Append to `tests/test_office_engine.py`:

```python
from office_engine import Office, build_office


def _set_full_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AWS_API_KEY", "k0")
    monkeypatch.setenv("ANTHROPIC_AWS_WORKSPACE_ID", "w0")
    monkeypatch.setenv("ANTHROPIC_AWS_BASE_URL", "https://r0.example")
    for i, prefix in enumerate(
        ["MANAGER", "EMPLOYEE_1", "EMPLOYEE_2", "EMPLOYEE_3", "EMPLOYEE_4"], start=1
    ):
        monkeypatch.setenv(f"{prefix}_KEY", f"k{i}")
        monkeypatch.setenv(f"{prefix}_WORKSPACE", f"w{i}")
        monkeypatch.setenv(f"{prefix}_BASE_URL", f"https://r{i}.example")


def test_build_office_creates_5_agents(monkeypatch):
    _set_full_env(monkeypatch)
    office = build_office()
    assert isinstance(office, Office)
    assert office.manager.name == "Manager"
    assert [a.name for a in office.employees] == ["Lan", "Minh", "Hà", "Tú"]


def test_build_office_missing_env_raises(monkeypatch):
    _set_full_env(monkeypatch)
    monkeypatch.delenv("EMPLOYEE_3_KEY")
    with pytest.raises(KeyError, match="EMPLOYEE_3_KEY"):
        build_office()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_office_engine.py -v -k "build_office"`
Expected: FAIL — `ImportError: cannot import name 'Office'`.

- [ ] **Step 3: Append `Office` dataclass + `build_office()` to `examples/office_engine.py`**

Append to end of file:

```python
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import AnthropicMultiAgentFormatter
from agentscope.memory import InMemoryMemory
from agentscope.pipeline import MsgHub

from _common import make_model


@dataclass
class Office:
    manager: ReActAgent
    employees: list[ReActAgent]
    hub: MsgHub | None = None  # populated lazily by run_turn (async context required)


def _agent_from_role(name: str, spec: RoleSpec) -> ReActAgent:
    api_key = os.environ[f"{spec.env_prefix}_KEY"]
    workspace_id = os.environ[f"{spec.env_prefix}_WORKSPACE"]
    base_url = os.environ[f"{spec.env_prefix}_BASE_URL"]
    return ReActAgent(
        name=name,
        sys_prompt=spec.sys_prompt,
        model=make_model(api_key=api_key, workspace_id=workspace_id, base_url=base_url),
        formatter=AnthropicMultiAgentFormatter(),
        memory=InMemoryMemory(),
    )


def build_office() -> Office:
    manager = _agent_from_role("Manager", ROLES["Manager"])
    employee_names = ["Lan", "Minh", "Hà", "Tú"]
    employees = [_agent_from_role(n, ROLES[n]) for n in employee_names]
    return Office(manager=manager, employees=employees)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_office_engine.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add examples/office_engine.py tests/test_office_engine.py
git commit -m "feat(engine): build_office() constructs 5 ReActAgents from env"
```

---

## Task 5: Implement `run_turn()` async generator

**Files:**
- Test: `tests/test_office_engine.py` (append)
- Modify: `examples/office_engine.py`

This is the trickiest task. Approach: bypass actual agent calls by using fake agents that return pre-canned `Msg` objects, then assert event sequence.

- [ ] **Step 1: Append failing test**

Append to `tests/test_office_engine.py`:

```python
from unittest.mock import AsyncMock, MagicMock

from agentscope.message import Msg
from office_engine import run_turn


def _fake_agent(name: str, reply_text: str):
    """Create a mock agent whose __call__ returns a Msg with given text."""
    agent = MagicMock()
    agent.name = name
    agent.__call__ = AsyncMock(
        return_value=Msg(name=name, content=reply_text, role="assistant"),
    )
    # ReActAgent.__call__ is invoked via agent(msg); make the object itself awaitable-callable
    async def _call(msg=None):
        return Msg(name=name, content=reply_text, role="assistant")
    agent.side_effect = None
    agent._call_impl = _call
    return agent


async def test_run_turn_yields_events_for_non_skip_replies(monkeypatch):
    """Manager + 2 employees speak; 2 employees return [skip] and are filtered."""
    # We bypass MsgHub by patching it. The test focuses on the filter+yield logic.
    from office_engine import Office
    import office_engine as oe

    # Build a minimal fake Office with callable agents
    async def manager_call(msg=None):
        return Msg(name="Manager", content="Lan, Minh — bắt tay vào việc.", role="assistant")

    async def lan_call(msg=None):
        return Msg(name="Lan", content="User story đã sẵn sàng.", role="assistant")

    async def minh_call(msg=None):
        return Msg(name="Minh", content="API design here.", role="assistant")

    async def ha_call(msg=None):
        return Msg(name="Hà", content="[skip]", role="assistant")

    async def tu_call(msg=None):
        return Msg(name="Tú", content="[skip]", role="assistant")

    def make_fake(name, fn):
        m = MagicMock(name=name)
        m.name = name
        m.__call__ = AsyncMock(side_effect=fn)
        return m

    manager = make_fake("Manager", manager_call)
    employees = [
        make_fake("Lan", lan_call),
        make_fake("Minh", minh_call),
        make_fake("Hà", ha_call),
        make_fake("Tú", tu_call),
    ]
    office = Office(manager=manager, employees=employees)

    # Patch MsgHub and fanout_pipeline to avoid real broadcast plumbing
    class _StubHub:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def broadcast(self, msg): return None

    async def _stub_fanout(agents):
        return [await a(None) for a in agents]

    monkeypatch.setattr(oe, "MsgHub", _StubHub)
    monkeypatch.setattr(oe, "fanout_pipeline", _stub_fanout)

    events = []
    async for ev in run_turn(office, "Cần API đăng nhập"):
        events.append(ev)

    speakers = [e.speaker for e in events]
    assert "Manager" in speakers
    assert "Lan" in speakers
    assert "Minh" in speakers
    assert "Hà" not in speakers, "[skip] should be filtered"
    assert "Tú" not in speakers, "[skip] should be filtered"
    # Last event for each speaker should have is_final=True
    last_per_speaker = {}
    for ev in events:
        last_per_speaker[ev.speaker] = ev
    for ev in last_per_speaker.values():
        assert ev.is_final, f"{ev.speaker}'s last event must be is_final=True"
```

- [ ] **Step 2: Run to see failure**

Run: `pytest tests/test_office_engine.py::test_run_turn_yields_events_for_non_skip_replies -v`
Expected: FAIL — `cannot import name 'run_turn'`.

- [ ] **Step 3: Append `run_turn()` to `examples/office_engine.py`**

Add imports at top of file (find the existing import section and add):

```python
from collections.abc import AsyncIterator

from agentscope.message import Msg
from agentscope.pipeline import MsgHub, fanout_pipeline
```

Then append:

```python
async def run_turn(office: Office, user_text: str) -> AsyncIterator[TurnEvent]:
    """One conversation turn.

    1. Broadcast user message into hub (auto-flows into every agent memory).
    2. Manager speaks.
    3. Employees speak in parallel via fanout_pipeline.
    4. Yield TurnEvent for each non-[skip] reply.

    Note: streaming token-by-token is not used here for simplicity — each agent's
    full reply is yielded as a single chunk with is_final=True. To enable
    token streaming, replace the manager/employee calls with stream consumers.
    """
    participants = [office.manager, *office.employees]
    user_msg = Msg(name="User", content=user_text, role="user")

    async with MsgHub(participants=participants, enable_auto_broadcast=True) as hub:
        office.hub = hub
        await hub.broadcast(user_msg)

        # Manager
        manager_reply = await office.manager(None)
        if manager_reply.get_text_content().strip() != "[skip]":
            yield TurnEvent(
                speaker=office.manager.name,
                text_chunk=manager_reply.get_text_content(),
                is_final=True,
            )

        # Employees in parallel
        replies = await fanout_pipeline(office.employees)
        for reply in replies:
            text = reply.get_text_content().strip()
            if text == "[skip]":
                continue
            yield TurnEvent(
                speaker=reply.name,
                text_chunk=reply.get_text_content(),
                is_final=True,
            )
```

- [ ] **Step 4: Fix test for the simpler signature (reply.get_text_content)**

The mock returns `Msg` objects which have `.get_text_content()`. Our stub needs to support that. Add helper to test:

In `tests/test_office_engine.py`, modify the fake `Msg` to use real `Msg`. The test already uses `Msg(name=..., content=..., role=...)` which is fine — `Msg.get_text_content()` returns the string content.

- [ ] **Step 5: Run test**

Run: `pytest tests/test_office_engine.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add examples/office_engine.py tests/test_office_engine.py
git commit -m "feat(engine): run_turn yields events, filters [skip] replies"
```

---

## Task 6: Implement CLI entry point `04_virtual_office_cli.py`

**Files:**
- Create: `examples/04_virtual_office_cli.py`

This is presentation code; manual testing only.

- [ ] **Step 1: Create the file**

```python
"""
Ví dụ 04 — Văn phòng ảo (CLI)

Chạy: python examples/04_virtual_office_cli.py
Yêu cầu: 4 employee key + 1 manager key trong .env.
Thoát: gõ `exit` hoặc Ctrl+C.
"""

import asyncio
import sys

from colorama import Fore, Style, init as colorama_init

from office_engine import build_office, run_turn

colorama_init()

COLORS = {
    "Manager": Fore.CYAN,
    "Lan":     Fore.YELLOW,
    "Minh":    Fore.GREEN,
    "Hà":      Fore.MAGENTA,
    "Tú":      Fore.BLUE,
}


def render(event) -> None:
    color = COLORS.get(event.speaker, Fore.WHITE)
    prefix = f"{color}[{event.speaker}]{Style.RESET_ALL} "
    print(f"{prefix}{event.text_chunk}")


def banner(office) -> None:
    print(f"\n{Fore.WHITE}╭─ Văn phòng đã sẵn sàng ─╮{Style.RESET_ALL}")
    print(f"  ✓ {COLORS['Manager']}Manager{Style.RESET_ALL} online")
    for emp in office.employees:
        c = COLORS.get(emp.name, Fore.WHITE)
        print(f"  ✓ {c}{emp.name}{Style.RESET_ALL} online")
    print(f"{Fore.WHITE}╰──────────────────────────╯{Style.RESET_ALL}")
    print("Gõ task của bạn (hoặc `exit`):\n")


async def main() -> None:
    try:
        office = build_office()
    except KeyError as e:
        print(f"Missing env var: {e.args[0]}", file=sys.stderr)
        sys.exit(1)

    banner(office)

    loop = asyncio.get_event_loop()
    while True:
        try:
            user_text = await loop.run_in_executor(None, input, "> ")
        except (EOFError, KeyboardInterrupt):
            print("\nTạm biệt!")
            return

        if user_text.strip().lower() in {"exit", "quit"}:
            print("Tạm biệt!")
            return
        if not user_text.strip():
            continue

        try:
            async for event in run_turn(office, user_text):
                render(event)
        except Exception as e:  # noqa: BLE001
            print(f"{Fore.RED}⚠️ Lỗi: {e}{Style.RESET_ALL}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Manual smoke test (scenarios 1, 2, 3, 6 from spec)**

With `.env` populated and valid keys:

Run: `set PYTHONIOENCODING=utf-8 && python examples/04_virtual_office_cli.py` (Windows cmd)
or: `$env:PYTHONIOENCODING="utf-8"; python examples/04_virtual_office_cli.py` (PowerShell)

Verify:
- Banner shows 5 `✓ … online` lines with colors.
- Type "Cần API đăng nhập với 2FA" → Manager speaks, then ≥ 2 employees speak (Backend should be one).
- Type `exit` → "Tạm biệt!" then clean exit.

Then test missing key:
- Remove `EMPLOYEE_3_KEY` from `.env` temporarily.
- Re-run → expected: `Missing env var: EMPLOYEE_3_KEY` → exit code 1.
- Restore `.env`.

- [ ] **Step 3: Commit**

```bash
git add examples/04_virtual_office_cli.py
git commit -m "feat(cli): add virtual office CLI entry point"
```

---

## Task 7: Implement `web/server.py` (FastAPI + WebSocket)

**Files:**
- Create: `web/__init__.py`
- Create: `web/server.py`

- [ ] **Step 1: Create empty `web/__init__.py`**

Empty file at `web/__init__.py`.

- [ ] **Step 2: Create `web/server.py`**

```python
"""FastAPI app: serves the static UI and one WebSocket per session."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Make examples/ importable as a flat module path (matches pytest.ini pythonpath)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))

from office_engine import build_office, run_turn  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"

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
        office = build_office()
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
```

- [ ] **Step 3: Smoke-import the module**

Run: `python -c "from web.server import app; print('routes:', [r.path for r in app.routes])"`
Expected: prints list containing `/`, `/api/roster`, `/ws`, `/static`.

- [ ] **Step 4: Commit**

```bash
git add web/__init__.py web/server.py
git commit -m "feat(web): FastAPI app + websocket session per connection"
```

---

## Task 8: Web entry point `05_virtual_office_web.py`

**Files:**
- Create: `examples/05_virtual_office_web.py`

- [ ] **Step 1: Create the file**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add examples/05_virtual_office_web.py
git commit -m "feat(web): launcher script that boots uvicorn + opens browser"
```

---

## Task 9: Static HTML — `web/static/index.html`

**Files:**
- Create: `web/static/index.html`

- [ ] **Step 1: Create the file**

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Văn phòng ảo</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <aside id="roster">
    <h1>Văn phòng</h1>
    <ul id="roster-list"></ul>
  </aside>

  <main id="chat">
    <header>
      <h2>#general</h2>
      <span id="conn-status" class="status offline">đang kết nối...</span>
    </header>
    <section id="feed" aria-live="polite"></section>
    <form id="input-form">
      <input
        id="input"
        type="text"
        placeholder="Mô tả việc cần làm, ví dụ: 'Thiết kế API đăng nhập 2FA'..."
        autocomplete="off"
        autofocus
      />
      <button type="submit">Gửi</button>
    </form>
  </main>

  <script type="module" src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add web/static/index.html
git commit -m "feat(web): static index.html with sidebar + chat layout"
```

---

## Task 10: Static CSS — `web/static/style.css`

**Files:**
- Create: `web/static/style.css`

- [ ] **Step 1: Create the file**

```css
:root {
  --bg: #1e1f22;
  --surface: #2b2d31;
  --surface-2: #313338;
  --text: #dbdee1;
  --muted: #949ba4;
  --accent: #5865f2;
  --green: #2ecc71;
  --red: #ed4245;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  display: flex;
  height: 100vh;
  overflow: hidden;
}

#roster {
  width: 240px;
  background: var(--surface);
  padding: 16px;
  border-right: 1px solid #1a1b1e;
  overflow-y: auto;
}

#roster h1 {
  font-size: 14px;
  text-transform: uppercase;
  color: var(--muted);
  letter-spacing: 1px;
  margin: 0 0 12px;
}

#roster-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

#roster-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 6px;
  margin-bottom: 4px;
}

#roster-list li:hover { background: var(--surface-2); }

.avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-weight: 600; color: white;
  font-size: 13px;
}

.name { font-weight: 500; }
.title { font-size: 12px; color: var(--muted); display: block; }

#chat {
  flex: 1;
  display: flex;
  flex-direction: column;
}

#chat > header {
  padding: 14px 20px;
  background: var(--surface);
  border-bottom: 1px solid #1a1b1e;
  display: flex; justify-content: space-between; align-items: center;
}

#chat > header h2 { margin: 0; font-size: 16px; }

.status { font-size: 12px; }
.status.online::before  { content: "●"; color: var(--green); margin-right: 4px; }
.status.offline::before { content: "●"; color: var(--red);   margin-right: 4px; }

#feed {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.msg {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.msg .body {
  background: var(--surface);
  padding: 8px 12px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-width: 70%;
}

.msg .body .who {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
}

#input-form {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #1a1b1e;
  background: var(--surface);
}

#input {
  flex: 1;
  background: var(--surface-2);
  border: none;
  color: var(--text);
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
}

#input:focus { outline: 2px solid var(--accent); }

#input-form button {
  background: var(--accent);
  color: white;
  border: none;
  padding: 0 16px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
}

#input-form button:hover { filter: brightness(1.1); }
```

- [ ] **Step 2: Commit**

```bash
git add web/static/style.css
git commit -m "feat(web): dark theme styling (Slack/Discord-ish)"
```

---

## Task 11: Static JS — `web/static/app.js`

**Files:**
- Create: `web/static/app.js`

- [ ] **Step 1: Create the file**

```javascript
// Văn phòng ảo — client logic

const rosterList = document.getElementById("roster-list");
const feed = document.getElementById("feed");
const form = document.getElementById("input-form");
const input = document.getElementById("input");
const status = document.getElementById("conn-status");

let socket = null;
let roster = [];
const colorByName = new Map();

async function loadRoster() {
  const res = await fetch("/api/roster");
  const data = await res.json();
  roster = data.members;
  for (const m of roster) colorByName.set(m.name, m.color);

  rosterList.innerHTML = "";
  for (const m of roster) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="avatar" style="background:${m.color}">${m.name[0]}</div>
      <div>
        <span class="name">${m.name}</span>
        <span class="title">${m.title}</span>
      </div>
    `;
    rosterList.appendChild(li);
  }
}

function setStatus(connected) {
  status.textContent = connected ? "online" : "offline";
  status.className = "status " + (connected ? "online" : "offline");
}

function makeBubble(speaker) {
  const color = colorByName.get(speaker) || "#888";
  const wrapper = document.createElement("div");
  wrapper.className = "msg";
  wrapper.innerHTML = `
    <div class="avatar" style="background:${color}">${speaker[0]}</div>
    <div class="body">
      <div class="who" style="color:${color}">${speaker}</div>
      <div class="text"></div>
    </div>
  `;
  feed.appendChild(wrapper);
  feed.scrollTop = feed.scrollHeight;
  return wrapper.querySelector(".text");
}

// Track the currently-growing bubble per speaker so chunk events append correctly
let currentBubble = null;
let currentSpeaker = null;

function handleEvent(ev) {
  if (ev.error) {
    appendSystem(`⚠️ ${ev.error}`);
    return;
  }
  if (ev.turn_complete) {
    currentBubble = null;
    currentSpeaker = null;
    return;
  }
  if (ev.speaker !== currentSpeaker) {
    currentSpeaker = ev.speaker;
    currentBubble = makeBubble(ev.speaker);
  }
  currentBubble.textContent += ev.text;
  feed.scrollTop = feed.scrollHeight;

  if (ev.final) {
    currentBubble = null;
    currentSpeaker = null;
  }
}

function appendSystem(text) {
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `<div class="body"><div class="text" style="color:#ed4245">${text}</div></div>`;
  feed.appendChild(div);
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws`);
  socket.onopen  = () => setStatus(true);
  socket.onclose = () => { setStatus(false); setTimeout(connect, 1500); };
  socket.onmessage = (e) => handleEvent(JSON.parse(e.data));
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || !socket || socket.readyState !== WebSocket.OPEN) return;
  appendUserMsg(text);
  socket.send(JSON.stringify({ text }));
  input.value = "";
});

function appendUserMsg(text) {
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `
    <div class="avatar" style="background:#7289da">U</div>
    <div class="body">
      <div class="who" style="color:#7289da">Bạn</div>
      <div class="text"></div>
    </div>
  `;
  div.querySelector(".text").textContent = text;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

(async () => {
  await loadRoster();
  connect();
})();
```

- [ ] **Step 2: Smoke-test the full web stack**

Run: `python examples/05_virtual_office_web.py`

Expected:
- Browser opens to `http://localhost:8000`.
- Sidebar shows 5 members with colored avatars.
- Status pill turns green ("online") within 1s.
- Type "Cần design API đăng nhập" → submit.
- Bubbles appear for Manager + at least 2 employees, each with its own color.
- Ctrl+C in terminal → server stops cleanly.

- [ ] **Step 3: Commit**

```bash
git add web/static/app.js
git commit -m "feat(web): websocket client + chat rendering"
```

---

## Task 12: Update `.env.example` and `README.md`

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Replace `.env.example`**

```env
# Copy file này thành .env rồi điền API key thật của bạn.
# (file .env đã được .gitignore — đừng commit secret)

# === Fallback (Examples 1-3 cũ, Manager tạm thời) ===
ANTHROPIC_AWS_API_KEY=AEAAA...
ANTHROPIC_AWS_WORKSPACE_ID=wrkspc_xxx
ANTHROPIC_AWS_BASE_URL=https://aws-external-anthropic.<region>.api.aws

# === 4 nhân viên (Example 4 & 5) ===
EMPLOYEE_1_KEY=...           # PM (Lan)
EMPLOYEE_1_WORKSPACE=wrkspc_xxx
EMPLOYEE_1_BASE_URL=https://aws-external-anthropic.<region>.api.aws

EMPLOYEE_2_KEY=...           # Backend (Minh)
EMPLOYEE_2_WORKSPACE=wrkspc_xxx
EMPLOYEE_2_BASE_URL=https://aws-external-anthropic.<region>.api.aws

EMPLOYEE_3_KEY=...           # Frontend (Hà)
EMPLOYEE_3_WORKSPACE=wrkspc_xxx
EMPLOYEE_3_BASE_URL=https://aws-external-anthropic.<region>.api.aws

EMPLOYEE_4_KEY=...           # QA (Tú) — lưu ý region khác
EMPLOYEE_4_WORKSPACE=wrkspc_xxx
EMPLOYEE_4_BASE_URL=https://aws-external-anthropic.<region>.api.aws

# === Manager (Example 4 & 5) ===
# Có thể trỏ vào fallback ở trên hoặc dùng key thứ 5 riêng
MANAGER_KEY=${ANTHROPIC_AWS_API_KEY}
MANAGER_WORKSPACE=${ANTHROPIC_AWS_WORKSPACE_ID}
MANAGER_BASE_URL=${ANTHROPIC_AWS_BASE_URL}
```

- [ ] **Step 2: Append to `README.md`**

Append the following section before the `## Tham khảo` heading:

```markdown
## Ví dụ 4 & 5 — Văn phòng ảo

Phòng chat đa-agent: 1 Manager phân việc cho 4 nhân viên (PM, Backend, Frontend, QA).
Tất cả ở chung "open office" (MsgHub), có thể chen phản biện chéo.

### Cấu hình
Sao chép `.env.example` → `.env`, điền 5 nhóm key (xem comment trong file).

### Chạy CLI (Ví dụ 4)
```powershell
$env:PYTHONIOENCODING="utf-8"
python examples/04_virtual_office_cli.py
```

### Chạy Web UI (Ví dụ 5)
```powershell
python examples/05_virtual_office_web.py
```
Trình duyệt sẽ tự mở http://localhost:8000. UI dark theme, sidebar trái liệt kê
5 thành viên, feed chính ở giữa, ô nhập ở dưới. Mỗi tab browser là 1 phiên
văn phòng độc lập (không chia sẻ memory).

### Test thủ công
Xem `docs/superpowers/specs/2026-05-20-virtual-office-design.md` Section 9
cho danh sách 10 scenario.

### Test tự động
```bash
pytest tests/test_office_engine.py -v
```
```

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: update env example + README for virtual office examples"
```

---

## Task 13: Run all 10 manual scenarios from spec Section 9

**Files:** none

This task is purely verification. **Do not skip.**

- [ ] **Step 1: Run automated tests**

Run: `pytest tests/test_office_engine.py -v`
Expected: 9 passed, 0 failed.

- [ ] **Step 2: Scenario 1 — CLI happy startup**

```powershell
$env:PYTHONIOENCODING="utf-8"
python examples/04_virtual_office_cli.py
```
Expected: banner + 5 `✓ <Name> online` lines, prompt `>` appears.

- [ ] **Step 3: Scenario 2 — missing env**

Temporarily remove `EMPLOYEE_3_KEY` from `.env`, re-run CLI.
Expected: `Missing env var: EMPLOYEE_3_KEY`, exit 1. Restore `.env`.

- [ ] **Step 4: Scenario 3 — API task**

In CLI, type: `Cần API đăng nhập với 2FA`
Expected: Manager assigns ≥ 2 employees; Minh (Backend) gives detailed reply.

- [ ] **Step 5: Scenario 4 — QA-only task**

Type: `Viết test plan cho module thanh toán`
Expected: Manager addresses Tú; the other 3 reply `[skip]` (not shown).

- [ ] **Step 6: Scenario 5 — controversial task**

Type: `Lưu mật khẩu plaintext cho dễ debug`
Expected: At least one of Tú/Minh chen ngang phản đối, even if not directly addressed.

- [ ] **Step 7: Scenario 6 — exit**

Type: `exit`
Expected: prints "Tạm biệt!", returns to shell, no stacktrace.

- [ ] **Step 8: Scenario 7 — web auto-open**

```powershell
python examples/05_virtual_office_web.py
```
Expected: browser opens to localhost:8000, sidebar has 5 colored members, status pill green.

- [ ] **Step 9: Scenario 8 — web chat**

In browser: type a task → submit.
Expected: bubbles appear for Manager + employees with their respective colors.

- [ ] **Step 10: Scenario 9 — WS disconnect resilience**

Stop the server (Ctrl+C), restart, keep browser open.
Expected: status pill auto-reconnects to green within ~1.5s; new submits work.

- [ ] **Step 11: Scenario 10 — two tabs**

Open second browser tab to localhost:8000. Submit different task in each.
Expected: each tab shows only its own conversation (separate Office instances per WS).

- [ ] **Step 12: If any scenario fails**

Capture the failure (stack trace or unexpected output) and fix at the relevant task's file. Re-run that scenario only. Repeat until all 10 pass.

- [ ] **Step 13: Final commit (if any fixes were made)**

```bash
git add -A
git commit -m "fix: address issues found during scenario verification"
```

---

## Self-Review (already done by author)

- ✅ Spec coverage: all 11 spec sections mapped to tasks (Section 4.1→T2, 4.2→T3-5, 4.3→T6, 4.4→T8, 4.5→T7, 4.6→T9-11, Section 6→T12, Section 8→T6/T7 error blocks, Section 9→T13, Section 10→T13).
- ✅ No placeholders ("TBD", "TODO", "implement later") — every code step includes full code.
- ✅ Type consistency: `TurnEvent.text_chunk` used uniformly; `Office.manager`/`Office.employees` consistent across T4/T5/T6/T7.
- ✅ `make_model` signature consistent T2→T4 (api_key, workspace_id, base_url + kwonly model_name/stream).
