from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile, Form
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
    return await _handle_turn(text, session_id, user, db, source_label="dtmf", is_audio=False)


@router.post("/turn", response_model=VoiceResponse)
async def voice_turn(
    payload: VoiceTextRequest,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await _handle_turn(payload.text, payload.session_id, user, db, source_label="voice", is_audio=False)


@router.post("/audio", response_model=VoiceResponse)
async def voice_audio(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    session_id: str | None = Form(None),
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Handle audio file upload and transcription via Whisper."""
    audio_bytes = await audio.read()
    return await _handle_turn(audio_bytes, session_id, user, db, source_label="voice_audio", is_audio=True, language=language)


async def _handle_turn(
    input_data: str | bytes,
    session_id: str | None,
    user: dict,
    db: AsyncIOMotorDatabase,
    source_label: str,
    is_audio: bool = False,
    language: str = "en"
) -> VoiceResponse:
    # Get borrower profile for context
    borrower = await db.users.find_one({"_id": loan_service.oid(user["id"])})
    
    if borrower is None:
        return VoiceResponse(
            transcript="",
            intent="ERROR",
            entities={},
            reply_text="User not found. Please sign in again.",
            audio_available=False,
            session_id=session_id or "",
            needs_clarification=False,
            clarification_question=""
        )
    
    # Build user profile for GPT-4 context
    user_profile = {
        "role": borrower.get("role", "borrower"),
        "credit_score": borrower.get("credit_score", 500),
        "borrowing_limit": borrower.get("borrowing_limit", 2000),
        "balance": borrower.get("lending_balance", 0) if borrower.get("role") == "lender" else 0
    }
    
    # Process voice turn with GPT-4
    result = voice_service.process_voice_turn(
        input_data,
        session_id,
        is_audio=is_audio,
        language=language,
        user_profile=user_profile
    )
    
    reply = result.response
    
    # Handle loan creation if intent is REQUEST_LOAN and all info is available
    if (
        result.intent == "REQUEST_LOAN"
        and not result.needs_clarification
        and result.entities.get("amount")
        and result.entities.get("duration_days")
        and borrower.get("role") == "borrower"
    ):
        try:
            loan = await loan_service.create_loan_request(
                db,
                borrower,
                float(result.entities["amount"]),
                int(result.entities["duration_days"]),
                result.entities.get("purpose", "voice-initiated loan"),
                source_label,
            )
            
            # Update reply with loan creation result
            if loan["status"] == "REJECTED":
                reason = loan.get("rejection_reason", "risk check failed")
                reply = f"Sorry, your loan request for ₹{loan['amount']:,.0f} was not approved. Reason: {reason}."
            else:
                reply = f"Great! Your loan request for ₹{loan['amount']:,.0f} for {loan['duration_days']} days has been approved and is now open for funding."
            
            # Emit notification
            from app.services.notification_service import emit_notification
            await emit_notification(
                db,
                user_id=str(borrower["_id"]),
                notif_type="LOAN_APPROVED" if loan["status"] in ("APPROVED", "OPEN_FOR_FUNDING") else "LOAN_REJECTED",
                title="Loan request processed",
                body=reply,
                loan_id=str(loan["_id"]),
            )
        except Exception as e:
            reply = f"There was an error processing your loan request: {str(e)}"
    
    # Handle other intents with actual data
    elif result.intent == "CHECK_BALANCE" and not result.needs_clarification:
        if borrower.get("role") == "lender":
            bal = borrower.get("lending_balance", 0)
            reply = f"Your available lending balance is ₹{bal:,.2f}."
        else:
            credit_score = borrower.get("credit_score", 500)
            limit = borrower.get("borrowing_limit", 2000)
            reply = f"Your credit score is {credit_score} with a borrowing limit of ₹{limit:,.0f}."
    
    elif result.intent == "CHECK_CREDIT_SCORE" and not result.needs_clarification:
        score = borrower.get("credit_score", 500)
        reply = f"Your current credit score is {score} out of 850."
    
    # Generate TTS response
    lang_map = {"en": "en-IN", "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN"}
    tts = voice_service.synthesize_reply(reply, language=lang_map.get(language, "en-IN"))
    
    # Persist session
    await db.voice_sessions.insert_one({
        "user_id": borrower["_id"],
        "session_id": result.session_id,
        "transcript": result.transcript,
        "intent": result.intent,
        "entities": result.entities,
        "reply_text": reply,
        "source": source_label,
        "language": language,
        "created_at": datetime.now(timezone.utc),
    })
    
    return VoiceResponse(
        transcript=result.transcript,
        intent=result.intent,
        entities=result.entities,
        reply_text=reply,
        audio_available=tts.get("audio_available", False),
        session_id=result.session_id,
        language=tts.get("language", "en-IN"),
        use_browser_tts=tts.get("use_browser_tts", True),
        needs_clarification=result.needs_clarification,
        clarification_question=result.clarification_question
    )
