import os
import pytest
from _common import make_model


def test_make_model_uses_explicit_args(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AWS_API_KEY", "fallback")
    monkeypatch.setenv("ANTHROPIC_AWS_WORKSPACE_ID", "fallback_ws")
    monkeypatch.setenv("ANTHROPIC_AWS_BASE_URL", "https://fallback.example")

    model = make_model(
        api_key="explicit_key",
        workspace_id="explicit_ws",
        base_url="https://explicit.example",
    )
    assert str(model.client.base_url).rstrip("/") == "https://explicit.example"
    assert model.client.default_headers.get("anthropic-workspace-id") == "explicit_ws"


def test_make_model_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AWS_API_KEY", "fallback_key")
    monkeypatch.setenv("ANTHROPIC_AWS_WORKSPACE_ID", "fallback_ws")
    monkeypatch.setenv("ANTHROPIC_AWS_BASE_URL", "https://fallback.example")

    model = make_model()
    assert str(model.client.base_url).rstrip("/") == "https://fallback.example"
    assert model.client.default_headers.get("anthropic-workspace-id") == "fallback_ws"
