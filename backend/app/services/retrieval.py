"""Recuperación local, determinista y trazable de evidencia preventiva."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from backend.app.schemas import (
    Category,
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeEvidence,
)

from .errors import InvalidKnowledgeBaseError

DEFAULT_KNOWLEDGE_BASE_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "knowledge"
    / "prevention_docs.v1.json"
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "al",
        "con",
        "de",
        "del",
        "el",
        "en",
        "es",
        "hay",
        "la",
        "las",
        "lo",
        "los",
        "para",
        "por",
        "que",
        "se",
        "sin",
        "un",
        "una",
        "y",
    }
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_PATTERN.findall(_normalize(value))
        if token not in _STOP_WORDS and len(token) > 1
    }


class PreventionKnowledgeRetriever:
    """Selecciona fragmentos por categoría y coincidencia léxica ponderada."""

    def __init__(
        self,
        knowledge_base_path: str | Path = DEFAULT_KNOWLEDGE_BASE_PATH,
        *,
        max_sources: int = 2,
    ) -> None:
        if isinstance(max_sources, bool) or not 1 <= max_sources <= 5:
            raise ValueError("max_sources debe estar entre 1 y 5.")
        self._path = Path(knowledge_base_path)
        self._max_sources = max_sources
        self._document: KnowledgeBase | None = None
        self._load_lock = Lock()

    def document(self) -> KnowledgeBase:
        """Carga una sola vez el corpus, también bajo comparaciones concurrentes."""

        if self._document is None:
            # Los dos proveedores comparten el recuperador. El bloqueo evita
            # validar el mismo archivo dos veces en el primer acceso paralelo.
            with self._load_lock:
                if self._document is None:
                    self._document = self._load()
        return self._document

    def retrieve(
        self,
        text: str,
        *,
        category: Category,
    ) -> tuple[KnowledgeEvidence, ...]:
        """Preselecciona la categoría antes de puntuar para evitar fugas temáticas."""

        knowledge_base = self.document()
        query_tokens = _tokens(text)
        candidates = [
            document
            for document in knowledge_base.documents
            if category in document.categories
        ]
        ranked = sorted(
            (
                (self._score(document, query_tokens, text), document)
                for document in candidates
            ),
            key=lambda item: (-item[0], item[1].source_id),
        )
        return tuple(
            KnowledgeEvidence(
                source_id=document.source_id,
                title=document.title,
                section=document.section,
                category=category,
                excerpt=document.content,
                source_type="preventive_document",
                version=knowledge_base.version,
                score=score,
            )
            for score, document in ranked[: self._max_sources]
        )

    def _load(self) -> KnowledgeBase:
        try:
            return KnowledgeBase.model_validate_json(
                self._path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise InvalidKnowledgeBaseError(
                "El corpus preventivo no está disponible o es inválido."
            ) from exc

    @staticmethod
    def _score(
        document: KnowledgeDocument,
        query_tokens: set[str],
        raw_query: str,
    ) -> float:
        keyword_tokens = _tokens(" ".join(document.keywords))
        heading_tokens = _tokens(f"{document.title} {document.section}")
        content_tokens = _tokens(document.content)
        normalized_query = _normalize(raw_query)
        phrase_hits = sum(
            _normalize(keyword) in normalized_query
            for keyword in document.keywords
        )
        score = (
            1
            + 4 * len(query_tokens & keyword_tokens)
            + 2 * len(query_tokens & heading_tokens)
            + len(query_tokens & content_tokens)
            + 3 * phrase_hits
        )
        return float(score)
