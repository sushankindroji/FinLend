"""User profile, credit score, transactions, auto-invest preferences, and export."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.serializers import serialize_doc
from app.core.security import get_current_user, require_role
from app.db.mongodb import get_db
from app.models.schemas import CreditScoreOut, UserPublic, WalletAction
from app.services.loan_service import oid
from app.services.risk_service import evaluate_borrower_risk
from app.services.realtime_service import get_realtime_service

router = APIRouter(prefix="/api/users", tags=["users"])


async def _get_user_or_404(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    doc = await db.users.find_one({"_id": oid(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


# ── Profile ────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(user=Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _get_user_or_404(db, user["id"])
    out = serialize_doc(doc)
    out.pop("password_hash", None)
    return out


@router.post("/me/deposit")
async def deposit_funds(
    payload: WalletAction,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    amount = round(payload.amount, 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount must be positive")

    doc = await _get_user_or_404(db, user["id"])
    field = "lending_balance" if doc["role"] == "lender" else "wallet_balance"

    updated = await db.users.find_one_and_update(
        {"_id": doc["_id"]},
        {"$inc": {field: amount}},
        return_document=True,
    )
    new_balance = round(updated.get(field, 0.0), 2)

    await db.transactions.insert_one({
        "user_id": doc["_id"],
        "type": "DEPOSIT",
        "amount": amount,
        "created_at": datetime.now(timezone.utc),
    })

    realtime = get_realtime_service()
    await realtime.notify_user(str(doc["_id"]), "wallet_balance_updated", {
        "user_id": str(doc["_id"]),
        "wallet_balance": new_balance,
        "balance": new_balance,
        "field": field,
        "amount": amount,
        "action": "DEPOSIT",
    })

    return {"status": "ok", "balance": new_balance, "wallet_balance": new_balance, "field": field}


@router.post("/me/withdraw")
async def withdraw_funds(
    payload: WalletAction,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    amount = round(payload.amount, 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Withdrawal amount must be positive")

    doc = await _get_user_or_404(db, user["id"])
    field = "lending_balance" if doc["role"] == "lender" else "wallet_balance"
    current_bal = doc.get(field, 0.0) or 0.0

    if amount > current_bal:
        raise HTTPException(status_code=400, detail=f"Insufficient balance. Current balance: ₹{current_bal:.2f}")

    updated = await db.users.find_one_and_update(
        {"_id": doc["_id"], field: {"$gte": amount}},
        {"$inc": {field: -amount}},
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Withdrawal failed due to insufficient funds or concurrent transaction")

    new_balance = round(updated.get(field, 0.0), 2)

    await db.transactions.insert_one({
        "user_id": doc["_id"],
        "type": "WITHDRAWAL",
        "amount": amount,
        "created_at": datetime.now(timezone.utc),
    })

    realtime = get_realtime_service()
    await realtime.notify_user(str(doc["_id"]), "wallet_balance_updated", {
        "user_id": str(doc["_id"]),
        "wallet_balance": new_balance,
        "balance": new_balance,
        "field": field,
        "amount": amount,
        "action": "WITHDRAW",
    })

    return {"status": "ok", "balance": new_balance, "wallet_balance": new_balance, "field": field}



@router.get("/me/credit-score", response_model=CreditScoreOut)
async def get_my_credit_score(user=Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _get_user_or_404(db, user["id"])
    if doc["role"] != "borrower":
        raise HTTPException(status_code=400, detail="Only borrowers have a credit score")

    risk = evaluate_borrower_risk(doc)
    history_cursor = db.credit_scores.find({"user_id": doc["_id"]}).sort("created_at", -1).limit(20)
    history = [serialize_doc(h) async for h in history_cursor]

    return CreditScoreOut(
        user_id=str(doc["_id"]),
        credit_score=doc.get("credit_score", 500),
        risk_category=risk["risk_category"],
        borrowing_limit=doc.get("borrowing_limit", 2000),
        explanation=risk["explanation"],
        history=history,
    )


@router.get("/me/transactions")
async def get_my_transactions(user=Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _get_user_or_404(db, user["id"])
    if doc["role"] == "borrower":
        loans_cursor = db.loans.find({"borrower_id": doc["_id"]})
        loan_ids = [loan["_id"] async for loan in loans_cursor]
    else:
        fundings_cursor = db.loan_fundings.find({"lender_id": doc["_id"]})
        # Enrich funding transactions with expected_return from the fundings collection
        fundings = [f async for f in fundings_cursor]
        loan_ids = [f["loan_id"] for f in fundings]
        # Build a map loan_id -> expected_return for enrichment
        funding_map = {str(f["loan_id"]): f.get("expected_return") for f in fundings}

    tx_cursor = db.transactions.find({"loan_id": {"$in": loan_ids}}).sort("created_at", -1)
    result = []
    async for t in tx_cursor:
        d = serialize_doc(t)
        if doc["role"] == "lender" and d["type"] == "FUNDING":
            d["expected_return"] = funding_map.get(d["loan_id"])
        result.append(d)
    return result


# ── Auto-invest preferences (lender) ──────────────────────────────────────

_DEFAULT_PREFS = {
    "enabled": False,
    "max_per_loan": 1000.0,
    "min_credit_score": 500,
    "risk_tolerance": "MEDIUM",
    "max_duration_days": 90,
}


@router.get("/me/auto-invest")
async def get_auto_invest(
    user=Depends(require_role("lender")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await _get_user_or_404(db, user["id"])
    prefs = doc.get("auto_invest_prefs", _DEFAULT_PREFS.copy())
    prefs["updated_at"] = doc.get("auto_invest_updated_at")
    return prefs


@router.put("/me/auto-invest")
async def update_auto_invest(
    body: dict,
    user=Depends(require_role("lender")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # Validate and merge over defaults
    allowed = {"enabled", "max_per_loan", "min_credit_score", "risk_tolerance", "max_duration_days"}
    prefs = _DEFAULT_PREFS.copy()
    prefs.update({k: v for k, v in body.items() if k in allowed})

    # Validate ranges
    if not (1 <= prefs["max_per_loan"] <= 100_000):
        raise HTTPException(status_code=400, detail="max_per_loan must be between 1 and 100 000")
    if not (300 <= prefs["min_credit_score"] <= 850):
        raise HTTPException(status_code=400, detail="min_credit_score must be 300–850")
    if prefs["risk_tolerance"] not in ("LOW", "MEDIUM", "HIGH", "ALL"):
        raise HTTPException(status_code=400, detail="risk_tolerance must be LOW, MEDIUM, HIGH, or ALL")
    if not (7 <= prefs["max_duration_days"] <= 365):
        raise HTTPException(status_code=400, detail="max_duration_days must be 7–365")

    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"_id": oid(user["id"])},
        {"$set": {"auto_invest_prefs": prefs, "auto_invest_updated_at": now}},
    )
    prefs["updated_at"] = now.isoformat()
    return prefs


# ── CSV Export ─────────────────────────────────────────────────────────────

@router.get("/me/export")
async def export_my_data(
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    type: str = Query("transactions", pattern="^(transactions|loans|repayments)$"),
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await _get_user_or_404(db, user["id"])

    if type == "transactions":
        # Build loan_ids for the user
        if doc["role"] == "borrower":
            loan_ids = [l["_id"] async for l in db.loans.find({"borrower_id": doc["_id"]})]
        else:
            loan_ids = [f["loan_id"] async for f in db.loan_fundings.find({"lender_id": doc["_id"]})]
        rows = [serialize_doc(t) async for t in
                db.transactions.find({"loan_id": {"$in": loan_ids}}).sort("created_at", -1)]
        fields = ["id", "loan_id", "type", "amount", "tx_hash", "chain_mode", "created_at"]

    elif type == "loans":
        rows = [serialize_doc(l) async for l in
                db.loans.find({"borrower_id": doc["_id"]}).sort("created_at", -1)]
        fields = ["id", "amount", "status", "risk_category", "total_due",
                  "amount_funded", "amount_repaid", "due_date", "purpose", "created_at"]

    elif type == "repayments":
        loan_ids = [l["_id"] async for l in db.loans.find({"borrower_id": doc["_id"]})]
        rows = [serialize_doc(r) async for r in
                db.repayments.find({"loan_id": {"$in": loan_ids}}).sort("created_at", -1)]
        fields = ["id", "loan_id", "amount", "is_on_time", "is_early", "days_late", "tx_hash", "created_at"]

    else:
        rows, fields = [], []

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    filename = f"finlend-{type}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
