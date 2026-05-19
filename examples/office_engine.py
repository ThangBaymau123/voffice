"""
Văn phòng ảo — logic chung cho CLI và Web.

Kiến trúc: 1 Manager + 4 employees ngồi chung MsgHub (auto-broadcast).
- build_office() — đọc env, dựng 5 ReActAgent.
- run_turn() — async generator phát TurnEvent từng chunk khi stream.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from agentscope.agent import ReActAgent
from agentscope.formatter import AnthropicMultiAgentFormatter
from agentscope.memory import InMemoryMemory
from agentscope.pipeline import MsgHub

from _common import make_model


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
    "Lan":  _emp("Lan",  "Product Manager",    "EMPLOYEE_1"),
    "Minh": _emp("Minh", "Backend Developer",  "EMPLOYEE_2"),
    "Hà":   _emp("Hà",   "Frontend Developer", "EMPLOYEE_3"),
    "Tú":   _emp("Tú",   "QA Tester",          "EMPLOYEE_4"),
}


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
