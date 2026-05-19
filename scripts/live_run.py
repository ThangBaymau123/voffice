"""Headless live end-to-end verification for voffice.

Drives `build_office` -> `run_turn` -> `ship_workspace` against the real
AWS-Bedrock-Claude gateway, then prints a final summary. Used for one-shot
verification — NOT part of the package, NOT a test (talks to a paid LLM).

Run:
    python scripts/live_run.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voffice import build_office, run_turn, ship_workspace  # noqa: E402


TASK = (
    "Build a tiny Python utility: function `is_palindrome(s: str) -> bool` "
    "that returns True if `s` reads the same forwards/backwards, "
    "case-insensitive, ignoring non-alphanumeric characters. "
    "Lan: 1-paragraph user story. "
    "Minh: file `palindrome.py` with the function. "
    "Hà: minimal `demo.html` (input box + button — vanilla JS, no framework). "
    "Tú: file `test_palindrome.py` with pytest cases including "
    "'A man a plan a canal Panama', 'racecar', 'hello', '' (empty), 'a'."
)


WORKSPACE = Path.cwd() / "live_workspace"


def _truncate(s: str, n: int = 400) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + f"\n... [truncated, {len(s) - n} chars]"


async def main() -> int:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)

    print(f"=== voffice live run ===")
    print(f"workspace: {WORKSPACE}")
    print(f"task: {_truncate(TASK, 200)}\n")

    office = build_office(WORKSPACE)
    print(f"office built: Manager + {len(office.employees)} employees")
    print(f"employees: {[e.name for e in office.employees]}\n")

    print("--- TURN START ---")
    event_count = 0
    async for event in run_turn(office, TASK):
        event_count += 1
        body = _truncate(event.text_chunk, 500)
        print(f"\n[{event.speaker}] (event #{event_count})")
        print(body)
    print("\n--- TURN END ---")

    print(f"\ndeliverables saved: {len(office.deliverables)}")
    for p in office.deliverables:
        try:
            rel = p.relative_to(WORKSPACE)
        except ValueError:
            rel = p
        print(f"  - {rel}  ({p.stat().st_size} bytes)")

    if not office.deliverables:
        print("\n!! No deliverables — aborting ship", file=sys.stderr)
        return 1

    print("\n--- SHIP ---")
    report = ship_workspace(office, "palindrome-live")
    print(f"shipped to: {report.project_dir}")
    print(f"files: {report.files_copied}, commit: {report.commit_sha}")
    print("file tree:")
    for t in report.file_tree:
        print(f"  {t}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
