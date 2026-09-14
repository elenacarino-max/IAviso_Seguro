"""Consulta de avisos y revisión humana de propuestas."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import (
    AuditEventRecord,
    Category,
    ErrorResponse,
    NoticePage,
    NoticeOrder,
    ProposalStatus,
    Provider,
    ReviewRequest,
    ReviewResponse,
    ReviewPriorityLevel,
    Urgency,
)

from .routes_triage import get_notice_repository

router = APIRouter(prefix="/api/v1/notices", tags=["notices"])


@router.get("", response_model=NoticePage)
def list_notices(
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
    search: Annotated[str | None, Query(max_length=200)] = None,
    status: ProposalStatus | None = None,
    closed: Annotated[
        bool | None,
        Query(
            description=(
                "true devuelve decisiones cerradas; false devuelve propuestas "
                "pendientes"
            )
        ),
    ] = None,
    urgency: Urgency | None = None,
    provider: Provider | None = None,
    category: Category | None = None,
    review_priority: ReviewPriorityLevel | None = None,
    order: NoticeOrder = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NoticePage:
    return repository.query_notices(
        search=search,
        status=status,
        closed=closed,
        urgency=urgency,
        provider=provider,
        category=category,
        review_priority=review_priority,
        order=order,
        page=page,
        limit=limit,
    )


@router.get(
    "/{notice_id}/audit-events",
    response_model=list[AuditEventRecord],
    responses={404: {"model": ErrorResponse, "description": "Aviso no encontrado"}},
)
def list_notice_audit_events(
    notice_id: UUID,
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
) -> tuple[AuditEventRecord, ...]:
    return repository.list_audit_events(notice_id)


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
