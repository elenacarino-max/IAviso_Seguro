"""Contratos públicos de anonimización sin conservar datos personales."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RedactionType = Literal["EMAIL", "PHONE", "DNI_NIE", "IBAN"]


class PrivacyContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class PrivacyMetadata(PrivacyContract):
    """Resumen seguro que puede devolverse al cliente y registrarse."""

    redacted: bool = False
    redaction_count: int = Field(default=0, strict=True, ge=0)
    redaction_types: tuple[RedactionType, ...] = ()

    @model_validator(mode="after")
    def require_consistent_summary(self):
        if self.redacted != (self.redaction_count > 0):
            raise ValueError("El indicador de anonimización no coincide con el recuento.")
        if self.redacted != bool(self.redaction_types):
            raise ValueError("Los tipos de anonimización no coinciden con el indicador.")
        if len(self.redaction_types) != len(set(self.redaction_types)):
            raise ValueError("Los tipos de anonimización deben ser únicos.")
        return self


class PrivacyResult(PrivacyContract):
    """Resultado interno; deliberadamente no incluye las coincidencias originales."""

    sanitized_text: str
    redacted: bool
    redaction_count: int = Field(strict=True, ge=0)
    redaction_types: tuple[RedactionType, ...]

    @model_validator(mode="after")
    def require_consistent_result(self):
        PrivacyMetadata(
            redacted=self.redacted,
            redaction_count=self.redaction_count,
            redaction_types=self.redaction_types,
        )
        return self

    def metadata(self) -> PrivacyMetadata:
        """Descarta el texto y expone solo estadísticas no sensibles."""

        return PrivacyMetadata(
            redacted=self.redacted,
            redaction_count=self.redaction_count,
            redaction_types=self.redaction_types,
        )
