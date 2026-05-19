"""
Ví dụ 03 — Multi-agent: ba chuyên gia tranh luận về một chủ đề

Mục tiêu học:
  1) `MsgHub` là "kênh broadcast" — message do một agent phát đi sẽ tự
     vào memory của những agent khác trong hub.
  2) `sequential_pipeline` cho các agent phát biểu lần lượt.
  3) `fanout_pipeline` cho các agent trả lời song song (asyncio).
  4) `MultiAgentFormatter` (khác với `ChatFormatter` ở ví dụ trước) —
     dùng khi có hơn 2 thực thể trong cuộc hội thoại.

Cách chạy:
  python examples/03_multi_agent_debate.py
"""

import asyncio

from agentscope.agent import ReActAgent
from agentscope.formatter import AnthropicMultiAgentFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.pipeline import MsgHub, fanout_pipeline, sequential_pipeline

from _common import make_model


def make_expert(name: str, role: str) -> ReActAgent:
    return ReActAgent(
        name=name,
        sys_prompt=(
            f"Bạn là {name}, một {role}. Trả lời ngắn (2-3 câu), bằng "
            f"tiếng Việt, từ góc nhìn chuyên môn của bạn. Phản biện "
            f"hoặc bổ sung quan điểm của các chuyên gia khác."
        ),
        model=make_model(),
        formatter=AnthropicMultiAgentFormatter(),
        memory=InMemoryMemory(),
    )


async def main() -> None:
    economist = make_expert("Lan", "nhà kinh tế học")
    engineer = make_expert("Minh", "kỹ sư phần mềm")
    ethicist = make_expert("Hà", "nhà đạo đức học công nghệ")

    topic = Msg(
        name="Host",
        content="Chủ đề tranh luận: 'AI có nên thay thế lập trình viên junior?'",
        role="user",
    )

    # Vòng 1: phát biểu tuần tự
    async with MsgHub(
        participants=[economist, engineer, ethicist],
        announcement=topic,
        enable_auto_broadcast=True,
    ) as hub:
        print("\n=== VÒNG 1: Phát biểu tuần tự ===\n")
        await sequential_pipeline([economist, engineer, ethicist])

        # Vòng 2: phản biện song song — mọi agent đọc cùng prompt và trả lời cùng lúc
        print("\n=== VÒNG 2: Phản biện song song ===\n")
        await hub.broadcast(
            Msg(
                name="Host",
                content="Mỗi người hãy đưa ra MỘT phản biện mạnh nhất với ý kiến đối lập.",
                role="user",
            ),
        )
        replies = await fanout_pipeline([economist, engineer, ethicist])
        for r in replies:
            print(f"\n[{r.name}] {r.get_text_content()}")


if __name__ == "__main__":
    asyncio.run(main())
