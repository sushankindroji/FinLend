"""Notification endpoints.

GET  /api/notifications          — list notifications for the authenticated user
PATCH /api/notifications/{id}/read  — mark one notification as read
PATCH /api/notifications/read-all   — mark all notifications as read
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.serializers import serialize_doc
from app.core.security import get_current_user
from app.db.mongodb import get_db
from app.services.loan_service import oid

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query: dict = {"user_id": oid(user["id"])}
    if unread_only:
        query["read"] = False

    cursor = db.notifications.find(query).sort("created_at", -1).limit(limit)
    return [serialize_doc(n) async for n in cursor]


@router.patch("/read-all", status_code=200)
async def mark_all_read(
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    result = await db.notifications.update_many(
        {"user_id": oid(user["id"]), "read": False},
        {"$set": {"read": True}},
    )
    return {"updated": result.modified_count}


@router.patch("/{notif_id}/read", status_code=200)
async def mark_read(
    notif_id: str,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    notif = await db.notifications.find_one({"_id": oid(notif_id)})
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    if str(notif["user_id"]) != user["id"]:
        raise HTTPException(status_code=403, detail="Not your notification")

    await db.notifications.update_one({"_id": oid(notif_id)}, {"$set": {"read": True}})
    notif["read"] = True
    return serialize_doc(notif)
