"""Helpers to serialize Mongo documents into API-friendly dicts.

Improvements over v1:
- Handles *any* ObjectId field safely (not just a fixed named set)
- Converts datetime objects to ISO strings for JSON-safe output
- Preserves None values correctly
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId


def _convert_value(v: Any) -> Any:
    """Recursively convert non-JSON-serializable values."""
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, datetime):
        # Return timezone-aware ISO string; keep None as None
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _convert_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_convert_value(item) for item in v]
    return v


def serialize_doc(doc: dict | None) -> dict | None:
    """Convert a MongoDB document to an API-safe dict.

    - ``_id`` is renamed to ``id`` (string)
    - All ObjectId values (including nested) are converted to strings
    - All datetime values are converted to ISO-format strings
    - Named ObjectId fields (borrower_id, lender_id, etc.) get string conversion
    """
    if doc is None:
        return None

    out: dict = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        else:
            out[k] = _convert_value(v)

    return out
