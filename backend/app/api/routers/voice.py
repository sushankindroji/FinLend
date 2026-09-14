from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import get_current_user
from app.db.mongodb import get_db
from app.models.schemas import VoiceResponse, VoiceTextRequest
from app.services import loan_service, voice_service

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/dtmf/{digit}", response_model=VoiceResponse)
async def dtmf_turn(
    digit: str,
    session_id: str | None = None,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    text = voice_service.dtmf_to_text(digit)
    return await _handle_turn(text, session_id, user, db, source_label="dtmf")


@router.post("/turn", response_model=VoiceResponse)
async def voice_turn(
    payload: VoiceTextRequest,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await _handle_turn(payload.text, payload.session_id, user, db, source_label="voice")


async def _handle_turn(
    text: str, session_id: str | None, user: dict, db: AsyncIOMotorDatabase, source_label: str
) -> VoiceResponse:
    result = voice_service.process_voice_turn(text, session_id)

    # FIX #14: guard against deleted/missing user — do not crash on None
    borrower = await db.users.find_one({"_id": loan_service.oid(user["id"])})

    reply = _build_reply(result.intent, result.entities, borrower)

    # Only create a loan if all preconditions are satisfied (borrower doc exists + correct role)
    if (
        result.intent == "REQUEST_LOAN"
        and "amount" in result.entities
        and borrower is not None
        and borrower.get("role") == "borrower"
    ):
        loan = await loan_service.create_loan_request(
            db,
            borrower,
            float(result.entities["amount"]),
            30,
            "voice-initiated loan",
            source_label,
        )
        reply = _build_loan_reply(loan)

        # Emit notification for voice-triggered loan creation
        from app.services.notification_service import emit_notification
        await emit_notification(
            db,
            user_id=str(borrower["_id"]),
            notif_type="LOAN_APPROVED" if loan["status"] in ("APPROVED", "OPEN_FOR_FUNDING") else "LOAN_REJECTED",
            title="Loan request processed",
            body=reply,
            loan_id=str(loan["_id"]),
        )

    tts = voice_service.synthesize_reply(reply)

    # Persist session regardless of whether borrower doc was found
    await db.voice_sessions.insert_one({
        "user_id": borrower["_id"] if borrower else None,
        "session_id": result.session_id,
        "transcript": result.transcript,
        "intent": result.intent,
        "entities": result.entities,
        "reply_text": reply,
        "source": source_label,
        "created_at": datetime.now(timezone.utc),
    })

    return VoiceResponse(
        transcript=result.transcript,
        intent=result.intent,
        entities=result.entities,
        reply_text=reply,
        audio_available=tts["audio_available"],
        session_id=result.session_id,
    )


def _build_loan_reply(loan: dict) -> str:
    status = loan["status"]
    if status == "REJECTED":
        reason = loan.get("rejection_reason", "risk check failed")
        return (
            f"Sorry, your loan request for ₹{loan['amount']:,.0f} was not approved. "
            f"Reason: {reason}."
        )
    return (
        f"Your loan request for ₹{loan['amount']:,.0f} has been accepted and is "
        f"now open for funding in the marketplace."
    )


def _build_reply(intent: str, entities: dict, borrower: dict | None) -> str:
    if borrower is None:
        return "I couldn't verify your account. Please try signing in again."

    role = borrower.get("role", "")

    if intent == "CHECK_BALANCE":
        if role == "lender":
            bal = borrower.get("lending_balance", 0)
            return f"Your available lending balance is ₹{bal:,.2f}."
        credit_score = borrower.get("credit_score", 500)
        limit = borrower.get("borrowing_limit", 2000)
        return f"Your credit score is {credit_score} with a borrowing limit of ₹{limit:,.0f}."

    if intent == "CHECK_CREDIT_SCORE":
        score = borrower.get("credit_score")
        if score is None:
            return "No credit score on file yet. It will appear after your first loan activity."
        return f"Your current credit score is {score} out of 850."

    if intent == "CHECK_LOAN_STATUS":
        return "Please check the loan status panel on your dashboard for the latest status of your loans."

    if intent == "REQUEST_LOAN":
        if "amount" not in entities:
            return "How much would you like to borrow? For example, say 'request a loan of 5000 rupees'."
        return "Processing your loan request…"

    if intent == "CHECK_REPAYMENT":
        return "Please check the repayment schedule on your dashboard for exact due dates and amounts."

    if intent == "MAKE_REPAYMENT":
        return "To make a repayment, tap the Repay button next to your active loan on the dashboard."

    if intent == "HELP":
        return (
            "You can say: check balance, check credit score, check loan status, "
            "request a loan of [amount], check repayment, or make a repayment."
        )

    return "Sorry, I didn't understand that. Say 'help' to hear what you can do."
