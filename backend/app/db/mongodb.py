"""Async MongoDB connection manager (Motor) + index bootstrap."""
from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

logger = logging.getLogger("finlend.db")


class Database:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


database = Database()


async def connect_to_mongo() -> None:
    settings = get_settings()
    database.client = AsyncIOMotorClient(settings.mongodb_uri)
    database.db = database.client[settings.mongodb_database]
    await ensure_indexes(database.db)
    logger.info("Connected to MongoDB at %s / db=%s", settings.mongodb_uri, settings.mongodb_database)


async def close_mongo_connection() -> None:
    if database.client:
        database.client.close()
        logger.info("MongoDB connection closed")


def get_db() -> AsyncIOMotorDatabase:
    if database.db is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo() first.")
    return database.db


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index("email", unique=True)
    await db.users.create_index("role")
    await db.loans.create_index("borrower_id")
    await db.loans.create_index("status")
    await db.loan_fundings.create_index("loan_id")
    await db.loan_fundings.create_index("lender_id")
    await db.repayments.create_index("loan_id")
    await db.credit_scores.create_index("user_id")
    await db.transactions.create_index("loan_id")
    await db.transactions.create_index("tx_hash")
    await db.voice_sessions.create_index("user_id")
    await db.audit_logs.create_index("entity_id")
    await db.audit_logs.create_index("created_at")
    # v2: notifications and risk flags
    await db.notifications.create_index("user_id")
    await db.notifications.create_index([("user_id", 1), ("read", 1)])
    await db.notifications.create_index("created_at")
    await db.risk_flags.create_index("entity_id")
    await db.risk_flags.create_index("entity_type")
    await db.risk_flags.create_index("resolved")
    await db.risk_flags.create_index("created_at")
