"""
Ví dụ 02 — Tự viết tool cho agent

Mục tiêu học:
  1) Tool chỉ là hàm Python có docstring + type hint.
  2) ToolResponse cho phép trả về nhiều block (text, image, ...).
  3) Bạn sẽ tự hoàn thiện hàm `track_expense` — quyết định cách lưu & truy vấn chi phí.

Cách chạy:
  python examples/02_custom_tool.py
"""

import asyncio
import json
from pathlib import Path

from agentscope.agent import ReActAgent, UserAgent
from agentscope.formatter import AnthropicChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse

from _common import make_model

# File lưu chi phí (giữ đơn giản — không dùng DB)
EXPENSE_FILE = Path(__file__).parent / "expenses.json"


def _load() -> list[dict]:
    if EXPENSE_FILE.exists():
        return json.loads(EXPENSE_FILE.read_text(encoding="utf-8"))
    return []


def _save(items: list[dict]) -> None:
    EXPENSE_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────
# TODO (DÀNH CHO BẠN): Viết hàm `track_expense` bên dưới.
#
# Đây là tool agent sẽ gọi mỗi khi người dùng nói kiểu:
#   "Hôm nay tôi tiêu 50k cho cà phê"
#   "Ghi lại 200000 tiền ăn trưa"
#
# Yêu cầu:
#   - Nhận `amount: float`, `category: str`, `note: str = ""`
#   - Lưu thêm bản ghi mới vào EXPENSE_FILE qua _load()/_save()
#   - Trả về ToolResponse với TextBlock xác nhận (tổng chi phí theo category là bao nhiêu)
#
# Quyết định thiết kế cần cân nhắc:
#   • Validate `amount > 0` rồi báo lỗi, hay cứ lưu? (an toàn vs linh hoạt)
#   • Có chuẩn hoá category về chữ thường không? (gộp "Cafe" và "cafe")
#   • Có lưu timestamp không? (nếu có, dùng datetime.now().isoformat())
#
# Docstring của bạn sẽ trở thành mô tả tool mà LLM đọc — viết rõ ràng!
# ─────────────────────────────────────────────────────────────────────────


def track_expense(amount: float, category: str, note: str = "") -> ToolResponse:
    """TODO: viết docstring + thân hàm tại đây."""
    raise NotImplementedError("Hãy hoàn thiện hàm track_expense!")


def list_expenses(category: str | None = None) -> ToolResponse:
    """Liệt kê các khoản chi đã ghi.

    Args:
        category: Nếu cung cấp, chỉ liệt kê khoản chi thuộc category đó.

    Returns:
        ToolResponse chứa danh sách dạng text.
    """
    items = _load()
    if category:
        items = [x for x in items if x.get("category") == category]

    if not items:
        text = "Chưa có khoản chi nào."
    else:
        lines = [
            f"- {x['amount']:>10,.0f} | {x['category']:<10} | {x.get('note', '')}"
            for x in items
        ]
        total = sum(x["amount"] for x in items)
        text = "\n".join(lines) + f"\n\nTổng: {total:,.0f}"

    return ToolResponse(content=[TextBlock(type="text", text=text)])


async def main() -> None:
    toolkit = Toolkit()
    toolkit.register_tool_function(track_expense)
    toolkit.register_tool_function(list_expenses)

    agent = ReActAgent(
        name="MoneyBot",
        sys_prompt=(
            "Bạn là trợ lý tài chính cá nhân. Khi người dùng nói tới "
            "khoản chi tiêu, hãy gọi tool `track_expense`. Khi họ hỏi "
            "đã chi bao nhiêu, gọi `list_expenses`."
        ),
        model=make_model(),
        formatter=AnthropicChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )

    user = UserAgent(name="user")
    msg = None
    while True:
        msg = await user(msg)
        if msg.get_text_content().strip().lower() in {"exit", "quit"}:
            break
        msg = await agent(msg)


if __name__ == "__main__":
    asyncio.run(main())
