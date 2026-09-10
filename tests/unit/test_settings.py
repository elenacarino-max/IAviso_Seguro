"""Pruebas del límite configurable de reparación."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.core.settings import Settings


def test_database_path_is_configurable(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "data/local/prueba.db")

    settings = Settings(_env_file=None)

    assert settings.database_path == Path("data/local/prueba.db")


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


def test_gemini_settings_are_configurable_and_key_remains_secret(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_BASE_URL", "https://gemini.example/v1beta")
    monkeypatch.setenv("EXTERNAL_API_KEY", "secreto-prueba")
    monkeypatch.setenv("EXTERNAL_MODEL", "gemini-prueba")
    monkeypatch.setenv("EXTERNAL_TEMPERATURE", "0.2")
    monkeypatch.setenv("EXTERNAL_TOP_P", "0.8")
    monkeypatch.setenv("LLM_MAX_RETRIES", "4")
    monkeypatch.setenv("LLM_RETRY_BASE_SECONDS", "1")
    monkeypatch.setenv("LLM_RETRY_MAX_SECONDS", "9")

    settings = Settings(_env_file=None)

    assert str(settings.external_api_base_url) == "https://gemini.example/v1beta"
    assert settings.external_api_key.get_secret_value() == "secreto-prueba"
    assert "secreto-prueba" not in repr(settings)
    assert settings.external_model == "gemini-prueba"
    assert settings.external_temperature == 0.2
    assert settings.external_top_p == 0.8
    assert settings.llm_max_retries == 4
    assert settings.llm_retry_base_seconds == 1
    assert settings.llm_retry_max_seconds == 9


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("llm_max_retries", -1),
        ("llm_max_retries", 6),
        ("llm_retry_base_seconds", -0.1),
        ("llm_retry_max_seconds", 301),
        ("external_temperature", 2.1),
        ("external_top_p", 0),
    ],
)
def test_external_numeric_settings_reject_unsafe_ranges(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_retry_base_cannot_exceed_retry_cap():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            llm_retry_base_seconds=5,
            llm_retry_max_seconds=4,
        )
