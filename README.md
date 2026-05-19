# 🏢 voffice — Virtual Office

> **One prompt → a runnable git project.**
> A multi-agent virtual software team (Manager + PM + Backend + Frontend + QA) that produces real files, runs `pytest` to verify, and packages the result as a git repo.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Built on AgentScope](https://img.shields.io/badge/built%20on-AgentScope-orange.svg)](https://github.com/agentscope-ai/agentscope)

🇻🇳 **Tiếng Việt:** [README.vi.md](README.vi.md)

---

## Why this exists

Most multi-agent frameworks output **conversations**. voffice outputs **artifacts**: a directory of working files plus a git history. You can `cd` into the result and `python backend/server.py`.

```
> Build a BMI calculator module with Python + pytest

[Manager] Lan, write user story. Minh, implement bmi.py. Tú, write test_bmi.py.
[Minh]    ✓ Saved: workspace/Minh/bmi.py
[Tú]      ✓ Saved: workspace/Tú/test_bmi.py
[Office]  🧪 Starting QA loop...
[QA-Bot]  ✅ Tests pass (iter 1) — 15 passed in 0.03s

> /ship bmi-calculator
✓ Shipped → projects/bmi-calculator
  4 files copied, commit a3f9c12
    .gitignore
    README.md
    backend/bmi.py
    docs/test_bmi.py  ← wait, tests go to docs? no — to backend/
```

## Killer features

| | Most agent frameworks | **voffice** |
|---|---|---|
| Output | text conversation | **runnable git repo** |
| Verification | none | **iterative pytest loop** (auto-fix on fail) |
| Multi-agent UI | none | **Slack-style web UI** + CLI |
| Packaging | manual | **`/ship <name>`** → git init + commit |
| Tool-use safety | full subprocess | **sandboxed file writes per agent** |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              You type a task in CLI or Web UI           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   MsgHub (auto-broadcast)     │
         │  ┌─────────────────────────┐  │
         │  │   Manager (coordinator) │  │
         │  ├─────────────────────────┤  │
         │  │ Lan (PM)  │ Minh (BE)   │  │
         │  │ Hà (FE)   │ Tú (QA)     │  │
         │  └─────────────────────────┘  │
         └────────────┬──────────────────┘
                      │ fanout — each writes files via
                      │ save_deliverable(filename, content)
                      ▼
              ┌───────────────────┐
              │  workspace/       │
              │   ├─ Lan/         │
              │   ├─ Minh/        │
              │   ├─ Hà/          │
              │   └─ Tú/          │
              └─────────┬─────────┘
                        │
                        ▼  (if .py + test_*.py exist)
              ┌───────────────────┐
              │  .verify/         │  ←─┐ Python deterministic
              │   $ pytest -x     │    │ subprocess.
              └───────────┬───────┘    │ Loop ≤ 3 iters:
                          │            │ ❌ fail → broadcast
                          ▼            │ Minh fixes → re-test
                       ✅ pass ────────┘
                          │
                          ▼  (when you type /ship <name>)
              ┌───────────────────┐
              │  projects/<name>/ │
              │   ├─ backend/     │   ← .py routed here
              │   ├─ frontend/    │   ← .html/.css/.js
              │   ├─ docs/        │   ← .md
              │   ├─ README.md    │   (auto-generated)
              │   └─ .git/        │   (commit ready)
              └───────────────────┘
```

## Quick start

```bash
git clone https://github.com/ThangBaymau123/voffice
cd voffice
pip install -e .

# Set up env (one API key per "employee"):
cp .env.example .env
$EDITOR .env

# CLI
voffice

# OR Web UI (http://localhost:8000)
voffice web
```

You need **5 Anthropic API keys** (one per agent role). Why? Each agent has its own quota, latency, and "personality" via separate workspace. You can point all five at the same key for testing — the code splits them per `MANAGER_KEY`, `EMPLOYEE_1_KEY`, etc.

`.env` shape — see [`.env.example`](.env.example).

## Usage

### CLI commands

| Command | What it does |
|---|---|
| (any text) | Send a task to the office |
| `/ship <name>` | Consolidate workspace into `projects/<name>/` with git init + commit |
| `exit` / `quit` | Leave the office |

### Programmatic API

```python
import asyncio
from pathlib import Path
from voffice import build_office, run_turn, ship_workspace

async def main():
    office = build_office(Path("./workspace"))
    async for event in run_turn(office, "Build a TODO REST API with Flask + SQLite"):
        print(f"[{event.speaker}] {event.text_chunk}")

    report = ship_workspace(office, "todo-api")
    print(f"Git repo ready at {report.project_dir}, commit {report.commit_sha}")

asyncio.run(main())
```

## How the QA loop works

The trickiest piece — and the most important for trust:

1. After fanout, voffice scans `workspace/Minh/*.py` (code) and `workspace/Tú/test_*.py` (tests).
2. If both exist, it copies them flat into `workspace/.verify/`.
3. It runs `python -m pytest -x --tb=short` in that directory **as a subprocess** (not via LLM tool calls — fully deterministic).
4. If pytest fails: voffice broadcasts the traceback into the hub. The Backend agent reads its memory, sees the failure, and saves a fixed version.
5. New code is re-copied to `.verify/` and pytest re-runs.
6. Loop until pass or `MAX_VERIFY_ITERS=3`.

LLMs do creative work (code, tests). Plain Python does verification. The combo is cheap and reliable.

## Project structure

```
voffice/
├── voffice/
│   ├── __init__.py       # public API
│   ├── model.py          # Anthropic model factory (AWS gateway or direct)
│   ├── engine.py         # roles, build_office, run_turn, ship_workspace, QA loop
│   ├── cli.py            # `voffice` CLI command
│   ├── server.py         # FastAPI + WebSocket
│   ├── launcher.py       # `voffice web` uvicorn launcher
│   └── static/           # index.html, style.css, app.js (dark Slack-style UI)
├── tests/                # pytest — model, roles, build_office, run_turn filter
├── examples/             # demo scripts using raw AgentScope (no voffice import)
├── docs/                 # design spec + implementation plan (in Vietnamese)
├── pyproject.toml
└── LICENSE
```

## Comparison with similar projects

| | [CrewAI](https://github.com/joaomdmoura/crewAI) | [AutoGen](https://github.com/microsoft/autogen) | [MetaGPT](https://github.com/geekan/MetaGPT) | **voffice** |
|---|---|---|---|---|
| Type | Framework | Framework | Product | **Product** |
| Output format | Strings | Strings | Files | **Files + git history** |
| Auto verification | ❌ | partial | partial | **✅ pytest loop** |
| Web UI included | ❌ | ❌ | CLI only | **✅ Slack-like** |
| Lines of code | ~10k | ~30k | ~20k | **~700** |
| One-prompt-to-repo | ❌ | ❌ | partial | **✅** |

(See [docs/](docs/) for design notes.)

## Security notes

- **Subprocess pytest** runs untrusted code generated by an LLM. We restrict to a `.verify/` directory but the code can still call `os.system`, `requests.get(...)`, etc. **Do not run on an unsegmented production machine.** For untrusted use, run inside Docker / a sandboxed VM.
- The `save_deliverable` tool sanitizes filenames (no path traversal) and routes to per-agent subdirs.
- API keys come from `.env`; rotate any key you've shared in chat logs.

## Roadmap

- [x] Iterative pytest QA loop
- [x] `/ship` → git project with layout
- [x] CLI + Slack-style Web UI
- [ ] **PyPI** package — `pipx install voffice`
- [ ] **Office packs** — content team, research team, indie-game team (community PRs welcome)
- [ ] **`/deploy`** — auto Vercel / Fly / GitHub
- [ ] **Ollama** fallback for keyless local mode
- [ ] **Token cost meter** per turn

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

The fastest way to help: open `voffice/engine.py`, find `ROLES`, add a new office pack (e.g., `ROLES_CONTENT_OFFICE`), and submit a PR.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- Built on [AgentScope](https://github.com/agentscope-ai/agentscope) (Alibaba Tongyi Lab).
- Uses [Anthropic Claude](https://www.anthropic.com/claude) — feels like having a senior eng pair-program with you.
