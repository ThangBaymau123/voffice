"""
Ví dụ 01 — Một ReActAgent đơn giản (Hello AgentScope)

Mục tiêu học:
  1) Hiểu 4 thành phần cốt lõi: Model, Formatter, Memory, Toolkit.
  2) Thấy vòng lặp Reason–Act–Observe của ReActAgent khi nó gọi tool.

Cách chạy:
  set ANTHROPIC_API_KEY=sk-ant-...        (Windows cmd)
  $env:ANTHROPIC_API_KEY="sk-ant-..."     (PowerShell)
  python examples/01_hello_agent.py
"""

import asyncio

from agentscope.agent import ReActAgent, UserAgent
from agentscope.formatter import AnthropicChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit, execute_python_code, view_text_file

from _common import make_model


async def main() -> None:
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(view_text_file)

    agent = ReActAgent(
        name="Friday",
        sys_prompt=(
            "Bạn là trợ lý AI tên Friday. Trả lời ngắn gọn, tiếng Việt. "
            "Khi cần tính toán hoặc đọc file, hãy dùng tool."
        ),
        model=make_model(),
        formatter=AnthropicChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
        max_iters=10,
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
