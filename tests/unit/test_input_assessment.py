"""Contratos y servicio del precheck sin depender de modelos reales."""

import pytest
from pydantic import ValidationError

from backend.app.schemas import (
    InputAssessmentDecision,
    InputAssessmentRequest,
    InputAssessmentResponse,
)
from backend.app.services import InputAssessmentService


class FakeAssessmentProvider:
    def __init__(self, output=None, *, error: Exception | None = None):
        self.output = output
        self.error = error
        self.received = []

    def assess(self, request):
        self.received.append(request)
        if self.error is not None:
            raise self.error
        return self.output


def request(text="Hay humo saliendo del cuadro eléctrico."):
    return InputAssessmentRequest(text=text, provider="local")


@pytest.mark.parametrize(
    "text",
    [
        "Hay humo saliendo del cuadro eléctrico.",
        "Un cable atraviesa el pasillo y varias personas han tropezado.",
        "La protección de la prensa está retirada mientras la máquina funciona.",
        "Se ha derramado un producto corrosivo en la zona de trabajo.",
        "Fuego en el cuadro eléctrico.",
    ],
)
def test_sufficient_descriptions_continue_without_questions(text):
    provider = FakeAssessmentProvider(
        {"sufficient": True, "questions": (), "missing_aspects": ()}
    )

    result = InputAssessmentService(provider).assess(
        request(text),
        request_id="req-sufficient",
    )

    assert result.available is True
    assert result.sufficient is True
    assert result.questions == ()
    assert result.missing_aspects == ()


@pytest.mark.parametrize(
    "text",
    ["Hay un problema.", "Algo no está bien.", "Puede ser peligroso.", "Revisad el almacén."],
)
def test_insufficient_descriptions_return_relevant_questions(text):
    provider = FakeAssessmentProvider(
        {
            "sufficient": False,
            "questions": (
                "¿Qué peligro concreto has observado?",
                "¿Hay personas expuestas actualmente?",
            ),
            "missing_aspects": ("hazard", "exposure"),
        }
    )

    result = InputAssessmentService(provider).assess(
        request(text),
        request_id="req-insufficient",
    )

    assert result.available is True
    assert result.sufficient is False
    assert 1 <= len(result.questions) <= 3


def test_three_questions_are_allowed_but_four_are_rejected():
    valid = InputAssessmentDecision(
        sufficient=False,
        questions=(
            "¿Qué peligro concreto has observado?",
            "¿Hay personas expuestas actualmente?",
            "¿Existe una señal de peligro inmediato?",
        ),
        missing_aspects=("hazard", "exposure", "immediacy"),
    )
    assert len(valid.questions) == 3

    with pytest.raises(ValidationError):
        InputAssessmentDecision(
            sufficient=False,
            questions=(*valid.questions, "¿En qué contexto ocurre?"),
            missing_aspects=valid.missing_aspects,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"sufficient": True, "questions": ("¿Qué peligro observaste?",), "missing_aspects": ()},
        {"sufficient": False, "questions": (), "missing_aspects": ("hazard",)},
        {"sufficient": False, "questions": ("¿Cuál es tu DNI?",), "missing_aspects": ("hazard",)},
        {"sufficient": False, "questions": ("¿Qué ocurrió?",), "missing_aspects": ("unknown",)},
        {"sufficient": True, "questions": (), "missing_aspects": (), "confidence": 0.9},
    ],
)
def test_invalid_or_unsafe_provider_output_becomes_unavailable(payload):
    result = InputAssessmentService(FakeAssessmentProvider(payload)).assess(
        request(),
        request_id="req-invalid",
    )

    assert result == InputAssessmentResponse(available=False, sufficient=None)


@pytest.mark.parametrize(
    "question",
    [
        "¿Cuál es tu nombre?",
        "¿Puedes facilitar un teléfono?",
        "¿Qué enfermedad tiene la persona?",
        "¿Cuál es su historial médico?",
        "¿Cuál es su nacionalidad?",
        "¿Cuál es el género de la persona?",
    ],
)
def test_provider_questions_cannot_request_sensitive_or_demographic_data(question):
    result = InputAssessmentService(
        FakeAssessmentProvider(
            {
                "sufficient": False,
                "questions": (question,),
                "missing_aspects": ("context",),
            }
        )
    ).assess(request(), request_id="req-unsafe-question")

    assert result == InputAssessmentResponse(available=False, sufficient=None)


def test_provider_failure_becomes_explicitly_unavailable():
    result = InputAssessmentService(
        FakeAssessmentProvider(error=RuntimeError("fallo sintético"))
    ).assess(request(), request_id="req-provider-error")

    assert result.available is False
    assert result.sufficient is None
    assert result.questions == ()


def test_public_response_rejects_false_success_on_technical_failure():
    with pytest.raises(ValidationError):
        InputAssessmentResponse(
            available=False,
            sufficient=True,
        )
