"""Admin API: users, loans, repayments, transactions, analytics, flags, export."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.serializers import serialize_doc
from app.core.security import require_role
from app.db.mongodb import get_db
from app.services.loan_service import oid

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Users ──────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    out = []
    async for u in db.users.find({}):
        d = serialize_doc(u)
        d.pop("password_hash", None)
        out.append(d)
    return out


# ── Loans ──────────────────────────────────────────────────────────────────

@router.get("/loans")
async def list_all_loans(
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.loans.find({}).sort("created_at", -1)
    return [serialize_doc(l) async for l in cursor]


# ── Repayments ─────────────────────────────────────────────────────────────

@router.get("/repayments")
async def list_all_repayments(
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.repayments.find({}).sort("created_at", -1)
    return [serialize_doc(r) async for r in cursor]


# ── Transactions ───────────────────────────────────────────────────────────

@router.get("/transactions")
async def list_transactions(
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from app.services.blockchain_service import get_blockchain_service
    chain = get_blockchain_service()
    cursor = db.transactions.find({}).sort("created_at", -1).limit(200)
    out = []
    async for t in cursor:
        d = serialize_doc(t)
        d["explorer_url"] = chain.explorer_url(d.get("tx_hash", ""))
        out.append(d)
    return out


# ── Analytics ──────────────────────────────────────────────────────────────

@router.get("/analytics")
async def analytics(
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    total_loans = await db.loans.count_documents({})

    status_pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    status_dist = {doc["_id"]: doc["count"] async for doc in db.loans.aggregate(status_pipeline)}

    risk_pipeline = [
        {"$match": {"risk_category": {"$ne": None}}},
        {"$group": {"_id": "$risk_category", "count": {"$sum": 1}}},
    ]
    risk_dist = {doc["_id"]: doc["count"] async for doc in db.loans.aggregate(risk_pipeline)}

    score_pipeline = [
        {"$match": {"role": "borrower", "credit_score": {"$ne": None}}},
        {
            "$bucket": {
                "groupBy": "$credit_score",
                "boundaries": [300, 500, 650, 750, 851],
                "default": "other",
                "output": {"count": {"$sum": 1}},
            }
        },
    ]
    score_dist = {
        str(doc["_id"]): doc["count"]
        async for doc in db.users.aggregate(score_pipeline)
    }

    # Use MongoDB aggregation (FIX #15) instead of Python-level iteration
    funded_result = await db.loans.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$amount_funded"}}}]
    ).to_list(1)
    total_funded = funded_result[0]["total"] if funded_result else 0.0

    repaid_result = await db.loans.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$amount_repaid"}}}]
    ).to_list(1)
    total_repaid = repaid_result[0]["total"] if repaid_result else 0.0

    borrower_count = await db.users.count_documents({"role": "borrower"})
    lender_count = await db.users.count_documents({"role": "lender"})
    flagged_count = await db.risk_flags.count_documents({"resolved": False})

    return {
        "total_loans": total_loans,
        "loan_status_distribution": status_dist,
        "risk_distribution": risk_dist,
        "credit_score_distribution": score_dist,
        "total_amount_funded": round(total_funded, 2),
        "total_amount_repaid": round(total_repaid, 2),
        "borrower_count": borrower_count,
        "lender_count": lender_count,
        "flagged_count": flagged_count,
    }


# ── Risk flags ─────────────────────────────────────────────────────────────

VALID_FLAG_TYPES = {
    "SUSPECTED_FRAUD", "IDENTITY_RISK", "RAPID_REQUESTS",
    "OVERPAYMENT_ATTEMPT", "UNUSUAL_PATTERN", "MANUAL_REVIEW",
}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@router.get("/flags")
async def list_flags(
    resolved: bool | None = None,
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query: dict = {}
    if resolved is not None:
        query["resolved"] = resolved
    cursor = db.risk_flags.find(query).sort("created_at", -1)
    return [serialize_doc(f) async for f in cursor]


@router.post("/flags", status_code=201)
async def create_flag(
    body: dict,
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    entity_type = body.get("entity_type", "").lower()
    if entity_type not in ("loan", "user"):
        raise HTTPException(status_code=400, detail="entity_type must be 'loan' or 'user'")

    entity_id = body.get("entity_id", "").strip()
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id is required")

    flag_type = body.get("flag_type", "MANUAL_REVIEW")
    if flag_type not in VALID_FLAG_TYPES:
        flag_type = "MANUAL_REVIEW"

    severity = body.get("severity", "MEDIUM")
    if severity not in VALID_SEVERITIES:
        severity = "MEDIUM"

    reason = body.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")

    doc = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "flag_type": flag_type,
        "reason": reason,
        "severity": severity,
        "resolved": False,
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
    }
    result = await db.risk_flags.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.patch("/flags/{flag_id}/resolve")
async def resolve_flag(
    flag_id: str,
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    flag = await db.risk_flags.find_one({"_id": oid(flag_id)})
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    if flag["resolved"]:
        raise HTTPException(status_code=409, detail="Flag is already resolved")

    now = datetime.now(timezone.utc)
    await db.risk_flags.update_one(
        {"_id": flag["_id"]},
        {"$set": {"resolved": True, "resolved_at": now, "resolved_by": user["id"]}},
    )
    flag["resolved"] = True
    flag["resolved_at"] = now
    return serialize_doc(flag)


# ── Export ─────────────────────────────────────────────────────────────────

@router.get("/export")
async def admin_export(
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    type: str = Query("transactions", pattern="^(transactions|loans|repayments|users|flags)$"),
    user=Depends(require_role("admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Export any admin dataset as CSV (PDF falls back to CSV for this prototype)."""
    if type == "transactions":
        rows = [serialize_doc(t) async for t in
                db.transactions.find({}).sort("created_at", -1).limit(5000)]
        fields = ["id", "loan_id", "type", "amount", "tx_hash", "chain_mode", "created_at"]

    elif type == "loans":
        rows = [serialize_doc(l) async for l in db.loans.find({}).sort("created_at", -1)]
        fields = ["id", "borrower_name", "amount", "status", "risk_category",
                  "total_due", "amount_funded", "amount_repaid", "due_date",
                  "purpose", "source", "created_at"]

    elif type == "repayments":
        rows = [serialize_doc(r) async for r in db.repayments.find({}).sort("created_at", -1)]
        fields = ["id", "loan_id", "borrower_id", "amount", "is_on_time",
                  "is_early", "days_late", "tx_hash", "created_at"]

    elif type == "users":
        rows = []
        async for u in db.users.find({}):
            d = serialize_doc(u)
            d.pop("password_hash", None)
            rows.append(d)
        fields = ["id", "name", "email", "role", "credit_score",
                  "borrowing_limit", "lending_balance", "created_at"]

    elif type == "flags":
        rows = [serialize_doc(f) async for f in db.risk_flags.find({}).sort("created_at", -1)]
        fields = ["id", "entity_type", "entity_id", "flag_type",
                  "severity", "reason", "resolved", "created_at", "resolved_at"]

    else:
        rows, fields = [], []

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    filename = f"finlend-admin-{type}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
