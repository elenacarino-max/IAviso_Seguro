"""Pruebas del filtro local sin exponer los datos que encuentra."""

import pytest

from backend.app.services import PrivacyService


@pytest.fixture
def privacy_service() -> PrivacyService:
    return PrivacyService()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Escribir a juan.perez+prl@example.com.", "Escribir a [EMAIL]."),
        ("Llamar al +34 612 345 678.", "Llamar al [PHONE]."),
        ("DNI 12345678Z.", "DNI [DNI_NIE]."),
        ("NIE X1234567L.", "NIE [DNI_NIE]."),
        (
            "Cuenta ES91 2100 0418 4502 0005 1332 para el aviso.",
            "Cuenta [IBAN] para el aviso.",
        ),
    ],
)
def test_sanitize_supported_personal_data(
    privacy_service: PrivacyService,
    text: str,
    expected: str,
):
    result = privacy_service.sanitize(text)

    assert result.sanitized_text == expected
    assert result.redacted is True
    assert result.redaction_count == 1
    assert len(result.redaction_types) == 1


def test_sanitize_multiple_values_uses_stable_placeholders(
    privacy_service: PrivacyService,
):
    text = (
        "DNI 12345678Z, email juan@email.com, teléfono 612-345-678 "
        "e IBAN GB82 WEST 1234 5698 7654 32."
    )

    result = privacy_service.sanitize(text)

    assert result.sanitized_text == (
        "DNI [DNI_NIE], email [EMAIL], teléfono [PHONE] e IBAN [IBAN]."
    )
    assert result.redaction_count == 4
    assert result.redaction_types == ("EMAIL", "PHONE", "DNI_NIE", "IBAN")


def test_sanitize_text_without_pii_is_unchanged(
    privacy_service: PrivacyService,
):
    text = "Hay agua derramada junto a la salida del almacén."

    result = privacy_service.sanitize(text)

    assert result.sanitized_text == text
    assert result.redacted is False
    assert result.redaction_count == 0
    assert result.redaction_types == ()


def test_privacy_result_never_contains_original_values(
    privacy_service: PrivacyService,
):
    originals = ("12345678Z", "juan@email.com", "612345678")
    result = privacy_service.sanitize(" · ".join(originals))

    serialized_result = result.model_dump_json()
    serialized_metadata = result.metadata().model_dump_json()
    assert all(value not in serialized_result for value in originals)
    assert all(value not in serialized_metadata for value in originals)
    assert set(type(result).model_fields) == {
        "sanitized_text",
        "redacted",
        "redaction_count",
        "redaction_types",
    }
