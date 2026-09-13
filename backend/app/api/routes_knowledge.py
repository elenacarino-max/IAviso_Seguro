"""Inventario público del corpus preventivo utilizado por el RAG."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.settings import get_settings
from backend.app.schemas import KnowledgeBaseSummary
from backend.app.services import PreventionKnowledgeRetriever

router = APIRouter(prefix="/api/v1", tags=["knowledge-base"])


@lru_cache
def get_knowledge_retriever() -> PreventionKnowledgeRetriever:
    """Construye un recuperador sobre el corpus configurado en el backend."""

    settings = get_settings()
    return PreventionKnowledgeRetriever(
        settings.knowledge_base_path,
        max_sources=settings.rag_max_sources,
    )


@router.get("/knowledge-base", response_model=KnowledgeBaseSummary)
def get_knowledge_base(
    retriever: Annotated[
        PreventionKnowledgeRetriever,
        Depends(get_knowledge_retriever),
    ],
) -> KnowledgeBaseSummary:
    """Expone versión y fuentes, pero no los fragmentos enviados al modelo."""

    return retriever.summary()
