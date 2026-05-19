"""Virtual office engine — orchestration of Manager + 4 employees.

Architecture: a single MsgHub broadcasts among 5 ReActAgents. Employees own
a per-agent `save_deliverable` tool that writes files under
workspace_dir/<Name>/. After each turn, an iterative pytest loop verifies the
generated Python code against the generated tests.

Public API (re-exported by voffice/__init__.py):
  build_office(workspace_dir) -> Office
  run_turn(office, user_text)  -> async generator of TurnEvent
  ship_workspace(office, name) -> ShipReport
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.formatter import AnthropicMultiAgentFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg, TextBlock
from agentscope.pipeline import MsgHub, fanout_pipeline
from agentscope.tool import Toolkit, ToolResponse, view_text_file

from voffice.model import make_model


# ─── Data types ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RoleSpec:
    title: str
    sys_prompt: str
    env_prefix: str  # MANAGER → MANAGER_KEY / _WORKSPACE / _BASE_URL


@dataclass
class TurnEvent:
    speaker: str
    text_chunk: str  # delta — NOT cumulative
    is_final: bool


@dataclass
class Office:
    manager: ReActAgent
    employees: list[ReActAgent]
    workspace_dir: Path
    deliverables: list[Path] = field(default_factory=list)
    turns_history: list[str] = field(default_factory=list)
    hub: MsgHub | None = None


@dataclass
class ShipReport:
    project_dir: Path
    files_copied: int
    file_tree: list[str]
    commit_sha: str


# ─── Roles & system prompts ───────────────────────────────────────────────


_EMPLOYEE_TEMPLATE = """\
You are {name}, the {title} of a software office.

REAL WORK (NOT just talking):
- When the Manager assigns you a task, you MUST create a real deliverable file
  using the tool `save_deliverable(filename, content)`. Examples:
    • PM       → user_story.md, requirements.md
    • Backend  → api_spec.md, auth_handler.py (RUNNABLE code; avoid exotic
                  imports outside flask/sqlalchemy/pytest)
    • Frontend → mockup.html, components.md
    • QA       → test_plan.md, test_<module>.py (real pytest, importing the
                 Backend file by name, e.g. `from login_api import validate_email`)
- File content must be usable, not placeholder.
- After saving, reply briefly confirming what file you created.

QA LOOP (relevant to Backend & QA):
- After Backend saves code + QA saves tests, the system AUTOMATICALLY runs pytest.
- If it fails, the full traceback is broadcast to everyone.
- Backend: READ the traceback, fix the code, save again WITH THE SAME filename
  (overwrite).
- QA: if your test was wrong, fix it and save again.
- The loop runs up to 3 iterations.

IMPORTANT: YOU MUST ACT, NOT SKIP, IF YOUR NAME APPEARS IN THE MANAGER'S MESSAGE.
- Manager listing your name (even in a bullet list) = you are assigned.
- Assigned → you MUST call save_deliverable, never [skip].
- Only [skip] if: Manager did NOT mention you at all AND you have no critique.

IF CRITIQUING (no deliverable):
- Inject a short 1-2 sentence technical objection; no need to save anything.

Reply in the user's language, from your professional perspective as a {title}.
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
            "You are the Manager of a 4-person software office: "
            "Lan (PM), Minh (Backend), Hà (Frontend), Tú (QA). "
            "When the user posts a task:\n"
            "  1. Analyze the request.\n"
            "  2. Assign SPECIFIC work to each relevant person, naming them.\n"
            "     Tell them to CREATE A DELIVERABLE FILE (Lan→user_story.md, "
            "Minh→api code, Hà→mockup, Tú→test_plan.md or test_*.py...).\n"
            "  3. Do not do the work yourself — only coordinate.\n"
            "Reply briefly (2-5 sentences), in the user's language."
        ),
        env_prefix="MANAGER",
    ),
    "Lan":  _emp("Lan",  "Product Manager",    "EMPLOYEE_1"),
    "Minh": _emp("Minh", "Backend Developer",  "EMPLOYEE_2"),
    "Hà":   _emp("Hà",   "Frontend Developer", "EMPLOYEE_3"),
    "Tú":   _emp("Tú",   "QA Tester",          "EMPLOYEE_4"),
}


# ─── Per-agent save tool ──────────────────────────────────────────────────


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.\-]")


def _sanitize_filename(name: str) -> str:
    base = Path(name).name  # drops any directory part
    return _SAFE_NAME.sub("_", base) or "untitled.txt"


def _make_save_tool(agent_name: str, office: Office):
    """Bind a save_deliverable function to (agent_name, office)."""
    def save_deliverable(filename: str, content: str) -> ToolResponse:
        """Save a real deliverable file into the workspace.

        Call this whenever the Manager assigns you a concrete task.
        Returns confirmation of the absolute path written.

        Args:
            filename: file name only (no path), e.g. "user_story.md", "auth.py".
            content: full file contents (markdown, code, anything).
        """
        safe = _sanitize_filename(filename)
        out_dir = office.workspace_dir / agent_name
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / safe
        path.write_text(content, encoding="utf-8")
        office.deliverables.append(path)
        return ToolResponse(
            content=[TextBlock(type="text", text=f"✓ Saved: {path}")],
        )
    save_deliverable.__name__ = "save_deliverable"
    return save_deliverable


# ─── Build & run ──────────────────────────────────────────────────────────


def _agent_from_role(
    name: str,
    spec: RoleSpec,
    *,
    toolkit: Toolkit | None = None,
    max_iters: int = 1,
) -> ReActAgent:
    api_key = os.environ[f"{spec.env_prefix}_KEY"]
    workspace_id = os.environ[f"{spec.env_prefix}_WORKSPACE"]
    base_url = os.environ[f"{spec.env_prefix}_BASE_URL"]
    return ReActAgent(
        name=name,
        sys_prompt=spec.sys_prompt,
        model=make_model(api_key=api_key, workspace_id=workspace_id, base_url=base_url),
        formatter=AnthropicMultiAgentFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
        max_iters=max_iters,
    )


def build_office(workspace_dir: Path) -> Office:
    """Build the office. Manager has no tools; each employee has save_deliverable + view_text_file."""
    workspace_dir = Path(workspace_dir).resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    office = Office(
        manager=None,  # type: ignore[arg-type] — assigned just below
        employees=[],
        workspace_dir=workspace_dir,
    )
    office.manager = _agent_from_role("Manager", ROLES["Manager"], max_iters=1)

    for name in ["Lan", "Minh", "Hà", "Tú"]:
        toolkit = Toolkit()
        toolkit.register_tool_function(_make_save_tool(name, office))
        toolkit.register_tool_function(view_text_file)
        agent = _agent_from_role(name, ROLES[name], toolkit=toolkit, max_iters=4)
        office.employees.append(agent)

    return office


# ─── Pytest verification loop ─────────────────────────────────────────────


MAX_VERIFY_ITERS = 3
PYTEST_TIMEOUT_SEC = 60


async def _run_pytest_in(verify_dir: Path) -> tuple[bool, str]:
    """Run pytest in verify_dir and return (passed, output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest", "-x", "--tb=short", "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(verify_dir),
        )
        stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=PYTEST_TIMEOUT_SEC)
        output = stdout_bytes.decode("utf-8", errors="replace")
        return proc.returncode == 0, output
    except asyncio.TimeoutError:
        return False, f"⏱️ pytest timed out after {PYTEST_TIMEOUT_SEC}s"


def _gather_python_files(directory: Path, test_only: bool) -> list[Path]:
    if not directory.exists():
        return []
    files = []
    for p in directory.glob("*.py"):
        is_test = p.name.startswith("test_") or p.name.endswith("_test.py")
        if test_only == is_test:
            files.append(p)
    return files


def _prepare_verify_dir(office: Office) -> Path | None:
    """Copy Backend code + QA tests into a flat verify dir, or None if N/A."""
    backend_dir = office.workspace_dir / "Minh"
    qa_dir = office.workspace_dir / "Tú"

    code_files = _gather_python_files(backend_dir, test_only=False)
    test_files = _gather_python_files(qa_dir, test_only=True)

    if not code_files or not test_files:
        return None

    verify_dir = office.workspace_dir / ".verify"
    if verify_dir.exists():
        shutil.rmtree(verify_dir)
    verify_dir.mkdir(parents=True)

    for f in code_files + test_files:
        shutil.copy2(f, verify_dir / f.name)
    return verify_dir


async def run_turn(office: Office, user_text: str) -> AsyncIterator[TurnEvent]:
    """One conversation turn with optional QA verification loop."""
    participants = [office.manager, *office.employees]
    user_msg = Msg(name="User", content=user_text, role="user")
    office.turns_history.append(user_text)

    deliverables_before = len(office.deliverables)
    backend = office.employees[1]  # Minh = index 1

    async with MsgHub(participants=participants, enable_auto_broadcast=True) as hub:
        office.hub = hub
        await hub.broadcast(user_msg)

        manager_reply = await office.manager(None)
        if manager_reply.get_text_content().strip() != "[skip]":
            yield TurnEvent(office.manager.name, manager_reply.get_text_content(), True)

        replies = await fanout_pipeline(office.employees)
        for reply in replies:
            text = reply.get_text_content().strip()
            if text == "[skip]":
                continue
            yield TurnEvent(reply.name, reply.get_text_content(), True)

        verify_dir = _prepare_verify_dir(office)
        if verify_dir is not None:
            yield TurnEvent("Office", f"🧪 Starting QA loop in {verify_dir.name}/ ...", True)

            for iteration in range(1, MAX_VERIFY_ITERS + 1):
                passed, output = await _run_pytest_in(verify_dir)
                tail = output[-1500:]

                if passed:
                    yield TurnEvent("QA-Bot", f"✅ Tests pass (iter {iteration})\n{tail[-400:]}", True)
                    break

                yield TurnEvent("QA-Bot", f"❌ Tests fail (iter {iteration}/{MAX_VERIFY_ITERS}):\n{tail}", True)

                if iteration == MAX_VERIFY_ITERS:
                    yield TurnEvent(
                        "Office",
                        f"⚠️ Still failing after {MAX_VERIFY_ITERS} iterations — manual intervention required.",
                        True,
                    )
                    break

                err_msg = Msg(
                    name="QA-Bot",
                    content=(
                        f"Pytest failed. Output:\n{tail}\n\n"
                        "Minh, fix the code and save again WITH THE SAME filename. "
                        "Tú, if the test is wrong, fix the test."
                    ),
                    role="user",
                )
                await hub.broadcast(err_msg)

                fix_reply = await backend(None)
                if fix_reply.get_text_content().strip() != "[skip]":
                    yield TurnEvent(backend.name, fix_reply.get_text_content(), True)

                for f in _gather_python_files(office.workspace_dir / "Minh", test_only=False):
                    shutil.copy2(f, verify_dir / f.name)

    new_files = office.deliverables[deliverables_before:]
    if new_files:
        listing = "\n".join(f"  • {p.relative_to(office.workspace_dir)}" for p in new_files)
        yield TurnEvent("Office", f"📁 Deliverables created:\n{listing}", True)


# ─── Ship: consolidate workspace into a runnable git project ──────────────


_LAYOUT: dict[str, str] = {
    ".md":   "docs",
    ".txt":  "docs",
    ".py":   "backend",
    ".sql":  "backend/db",
    ".html": "frontend",
    ".htm":  "frontend",
    ".js":   "frontend",
    ".jsx":  "frontend",
    ".ts":   "frontend",
    ".tsx":  "frontend",
    ".css":  "frontend",
    ".scss": "frontend",
    ".json": "config",
    ".yml":  "config",
    ".yaml": "config",
    ".env":  "config",
    ".fig":  "design",
    ".svg":  "design",
    ".png":  "design",
    ".jpg":  "design",
}


def _route_file(ext: str) -> str:
    return _LAYOUT.get(ext.lower(), "misc")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return s or "project"


def _generate_readme(project_dir: Path, project_name: str, history: list[str], files: list[Path]) -> None:
    by_dir: dict[str, list[str]] = {}
    for f in files:
        rel = f.relative_to(project_dir)
        by_dir.setdefault(rel.parts[0], []).append(rel.as_posix())

    sections = []
    for d, paths in sorted(by_dir.items()):
        lines = "\n".join(f"- `{p}`" for p in sorted(paths))
        sections.append(f"### `{d}/`\n{lines}")

    history_section = "\n".join(f"{i+1}. {h}" for i, h in enumerate(history)) or "_(none)_"

    content = f"""# {project_name}

> Generated by **voffice** (Virtual Office) on {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Original prompts
{history_section}

## Structure

{chr(10).join(sections) if sections else "_(empty)_"}

## How to run

> ⚠️ This is auto-generated code — may need tweaks before production.

- **Backend (Python):** `cd backend && pip install -r requirements.txt && python <file>.py`
- **Frontend:** open `frontend/*.html` in a browser, or bundle with vite/webpack.
- **Tests:** see `docs/*test*.md` for the manual test plan.

## Provenance
Generated by https://github.com/your-user/voffice
"""
    (project_dir / "README.md").write_text(content, encoding="utf-8")


def _generate_gitignore(project_dir: Path) -> None:
    (project_dir / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.venv/\nnode_modules/\n.env\n.DS_Store\n*.log\n",
        encoding="utf-8",
    )


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def ship_workspace(office: Office, project_name: str) -> ShipReport:
    """Consolidate every deliverable in workspace → standard project + git init + commit local."""
    slug = _slugify(project_name)
    projects_root = office.workspace_dir.parent / "projects"
    project_dir = projects_root / slug
    if project_dir.exists():
        project_dir = projects_root / f"{slug}-{datetime.now().strftime('%H%M%S')}"
    project_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for nv_dir in office.workspace_dir.iterdir():
        if not nv_dir.is_dir():
            continue
        for src in nv_dir.iterdir():
            if not src.is_file():
                continue
            target_subdir = project_dir / _route_file(src.suffix)
            target_subdir.mkdir(parents=True, exist_ok=True)
            dst = target_subdir / src.name
            shutil.copy2(src, dst)
            copied.append(dst)

    _generate_readme(project_dir, project_name, office.turns_history, copied)
    _generate_gitignore(project_dir)

    _run_git(["init", "-b", "main"], cwd=project_dir)
    _run_git(["config", "user.name", "Virtual Office"], cwd=project_dir)
    _run_git(["config", "user.email", "office@local"], cwd=project_dir)
    _run_git(["add", "-A"], cwd=project_dir)
    _run_git(
        ["commit", "-m",
         f"Initial commit: {project_name}\n\n"
         f"Generated by voffice from {len(office.turns_history)} turn(s)."],
        cwd=project_dir,
    )
    sha = _run_git(["rev-parse", "--short", "HEAD"], cwd=project_dir)

    tree = sorted(str(p.relative_to(project_dir)) for p in project_dir.rglob("*") if p.is_file())
    return ShipReport(project_dir=project_dir, files_copied=len(copied), file_tree=tree, commit_sha=sha)
