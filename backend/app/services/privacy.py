"""Anonimización determinista y local previa a proveedores y persistencia."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from backend.app.schemas.privacy import PrivacyMetadata, PrivacyResult, RedactionType

_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+(?![\w-])",
    re.IGNORECASE,
)
_DNI_NIE = re.compile(
    r"(?<![A-Z0-9])(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z])(?![A-Z0-9])",
    re.IGNORECASE,
)
_PHONE = re.compile(
    r"(?<![\dA-Z])(?:(?:\+34|0034)[ .-]?)?[6789](?:[ .-]?\d){8}(?![\dA-Z])",
    re.IGNORECASE,
)
# Se captura un candidato algo más largo para poder separar un IBAN formateado
# del texto que lo sigue. La validación mod-97 determina el final real y evita
# guardar o devolver el candidato encontrado.
_IBAN_CANDIDATE = re.compile(
    r"(?<![A-Z0-9])[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,50}",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SanitizedNotice:
    """Campos libres ya limpios y su único resumen público."""

    text: str
    location: str | None
    privacy: PrivacyMetadata


class PrivacyService:
    """Sustituye PII conocida por marcadores estables, sin servicios externos."""

    def sanitize(self, text: str) -> PrivacyResult:
        counts: dict[RedactionType, int] = {
            "EMAIL": 0,
            "PHONE": 0,
            "DNI_NIE": 0,
            "IBAN": 0,
        }

        sanitized = self._redact_ibans(text, counts)
        for redaction_type, pattern, placeholder in (
            ("EMAIL", _EMAIL, "[EMAIL]"),
            ("DNI_NIE", _DNI_NIE, "[DNI_NIE]"),
            ("PHONE", _PHONE, "[PHONE]"),
        ):
            sanitized = pattern.sub(
                self._replacement(counts, redaction_type, placeholder),
                sanitized,
            )

        redaction_types = tuple(
            redaction_type
            for redaction_type in ("EMAIL", "PHONE", "DNI_NIE", "IBAN")
            if counts[redaction_type] > 0
        )
        redaction_count = sum(counts.values())
        return PrivacyResult(
            sanitized_text=sanitized,
            redacted=redaction_count > 0,
            redaction_count=redaction_count,
            redaction_types=redaction_types,
        )

    def sanitize_notice(self, text: str, location: str | None) -> SanitizedNotice:
        """Aplica una única política al texto y a la ubicación libre opcional."""

        text_result = self.sanitize(text)
        location_result = self.sanitize(location) if location is not None else None
        results = (
            (text_result,)
            if location_result is None
            else (text_result, location_result)
        )
        redaction_types = tuple(
            redaction_type
            for redaction_type in ("EMAIL", "PHONE", "DNI_NIE", "IBAN")
            if any(redaction_type in result.redaction_types for result in results)
        )
        redaction_count = sum(result.redaction_count for result in results)
        return SanitizedNotice(
            text=text_result.sanitized_text,
            location=(
                location_result.sanitized_text
                if location_result is not None
                else None
            ),
            privacy=PrivacyMetadata(
                redacted=redaction_count > 0,
                redaction_count=redaction_count,
                redaction_types=redaction_types,
            ),
        )

    @staticmethod
    def _replacement(
        counts: dict[RedactionType, int],
        redaction_type: RedactionType,
        placeholder: str,
    ) -> Callable[[re.Match[str]], str]:
        def replace(_: re.Match[str]) -> str:
            counts[redaction_type] += 1
            return placeholder

        return replace

    @classmethod
    def _redact_ibans(
        cls,
        text: str,
        counts: dict[RedactionType, int],
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            candidate = match.group(0)
            end = cls._valid_iban_end(candidate)
            if end is None:
                return candidate
            counts["IBAN"] += 1
            return "[IBAN]" + candidate[end:]

        sanitized = text
        while True:
            previous_count = counts["IBAN"]
            sanitized = _IBAN_CANDIDATE.sub(replace, sanitized)
            if counts["IBAN"] == previous_count:
                return sanitized

    @classmethod
    def _valid_iban_end(cls, candidate: str) -> int | None:
        compact = ""
        for index, character in enumerate(candidate):
            if character not in " -":
                compact += character.upper()
            length = len(compact)
            if not 15 <= length <= 34:
                continue
            next_character = candidate[index + 1 : index + 2]
            # En formato compacto no se acepta como IBAN solo un prefijo de
            # otra secuencia alfanumérica más larga.
            if next_character and next_character.isalnum():
                continue
            if cls._has_valid_iban_checksum(compact):
                return index + 1
        return None

    @staticmethod
    def _has_valid_iban_checksum(compact: str) -> bool:
        if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
            return False
        rearranged = compact[4:] + compact[:4]
        numeric = "".join(
            character if character.isdigit() else str(ord(character) - 55)
            for character in rearranged
        )
        remainder = 0
        for character in numeric:
            remainder = (remainder * 10 + int(character)) % 97
        return remainder == 1
