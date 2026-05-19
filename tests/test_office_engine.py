"""Tests for voffice — model factory, roles, build_office, run_turn filter."""

import pytest

from voffice import make_model, ROLES, RoleSpec, TurnEvent, Office, build_office, run_turn


# ─── make_model ────────────────────────────────────────────────────────────


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


# ─── ROLES ─────────────────────────────────────────────────────────────────


def test_roles_has_5_entries():
    assert set(ROLES.keys()) == {"Manager", "Lan", "Minh", "Hà", "Tú"}


def test_each_role_has_required_fields():
    for name, spec in ROLES.items():
        assert isinstance(spec, RoleSpec)
        assert spec.title, f"{name} missing title"
        assert spec.sys_prompt, f"{name} missing sys_prompt"
        assert spec.env_prefix, f"{name} missing env_prefix"


def test_employee_sys_prompts_contain_skip_rule():
    for name in ["Lan", "Minh", "Hà", "Tú"]:
        assert "[skip]" in ROLES[name].sys_prompt, (
            f"{name}'s sys_prompt must instruct to return [skip] when silent"
        )


def test_turn_event_dataclass_shape():
    ev = TurnEvent(speaker="Lan", text_chunk="hello", is_final=False)
    assert ev.speaker == "Lan"
    assert ev.text_chunk == "hello"
    assert ev.is_final is False


# ─── build_office ──────────────────────────────────────────────────────────


def _set_full_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AWS_API_KEY", "k0")
    monkeypatch.setenv("ANTHROPIC_AWS_WORKSPACE_ID", "w0")
    monkeypatch.setenv("ANTHROPIC_AWS_BASE_URL", "https://r0.example")
    for i, prefix in enumerate(
        ["MANAGER", "EMPLOYEE_1", "EMPLOYEE_2", "EMPLOYEE_3", "EMPLOYEE_4"], start=1
    ):
        monkeypatch.setenv(f"{prefix}_KEY", f"k{i}")
        monkeypatch.setenv(f"{prefix}_WORKSPACE", f"w{i}")
        monkeypatch.setenv(f"{prefix}_BASE_URL", f"https://r{i}.example")


def test_build_office_creates_5_agents(monkeypatch, tmp_path):
    _set_full_env(monkeypatch)
    office = build_office(tmp_path / "ws")
    assert isinstance(office, Office)
    assert office.manager.name == "Manager"
    assert [a.name for a in office.employees] == ["Lan", "Minh", "Hà", "Tú"]
    assert office.workspace_dir.exists()


def test_build_office_missing_env_raises(monkeypatch, tmp_path):
    _set_full_env(monkeypatch)
    monkeypatch.delenv("EMPLOYEE_3_KEY")
    with pytest.raises(KeyError, match="EMPLOYEE_3_KEY"):
        build_office(tmp_path / "ws")


# ─── run_turn ──────────────────────────────────────────────────────────────


from unittest.mock import AsyncMock

from agentscope.message import Msg


async def test_run_turn_yields_events_for_non_skip_replies(monkeypatch, tmp_path):
    """Manager + 2 employees speak; 2 employees return [skip] and are filtered.

    We bypass MsgHub/fanout/QA-loop plumbing — focus on the filter & yield logic.
    """
    import voffice.engine as oe

    async def manager_call(msg=None):
        return Msg(name="Manager", content="Lan, Minh — get to work.", role="assistant")

    async def lan_call(msg=None):
        return Msg(name="Lan", content="User story drafted.", role="assistant")

    async def minh_call(msg=None):
        return Msg(name="Minh", content="API designed.", role="assistant")

    async def ha_call(msg=None):
        return Msg(name="Hà", content="[skip]", role="assistant")

    async def tu_call(msg=None):
        return Msg(name="Tú", content="[skip]", role="assistant")

    def make_fake(name, fn):
        m = AsyncMock(side_effect=fn)
        m.name = name
        return m

    manager = make_fake("Manager", manager_call)
    employees = [
        make_fake("Lan", lan_call),
        make_fake("Minh", minh_call),
        make_fake("Hà", ha_call),
        make_fake("Tú", tu_call),
    ]
    office = Office(manager=manager, employees=employees, workspace_dir=tmp_path)

    class _StubHub:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def broadcast(self, msg): return None

    async def _stub_fanout(agents):
        return [await a(None) for a in agents]

    monkeypatch.setattr(oe, "MsgHub", _StubHub)
    monkeypatch.setattr(oe, "fanout_pipeline", _stub_fanout)

    events = []
    async for ev in run_turn(office, "Build a login API"):
        events.append(ev)

    speakers = [e.speaker for e in events]
    assert "Manager" in speakers
    assert "Lan" in speakers
    assert "Minh" in speakers
    assert "Hà" not in speakers, "[skip] should be filtered"
    assert "Tú" not in speakers, "[skip] should be filtered"
    for ev in events:
        if ev.speaker in {"Manager", "Lan", "Minh"}:
            assert ev.is_final, f"{ev.speaker}'s event must be is_final=True"
