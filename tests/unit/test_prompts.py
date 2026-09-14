"""Pruebas estables de los límites esenciales del prompt de sistema."""

from backend.app.prompts.system import SYSTEM_PROMPT


def test_system_prompt_names_the_required_bias_dimensions():
    prompt = SYSTEM_PROMPT.casefold()

    for concept in ("género", "origen", "raza", "barrio inferido"):
        assert concept in prompt
    assert "determinar la urgencia" in prompt
