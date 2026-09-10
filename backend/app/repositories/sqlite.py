"""Persistencia SQLite transaccional para avisos y revisiones."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from backend.app.schemas import (
    AuditEventRecord,
    ClassificationDecision,
    NoticeRecord,
    ReviewRecord,
    ReviewRequest,
    ReviewResponse,
    TriageProposalResponse,
    TriageRequest,
    TriageResult,
    TriageRunRecord,
)

from .errors import NoticeNotFoundError, PersistenceError, ReviewConflictError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    location TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS triage_runs (
    id TEXT PRIMARY KEY,
    notice_id TEXT NOT NULL REFERENCES notices(id) ON DELETE RESTRICT,
    request_id TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL CHECK (provider IN ('local', 'external')),
    model TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('pending_review', 'approved', 'modified', 'rejected')
    ),
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    proposal_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    triage_run_id TEXT NOT NULL UNIQUE
        REFERENCES triage_runs(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'modified', 'rejected')),
    final_category TEXT,
    final_urgency TEXT,
    final_department TEXT,
    comment TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (
        (decision = 'rejected' AND final_category IS NULL
            AND final_urgency IS NULL AND final_department IS NULL)
        OR
        (decision IN ('approved', 'modified') AND final_category IS NOT NULL
            AND final_urgency IS NOT NULL AND final_department IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id TEXT NOT NULL REFERENCES notices(id) ON DELETE RESTRICT,
    triage_run_id TEXT NOT NULL REFERENCES triage_runs(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('triage_created', 'review_completed')
    ),
    previous_status TEXT,
    new_status TEXT NOT NULL,
    actor TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_triage_runs_notice
    ON triage_runs(notice_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_notice
    ON audit_events(notice_id, id);
"""


class SQLiteNoticeRepository:
    """Guarda propuestas originales y aplica una única revisión atómica."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._database_path = str(database_path)
        self._clock = clock or (lambda: datetime.now(UTC))
        if self._database_path != ":memory:":
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=5,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise PersistenceError("No se pudo inicializar la base de datos.") from exc

    def create_triage(
        self,
        request: TriageRequest,
        result: TriageResult,
        *,
        request_id: str,
        model: str | None,
    ) -> TriageProposalResponse:
        notice_id = uuid4()
        triage_run_id = uuid4()
        created_at = self._utc_now()
        proposal_json = result.model_dump_json()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO notices (id, text, location, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(notice_id),
                    request.text,
                    request.location,
                    created_at.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO triage_runs (
                    id, notice_id, request_id, provider, model, status,
                    version, proposal_json, created_at
                ) VALUES (?, ?, ?, ?, ?, 'pending_review', 0, ?, ?)
                """,
                (
                    str(triage_run_id),
                    str(notice_id),
                    request_id,
                    request.provider,
                    model or None,
                    proposal_json,
                    created_at.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    notice_id, triage_run_id, event_type, previous_status,
                    new_status, actor, created_at
                ) VALUES (?, ?, 'triage_created', NULL, 'pending_review', NULL, ?)
                """,
                (str(notice_id), str(triage_run_id), created_at.isoformat()),
            )
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise PersistenceError("No se pudo guardar la propuesta.") from exc
        finally:
            connection.close()

        return TriageProposalResponse(
            **result.model_dump(),
            notice_id=notice_id,
            triage_run_id=triage_run_id,
            status="pending_review",
            version=0,
            provider=request.provider,
            model=model or None,
            created_at=created_at,
        )

    def list_notices(self) -> tuple[NoticeRecord, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        n.id AS notice_id,
                        n.text AS notice_text,
                        n.location AS notice_location,
                        n.created_at AS notice_created_at,
                        tr.id AS run_id,
                        tr.request_id,
                        tr.provider,
                        tr.model,
                        tr.status,
                        tr.version,
                        tr.proposal_json,
                        tr.created_at AS run_created_at,
                        r.id AS review_id,
                        r.decision,
                        r.final_category,
                        r.final_urgency,
                        r.final_department,
                        r.comment,
                        r.reviewer,
                        r.created_at AS review_created_at
                    FROM notices AS n
                    JOIN triage_runs AS tr ON tr.notice_id = n.id
                    LEFT JOIN reviews AS r ON r.triage_run_id = tr.id
                    ORDER BY n.created_at DESC, tr.created_at DESC
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("No se pudieron consultar los avisos.") from exc

        try:
            grouped: dict[str, dict[str, object]] = {}
            for row in rows:
                notice_id = cast(str, row["notice_id"])
                notice = grouped.setdefault(
                    notice_id,
                    {
                        "id": UUID(notice_id),
                        "text": row["notice_text"],
                        "location": row["notice_location"],
                        "created_at": datetime.fromisoformat(
                            row["notice_created_at"]
                        ),
                        "triage_runs": [],
                    },
                )
                runs = cast(list[TriageRunRecord], notice["triage_runs"])
                runs.append(self._run_from_row(row))

            return tuple(
                NoticeRecord(
                    id=cast(UUID, item["id"]),
                    text=cast(str, item["text"]),
                    location=cast(str | None, item["location"]),
                    created_at=cast(datetime, item["created_at"]),
                    triage_runs=tuple(
                        cast(list[TriageRunRecord], item["triage_runs"])
                    ),
                )
                for item in grouped.values()
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PersistenceError("Los avisos guardados son inválidos.") from exc

    def review_notice(
        self,
        notice_id: UUID,
        review: ReviewRequest,
    ) -> ReviewResponse:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT id, request_id, provider, model, status, version,
                       proposal_json, created_at
                FROM triage_runs
                WHERE notice_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (str(notice_id),),
            ).fetchone()
            if row is None:
                raise NoticeNotFoundError("El aviso solicitado no existe.")
            if row["status"] != "pending_review":
                raise ReviewConflictError("La propuesta ya fue revisada.")
            if row["version"] != review.expected_version:
                raise ReviewConflictError("La versión de la propuesta ha cambiado.")

            proposal = TriageResult.model_validate_json(row["proposal_json"])
            final = self._final_classification(proposal, review)
            original = ClassificationDecision(
                category=proposal.category,
                urgency=proposal.urgency,
                department=proposal.department,
            )
            if review.decision == "modified" and final == original:
                raise ReviewConflictError(
                    "La revisión modificada no cambia la clasificación."
                )
            new_version = review.expected_version + 1
            updated = connection.execute(
                """
                UPDATE triage_runs
                SET status = ?, version = ?
                WHERE id = ? AND status = 'pending_review' AND version = ?
                """,
                (review.decision, new_version, row["id"], review.expected_version),
            )
            if updated.rowcount != 1:
                raise ReviewConflictError("La propuesta cambió durante la revisión.")

            review_id = uuid4()
            created_at = self._utc_now()
            final_values = (
                (None, None, None)
                if final is None
                else (final.category, final.urgency, final.department)
            )
            connection.execute(
                """
                INSERT INTO reviews (
                    id, triage_run_id, decision, final_category, final_urgency,
                    final_department, comment, reviewer, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(review_id),
                    row["id"],
                    review.decision,
                    *final_values,
                    review.comment,
                    review.reviewer,
                    created_at.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    notice_id, triage_run_id, event_type, previous_status,
                    new_status, actor, created_at
                ) VALUES (?, ?, 'review_completed', 'pending_review', ?, ?, ?)
                """,
                (
                    str(notice_id),
                    row["id"],
                    review.decision,
                    review.reviewer,
                    created_at.isoformat(),
                ),
            )
            connection.commit()
        except (NoticeNotFoundError, ReviewConflictError):
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ReviewConflictError("La propuesta ya fue revisada.") from exc
        except sqlite3.Error as exc:
            connection.rollback()
            raise PersistenceError("No se pudo guardar la revisión.") from exc
        except (TypeError, ValueError) as exc:
            connection.rollback()
            raise PersistenceError("La propuesta guardada es inválida.") from exc
        finally:
            connection.close()

        record = ReviewRecord(
            id=review_id,
            decision=review.decision,
            final_classification=final,
            comment=review.comment,
            reviewer=review.reviewer,
            created_at=created_at,
        )
        return ReviewResponse(
            notice_id=notice_id,
            triage_run=TriageRunRecord(
                id=UUID(row["id"]),
                request_id=row["request_id"],
                provider=row["provider"],
                model=row["model"],
                status=review.decision,
                version=new_version,
                proposal=proposal,
                created_at=datetime.fromisoformat(row["created_at"]),
                review=record,
            ),
        )

    def list_audit_events(self, notice_id: UUID) -> tuple[AuditEventRecord, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, notice_id, triage_run_id, event_type,
                           previous_status, new_status, actor, created_at
                    FROM audit_events
                    WHERE notice_id = ?
                    ORDER BY id
                    """,
                    (str(notice_id),),
                ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("No se pudo consultar la auditoría.") from exc
        return tuple(
            AuditEventRecord(
                id=row["id"],
                notice_id=UUID(row["notice_id"]),
                triage_run_id=UUID(row["triage_run_id"]),
                event_type=row["event_type"],
                previous_status=row["previous_status"],
                new_status=row["new_status"],
                actor=row["actor"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        )

    @staticmethod
    def _final_classification(
        proposal: TriageResult,
        review: ReviewRequest,
    ) -> ClassificationDecision | None:
        if review.decision == "rejected":
            return None
        return ClassificationDecision(
            category=review.category or proposal.category,
            urgency=review.urgency or proposal.urgency,
            department=review.department or proposal.department,
        )

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> TriageRunRecord:
        review = None
        if row["review_id"] is not None:
            final = None
            if row["final_category"] is not None:
                final = ClassificationDecision(
                    category=row["final_category"],
                    urgency=row["final_urgency"],
                    department=row["final_department"],
                )
            review = ReviewRecord(
                id=UUID(row["review_id"]),
                decision=row["decision"],
                final_classification=final,
                comment=row["comment"],
                reviewer=row["reviewer"],
                created_at=datetime.fromisoformat(row["review_created_at"]),
            )
        return TriageRunRecord(
            id=UUID(row["run_id"]),
            request_id=row["request_id"],
            provider=row["provider"],
            model=row["model"],
            status=row["status"],
            version=row["version"],
            proposal=TriageResult.model_validate_json(row["proposal_json"]),
            created_at=datetime.fromisoformat(row["run_created_at"]),
            review=review,
        )

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "El reloj del repositorio debe devolver una fecha con zona."
            )
        return value.astimezone(UTC)
