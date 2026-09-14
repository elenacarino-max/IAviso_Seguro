"""Agregación determinista de métricas persistidas para el dashboard."""

from decimal import Decimal

from backend.app.schemas import (
    ComparisonProviderResult,
    ComparisonReviewRecord,
    ComparisonResponse,
    MetricsSummary,
    NoticeRecord,
    Provider,
    ProviderMetricsSummary,
    TriageRunRecord,
    UncertaintyLevel,
    UncertaintyLevelSummary,
)


class MetricsSummaryService:
    """Resume ejecuciones observadas sin inventar valores ausentes."""

    def summarize(
        self,
        notices: tuple[NoticeRecord, ...],
        comparisons: tuple[ComparisonResponse, ...] = (),
    ) -> MetricsSummary:
        runs = tuple(run for notice in notices for run in notice.triage_runs)
        comparison_runs = tuple(
            item for comparison in comparisons for item in comparison.results
        )
        pending = sum(run.status == "pending_review" for run in runs)
        approved = sum(run.status == "approved" for run in runs)
        modified = sum(run.status == "modified" for run in runs)
        rejected = sum(run.status == "rejected" for run in runs)
        reviewed = approved + modified + rejected
        policy_runs = tuple(
            run
            for run in runs
            if run.uncertainty is not None
            and run.review_priority is not None
            and run.review_policy_version is not None
        )
        return MetricsSummary(
            total_notices=len(notices),
            total_runs=len(runs) + len(comparison_runs),
            pending_review=pending,
            reviewed=reviewed,
            approved=approved,
            modified=modified,
            rejected=rejected,
            acceptance_rate=(approved / reviewed if reviewed else None),
            correction_rate=(modified / reviewed if reviewed else None),
            rejection_rate=(rejected / reviewed if reviewed else None),
            review_policy_observations=len(policy_runs),
            pending_high_priority=sum(
                run.status == "pending_review"
                and run.review_priority is not None
                and run.review_priority.level == "high"
                for run in policy_runs
            ),
            pending_critical_priority=sum(
                run.status == "pending_review"
                and run.review_priority is not None
                and run.review_priority.level == "critical"
                for run in policy_runs
            ),
            uncertainty=tuple(
                self._uncertainty_summary(level, policy_runs)
                for level in ("low", "medium", "high")
            ),
            providers=tuple(
                self._provider_summary(provider, runs, comparisons)
                for provider in ("local", "external")
            ),
        )

    @staticmethod
    def _uncertainty_summary(
        level: UncertaintyLevel,
        policy_runs: tuple[TriageRunRecord, ...],
    ) -> UncertaintyLevelSummary:
        selected = tuple(
            run
            for run in policy_runs
            if run.uncertainty is not None and run.uncertainty.level == level
        )
        reviewed = tuple(
            run for run in selected if run.status != "pending_review"
        )
        return UncertaintyLevelSummary(
            level=level,
            runs=len(selected),
            rate=(len(selected) / len(policy_runs) if policy_runs else None),
            reviewed_runs=len(reviewed),
            human_correction_rate=(
                sum(run.status == "modified" for run in reviewed) / len(reviewed)
                if reviewed
                else None
            ),
        )

    @staticmethod
    def _provider_summary(
        provider: Provider,
        runs: tuple[TriageRunRecord, ...],
        comparisons: tuple[ComparisonResponse, ...],
    ) -> ProviderMetricsSummary:
        selected = tuple(run for run in runs if run.provider == provider)
        comparison_items: tuple[
            tuple[ComparisonProviderResult, ComparisonResponse], ...
        ] = tuple(
            (item, comparison)
            for comparison in comparisons
            for item in comparison.results
            if item.provider == provider
        )
        measured = (
            tuple(run.metrics for run in selected if run.metrics is not None)
            + tuple(item.metrics for item, _ in comparison_items)
        )
        reviewed = tuple(run for run in selected if run.status != "pending_review")
        reviewed_comparisons: tuple[
            tuple[ComparisonProviderResult, ComparisonReviewRecord], ...
        ] = tuple(
            (item, review)
            for item, comparison in comparison_items
            for review in (comparison.review,)
            if review is not None
        )
        tokens = tuple(
            metrics.total_tokens
            for metrics in measured
            if metrics.total_tokens is not None
        )
        costs = tuple(
            metrics.api_cost
            for metrics in measured
            if metrics.api_cost is not None
        )
        json_valid_values = tuple(
            metrics.json_valid
            for metrics in measured
            if metrics.json_valid is not None
        )
        currencies = {
            metrics.api_cost_currency
            for metrics in measured
            if metrics.api_cost is not None and metrics.api_cost_currency is not None
        }

        def parameter_values(name: str) -> tuple[float, ...]:
            values = {
                float(value)
                for metrics in measured
                if (value := metrics.parameters.get(name)) is not None
                and not isinstance(value, bool)
            }
            return tuple(sorted(values))

        comparison_agreements = sum(
            item.result is not None
            and item.result.category == review.category
            and item.result.urgency == review.urgency
            and item.result.department == review.department
            for item, review in reviewed_comparisons
        )
        reviewed_count = len(reviewed) + len(reviewed_comparisons)

        return ProviderMetricsSummary(
            provider=provider,
            models=tuple(
                sorted(
                    {run.model for run in selected if run.model}
                    | {
                        item.metrics.model
                        for item, _ in comparison_items
                        if item.metrics.model
                    }
                )
            ),
            runs=len(selected) + len(comparison_items),
            reviewed_runs=reviewed_count,
            mean_latency_ms=(
                sum(metrics.latency_ms for metrics in measured) / len(measured)
                if measured
                else None
            ),
            mean_provider_attempts=(
                sum(metrics.provider_attempts for metrics in measured) / len(measured)
                if measured
                else None
            ),
            repair_rate=(
                sum(metrics.repair_attempts > 0 for metrics in measured)
                / len(measured)
                if measured
                else None
            ),
            mean_repair_attempts=(
                sum(metrics.repair_attempts for metrics in measured) / len(measured)
                if measured
                else None
            ),
            success_rate=(
                sum(metrics.success for metrics in measured) / len(measured)
                if measured
                else None
            ),
            json_valid_rate=(
                sum(json_valid_values) / len(json_valid_values)
                if json_valid_values
                else None
            ),
            json_valid_observations=len(json_valid_values),
            human_agreement_rate=(
                (
                    sum(run.status == "approved" for run in reviewed)
                    + comparison_agreements
                )
                / reviewed_count
                if reviewed_count
                else None
            ),
            mean_total_tokens=(sum(tokens) / len(tokens) if tokens else None),
            token_observations=len(tokens),
            mean_api_cost=(
                sum(costs, Decimal(0)) / Decimal(len(costs)) if costs else None
            ),
            api_cost_currency=(next(iter(currencies)) if len(currencies) == 1 else None),
            cost_observations=len(costs),
            temperatures=parameter_values("temperature"),
            top_p_values=parameter_values("top_p"),
        )
