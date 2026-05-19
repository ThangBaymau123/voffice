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


from office_engine import ROLES, RoleSpec, TurnEvent


def test_roles_has_5_entries():
    expected = {"Manager", "Lan", "Minh", "Hà", "Tú"}
    assert set(ROLES.keys()) == expected


def test_each_role_has_required_fields():
    for name, spec in ROLES.items():
        assert isinstance(spec, RoleSpec)
        assert spec.title, f"{name} missing title"
        assert spec.sys_prompt, f"{name} missing sys_prompt"
        assert spec.env_prefix, f"{name} missing env_prefix"


def test_employee_sys_prompts_contain_skip_rule():
    employee_names = ["Lan", "Minh", "Hà", "Tú"]
    for name in employee_names:
        assert "[skip]" in ROLES[name].sys_prompt, (
            f"{name}'s sys_prompt must instruct to return [skip] when silent"
        )


def test_turn_event_dataclass_shape():
    ev = TurnEvent(speaker="Lan", text_chunk="xin chào", is_final=False)
    assert ev.speaker == "Lan"
    assert ev.text_chunk == "xin chào"
    assert ev.is_final is False


from office_engine import Office, build_office


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


def test_build_office_creates_5_agents(monkeypatch):
    _set_full_env(monkeypatch)
    office = build_office()
    assert isinstance(office, Office)
    assert office.manager.name == "Manager"
    assert [a.name for a in office.employees] == ["Lan", "Minh", "Hà", "Tú"]


def test_build_office_missing_env_raises(monkeypatch):
    _set_full_env(monkeypatch)
    monkeypatch.delenv("EMPLOYEE_3_KEY")
    with pytest.raises(KeyError, match="EMPLOYEE_3_KEY"):
        build_office()
