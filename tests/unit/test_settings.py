"""Pruebas del límite configurable de reparación."""

import pytest
from pydantic import ValidationError

from backend.app.core.settings import Settings


@pytest.mark.parametrize("attempts", [0, 1, 3])
def test_repair_attempts_accept_safe_range(attempts):
    settings = Settings(_env_file=None, llm_repair_attempts=attempts)
    assert settings.llm_repair_attempts == attempts


@pytest.mark.parametrize("attempts", [-1, 4])
def test_repair_attempts_reject_out_of_range(attempts):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_repair_attempts=attempts)


def test_ollama_settings_can_be_configured_without_fixed_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:22114")
    monkeypatch.setenv("LOCAL_MODEL", "modelo-local:prueba")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("OLLAMA_TEMPERATURE", "0.2")
    monkeypatch.setenv("OLLAMA_TOP_P", "0.8")

    settings = Settings(_env_file=None)

    assert str(settings.ollama_base_url) == "http://localhost:22114/"
    assert settings.local_model == "modelo-local:prueba"
    assert settings.llm_timeout_seconds == 12.5
    assert settings.ollama_temperature == 0.2
    assert settings.ollama_top_p == 0.8


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("llm_timeout_seconds", 0),
        ("ollama_temperature", 2.1),
        ("ollama_top_p", 0),
        ("ollama_top_p", 1.1),
    ],
)
def test_ollama_numeric_settings_reject_unsafe_ranges(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
