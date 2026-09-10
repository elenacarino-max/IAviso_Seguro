"""Consulta de avisos y revisión humana de propuestas."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import (
    ErrorResponse,
    NoticeRecord,
    ReviewRequest,
    ReviewResponse,
)

from .routes_triage import get_notice_repository

router = APIRouter(prefix="/api/v1/notices", tags=["notices"])


@router.get("", response_model=list[NoticeRecord])
def list_notices(
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
) -> tuple[NoticeRecord, ...]:
    return repository.list_notices()


@router.post(
    "/{notice_id}/reviews",
    response_model=ReviewResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Aviso no encontrado"},
        409: {"model": ErrorResponse, "description": "Revisión en conflicto"},
        500: {"model": ErrorResponse, "description": "Error de persistencia"},
    },
)
def review_notice(
    notice_id: UUID,
    payload: ReviewRequest,
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
) -> ReviewResponse:
    return repository.review_notice(notice_id, payload)
