"""Model factory for Anthropic Claude (via AWS gateway or direct API).

`make_model()` builds an `AnthropicChatModel` from AgentScope. Each parameter
may be passed explicitly (one key per agent) or falls back to ANTHROPIC_AWS_*
environment variables. This is the only file that talks to provider config.
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
    """Build an AnthropicChatModel; explicit args override env fallbacks."""
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
