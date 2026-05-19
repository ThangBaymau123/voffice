"""
Helpers dùng chung cho mọi ví dụ.

`make_model()` xây dựng `AnthropicChatModel` của AgentScope nhưng trỏ vào
Anthropic-on-AWS gateway thay vì api.anthropic.com mặc định.

AnthropicChatModel(client_kwargs=...) sẽ chuyển tiếp dict này xuống
anthropic.AsyncAnthropic — ở đó `base_url` và `default_headers` đều được
hỗ trợ chính thức.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from agentscope.model import AnthropicChatModel

load_dotenv()  # Nạp biến từ .env

DEFAULT_MODEL = "claude-sonnet-4-5"


def make_model(model_name: str = DEFAULT_MODEL, *, stream: bool = True) -> AnthropicChatModel:
    api_key = os.environ["ANTHROPIC_AWS_API_KEY"]
    base_url = os.environ["ANTHROPIC_AWS_BASE_URL"]
    workspace_id = os.environ["ANTHROPIC_AWS_WORKSPACE_ID"]

    return AnthropicChatModel(
        model_name=model_name,
        api_key=api_key,
        stream=stream,
        client_kwargs={
            "base_url": base_url,
            "default_headers": {
                "anthropic-workspace-id": workspace_id,
            },
        },
    )
