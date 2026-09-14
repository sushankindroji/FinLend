"""Behavioral credit-scoring engine (req #7A) and borrowing-limit mapper (req #8).

This is intentionally deterministic and rule-based, separate from the
scikit-learn risk classifier in app/ml. The two are combined in
app/services/risk_service.py to produce the final credit_score + risk_category
exposed to the API.
"""
from app.core.config import CREDIT_SCORE_CONFIG, BORROWING_LIMIT_TIERS


def clamp_score(score: float) -> int:
    lo = CREDIT_SCORE_CONFIG["min_score"]
    hi = CREDIT_SCORE_CONFIG["max_score"]
    return int(max(lo, min(hi, round(score))))


def initial_score() -> int:
    return CREDIT_SCORE_CONFIG["base_score"]


def apply_event(current_score: int, event: str) -> int:
    """event in {on_time_repayment, completed_loan, early_repayment, late_repayment, default}"""
    if event not in CREDIT_SCORE_CONFIG:
        raise ValueError(f"Unknown credit scoring event: {event}")
    delta = CREDIT_SCORE_CONFIG[event]
    return clamp_score(current_score + delta)


def score_for_repayment(current_score: int, *, is_early: bool, is_on_time: bool, is_default: bool) -> tuple[int, list[str]]:
    """Apply the correct combination of events for a single repayment outcome.

    Returns (new_score, applied_events)
    """
    score = current_score
    applied = []
    if is_default:
        score = apply_event(score, "default")
        applied.append("default")
        return score, applied

    if is_on_time:
        score = apply_event(score, "on_time_repayment")
        applied.append("on_time_repayment")
        if is_early:
            score = apply_event(score, "early_repayment")
            applied.append("early_repayment")
    else:
        score = apply_event(score, "late_repayment")
        applied.append("late_repayment")

    return score, applied


def score_for_loan_completion(current_score: int) -> tuple[int, list[str]]:
    score = apply_event(current_score, "completed_loan")
    return score, ["completed_loan"]


def borrowing_limit_for_score(score: int) -> float:
    for lo, hi, limit in BORROWING_LIMIT_TIERS:
        if lo <= score <= hi:
            return float(limit)
    # Fallback: below lowest tier -> lowest limit, above highest -> highest limit
    if score < BORROWING_LIMIT_TIERS[0][0]:
        return float(BORROWING_LIMIT_TIERS[0][2])
    return float(BORROWING_LIMIT_TIERS[-1][2])
