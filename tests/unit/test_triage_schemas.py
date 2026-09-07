"""Pruebas de límites de confianza sin conexiones a modelos ni servicios."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.schemas import TriageRequest, TriageResult


@pytest.fixture
def valid_result():
    return {
        "category": "riesgo_electrico",
        "urgency": "alta",
        "summary": "Cable deteriorado visible junto al acceso del almacén de demostración.",
        "department": "mantenimiento",
        "justification": "Ejemplo sintético de formato; prioridad pendiente de revisión profesional.",
    }



def test_valid_request_normalizes_boundaries():
    result = TriageRequest.model_validate_json(
        '{"text": "  Cable deteriorado.  ", "provider": "local", "location": " Taller "}'
    )
    assert result.text == "Cable deteriorado."
    assert result.location == "Taller"


@pytest.mark.parametrize("changes", [
    {"text": " "}, {"text": 123}, {"text": None}, {"text": "a" * 4001},
    {"provider": "unknown"}, {"provider": True}, {"location": " "},
    {"location": 123}, {"location": "a" * 201}, {"unexpected": "value"},
])
def test_invalid_request_is_rejected(changes):
    payload = {"text": "Aviso sintético", "provider": "local", **changes}
    with pytest.raises(ValidationError):
        TriageRequest.model_validate_json(json.dumps(payload))


def test_provider_is_required():
    with pytest.raises(ValidationError):
        TriageRequest(text="Aviso sintético")


def test_request_accepts_limits_and_optional_location():
    result = TriageRequest(text="a" * 4000, provider="external", location="a" * 200)
    assert len(result.location) == 200
    assert TriageRequest(text="Aviso", provider="local").location is None


def test_valid_result_round_trip(valid_result):
    result = TriageResult.model_validate_json(json.dumps(valid_result))
    assert TriageResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("changes", [
    {"category": "desconocida"}, {"urgency": "urgente"},
    {"department": "desconocido"}, {"summary": "Resumen demasiado corto"},
    {"summary": "uno dos tres cuatro cinco seis siete ocho nueve diez once"},
    {"summary": "uno dos tres cuatro cinco seis siete ocho nueve !!!"},
    {"summary": 10}, {"justification": " "}, {"justification": "a" * 2001},
    {"approved": True},
])
def test_invalid_model_result_is_rejected(valid_result, changes):
    with pytest.raises(ValidationError):
        TriageResult.model_validate_json(json.dumps({**valid_result, **changes}))


@pytest.mark.parametrize("field", ["category", "urgency", "summary", "department", "justification"])
def test_missing_model_field_is_rejected(valid_result, field):
    del valid_result[field]
    with pytest.raises(ValidationError):
        TriageResult.model_validate(valid_result)


def test_summary_normalizes_repeated_whitespace(valid_result):
    valid_result["summary"] = "  Cable  deteriorado\tvisible junto al acceso del almacén de demostración.  "
    assert TriageResult(**valid_result).summary == "Cable deteriorado visible junto al acceso del almacén de demostración."


@pytest.mark.parametrize("raw", ["No puedo clasificar", "{", "[]", "null"])
def test_non_object_or_broken_json_is_rejected(raw):
    with pytest.raises(ValidationError):
        TriageResult.model_validate_json(raw)


def test_synthetic_examples_match_request_contract():
    path = Path(__file__).resolve().parents[2] / "data" / "examples" / "avisos.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        TriageRequest.model_validate({key: value for key, value in case.items() if key != "id"})
