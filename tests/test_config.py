from pathlib import Path

import pytest

from chatbot_app.bootstrap import build_system_prompt
from chatbot_core.config import load_tenant_config

REPO_ROOT = Path(__file__).parent.parent


def test_demo_tenant_config_is_valid() -> None:
    tenant = load_tenant_config(REPO_ROOT / "tenants", "demo_clinica")
    assert tenant.id == "demo_clinica"
    assert tenant.scheduling.enabled
    assert {s.id for s in tenant.scheduling.services} == {
        "consulta_general",
        "limpieza",
        "blanqueamiento",
    }
    assert 0 in tenant.scheduling.hours


def test_missing_tenant_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_tenant_config(REPO_ROOT / "tenants", "no_existe")


def test_system_prompt_includes_tenant_specifics() -> None:
    tenant = load_tenant_config(REPO_ROOT / "tenants", "demo_clinica")
    prompt = build_system_prompt(tenant)
    assert "Clínica Dental Sonrisa" in prompt
    assert tenant.out_of_scope_response.strip() in prompt
    assert "search_kb" in prompt
