"""Notification service — creates and manages in-app notifications.

Notifications are lightweight MongoDB documents written by backend services
whenever meaningful loan lifecycle events occur (approval, funding, repayment,
late status, etc.).  The frontend polls GET /api/notifications to display them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

VALID_TYPES = {
    "LOAN_APPROVED", "LOAN_REJECTED", "LOAN_FUNDED", "LOAN_ACTIVE",
    "REPAYMENT_RECEIVED", "LOAN_REPAID", "LOAN_LATE", "LOAN_DEFAULTED",
    "CREDIT_UPDATED", "AUTO_INVEST", "SYSTEM",
}


async def emit_notification(
    db: AsyncIOMotorDatabase,
    *,
    user_id: str,
    notif_type: str,
    title: str,
    body: str,
    loan_id: Optional[str] = None,
) -> dict:
    """Insert a notification document and return it."""
    from bson import ObjectId
    if notif_type not in VALID_TYPES:
        notif_type = "SYSTEM"

    doc = {
        "user_id": ObjectId(user_id),
        "type": notif_type,
        "title": title,
        "body": body,
        "loan_id": ObjectId(loan_id) if loan_id else None,
        "read": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.notifications.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc
