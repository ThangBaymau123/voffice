"""
Helpers dùng chung cho mọi ví dụ.

`make_model()` xây dựng `AnthropicChatModel` của AgentScope trỏ vào Anthropic
gateway. Mỗi tham số có thể truyền tường minh (cho từng agent dùng key/region
riêng) hoặc fallback sang biến môi trường `ANTHROPIC_AWS_*`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from agentscope.model import AnthropicChatModel

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-4-5"


def make_model(
    api_key: str | None = None,
    workspace_id: str | None = None,
    base_url: str | None = None,
    *,
    model_name: str = DEFAULT_MODEL,
    stream: bool = True,
) -> AnthropicChatModel:
    api_key = api_key or os.environ["ANTHROPIC_AWS_API_KEY"]
    workspace_id = workspace_id or os.environ["ANTHROPIC_AWS_WORKSPACE_ID"]
    base_url = base_url or os.environ["ANTHROPIC_AWS_BASE_URL"]

    return AnthropicChatModel(
        model_name=model_name,
        api_key=api_key,
        stream=stream,
        client_kwargs={
            "base_url": base_url,
            "default_headers": {"anthropic-workspace-id": workspace_id},
        },
    )
