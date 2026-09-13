"""Pruebas deterministas de similitud sin depender de Ollama."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from backend.app.schemas import StoredNoticeEmbedding
from backend.app.services import SimilarityService

NOW = datetime(2026, 9, 13, 10, tzinfo=UTC)


class FakeEmbeddingProvider:
    def __init__(self, vector=(1.0, 0.0), error: Exception | None = None):
        self.vector = vector
        self.error = error
        self.received: list[str] = []

    def embed(self, text: str):
        self.received.append(text)
        if self.error is not None:
            raise self.error
        return self.vector


class FakeEmbeddingRepository:
    def __init__(self, candidates=()):
        self.candidates = candidates
        self.requested_models: list[str] = []

    def list_notice_embeddings(self, model: str):
        self.requested_models.append(model)
        return self.candidates


def candidate(
    identifier: int,
    vector: tuple[float, ...],
    *,
    model: str = "embed-test",
    location: str | None = "Almacén",
):
    return StoredNoticeEmbedding(
        notice_id=UUID(int=identifier),
        model=model,
        dimensions=len(vector),
        vector=vector,
        location=location,
        created_at=NOW,
        category="riesgo_electrico",
        urgency="alta",
    )


def service(provider, *, threshold=0.5, top_k=3, enabled=True):
    return SimilarityService(
        provider,
        enabled=enabled,
        model="embed-test",
        threshold=threshold,
        top_k=top_k,
    )


def test_cosine_similarity_identical_and_different_vectors():
    assert SimilarityService.cosine_similarity((1.0, 2.0), (1.0, 2.0)) == 1
    assert SimilarityService.cosine_similarity((1.0, 0.0), (0.0, 1.0)) == 0


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ((), ()),
        ((1.0,), (1.0, 2.0)),
        ((0.0, 0.0), (1.0, 0.0)),
    ],
)
def test_cosine_rejects_invalid_or_incompatible_vectors(left, right):
    with pytest.raises(ValueError):
        SimilarityService.cosine_similarity(left, right)


def test_matches_are_sorted_filtered_and_limited():
    repository = FakeEmbeddingRepository(
        (
            candidate(1, (0.6, 0.8)),
            candidate(2, (1.0, 0.0)),
            candidate(3, (0.8, 0.6)),
            candidate(4, (0.0, 1.0)),
        )
    )

    analysis = service(
        FakeEmbeddingProvider(),
        threshold=0.7,
        top_k=2,
    ).analyze("Cable en pasillo", "Almacén", repository, request_id="req-1")

    assert analysis.result.available is True
    assert [match.notice_id.int for match in analysis.result.matches] == [2, 3]
    assert [match.score for match in analysis.result.matches] == [1, 0.8]
    assert analysis.result.match_count == 2


def test_incompatible_model_and_dimensions_are_ignored():
    repository = FakeEmbeddingRepository(
        (
            candidate(1, (1.0, 0.0), model="another-model"),
            candidate(2, (1.0, 0.0, 0.0)),
        )
    )

    result = service(FakeEmbeddingProvider()).analyze(
        "Aviso",
        None,
        repository,
        request_id="req-2",
    ).result

    assert result.available is True
    assert result.has_similar is False
    assert result.matches == ()


@pytest.mark.parametrize("location", ["Almacén", "almacén", " ALMACÉN "])
def test_location_normalization_detects_the_same_zone(location):
    result = service(FakeEmbeddingProvider()).analyze(
        "Aviso",
        location,
        FakeEmbeddingRepository((candidate(1, (1.0, 0.0)),)),
        request_id="req-3",
    ).result

    assert result.matches[0].same_location is True


def test_no_history_is_available_without_matches():
    analysis = service(FakeEmbeddingProvider()).analyze(
        "Primer aviso",
        None,
        FakeEmbeddingRepository(),
        request_id="req-4",
    )

    assert analysis.result.available is True
    assert analysis.result.match_count == 0
    assert analysis.embedding is not None


@pytest.mark.parametrize(
    "provider",
    [
        FakeEmbeddingProvider(vector=()),
        FakeEmbeddingProvider(vector=(0.0, 0.0)),
        FakeEmbeddingProvider(error=RuntimeError("fallo sintético")),
    ],
)
def test_invalid_vector_or_provider_failure_is_non_blocking(provider):
    analysis = service(provider).analyze(
        "Aviso",
        None,
        FakeEmbeddingRepository(),
        request_id="req-5",
    )

    assert analysis.result.available is False
    assert analysis.embedding is None


def test_disabled_similarity_does_not_call_provider():
    provider = FakeEmbeddingProvider()

    analysis = service(provider, enabled=False).analyze(
        "Aviso",
        None,
        FakeEmbeddingRepository(),
        request_id="req-6",
    )

    assert analysis.result.available is False
    assert provider.received == []
