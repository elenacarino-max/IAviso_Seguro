"""Contratos persistidos para propuestas y revisión humana."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .catalogs import Category, Department, Provider, Urgency
from .triage import TriageResult

ProposalStatus = Literal["pending_review", "approved", "modified", "rejected"]
ReviewDecision = Literal["approved", "modified", "rejected"]
ReviewerName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
ReviewComment = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class WorkflowContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class ClassificationDecision(WorkflowContract):
    """Campos que un técnico puede confirmar o modificar."""

    category: Category
    urgency: Urgency
    department: Department


class ReviewRequest(WorkflowContract):
    """Decisión humana con versión esperada para control de concurrencia."""

    decision: ReviewDecision
    reviewer: ReviewerName
    comment: ReviewComment
    expected_version: int = Field(strict=True, ge=0)
    category: Category | None = None
    urgency: Urgency | None = None
    department: Department | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        changes = (self.category, self.urgency, self.department)
        if self.decision == "modified" and all(value is None for value in changes):
            raise ValueError("Una revisión modificada debe cambiar algún campo.")
        if self.decision != "modified" and any(value is not None for value in changes):
            raise ValueError(
                "Solo una revisión modificada puede incluir campos corregidos."
            )
        return self


class TriageProposalResponse(TriageResult):
    """Propuesta recién creada, siempre pendiente de revisión."""

    notice_id: UUID
    triage_run_id: UUID
    status: Literal["pending_review"]
    version: int = Field(strict=True, ge=0)
    provider: Provider
    model: str | None
    created_at: datetime


class ReviewRecord(WorkflowContract):
    id: UUID
    decision: ReviewDecision
    final_classification: ClassificationDecision | None
    comment: ReviewComment
    reviewer: ReviewerName
    created_at: datetime


class TriageRunRecord(WorkflowContract):
    id: UUID
    request_id: str
    provider: Provider
    model: str | None
    status: ProposalStatus
    version: int = Field(strict=True, ge=0)
    proposal: TriageResult
    created_at: datetime
    review: ReviewRecord | None


class NoticeRecord(WorkflowContract):
    id: UUID
    text: str
    location: str | None
    created_at: datetime
    triage_runs: tuple[TriageRunRecord, ...]


class ReviewResponse(WorkflowContract):
    notice_id: UUID
    triage_run: TriageRunRecord


class AuditEventRecord(WorkflowContract):
    id: int = Field(strict=True, ge=1)
    notice_id: UUID
    triage_run_id: UUID
    event_type: Literal["triage_created", "review_completed"]
    previous_status: ProposalStatus | None
    new_status: ProposalStatus
    actor: str | None
    created_at: datetime
