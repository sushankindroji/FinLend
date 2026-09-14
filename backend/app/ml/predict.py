"""Prediction service wrapping the trained scikit-learn model.

If no trained model artifact is present yet (fresh clone before running
`python -m app.ml.train_model`), falls back to a transparent rule-based
heuristic so the API never crashes -- this fallback is clearly labeled
in the response explanation, honoring req #59 (no faked ML accuracy).
"""
import os
from typing import Optional

import joblib

from app.ml.feature_engineering import build_feature_frame

_ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "risk_model.joblib")

_cached_bundle: Optional[dict] = None


def _load_bundle() -> Optional[dict]:
    global _cached_bundle
    if _cached_bundle is not None:
        return _cached_bundle
    if os.path.exists(_ARTIFACT_PATH):
        _cached_bundle = joblib.load(_ARTIFACT_PATH)
    return _cached_bundle


def _heuristic_risk(features: dict) -> tuple[str, str]:
    defaults = features.get("defaults", 0)
    late = features.get("late_repayments", 0)
    completed = features.get("completed_loans", 0)
    ratio = features.get("repayment_ratio", 1.0)

    if defaults >= 1 or ratio < 0.6:
        return "HIGH", "Heuristic fallback (model not yet trained): prior default(s) or low repayment ratio."
    if late >= 2 or ratio < 0.9:
        return "MEDIUM", "Heuristic fallback (model not yet trained): some late repayments observed."
    if completed == 0:
        return "MEDIUM", "Heuristic fallback (model not yet trained): new borrower, insufficient history."
    return "LOW", "Heuristic fallback (model not yet trained): consistent on-time repayment history."


def predict_risk(features: dict) -> dict:
    """Return {risk_category, confidence, explanation, model_used}."""
    bundle = _load_bundle()
    if bundle is None:
        category, explanation = _heuristic_risk(features)
        return {
            "risk_category": category,
            "confidence": None,
            "explanation": explanation,
            "model_used": "heuristic_fallback",
        }

    model = bundle["model"]
    X = build_feature_frame(features)
    proba = model.predict_proba(X)[0]
    classes = list(model.classes_)
    pred = model.predict(X)[0]
    confidence = float(max(proba))

    top_features = sorted(
        zip(X.columns, model.feature_importances_), key=lambda t: -t[1]
    )[:3]
    top_feat_names = ", ".join(f for f, _ in top_features)

    explanation = (
        f"RandomForest classifier predicted {pred} risk with {confidence:.0%} "
        f"confidence, most influenced by: {top_feat_names}."
    )
    return {
        "risk_category": pred,
        "confidence": confidence,
        "explanation": explanation,
        "model_used": "random_forest",
        "class_probabilities": dict(zip(classes, proba.tolist())),
    }
