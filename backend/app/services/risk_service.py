"""Combines the ML risk classifier with the rule-based credit score to
produce the final decision used by the loan approval flow."""
from app.ml.predict import predict_risk


def build_ml_features(user_doc: dict) -> dict:
    stats = user_doc.get("stats", {})
    return {
        "completed_loans": stats.get("completed_loans", 0),
        "on_time_repayments": stats.get("on_time_repayments", 0),
        "late_repayments": stats.get("late_repayments", 0),
        "defaults": stats.get("defaults", 0),
        "average_delay_days": stats.get("average_delay_days", 0.0),
        "total_borrowed": stats.get("total_borrowed", 0.0),
        "total_repaid": stats.get("total_repaid", 0.0),
        "repayment_ratio": (
            stats.get("total_repaid", 0.0) / stats.get("total_borrowed", 1.0)
            if stats.get("total_borrowed", 0.0) > 0 else 1.0
        ),
        "loan_duration": stats.get("avg_loan_duration", 30),
        "previous_credit_score": user_doc.get("credit_score", 500),
    }


def evaluate_borrower_risk(user_doc: dict) -> dict:
    features = build_ml_features(user_doc)
    result = predict_risk(features)
    result["features_used"] = features
    return result
