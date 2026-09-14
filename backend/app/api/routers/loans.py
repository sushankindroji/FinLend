"""Loan lifecycle API: request, list, fund, repay, schedule."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.serializers import serialize_doc
from app.core.security import get_current_user, require_role
from app.db.mongodb import get_db
from app.models.schemas import LoanFundingCreate, LoanRequestCreate, RepaymentCreate
from app.services import loan_service

router = APIRouter(prefix="/api/loans", tags=["loans"])


async def _get_user_doc(db, user_id):
    doc = await db.users.find_one({"_id": loan_service.oid(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


@router.post("", status_code=201)
async def request_loan(
    payload: LoanRequestCreate,
    user=Depends(require_role("borrower")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    borrower = await _get_user_doc(db, user["id"])
    loan = await loan_service.create_loan_request(
        db, borrower, payload.amount, payload.duration_days, payload.purpose, payload.source
    )
    return serialize_doc(loan)


@router.get("")
async def list_loans(
    status: str | None = None,
    mine: bool = False,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query: dict = {}
    if status:
        query["status"] = status
    if mine and user["role"] == "borrower":
        query["borrower_id"] = loan_service.oid(user["id"])
    elif not mine or user["role"] != "borrower":
        if user["role"] == "lender" and not status:
            query["status"] = {"$in": ["OPEN_FOR_FUNDING", "PARTIALLY_FUNDED"]}

    cursor = db.loans.find(query).sort("created_at", -1)
    return [serialize_doc(l) async for l in cursor]


@router.get("/{loan_id}")
async def get_loan(
    loan_id: str,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    loan = await db.loans.find_one({"_id": loan_service.oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return serialize_doc(loan)


@router.get("/{loan_id}/fundings")
async def get_loan_fundings(
    loan_id: str,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.loan_fundings.find({"loan_id": loan_service.oid(loan_id)})
    return [serialize_doc(f) async for f in cursor]


@router.get("/{loan_id}/repayments")
async def get_loan_repayments(
    loan_id: str,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.repayments.find({"loan_id": loan_service.oid(loan_id)})
    return [serialize_doc(r) async for r in cursor]


@router.get("/{loan_id}/schedule")
async def get_repayment_schedule(
    loan_id: str,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return a structured repayment schedule for the loan.

    For active / partially-repaid loans the schedule reflects actual payments
    already made and marks future instalments as 'upcoming', 'due', or 'overdue'.
    For loans not yet active (no due_date) the schedule is a forward-looking
    simulation broken into monthly instalments.
    """
    loan = await db.loans.find_one({"_id": loan_service.oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    total_due: float = loan["total_due"]
    duration_days: int = loan["duration_days"]
    due_date = loan.get("due_date")
    amount_repaid: float = loan.get("amount_repaid", 0.0)
    status: str = loan.get("status", "")

    # --- Build schedule entries ---
    # Divide into approximately monthly payments (≈30-day chunks).
    num_payments = max(1, ceil(duration_days / 30))
    payment_amount = round(total_due / num_payments, 2)

    # Anchor start from due_date - duration_days, or now if loan not yet active.
    if due_date:
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        start_date = due_date - timedelta(days=duration_days)
    else:
        start_date = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    running_repaid = amount_repaid
    schedule = []

    for i in range(num_payments):
        is_last = i == num_payments - 1
        # Last payment absorbs rounding remainder
        payment = round(total_due - (payment_amount * i), 2) if is_last else payment_amount
        interval_days = round(duration_days / num_payments)
        payment_due = start_date + timedelta(days=interval_days * (i + 1))

        # Determine status
        if running_repaid >= payment - 1e-6:
            entry_status = "paid"
            paid_amount = payment
            running_repaid = max(0.0, round(running_repaid - payment, 2))
        elif status in ("REPAID",):
            entry_status = "paid"
            paid_amount = payment
        else:
            if due_date and payment_due < now:
                entry_status = "overdue"
            elif due_date and (payment_due - now).days <= 7:
                entry_status = "due"
            else:
                entry_status = "upcoming"
            paid_amount = None

        schedule.append({
            "payment_number": i + 1,
            "due_date": payment_due.isoformat(),
            "principal": round(payment / (1 + loan.get("interest_rate", 0.10)), 2),
            "interest": round(payment - payment / (1 + loan.get("interest_rate", 0.10)), 2),
            "total": payment,
            "status": entry_status,
            "paid_amount": paid_amount,
        })

    return schedule


@router.post("/{loan_id}/fund", status_code=201)
async def fund_loan(
    loan_id: str,
    payload: LoanFundingCreate,
    user=Depends(require_role("lender")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    lender = await _get_user_doc(db, user["id"])
    result = await loan_service.fund_loan(db, loan_id, lender, payload.amount)
    return {
        "loan": serialize_doc(result["loan"]),
        "funding": serialize_doc(result["funding"]),
    }


@router.post("/{loan_id}/repay", status_code=201)
async def repay_loan(
    loan_id: str,
    payload: RepaymentCreate,
    user=Depends(require_role("borrower")),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    borrower = await _get_user_doc(db, user["id"])
    result = await loan_service.repay_loan(db, loan_id, borrower, payload.amount)
    return {
        "loan": serialize_doc(result["loan"]),
        "repayment": serialize_doc(result["repayment"]),
        "credit_score": result["credit_score"],
        "borrowing_limit": result["borrowing_limit"],
        "events": result["events"],
    }
