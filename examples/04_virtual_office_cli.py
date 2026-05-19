"""
Ví dụ 04 — Văn phòng ảo (CLI)

Chạy: python examples/04_virtual_office_cli.py
Yêu cầu: 4 employee key + 1 manager key trong .env.
Thoát: gõ `exit` hoặc Ctrl+C.
"""

import asyncio
import sys
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

from office_engine import build_office, run_turn

colorama_init()

COLORS = {
    "Manager": Fore.CYAN,
    "Lan":     Fore.YELLOW,
    "Minh":    Fore.GREEN,
    "Hà":      Fore.MAGENTA,
    "Tú":      Fore.BLUE,
    "Office":  Fore.WHITE,
}

DEFAULT_WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"


def render(event) -> None:
    color = COLORS.get(event.speaker, Fore.WHITE)
    prefix = f"{color}[{event.speaker}]{Style.RESET_ALL} "
    print(f"{prefix}{event.text_chunk}")


def banner(office) -> None:
    print(f"\n{Fore.WHITE}╭─ Văn phòng đã sẵn sàng ─╮{Style.RESET_ALL}")
    print(f"  📁 workspace: {office.workspace_dir}")
    print(f"  ✓ {COLORS['Manager']}Manager{Style.RESET_ALL} online")
    for emp in office.employees:
        c = COLORS.get(emp.name, Fore.WHITE)
        print(f"  ✓ {c}{emp.name}{Style.RESET_ALL} online (có tool save_deliverable)")
    print(f"{Fore.WHITE}╰──────────────────────────╯{Style.RESET_ALL}")
    print("Gõ task của bạn (hoặc `exit`):\n")


def ask_workspace() -> Path:
    print(f"{Fore.WHITE}Thư mục lưu deliverable?{Style.RESET_ALL}")
    print(f"  (Enter để dùng mặc định: {DEFAULT_WORKSPACE})")
    raw = input("workspace> ").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_WORKSPACE


async def main() -> None:
    workspace = ask_workspace()
    try:
        office = build_office(workspace)
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
