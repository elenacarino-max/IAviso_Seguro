"""Agregación preventiva determinista sobre avisos persistidos."""

from collections import Counter, defaultdict
from collections.abc import Callable, Hashable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from backend.app.schemas import (
    CategoryAggregate,
    LocationAggregate,
    NoticeRecord,
    PendingPriorityAggregate,
    PendingPrioritySummary,
    PreventiveAnalyticsResponse,
    PreventiveHotspot,
    PreventivePeriod,
    PreventiveTimelinePoint,
    PreventiveTotals,
    PreventiveWindow,
    TimelineGranularity,
    TriageRunRecord,
    UrgencyAggregate,
)

from .location_normalization import location_display_label, normalize_location

HOTSPOT_MINIMUM = 2
TREND_MINIMUM = 3
RankKey = TypeVar("RankKey", bound=Hashable)


class PreventiveAnalyticsService:
    """Resume hechos observados sin inferencia causal ni predicción."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def summarize(
        self,
        notices: tuple[NoticeRecord, ...],
        window: PreventiveWindow,
    ) -> PreventiveAnalyticsResponse:
        now = self._aware_utc(self._clock())
        start = self._window_start(window, now)
        selected = tuple(
            notice
            for notice in notices
            if (start is None or self._aware_utc(notice.created_at) >= start)
            and self._aware_utc(notice.created_at) <= now
        )

        confirmed: list[tuple[NoticeRecord, TriageRunRecord]] = []
        pending: list[tuple[NoticeRecord, TriageRunRecord]] = []
        rejected: list[tuple[NoticeRecord, TriageRunRecord]] = []
        for notice in selected:
            run = self._latest_run(notice)
            if run is None:
                continue
            if run.status in {"approved", "modified"}:
                if run.review is not None and run.review.final_classification is not None:
                    confirmed.append((notice, run))
            elif run.status == "pending_review":
                pending.append((notice, run))
            elif run.status == "rejected":
                rejected.append((notice, run))

        location_counts: Counter[str | None] = Counter()
        location_severe: Counter[str | None] = Counter()
        category_counts: Counter[str] = Counter()
        urgency_counts: Counter[str] = Counter()
        hotspot_counts: Counter[tuple[str | None, str]] = Counter()
        hotspot_severe: Counter[tuple[str | None, str]] = Counter()

        for notice, run in confirmed:
            final = run.review.final_classification
            assert final is not None  # Garantizado al construir confirmed.
            location = normalize_location(notice.location)
            key = (location, final.category)
            location_counts[location] += 1
            category_counts[final.category] += 1
            urgency_counts[final.urgency] += 1
            hotspot_counts[key] += 1
            if final.urgency in {"alta", "critica"}:
                location_severe[location] += 1
                hotspot_severe[key] += 1

        priority_counts: Counter[str] = Counter(
            run.review_priority.level
            for _, run in pending
            if run.review_priority is not None
        )
        missing_priority = sum(run.review_priority is None for _, run in pending)

        return PreventiveAnalyticsResponse(
            period=PreventivePeriod(
                window=window,
                start_at=start,
                end_at=now,
                granularity=self._granularity(window),
            ),
            totals=PreventiveTotals(
                confirmed_notices=len(confirmed),
                pending_notices=len(pending),
                rejected_notices=len(rejected),
            ),
            pending_by_priority=PendingPrioritySummary(
                levels=tuple(
                    PendingPriorityAggregate(level=level, total=priority_counts[level])
                    for level in ("low", "medium", "high", "critical")
                ),
                policy_unavailable=missing_priority,
            ),
            by_location=tuple(
                LocationAggregate(
                    location=location_display_label(location),
                    total=total,
                    high_or_critical_urgency=location_severe[location],
                )
                for location, total in self._rank(location_counts)
            ),
            by_category=tuple(
                CategoryAggregate(category=category, total=total)
                for category, total in self._rank(category_counts)
            ),
            by_urgency=tuple(
                UrgencyAggregate(urgency=urgency, total=total)
                for urgency, total in self._rank(urgency_counts)
            ),
            location_category_hotspots=tuple(
                PreventiveHotspot(
                    location=location_display_label(location),
                    category=category,
                    total=total,
                    high_or_critical_urgency=hotspot_severe[(location, category)],
                )
                for (location, category), total in self._rank(hotspot_counts)
                if total >= HOTSPOT_MINIMUM
            ),
            timeline=self._timeline(selected, window),
            hotspot_minimum=HOTSPOT_MINIMUM,
            enough_data_for_trends=len(confirmed) >= TREND_MINIMUM,
        )

    @staticmethod
    def _latest_run(notice: NoticeRecord) -> TriageRunRecord | None:
        return max(notice.triage_runs, key=lambda run: run.created_at, default=None)

    @staticmethod
    def _rank(counter: Counter[RankKey]) -> tuple[tuple[RankKey, int], ...]:
        return tuple(
            sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
        )

    def _timeline(
        self,
        notices: tuple[NoticeRecord, ...],
        window: PreventiveWindow,
    ) -> tuple[PreventiveTimelinePoint, ...]:
        buckets: dict[str, Counter[str]] = defaultdict(Counter)
        for notice in notices:
            run = self._latest_run(notice)
            if run is None:
                continue
            if (
                run.status in {"approved", "modified"}
                and run.review is not None
                and run.review.final_classification is not None
            ):
                status = "confirmed"
            elif run.status == "pending_review":
                status = "pending"
            elif run.status == "rejected":
                status = "rejected"
            else:
                continue
            bucket = self._period_key(self._aware_utc(notice.created_at), window)
            buckets[bucket][status] += 1
        return tuple(
            PreventiveTimelinePoint(
                period=period,
                total_notices=sum(counts.values()),
                confirmed_notices=counts["confirmed"],
                pending_notices=counts["pending"],
                rejected_notices=counts["rejected"],
            )
            for period, counts in sorted(buckets.items())
        )

    @staticmethod
    def _window_start(window: PreventiveWindow, now: datetime) -> datetime | None:
        return None if window == "all" else now - timedelta(days=int(window))

    @staticmethod
    def _granularity(window: PreventiveWindow) -> TimelineGranularity:
        if window in {"7", "30"}:
            return "day"
        if window == "90":
            return "week"
        return "month"

    @staticmethod
    def _period_key(value: datetime, window: PreventiveWindow) -> str:
        if window in {"7", "30"}:
            return value.date().isoformat()
        if window == "90":
            return (value.date() - timedelta(days=value.weekday())).isoformat()
        return value.strftime("%Y-%m")

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Las fechas preventivas deben incluir zona horaria.")
        return value.astimezone(UTC)
