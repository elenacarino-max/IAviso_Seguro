"""Las tres demos de cierre son ejecutables y completamente sintéticas."""

from scripts.run_demos import (
    run_main_demo,
    run_rate_limit_demo,
    run_repair_demo,
)


def test_main_demo_creates_lists_and_humanly_approves_proposal():
    result = run_main_demo()

    assert result == {
        "scenario": "main",
        "created_status": "pending_review",
        "listed_notices": 1,
        "reviewed_status": "approved",
        "proposal_preserved": True,
        "human_validation_required": True,
    }


def test_invalid_output_demo_repairs_once():
    result = run_repair_demo()

    assert result["success"] is True
    assert result["provider_attempts"] == 3
    assert result["repair_attempts"] == 1
    assert result["json_valid"] is True


def test_rate_limit_demo_applies_retry_after_and_recovers():
    result = run_rate_limit_demo()

    assert result["recovered"] is True
    assert result["provider_attempts"] == 2
    assert result["backoff_seconds"] == [2]
    assert result["retry_after_respected"] is True
