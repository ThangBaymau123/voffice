"""
Văn phòng ảo — logic chung cho CLI và Web.

Kiến trúc: 1 Manager + 4 employees ngồi chung MsgHub (auto-broadcast).
Mỗi nhân viên (không phải Manager) được trang bị tool `save_deliverable`
để tạo file thật trong workspace_dir → "làm việc" chứ không chỉ "nói".

API chính:
  build_office(workspace_dir) → Office
  run_turn(office, user_text)  → async generator của TurnEvent
"""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.formatter import AnthropicMultiAgentFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg, TextBlock
from agentscope.pipeline import MsgHub, fanout_pipeline
from agentscope.tool import Toolkit, ToolResponse, view_text_file

from _common import make_model


@dataclass(frozen=True)
class RoleSpec:
    title: str
    sys_prompt: str
    env_prefix: str


@dataclass
class TurnEvent:
    speaker: str
    text_chunk: str
    is_final: bool


_EMPLOYEE_TEMPLATE = """\
Bạn là {name}, {title} trong văn phòng phần mềm.

NHIỆM VỤ THẬT (KHÔNG chỉ nói):
- Khi Manager giao việc cho bạn, bạn PHẢI tạo file deliverable cụ thể
  bằng tool `save_deliverable(filename, content)`. Ví dụ:
    • PM → user_story.md, requirements.md
    • Backend → api_spec.md, auth_handler.py
    • Frontend → mockup.html, components.md
    • QA → test_plan.md, test_cases.md
- Nội dung file phải dùng được luôn — không phải placeholder.
- Sau khi save, trả lời ngắn xác nhận đã tạo file gì.

KHI NÀO IM LẶNG:
- Nếu Manager không nhắc bạn VÀ bạn không thấy lỗi kỹ thuật nghiêm trọng
  → trả lời CHÍNH XÁC chuỗi: [skip]
- Nếu thấy lỗi kỹ thuật trong cách Manager phân công → chen ngắn 1-2 câu
  phản biện (không cần save file).

Trả lời tiếng Việt, từ góc nhìn chuyên môn ({title}) của bạn.
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
            "     Yêu cầu họ TẠO FILE DELIVERABLE (Lan→user_story.md, "
            "Minh→api code, Hà→mockup, Tú→test_plan.md...).\n"
            "  3. Không tự làm thay — chỉ điều phối.\n"
            "Trả lời ngắn (2-5 câu), tiếng Việt."
        ),
        env_prefix="MANAGER",
    ),
    "Lan":  _emp("Lan",  "Product Manager",    "EMPLOYEE_1"),
    "Minh": _emp("Minh", "Backend Developer",  "EMPLOYEE_2"),
    "Hà":   _emp("Hà",   "Frontend Developer", "EMPLOYEE_3"),
    "Tú":   _emp("Tú",   "QA Tester",          "EMPLOYEE_4"),
}


@dataclass
class Office:
    manager: ReActAgent
    employees: list[ReActAgent]
    workspace_dir: Path
    deliverables: list[Path] = field(default_factory=list)
    hub: MsgHub | None = None


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.\-]")


def _sanitize_filename(name: str) -> str:
    """Strip path traversal, normalize separators."""
    base = Path(name).name  # drops any directory part
    return _SAFE_NAME.sub("_", base) or "untitled.txt"


def _make_save_tool(agent_name: str, office: Office):
    """Return a per-agent save_deliverable function bound to office.workspace_dir.

    Each call writes to workspace_dir/<agent_name>/<filename> and records the
    path in office.deliverables so the UI can list them.
    """
    def save_deliverable(filename: str, content: str) -> ToolResponse:
        """Lưu một file deliverable thật vào workspace.

        Dùng tool này MỖI KHI bạn được Manager giao việc cụ thể.
        Trả về xác nhận đường dẫn file đã ghi.

        Args:
            filename: Tên file (không có path), ví dụ "user_story.md", "auth.py".
            content: Toàn bộ nội dung file (markdown, code, bất cứ gì).
        """
        safe = _sanitize_filename(filename)
        out_dir = office.workspace_dir / agent_name
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / safe
        path.write_text(content, encoding="utf-8")
        office.deliverables.append(path)
        return ToolResponse(
            content=[TextBlock(type="text", text=f"✓ Đã lưu: {path}")],
        )
    save_deliverable.__name__ = "save_deliverable"
    return save_deliverable


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
    """Dựng văn phòng. Manager không có tool; mỗi employee có save_deliverable."""
    workspace_dir = Path(workspace_dir).resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    office = Office(
        manager=None,  # type: ignore[arg-type] — set ngay dưới
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


async def run_turn(office: Office, user_text: str) -> AsyncIterator[TurnEvent]:
    """One conversation turn.

    1. Broadcast user message into hub.
    2. Manager speaks (no tools).
    3. Employees act in parallel — each may call `save_deliverable` 1+ times
       (ReAct loop, max 4 iterations) before responding.
    4. Yield events for non-[skip] replies. After all replies, yield a synthetic
       "Office" event listing files saved this turn.
    """
    participants = [office.manager, *office.employees]
    user_msg = Msg(name="User", content=user_text, role="user")

    deliverables_before = len(office.deliverables)

    async with MsgHub(participants=participants, enable_auto_broadcast=True) as hub:
        office.hub = hub
        await hub.broadcast(user_msg)

        manager_reply = await office.manager(None)
        if manager_reply.get_text_content().strip() != "[skip]":
            yield TurnEvent(
                speaker=office.manager.name,
                text_chunk=manager_reply.get_text_content(),
                is_final=True,
            )

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

    new_files = office.deliverables[deliverables_before:]
    if new_files:
        listing = "\n".join(f"  • {p.relative_to(office.workspace_dir)}" for p in new_files)
        yield TurnEvent(
            speaker="Office",
            text_chunk=f"📁 Deliverable đã tạo:\n{listing}",
            is_final=True,
        )
