"""Pruebas de los contratos de revisión humana."""

import pytest
from pydantic import ValidationError

from backend.app.schemas import ReviewRequest


def test_modified_review_requires_at_least_one_corrected_field():
    with pytest.raises(ValidationError):
        ReviewRequest(
            decision="modified",
            reviewer="Técnica demo",
            comment="Corrección sintética.",
            expected_version=0,
        )


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_non_modified_review_rejects_corrected_fields(decision):
    with pytest.raises(ValidationError):
        ReviewRequest(
            decision=decision,
            reviewer="Técnica demo",
            comment="Decisión sintética.",
            expected_version=0,
            urgency="baja",
        )


@pytest.mark.parametrize("expected_version", [-1, True, 1.5])
def test_expected_version_is_non_negative_and_strict(expected_version):
    with pytest.raises(ValidationError):
        ReviewRequest(
            decision="approved",
            reviewer="Técnica demo",
            comment="Decisión sintética.",
            expected_version=expected_version,
        )
