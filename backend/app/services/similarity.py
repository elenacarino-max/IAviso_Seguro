"""Detección complementaria de avisos recurrentes mediante coseno."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Protocol

from backend.app.providers import EmbeddingProvider
from backend.app.schemas.similarity import (
    NoticeEmbedding,
    SimilarityMatch,
    SimilarityResult,
    StoredNoticeEmbedding,
)

from .location_normalization import normalize_location

_logger = logging.getLogger("iaviso.similarity")


class EmbeddingRepository(Protocol):
    def list_notice_embeddings(
        self,
        model: str,
    ) -> tuple[StoredNoticeEmbedding, ...]: ...


@dataclass(frozen=True, slots=True)
class SimilarityAnalysis:
    """Resultado público y vector interno que se guardarán juntos."""

    result: SimilarityResult
    embedding: NoticeEmbedding | None


class SimilarityService:
    """Genera y compara embeddings sin condicionar el triaje principal."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        enabled: bool,
        model: str,
        threshold: float,
        top_k: int,
    ) -> None:
        if isinstance(threshold, bool) or not 0 <= threshold <= 1:
            raise ValueError("threshold debe estar entre 0 y 1.")
        if isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k debe ser positivo.")
        self._provider = provider
        self._enabled = enabled
        self._model = model.strip()
        self._threshold = threshold
        self._top_k = top_k

    def analyze(
        self,
        text: str,
        location: str | None,
        repository: EmbeddingRepository,
        *,
        request_id: str,
    ) -> SimilarityAnalysis:
        if not self._enabled:
            return SimilarityAnalysis(SimilarityResult(), None)

        try:
            vector = self._provider.embed(text)
            embedding = NoticeEmbedding(
                model=self._model,
                dimensions=len(vector),
                vector=vector,
            )
        except Exception as exc:  # La capacidad es opcional y debe fallar abierta.
            self._log_unavailable(request_id, exc)
            return SimilarityAnalysis(SimilarityResult(), None)

        try:
            historical = repository.list_notice_embeddings(self._model)
            matches = self._find_matches(embedding, location, historical)
        except Exception as exc:  # Un histórico dañado tampoco bloquea el aviso.
            self._log_unavailable(request_id, exc)
            return SimilarityAnalysis(SimilarityResult(), embedding)

        result = SimilarityResult(
            available=True,
            has_similar=bool(matches),
            match_count=len(matches),
            matches=matches,
        )
        return SimilarityAnalysis(result, embedding)

    def _find_matches(
        self,
        embedding: NoticeEmbedding,
        location: str | None,
        historical: tuple[StoredNoticeEmbedding, ...],
    ) -> tuple[SimilarityMatch, ...]:
        normalized_location = normalize_location(location)
        scored: list[SimilarityMatch] = []
        for candidate in historical:
            if (
                candidate.model != embedding.model
                or candidate.dimensions != embedding.dimensions
            ):
                continue
            score = self.cosine_similarity(embedding.vector, candidate.vector)
            if score < self._threshold:
                continue
            candidate_location = normalize_location(candidate.location)
            scored.append(
                SimilarityMatch(
                    notice_id=candidate.notice_id,
                    score=round(score, 6),
                    same_location=(
                        normalized_location is not None
                        and normalized_location == candidate_location
                    ),
                    location=candidate.location,
                    created_at=candidate.created_at,
                    category=candidate.category,
                    urgency=candidate.urgency,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return tuple(scored[: self._top_k])

    @staticmethod
    def cosine_similarity(
        left: tuple[float, ...],
        right: tuple[float, ...],
    ) -> float:
        if not left or len(left) != len(right):
            raise ValueError("Los vectores deben tener la misma dimensión.")
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            raise ValueError("No se puede comparar un vector nulo.")
        raw_score = sum(a * b for a, b in zip(left, right, strict=True)) / (
            left_norm * right_norm
        )
        # Los embeddings pueden producir un coseno negativo. Para la señal
        # pública se recorta a cero; no se transforma en probabilidad.
        if math.isclose(raw_score, 1.0, rel_tol=1e-12, abs_tol=1e-12):
            return 1.0
        return min(1.0, max(0.0, raw_score))

    def _log_unavailable(self, request_id: str, exc: Exception) -> None:
        _logger.warning(
            "similarity_unavailable",
            extra={
                "request_id": request_id,
                "provider": "ollama",
                "model": self._model or None,
                "error_type": type(exc).__name__,
            },
        )
