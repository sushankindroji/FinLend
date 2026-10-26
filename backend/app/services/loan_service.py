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
    CREDIT_SCORE_CONFIG,
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
    amount = round(amount, 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Funding amount must be greater than zero")

    loan = await db.loans.find_one({"_id": oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    if loan["status"] not in ("OPEN_FOR_FUNDING", "PARTIALLY_FUNDED"):
        raise HTTPException(status_code=409, detail=f"Loan is not open for funding (status={loan['status']})")

    remaining = round(loan["amount"] - loan["amount_funded"], 2)
    if amount > remaining + 1e-6:
        raise HTTPException(status_code=400, detail=f"Amount exceeds remaining funding needed ({remaining})")

    # 1. ATOMIC LENDER BALANCE DEDUCTION (Protects against concurrent balance overdraft)
    updated_lender = await db.users.find_one_and_update(
        {"_id": lender["_id"], "lending_balance": {"$gte": amount}},
        {"$inc": {"lending_balance": -amount}},
        return_document=True,
    )
    if not updated_lender:
        raise HTTPException(status_code=400, detail="Insufficient lending balance or concurrent funding transaction in progress")

    # 2. ATOMIC LOAN FUNDING UPDATE (Protects against simultaneous funding / overfunding race conditions)
    updated_loan = await db.loans.find_one_and_update(
        {
            "_id": loan["_id"],
            "status": {"$in": ["OPEN_FOR_FUNDING", "PARTIALLY_FUNDED"]},
            "$expr": {"$lte": [{"$add": ["$amount_funded", amount]}, {"$add": ["$amount", 0.01]}]},
        },
        {
            "$inc": {"amount_funded": amount},
            "$set": {"updated_at": _now()},
        },
        return_document=True,
    )
    if not updated_loan:
        # Rollback the lender's balance immediately!
        await db.users.update_one({"_id": lender["_id"]}, {"$inc": {"lending_balance": amount}})
        raise HTTPException(
            status_code=409,
            detail="Simultaneous funding attempt prevented: loan has already been filled or amount exceeds remaining requirement.",
        )

    loan = updated_loan
    new_funded = round(loan["amount_funded"], 2)
    is_fully_funded = new_funded >= loan["amount"] - 1e-6

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

    if is_fully_funded:
        # FIX #16: clean single-path transition regardless of current status.
        if loan["status"] == "OPEN_FOR_FUNDING":
            loan = await _set_status(db, loan, "PARTIALLY_FUNDED")
        loan = await _set_status(db, loan, "FUNDED")
        due_date = _now() + timedelta(days=loan["duration_days"])
        loan = await _set_status(db, loan, "ACTIVE", {"due_date": due_date})

        # Disburse loan funds directly into borrower's real-time wallet balance!
        borrower_updated = await db.users.find_one_and_update(
            {"_id": loan["borrower_id"]},
            {"$inc": {"wallet_balance": loan["amount"]}},
            return_document=True,
        )
        new_wallet_bal = round(borrower_updated.get("wallet_balance", 0.0), 2) if borrower_updated else loan["amount"]

        await db.transactions.insert_one({
            "loan_id": loan["_id"],
            "user_id": loan["borrower_id"],
            "type": "DISBURSEMENT",
            "amount": loan["amount"],
            "tx_hash": tx["tx_hash"],
            "chain_mode": tx["mode"],
            "created_at": _now(),
        })

        realtime = get_realtime_service()
        await realtime.notify_user(str(loan["borrower_id"]), "wallet_balance_updated", {
            "user_id": str(loan["borrower_id"]),
            "wallet_balance": new_wallet_bal,
            "balance": new_wallet_bal,
            "amount": loan["amount"],
            "action": "LOAN_DISBURSED",
            "message": f"Loan #{str(loan['_id'])[-6:]} disbursed: ₹{loan['amount']:,.0f} added to your wallet.",
        })
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

    # ── Strict Bank Wallet Balance Enforcement ──
    fresh_borrower = await db.users.find_one({"_id": borrower["_id"]})
    wallet_balance = float((fresh_borrower or borrower).get("wallet_balance") or 0.0)
    if wallet_balance < amount - 1e-6:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient wallet balance (₹{wallet_balance:,.2f}). Please deposit funds first to repay ₹{amount:,.2f}."
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

    # Atomic debit of borrower wallet balance
    updated_b = await db.users.find_one_and_update(
        {"_id": borrower["_id"], "wallet_balance": {"$gte": amount}},
        {"$inc": {"wallet_balance": -amount}},
        return_document=True,
    )
    if not updated_b:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient wallet balance (₹{wallet_balance:,.2f}). Please deposit funds first to repay ₹{amount:,.2f}."
        )
    new_wallet_bal = round(updated_b.get("wallet_balance", 0.0), 2)

    chain = get_blockchain_service()
    amount_wei = int(amount * 10**18)
    tx = chain.record_repayment(str(loan["_id"]), str(borrower["_id"]), amount_wei)

    realtime = get_realtime_service()
    await realtime.notify_user(str(borrower["_id"]), "wallet_balance_updated", {
        "user_id": str(borrower["_id"]),
        "wallet_balance": new_wallet_bal,
        "balance": new_wallet_bal,
        "amount": amount,
        "action": "LOAN_REPAYMENT",
        "message": f"Repayment of ₹{amount:,.2f} deducted from wallet for Loan #{str(loan['_id'])[-6:]}.",
    })

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

    # ── DISTRIBUTE LENDER PAYOUTS (PROPORTIONAL PRINCIPAL + INTEREST) ──
    fundings = await db.loan_fundings.find({"loan_id": loan["_id"]}).to_list(100)
    total_loan_amount = loan.get("amount", 0.0)
    if fundings and total_loan_amount > 0:
        for funding in fundings:
            lender_id = funding["lender_id"]
            ratio = funding["amount"] / total_loan_amount
            payout_amount = round(amount * ratio, 2)
            if payout_amount <= 0:
                continue

            await db.users.update_one(
                {"_id": lender_id},
                {"$inc": {"lending_balance": payout_amount}},
            )
            await db.transactions.insert_one({
                "loan_id": loan["_id"],
                "lender_id": lender_id,
                "type": "PAYOUT",
                "amount": payout_amount,
                "tx_hash": tx["tx_hash"],
                "chain_mode": tx["mode"],
                "created_at": now,
            })
            await emit_notification(
                db,
                user_id=str(lender_id),
                notif_type="PAYOUT_RECEIVED",
                title="Lender Payout Received 💰",
                body=f"You received a payout of ₹{payout_amount:,.2f} for Loan #{str(loan['_id'])[-6:]}.",
                loan_id=str(loan["_id"]),
            )
            realtime = get_realtime_service()
            await realtime.notify_user(str(lender_id), "payout_received", {
                "loan_id": str(loan["_id"]),
                "amount": payout_amount,
                "message": f"Received ₹{payout_amount:,.2f} payout",
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


# ---------------------------------------------------------------------------
# Automatic Overdue Loan Detection
# ---------------------------------------------------------------------------
async def detect_and_process_overdue_loans(db: AsyncIOMotorDatabase) -> dict:
    """Scan all ACTIVE and LATE loans, detect overdue loans, transition state,
    and update borrower credit scores and risk flags.
    """
    now = _now()
    active_cursor = db.loans.find({"status": {"$in": ["ACTIVE", "LATE"]}})
    loans = [l async for l in active_cursor]

    marked_late = []
    marked_defaulted = []

    for loan in loans:
        due_date = loan.get("due_date")
        if not due_date:
            continue
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)

        delta_days = (now - due_date).days
        if delta_days <= 0:
            continue  # Not overdue

        borrower_id = loan.get("borrower_id")
        borrower = await db.users.find_one({"_id": borrower_id}) if borrower_id else None

        if delta_days > LATE_GRACE_PERIOD_DAYS:
            # Overdue past grace period -> DEFAULTED
            if loan["status"] != "DEFAULTED":
                await _set_status(db, loan, "DEFAULTED")
                marked_defaulted.append(str(loan["_id"]))

                if borrower:
                    current_score = borrower.get("credit_score", credit_engine.initial_score())
                    new_score, events = credit_engine.score_for_repayment(
                        current_score, is_early=False, is_on_time=False, is_default=True
                    )
                    new_limit = credit_engine.borrowing_limit_for_score(new_score)
                    stats = borrower.get("stats", {})
                    stats["defaults"] = stats.get("defaults", 0) + 1

                    await db.users.update_one(
                        {"_id": borrower["_id"]},
                        {"$set": {"credit_score": new_score, "borrowing_limit": new_limit, "stats": stats}}
                    )
                    await db.credit_scores.insert_one({
                        "user_id": borrower["_id"],
                        "credit_score": new_score,
                        "previous_score": current_score,
                        "events": events,
                        "borrowing_limit": new_limit,
                        "reason": f"loan defaulted: overdue by {delta_days} days on loan {loan['_id']}",
                        "created_at": now,
                    })

                await emit_notification(
                    db,
                    user_id=str(borrower_id),
                    notif_type="LOAN_DEFAULTED",
                    title="Loan Default Notice ⚠️",
                    body=f"Loan #{str(loan['_id'])[-6:]} is {delta_days} days overdue and has defaulted.",
                    loan_id=str(loan["_id"]),
                )
                await _audit(db, "loan", str(loan["_id"]), "AUTOMATIC_DEFAULT", {"days_overdue": delta_days})

        elif loan["status"] == "ACTIVE":
            # Overdue but within grace period -> LATE
            await _set_status(db, loan, "LATE")
            marked_late.append(str(loan["_id"]))

            if borrower:
                current_score = borrower.get("credit_score", credit_engine.initial_score())
                penalty = CREDIT_SCORE_CONFIG.get("late_repayment", -30)
                new_score = max(CREDIT_SCORE_CONFIG["min_score"], current_score + penalty)
                new_limit = credit_engine.borrowing_limit_for_score(new_score)
                stats = borrower.get("stats", {})
                stats["late_repayments"] = stats.get("late_repayments", 0) + 1

                await db.users.update_one(
                    {"_id": borrower["_id"]},
                    {"$set": {"credit_score": new_score, "borrowing_limit": new_limit, "stats": stats}}
                )
                await db.credit_scores.insert_one({
                    "user_id": borrower["_id"],
                    "credit_score": new_score,
                    "previous_score": current_score,
                    "events": [f"late_penalty_{penalty}"],
                    "borrowing_limit": new_limit,
                    "reason": f"loan overdue: {delta_days} days late on loan {loan['_id']}",
                    "created_at": now,
                })

            await emit_notification(
                db,
                user_id=str(borrower_id),
                notif_type="LOAN_LATE",
                title="Loan Overdue Alert ⚠️",
                body=f"Your payment on loan #{str(loan['_id'])[-6:]} is {delta_days} day(s) overdue.",
                loan_id=str(loan["_id"]),
            )
            await _audit(db, "loan", str(loan["_id"]), "AUTOMATIC_LATE_DETECTED", {"days_overdue": delta_days})

    return {
        "status": "ok",
        "scanned_loans": len(loans),
        "marked_late": marked_late,
        "marked_defaulted": marked_defaulted,
        "timestamp": now.isoformat(),
    }

