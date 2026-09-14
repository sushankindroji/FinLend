"""Shared feature processing so training and inference stay in sync."""
import pandas as pd

from app.ml.generate_synthetic_data import FEATURE_COLUMNS

__all__ = ["FEATURE_COLUMNS", "build_feature_frame"]


def build_feature_frame(record: dict) -> pd.DataFrame:
    """Build a single-row DataFrame with the correct column order/types
    from a raw feature dict (as produced by the borrower's live loan
    history in the backend).
    """
    row = {col: record.get(col, 0) for col in FEATURE_COLUMNS}
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)
