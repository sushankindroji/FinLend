"""Core loan lifecycle logic: state machine transitions, P2P funding rules,
repayment processing, and the credit-score / borrowing-limit feedback loop.

This is the heart of the primary user story (master prompt req #5/#6/#9).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import (
    LOAN_STATE_TRANSITIONS,
    SIMULATED_INTEREST_RATE,
    EARLY_REPAYMENT_THRESHOLD_DAYS,
    LATE_GRACE_PERIOD_DAYS,
)
from app.services import credit_engine
from app.services.blockchain_service import get_blockchain_service
from app.services.risk_service import evaluate_borrower_risk
from app.services.notification_service import emit_notification
from app.services.realtime_service import get_realtime_service


def _now():
    return datetime.now(timezone.utc)


def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid id") from exc


async def _audit(db: AsyncIOMotorDatabase, entity_type: str, entity_id: str, action: str, meta: dict):
    await db.audit_logs.insert_one({
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "meta": meta,
        "created_at": _now(),
    })


def _assert_transition(current: str, target: str):
    allowed = LOAN_STATE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid loan state transition: {current} -> {target}",
        )


async def _set_status(db: AsyncIOMotorDatabase, loan: dict, new_status: str, extra: Optional[dict] = None):
    old_status = loan["status"]
    _assert_transition(old_status, new_status)
    update = {"status": new_status, "updated_at": _now()}
    if extra:
        update.update(extra)
    await db.loans.update_one({"_id": loan["_id"]}, {"$set": update})
    await _audit(db, "loan", str(loan["_id"]), f"STATUS_{old_status}_TO_{new_status}", extra or {})
    loan.update(update)
    
    # Real-time status change broadcast
    realtime = get_realtime_service()
    await realtime.broadcast_loan_status_change(
        loan_id=str(loan["_id"]),
        old_status=old_status,
        new_status=new_status,
        borrower_id=str(loan.get("borrower_id", "")),
    )
    
    return loan


# ---------------------------------------------------------------------------
# Loan request -> credit check -> approval/rejection
# ---------------------------------------------------------------------------
async def create_loan_request(db: AsyncIOMotorDatabase, borrower: dict, amount: float,
                               duration_days: int, purpose: Optional[str], source: str) -> dict:
    borrowing_limit = borrower.get("borrowing_limit", 2000)
    total_due = round(amount * (1 + SIMULATED_INTEREST_RATE), 2)

    loan_doc = {
        "borrower_id": borrower["_id"],
        "borrower_name": borrower.get("name"),
        "amount": amount,
        "duration_days": duration_days,
        "interest_rate": SIMULATED_INTEREST_RATE,
        "total_due": total_due,
        "amount_funded": 0.0,
        "amount_repaid": 0.0,
        "status": "REQUESTED",
        "risk_category": None,
        "purpose": purpose,
        "source": source,
        "due_date": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    result = await db.loans.insert_one(loan_doc)
    loan_doc["_id"] = result.inserted_id
    await _audit(db, "loan", str(loan_doc["_id"]), "CREATED", {"amount": amount, "source": source})

    # -- CREDIT_CHECK --
    loan_doc = await _set_status(db, loan_doc, "CREDIT_CHECK")
    risk_result = evaluate_borrower_risk(borrower)
    risk_category = risk_result["risk_category"]

    approved = amount <= borrowing_limit and risk_category != "HIGH"

    if not approved:
        reason = (
            f"amount {amount} exceeds borrowing limit {borrowing_limit}"
            if amount > borrowing_limit else f"risk category {risk_category}"
        )
        loan_doc = await _set_status(db, loan_doc, "REJECTED", {
            "risk_category": risk_category,
            "rejection_reason": reason,
        })
        # Notify borrower of rejection
        await emit_notification(
            db,
            user_id=str(borrower["_id"]),
            notif_type="LOAN_REJECTED",
            title="Loan request rejected",
            body=f"Your ₹{amount:,.0f} loan request was not approved. {reason}.",
            loan_id=str(loan_doc["_id"]),
        )
        return loan_doc

    loan_doc = await _set_status(db, loan_doc, "APPROVED", {"risk_category": risk_category})
    loan_doc = await _set_status(db, loan_doc, "OPEN_FOR_FUNDING")
    # Notify borrower of approval
    await emit_notification(
        db,
        user_id=str(borrower["_id"]),
        notif_type="LOAN_APPROVED",
        title="Loan request approved 🎉",
        body=f"Your ₹{amount:,.0f} loan request has been approved and is now open for funding.",
        loan_id=str(loan_doc["_id"]),
    )
    return loan_doc


# ---------------------------------------------------------------------------
# P2P funding
# ---------------------------------------------------------------------------
async def fund_loan(db: AsyncIOMotorDatabase, loan_id: str, lender: dict, amount: float) -> dict:
    loan = await db.loans.find_one({"_id": oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    if loan["status"] not in ("OPEN_FOR_FUNDING", "PARTIALLY_FUNDED"):
        raise HTTPException(status_code=409, detail=f"Loan is not open for funding (status={loan['status']})")

    remaining = round(loan["amount"] - loan["amount_funded"], 2)
    if amount > remaining + 1e-6:
        raise HTTPException(status_code=400, detail=f"Amount exceeds remaining funding needed ({remaining})")

    lending_balance = lender.get("lending_balance", 0)
    if amount > lending_balance:
        raise HTTPException(status_code=400, detail="Insufficient lending balance")

    expected_return = round(amount * (1 + loan["interest_rate"]), 2)

    chain = get_blockchain_service()
    amount_wei = int(amount * 10**18)
    tx = chain.record_funding(str(loan["_id"]), str(lender["_id"]), amount_wei)

    funding_doc = {
        "loan_id": loan["_id"],
        "lender_id": lender["_id"],
        "amount": amount,
        "expected_return": expected_return,
        "tx_hash": tx["tx_hash"],
        "chain_mode": tx["mode"],
        "created_at": _now(),
    }
    result = await db.loan_fundings.insert_one(funding_doc)
    funding_doc["_id"] = result.inserted_id

    await db.transactions.insert_one({
        "loan_id": loan["_id"],
        "type": "FUNDING",
        "amount": amount,
        "tx_hash": tx["tx_hash"],
        "chain_mode": tx["mode"],
        "created_at": _now(),
    })

    await db.users.update_one({"_id": lender["_id"]}, {"$inc": {"lending_balance": -amount}})

    new_funded = round(loan["amount_funded"] + amount, 2)
    is_fully_funded = new_funded >= loan["amount"] - 1e-6

    await db.loans.update_one({"_id": loan["_id"]}, {"$set": {"amount_funded": new_funded, "updated_at": _now()}})
    loan["amount_funded"] = new_funded

    if is_fully_funded:
        # FIX #16: clean single-path transition regardless of current status.
        # OPEN_FOR_FUNDING -> PARTIALLY_FUNDED is an allowed intermediate only
        # when we pass through it; skip it if already PARTIALLY_FUNDED.
        if loan["status"] == "OPEN_FOR_FUNDING":
            loan = await _set_status(db, loan, "PARTIALLY_FUNDED")
        loan = await _set_status(db, loan, "FUNDED")
        due_date = _now() + timedelta(days=loan["duration_days"])
        loan = await _set_status(db, loan, "ACTIVE", {"due_date": due_date})
    else:
        if loan["status"] != "PARTIALLY_FUNDED":
            loan = await _set_status(db, loan, "PARTIALLY_FUNDED")

    await _audit(db, "loan", str(loan["_id"]), "FUNDED_PARTIAL", {"lender_id": str(lender["_id"]), "amount": amount})

    # Real-time updates
    realtime = get_realtime_service()
    await realtime.broadcast_funding_progress(
        loan_id=str(loan["_id"]),
        loan_amount=loan["amount"],
        amount_funded=new_funded,
        lender_id=str(lender["_id"]),
        contribution=amount,
        status=loan["status"],
    )

    # Notifications
    borrower_id = str(loan.get("borrower_id", ""))
    lender_id = str(lender["_id"])
    if is_fully_funded:
        if borrower_id:
            await emit_notification(
                db,
                user_id=borrower_id,
                notif_type="LOAN_ACTIVE",
                title="Your loan is now active 🚀",
                body=f"Your ₹{loan['amount']:,.0f} loan has been fully funded and is now active.",
                loan_id=str(loan["_id"]),
            )
        await emit_notification(
            db,
            user_id=lender_id,
            notif_type="LOAN_FUNDED",
            title="Funding complete",
            body=f"Loan #...{str(loan['_id'])[-6:]} is now fully funded and active.",
            loan_id=str(loan["_id"]),
        )
    else:
        await emit_notification(
            db,
            user_id=lender_id,
            notif_type="LOAN_FUNDED",
            title="Funding recorded",
            body=f"Your ₹{amount:,.0f} investment in loan #...{str(loan['_id'])[-6:]} was recorded.",
            loan_id=str(loan["_id"]),
        )

    return {"loan": loan, "funding": funding_doc}


# ---------------------------------------------------------------------------
# Repayment
# ---------------------------------------------------------------------------
async def repay_loan(db: AsyncIOMotorDatabase, loan_id: str, borrower: dict, amount: float) -> dict:
    loan = await db.loans.find_one({"_id": oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if str(loan["borrower_id"]) != str(borrower["_id"]):
        raise HTTPException(status_code=403, detail="Not your loan")
    if loan["status"] not in ("ACTIVE", "LATE"):
        raise HTTPException(status_code=409, detail=f"Loan cannot accept repayment in status {loan['status']}")

    remaining_due = round(loan["total_due"] - loan["amount_repaid"], 2)
    # FIX #17a: strict overpayment guard — no tolerance above remaining due.
    if amount > remaining_due + 1e-6:
        raise HTTPException(
            status_code=400,
            detail=f"Repayment amount ₹{amount} exceeds remaining balance ₹{remaining_due}. "
                   f"Use ₹{remaining_due} to pay in full.",
        )

    now = _now()
    due_date = loan.get("due_date")
    days_late = 0
    is_on_time = True
    is_early = False
    if due_date:
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        delta_days = (now - due_date).days
        if delta_days > 0:
            days_late = delta_days
            is_on_time = False
        elif delta_days <= -EARLY_REPAYMENT_THRESHOLD_DAYS:
            is_early = True

    is_default = days_late > LATE_GRACE_PERIOD_DAYS

    chain = get_blockchain_service()
    amount_wei = int(amount * 10**18)
    tx = chain.record_repayment(str(loan["_id"]), str(borrower["_id"]), amount_wei)

    repayment_doc = {
        "loan_id": loan["_id"],
        "borrower_id": borrower["_id"],
        "amount": amount,
        "is_on_time": is_on_time,
        "is_early": is_early,
        "days_late": days_late,
        "tx_hash": tx["tx_hash"],
        "chain_mode": tx["mode"],
        "created_at": now,
    }
    result = await db.repayments.insert_one(repayment_doc)
    repayment_doc["_id"] = result.inserted_id

    await db.transactions.insert_one({
        "loan_id": loan["_id"],
        "type": "REPAYMENT",
        "amount": amount,
        "tx_hash": tx["tx_hash"],
        "chain_mode": tx["mode"],
        "created_at": now,
    })

    new_repaid = round(loan["amount_repaid"] + amount, 2)
    is_fully_repaid = new_repaid >= loan["total_due"] - 1e-6

    await db.loans.update_one({"_id": loan["_id"]}, {"$set": {"amount_repaid": new_repaid, "updated_at": now}})
    loan["amount_repaid"] = new_repaid

    # -- credit scoring feedback loop --
    current_score = borrower.get("credit_score", credit_engine.initial_score())
    new_score, events = credit_engine.score_for_repayment(
        current_score, is_early=is_early, is_on_time=is_on_time, is_default=is_default
    )

    stats = borrower.get("stats", {})
    stats["total_repaid"] = stats.get("total_repaid", 0.0) + amount
    if is_default:
        stats["defaults"] = stats.get("defaults", 0) + 1
    elif is_on_time:
        stats["on_time_repayments"] = stats.get("on_time_repayments", 0) + 1
    else:
        # FIX #17b: increment late_repayments BEFORE using it as the denominator
        # so the running average uses the correct count (n, not n-1).
        prev_avg = stats.get("average_delay_days", 0.0)
        prev_count = stats.get("late_repayments", 0)
        stats["late_repayments"] = prev_count + 1
        new_count = stats["late_repayments"]
        stats["average_delay_days"] = round(
            ((prev_avg * prev_count) + days_late) / new_count, 2
        )

    if is_fully_repaid:
        loan = await _set_status(db, loan, "DEFAULTED" if is_default else "REPAID")
        if not is_default:
            new_score, completion_events = credit_engine.score_for_loan_completion(new_score)
            events += completion_events
            stats["completed_loans"] = stats.get("completed_loans", 0) + 1
            stats["total_borrowed"] = stats.get("total_borrowed", 0.0) + loan["amount"]
    elif is_default:
        loan = await _set_status(db, loan, "DEFAULTED")
    elif not is_on_time:
        if loan["status"] != "LATE":
            loan = await _set_status(db, loan, "LATE")

    new_limit = credit_engine.borrowing_limit_for_score(new_score)

    await db.users.update_one(
        {"_id": borrower["_id"]},
        {"$set": {"credit_score": new_score, "borrowing_limit": new_limit, "stats": stats}},
    )
    await db.credit_scores.insert_one({
        "user_id": borrower["_id"],
        "credit_score": new_score,
        "previous_score": current_score,
        "events": events,
        "borrowing_limit": new_limit,
        "reason": f"repayment on loan {loan['_id']}",
        "created_at": now,
    })

    await _audit(db, "loan", str(loan["_id"]), "REPAYMENT_APPLIED", {
        "amount": amount, "new_score": new_score, "events": events,
    })

    # Real-time repayment broadcast
    realtime = get_realtime_service()
    await realtime.broadcast_repayment(
        loan_id=str(loan["_id"]),
        borrower_id=str(borrower["_id"]),
        amount=amount,
        remaining=remaining_due - amount,
        is_final=is_fully_repaid,
    )

    # Notifications
    borrower_uid = str(borrower["_id"])
    loan_oid_str = str(loan["_id"])
    final_status = loan["status"]

    if final_status == "REPAID":
        await emit_notification(
            db,
            user_id=borrower_uid,
            notif_type="LOAN_REPAID",
            title="Loan fully repaid 🏆",
            body=f"Congratulations! Your ₹{loan['amount']:,.0f} loan is fully repaid. Credit score: {new_score}.",
            loan_id=loan_oid_str,
        )
    elif final_status == "DEFAULTED":
        await emit_notification(
            db,
            user_id=borrower_uid,
            notif_type="LOAN_DEFAULTED",
            title="Loan marked as defaulted",
            body=f"Your ₹{loan['amount']:,.0f} loan was marked as defaulted. Credit score: {new_score}.",
            loan_id=loan_oid_str,
        )
    elif final_status == "LATE":
        await emit_notification(
            db,
            user_id=borrower_uid,
            notif_type="LOAN_LATE",
            title="Loan payment overdue ⚠️",
            body=f"Your ₹{loan['amount']:,.0f} loan is {days_late} day(s) overdue. Please repay as soon as possible.",
            loan_id=loan_oid_str,
        )
    else:
        await emit_notification(
            db,
            user_id=borrower_uid,
            notif_type="REPAYMENT_RECEIVED",
            title="Repayment recorded",
            body=f"₹{amount:,.2f} repayment recorded. Credit score updated to {new_score}.",
            loan_id=loan_oid_str,
        )

    # Credit score update notification
    if events:
        await emit_notification(
            db,
            user_id=borrower_uid,
            notif_type="CREDIT_UPDATED",
            title="Credit score updated",
            body=f"Score: {new_score} (events: {', '.join(events)}). Borrowing limit: ₹{new_limit:,.0f}.",
            loan_id=loan_oid_str,
        )

    return {
        "loan": loan,
        "repayment": repayment_doc,
        "credit_score": new_score,
        "borrowing_limit": new_limit,
        "events": events,
    }
