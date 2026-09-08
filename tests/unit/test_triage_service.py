"""Pruebas de validación, reparación y errores del servicio de triaje."""

import json
from unittest.mock import patch

import pytest

from backend.app.providers import (
    ProviderConnectionError,
    ProviderRateLimitError,
    RepairContext,
    ToolCall,
)
from backend.app.schemas import TriageRequest
from backend.app.services import InvalidProviderOutputError, TriageService

VALID_RESULT = {
    "category": "riesgo_electrico",
    "urgency": "alta",
    "summary": "Cable deteriorado visible junto al acceso del almacén de demostración.",
    "department": "mantenimiento",
    "justification": "Ejemplo sintético pendiente de revisión profesional.",
}

TOOL_CALL = ToolCall(
    name="consultar_matriz_riesgos",
    arguments={"category": "riesgo_electrico"},
)



class SequenceProvider:
    """Proveedor de prueba que entrega respuestas en el orden indicado."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.repairs: list[RepairContext | None] = []
        self.observations = []

    def generate(self, request, *, observation=None, repair=None):
        self.observations.append(observation)
        self.repairs.append(repair)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


@pytest.fixture
def triage_request():
    return TriageRequest(text="Hay un cable deteriorado.", provider="local")


def test_accepts_valid_json_without_repair(triage_request):
    provider = SequenceProvider(TOOL_CALL, json.dumps(VALID_RESULT))

    result = TriageService(provider).triage(triage_request, request_id="req-valid")

    assert result.category == "riesgo_electrico"
    assert provider.repairs == [None, None]
    assert provider.observations[1].rule_id == "RM-ELEC-001"


def test_repairs_broken_json_then_accepts_valid_output(triage_request):
    provider = SequenceProvider(TOOL_CALL, "{", json.dumps(VALID_RESULT))

    result = TriageService(provider, max_repair_attempts=1).triage(
        triage_request,
        request_id="req-json",
    )

    assert result.urgency == "alta"
    assert provider.repairs[0] is None
    assert provider.repairs[1] is None
    assert provider.repairs[2].invalid_output == "{"
    assert provider.repairs[2].validation_errors


def test_repairs_invalid_enum_then_accepts_valid_mapping(triage_request):
    invalid_result = {**VALID_RESULT, "urgency": "urgente"}
    provider = SequenceProvider(TOOL_CALL, invalid_result, VALID_RESULT)

    result = TriageService(provider, max_repair_attempts=1).triage(
        triage_request,
        request_id="req-enum",
    )

    assert result.urgency == "alta"
    assert any("urgency" in error for error in provider.repairs[2].validation_errors)


def test_repair_feedback_explains_ten_word_constraint(triage_request):
    invalid_result = {**VALID_RESULT, "summary": "Resumen demasiado breve."}
    provider = SequenceProvider(TOOL_CALL, invalid_result, VALID_RESULT)

    TriageService(provider, max_repair_attempts=1).triage(
        triage_request,
        request_id="req-summary",
    )

    assert any(
        "exactamente 10 palabras" in error
        for error in provider.repairs[2].validation_errors
    )


def test_exhaustion_raises_stable_service_error(triage_request):
    provider = SequenceProvider(TOOL_CALL, "{", "[]")

    with pytest.raises(InvalidProviderOutputError) as captured:
        TriageService(provider, max_repair_attempts=1).triage(
            triage_request,
            request_id="req-exhausted",
        )

    assert captured.value.attempts == 2
    assert len(provider.repairs) == 3


@pytest.mark.parametrize("value", [-1, 4, True, 1.5])
def test_repair_limit_is_small_and_strict(value):
    with pytest.raises(ValueError):
        TriageService(SequenceProvider(VALID_RESULT), max_repair_attempts=value)


@pytest.mark.parametrize(
    "provider_error",
    [ProviderConnectionError("sin conexión"), ProviderRateLimitError(30)],
)
def test_provider_errors_are_not_repaired_in_this_phase(triage_request, provider_error):
    provider = SequenceProvider(provider_error, VALID_RESULT)

    with pytest.raises(type(provider_error)):
        TriageService(provider, max_repair_attempts=3).triage(
            triage_request,
            request_id="req-provider",
        )

    assert provider.repairs == [None]


def test_each_attempt_logs_only_technical_metadata(triage_request):
    provider = SequenceProvider(TOOL_CALL, "texto sensible de salida", VALID_RESULT)

    with patch("backend.app.services.triage_service._logger") as logger:
        TriageService(provider, max_repair_attempts=1).triage(
            triage_request,
            request_id="req-log",
        )

    invalid_metadata = logger.warning.call_args.kwargs["extra"]
    accepted_metadata = logger.info.call_args.kwargs["extra"]
    assert invalid_metadata == {
        "request_id": "req-log",
        "attempt": 1,
        "outcome": "invalid_output",
        "error_type": "ValidationError",
    }
    assert accepted_metadata == {
        "request_id": "req-log",
        "attempt": 2,
        "outcome": "accepted",
    }
    logged_calls = logger.warning.call_args_list + logger.info.call_args_list
    assert "texto sensible" not in repr(logged_calls)
    assert any(call.args[0] == "tool_execution" for call in logger.info.call_args_list)


@pytest.mark.parametrize("retry_after", [-1, True, 1.5])
def test_rate_limit_rejects_invalid_retry_after(retry_after):
    with pytest.raises(ValueError):
        ProviderRateLimitError(retry_after)
