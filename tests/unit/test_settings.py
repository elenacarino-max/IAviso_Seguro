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
