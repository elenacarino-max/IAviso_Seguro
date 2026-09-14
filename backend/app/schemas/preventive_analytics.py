"""Contratos estrictos del análisis preventivo histórico."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .catalogs import Category, Urgency
from .review_policy import ReviewPriorityLevel

PreventiveWindow = Literal["7", "30", "90", "all"]
TimelineGranularity = Literal["day", "week", "month"]


class PreventiveAnalyticsContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class PreventivePeriod(PreventiveAnalyticsContract):
    window: PreventiveWindow
    start_at: datetime | None
    end_at: datetime
    granularity: TimelineGranularity


class PreventiveTotals(PreventiveAnalyticsContract):
    confirmed_notices: int = Field(strict=True, ge=0)
    pending_notices: int = Field(strict=True, ge=0)
    rejected_notices: int = Field(strict=True, ge=0)


class LocationAggregate(PreventiveAnalyticsContract):
    location: str
    total: int = Field(strict=True, ge=1)
    high_or_critical_urgency: int = Field(strict=True, ge=0)


class CategoryAggregate(PreventiveAnalyticsContract):
    category: Category
    total: int = Field(strict=True, ge=1)


class UrgencyAggregate(PreventiveAnalyticsContract):
    urgency: Urgency
    total: int = Field(strict=True, ge=1)


class PreventiveHotspot(PreventiveAnalyticsContract):
    location: str
    category: Category
    total: int = Field(strict=True, ge=2)
    high_or_critical_urgency: int = Field(strict=True, ge=0)


class PendingPriorityAggregate(PreventiveAnalyticsContract):
    level: ReviewPriorityLevel
    total: int = Field(strict=True, ge=0)


class PendingPrioritySummary(PreventiveAnalyticsContract):
    levels: tuple[PendingPriorityAggregate, ...]
    policy_unavailable: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def require_all_priority_levels(self) -> Self:
        if (
            len(self.levels) != 4
            or {item.level for item in self.levels}
            != {"low", "medium", "high", "critical"}
        ):
            raise ValueError("Deben incluirse los cuatro niveles de prioridad.")
        return self


class PreventiveTimelinePoint(PreventiveAnalyticsContract):
    period: str
    total_notices: int = Field(strict=True, ge=1)
    confirmed_notices: int = Field(strict=True, ge=0)
    pending_notices: int = Field(strict=True, ge=0)
    rejected_notices: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def total_must_match_statuses(self) -> Self:
        if self.total_notices != (
            self.confirmed_notices + self.pending_notices + self.rejected_notices
        ):
            raise ValueError("El total temporal debe coincidir con sus estados.")
        return self


class PreventiveAnalyticsResponse(PreventiveAnalyticsContract):
    period: PreventivePeriod
    totals: PreventiveTotals
    pending_by_priority: PendingPrioritySummary
    by_location: tuple[LocationAggregate, ...]
    by_category: tuple[CategoryAggregate, ...]
    by_urgency: tuple[UrgencyAggregate, ...]
    location_category_hotspots: tuple[PreventiveHotspot, ...]
    timeline: tuple[PreventiveTimelinePoint, ...]
    hotspot_minimum: Literal[2] = 2
    enough_data_for_trends: bool

