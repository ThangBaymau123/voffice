"""voffice CLI — entry point for `voffice` command.

Usage:
  voffice           # interactive REPL
  voffice web       # launch FastAPI web UI on http://localhost:8000
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Direct invocation (`python voffice/cli.py`) leaves the project root off
# sys.path. Insert it so `from voffice.engine import ...` resolves before
# the package is pip-installed.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from colorama import Fore, Style, init as colorama_init

from voffice.engine import Office, build_office, run_turn, ship_workspace

# Windows consoles default to cp1252, which crashes on Vietnamese agent names
# (Hà, Tú, Đ...) streamed by the model. Force UTF-8 before colorama wraps stdout.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

colorama_init()

COLORS = {
    "Manager": Fore.CYAN,
    "Lan":     Fore.YELLOW,
    "Minh":    Fore.GREEN,
    "Hà":      Fore.MAGENTA,
    "Tú":      Fore.BLUE,
    "QA-Bot":  Fore.RED,
    "Office":  Fore.WHITE,
}

DEFAULT_WORKSPACE = Path.cwd() / "workspace"


def _render(event) -> None:
    color = COLORS.get(event.speaker, Fore.WHITE)
    prefix = f"{color}[{event.speaker}]{Style.RESET_ALL} "
    print(f"{prefix}{event.text_chunk}")


def _banner(office: Office) -> None:
    print(f"\n{Fore.WHITE}╭─ Virtual Office ready ──╮{Style.RESET_ALL}")
    print(f"  📁 workspace: {office.workspace_dir}")
    print(f"  ✓ {COLORS['Manager']}Manager{Style.RESET_ALL}")
    for emp in office.employees:
        c = COLORS.get(emp.name, Fore.WHITE)
        print(f"  ✓ {c}{emp.name}{Style.RESET_ALL} (has save_deliverable)")
    print(f"{Fore.WHITE}╰─────────────────────────╯{Style.RESET_ALL}")
    print("Type a task. `/ship <name>` to package + git commit. `exit` to quit.\n")


def _ask_workspace() -> Path:
    print(f"{Fore.WHITE}Workspace directory?{Style.RESET_ALL}")
    print(f"  (Enter for default: {DEFAULT_WORKSPACE})")
    raw = input("workspace> ").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_WORKSPACE


def _handle_ship(office: Office, raw: str) -> None:
    name = raw[len("/ship"):].strip()
    if not name:
        print(f"{Fore.RED}Usage: /ship <project-name>{Style.RESET_ALL}")
        return
    if not office.deliverables:
        print(f"{Fore.RED}Workspace empty — no files to ship yet.{Style.RESET_ALL}")
        return
    try:
        report = ship_workspace(office, name)
    except Exception as e:  # noqa: BLE001
        print(f"{Fore.RED}⚠️ Ship error: {e}{Style.RESET_ALL}")
        return
    print(f"\n{Fore.GREEN}✓ Shipped → {report.project_dir}{Style.RESET_ALL}")
    print(f"  {report.files_copied} files copied, commit {report.commit_sha}")
    print(f"  File tree:")
    for t in report.file_tree[:30]:
        print(f"    {t}")
    if len(report.file_tree) > 30:
        print(f"    ... and {len(report.file_tree) - 30} more files")
    print(f"  Push: cd \"{report.project_dir}\" && git remote add origin <URL> && git push -u origin main\n")


async def _main() -> None:
    workspace = _ask_workspace()
    try:
        office = build_office(workspace)
    except KeyError as e:
        print(f"Missing env var: {e.args[0]}", file=sys.stderr)
        sys.exit(1)

    _banner(office)

    loop = asyncio.get_event_loop()
    while True:
        try:
            user_text = await loop.run_in_executor(None, input, "> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

        if user_text.strip().lower() in {"exit", "quit"}:
            print("Goodbye!")
            return
        if not user_text.strip():
            continue
        if user_text.strip().startswith("/ship"):
            _handle_ship(office, user_text.strip())
            continue

        try:
            async for event in run_turn(office, user_text):
                _render(event)
        except Exception as e:  # noqa: BLE001
            print(f"{Fore.RED}⚠️ Error: {e}{Style.RESET_ALL}", file=sys.stderr)


def main() -> None:
    """Entry point for the `voffice` CLI command."""
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        from voffice.launcher import run_web
        run_web()
        return
    asyncio.run(_main())


if __name__ == "__main__":
    main()
