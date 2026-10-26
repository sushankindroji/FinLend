from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, Form
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase
import httpx

from app.core.security import get_current_user
from app.db.mongodb import get_db
from app.models.schemas import VoiceResponse, VoiceTextRequest
from app.services import loan_service, voice_service

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/tts")
async def text_to_speech(
    text: str,
    language: str = "te"
):
    """100% Free high-quality streaming TTS for Telugu (te), Hindi (hi), and English (en)."""
    lang_code = "te" if "te" in language.lower() else "hi" if "hi" in language.lower() else "en"
    clean_text = text.replace("*", "").replace("#", "").strip()[:300]
    try:
        url = "https://translate.google.com/translate_tts"
        params = {
            "ie": "UTF-8",
            "tl": lang_code,
            "client": "tw-ob",
            "q": clean_text
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                return Response(content=resp.content, media_type="audio/mpeg")
    except Exception as e:
        print(f"TTS streaming error: {e}")
    return Response(content=b"", status_code=500)


@router.post("/dtmf/{digit}", response_model=VoiceResponse)
async def dtmf_turn(
    digit: str,
    session_id: str | None = None,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    text = voice_service.dtmf_to_text(digit)
    return await _handle_turn(text, session_id, user, db, source_label="dtmf", is_audio=False, language="en")


@router.post("/turn", response_model=VoiceResponse)
async def voice_turn(
    payload: VoiceTextRequest,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await _handle_turn(
        payload.text,
        payload.session_id,
        user,
        db,
        source_label="voice",
        is_audio=False,
        language=payload.language or "en"
    )


@router.post("/audio", response_model=VoiceResponse)
async def voice_audio(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    session_id: str | None = Form(None),
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Handle audio upload and transcribe with Groq Whisper (100% FREE)."""
    audio_bytes = await audio.read()
    return await _handle_turn(audio_bytes, session_id, user, db, source_label="voice_audio", is_audio=True, language=language)


@router.post("/transcribe-whisper")
async def transcribe_whisper(
    audio: UploadFile = File(...),
    language: Optional[str] = Form("en"),
    user=Depends(get_current_user),
):
    """Direct audio transcription using Groq Whisper (whisper-large-v3-turbo) - Free tier."""
    audio_bytes = await audio.read()
    text = voice_service.transcribe_with_whisper(audio_bytes, filename=audio.filename or "audio.wav", language=language)
    return {"text": text}


def _format_localized_reply(intent: str, data: dict, language: str = "en", default_text: str = "") -> str:
    lang = (language or "en").lower()
    is_te = "te" in lang
    is_hi = "hi" in lang

    if intent == "REPAY_LOAN":
        amt = data.get("amount", 0)
        new_rem = data.get("remaining_due", 0)
        if new_rem <= 0.01:
            if is_te:
                return f"అద్భుతం! మీ ₹{amt:,.0f} చెల్లింపు విజయవంతమైంది మరియు బ్లాక్‌చెయిన్‌లో నమోదైంది! మీ లోన్ పూర్తిగా చెల్లించబడింది, మీ క్రెడిట్ స్కోర్ పెరిగింది!"
            elif is_hi:
                return f"बहुत बढ़िया! आपका ₹{amt:,.0f} का भुगतान ब्लॉकचेन पर दर्ज हो गया है! आपका लोन पूरा चुकता हो गया है और आपका क्रेडिट स्कोर बढ़ गया है!"
            return f"Awesome! Your payment of ₹{amt:,.0f} is complete and verified on blockchain! Your loan is fully settled, and your credit score has increased!"
        else:
            if is_te:
                return f"విజయవంతమైంది! ₹{amt:,.0f} చెల్లింపు బ్లాక్‌చెయిన్‌లో నమోదైంది. మీ మిగిలిన లోన్ బాకీ ₹{new_rem:,.0f}."
            elif is_hi:
                return f"सफलता! ₹{amt:,.0f} का भुगतान ब्लॉकचेन पर दर्ज किया गया। आपकी शेष लोन राशि ₹{new_rem:,.0f} है।"
            return f"Success! Repayment of ₹{amt:,.0f} recorded on blockchain. Your remaining loan balance is ₹{new_rem:,.0f}."

    elif intent == "REPAY_PROMPT":
        amt = data.get("amount", 0)
        rem = data.get("remaining_due", 0)
        if is_te:
            return f"మీకు ₹{amt:,.0f} యాక్టివ్ లోన్ ఉంది, మిగిలిన బాకీ ₹{rem:,.0f}. ఈరోజు మీరు ఎంత చెల్లించాలనుకుంటున్నారు? మీరు మొత్తం లేదా ₹500 వంటి ఏదైనా మొత్తం చెప్పవచ్చు."
        elif is_hi:
            return f"आपके पास ₹{amt:,.0f} का सक्रिय लोन है जिसकी शेष राशि ₹{rem:,.0f} है। आज आप कितना चुकाना चाहेंगे? आप पूरा या 500 रुपये जैसा कोई भी हिस्सा बता सकते हैं।"
        return f"You have an active loan of ₹{amt:,.0f} with ₹{rem:,.0f} remaining balance. How much would you like to repay today? You can say full or any specific amount like 500."

    elif intent == "NO_ACTIVE_LOANS":
        limit = data.get("limit", 2000)
        if is_te:
            return f"మీకు ప్రస్తుతం తిరిగి చెల్లించాల్సిన యాక్టివ్ లోన్లు లేవు. మీ అప్పు పరిమితి ₹{limit:,.0f}. మీరు కొత్త లోన్ కోసం దరఖాస్తు చేసుకోవాలనుకుంటున్నారా?"
        elif is_hi:
            return f"वर्तमान में आपके पास चुकाने के लिए कोई सक्रिय लोन नहीं है। आपकी उधार सीमा ₹{limit:,.0f} है। क्या आप नया लोन लेना चाहते हैं?"
        return f"You do not have any active loans pending repayment. Your borrowing limit is ₹{limit:,.0f} if you would like to apply for a new loan."

    elif intent == "CHECK_LOAN_STATUS":
        amt = data.get("amount", 0)
        status = data.get("status", "ACTIVE")
        rem = data.get("remaining_due", 0)
        if is_te:
            return f"మీకు ₹{amt:,.0f} యాక్టివ్ లోన్ ఉంది (స్థితి: {status}). మీ మిగిలిన బాకీ ₹{rem:,.0f}."
        elif is_hi:
            return f"आपके पास ₹{amt:,.0f} का सक्रिय लोन है। आपकी शेष बकाया राशि ₹{rem:,.0f} है।"
        return f"You have an active loan of ₹{amt:,.0f} in status {status}. Your remaining balance is ₹{rem:,.0f}."

    elif intent == "CHECK_BALANCE":
        limit = data.get("limit", 2000)
        score = data.get("score", 500)
        if is_te:
            return f"మీ ప్రస్తుత అప్పు పరిమితి ₹{limit:,.0f} మరియు క్రెడిట్ స్కోర్ {score}."
        elif is_hi:
            return f"आपकी वर्तमान उधार सीमा ₹{limit:,.0f} और क्रेडिट स्कोर {score} है।"
        return f"Your current borrowing limit is ₹{limit:,.0f} with a credit score of {score}."

    elif intent == "CHECK_CREDIT_SCORE":
        score = data.get("score", 500)
        if is_te:
            return f"మీ క్రెడిట్ స్కోర్ 850 కి {score}. సకాలంలో తిరిగి చెల్లించడం వల్ల మీ స్కోర్ మరియు అప్పు పరిమితి పెరుగుతుంది."
        elif is_hi:
            return f"आपका क्रेडिट स्कोर 850 में से {score} है। समय पर भुगतान करने से आपका स्कोर और उधार सीमा बढ़ेगी।"
        return f"Your credit score is {score} out of 850. Making on-time repayments will increase your score and raise your borrowing limit."

    elif intent == "END_CALL":
        if is_te:
            return "ఫిన్లెండ్ వాయిస్ ఏజెంట్‌తో మాట్లాడినందుకు ధన్యవాదాలు. సెలవు! మళ్ళీ కలవండి."
        elif is_hi:
            return "फिनलैंड वॉइस एजेंट से बात करने के लिए धन्यवाद। आपका दिन शुभ हो! अलविदा।"
        return "Thank you for speaking with FinLend Voice Agent. Have a wonderful day! Goodbye."

    return default_text


async def _handle_turn(
    input_data: str | bytes,
    session_id: str | None,
    user: dict,
    db: AsyncIOMotorDatabase,
    source_label: str,
    is_audio: bool = False,
    language: str = "en"
) -> VoiceResponse:
    # 1. Fetch user & role
    borrower = await db.users.find_one({"_id": loan_service.oid(user["id"])})
    
    if borrower is None:
        err_msg = "వినియోగదారు కనుగొనబడలేదు." if "te" in language else "उपयोगकर्ता नहीं मिला।" if "hi" in language else "User not found. Please sign in again."
        return VoiceResponse(
            transcript="",
            intent="ERROR",
            entities={},
            reply_text=err_msg,
            audio_available=False,
            session_id=session_id or "",
            needs_clarification=False,
            clarification_question="",
            end_call=True
        )

    # 2. Fetch active and outstanding loans for context
    active_loans_cursor = db.loans.find({
        "borrower_id": borrower["_id"],
        "status": {"$in": ["ACTIVE", "LATE", "FUNDED", "DISBURSED"]}
    }).sort("created_at", -1)
    active_loans = await active_loans_cursor.to_list(10)

    # Build detailed context for Groq AI
    active_loans_info = []
    for l in active_loans:
        amount_repaid = l.get("amount_repaid", 0.0)
        total_due = l.get("total_due", l.get("amount", 0.0))
        rem = max(0.0, round(total_due - amount_repaid, 2))
        active_loans_info.append({
            "id": str(l["_id"]),
            "amount": l.get("amount", 0),
            "total_due": total_due,
            "amount_repaid": amount_repaid,
            "remaining_due": rem,
            "status": l.get("status"),
            "duration_days": l.get("duration_days"),
        })

    user_profile = {
        "role": borrower.get("role", "borrower"),
        "credit_score": borrower.get("credit_score", 500),
        "borrowing_limit": borrower.get("borrowing_limit", 2000),
        "balance": borrower.get("lending_balance", 0) if borrower.get("role") == "lender" else (borrower.get("wallet_balance", 0.0) or 0.0),
        "wallet_balance": borrower.get("wallet_balance", 0.0) or 0.0,
        "active_loans": active_loans_info
    }

    # 3. Process turn with Groq Whisper & Conversational AI in user's language
    result = voice_service.process_voice_turn(
        input_data,
        session_id,
        is_audio=is_audio,
        language=language,
        user_profile=user_profile
    )

    reply = result.response
    action_taken = None
    end_call = result.end_call
    action_data = {}

    # 4. Execute Autonomous Actions based on detected intent:

    # ── ACTION A: REPAY_LOAN ──────────────────────────────────────────
    if result.intent == "REPAY_LOAN":
        if not active_loans:
            reply = _format_localized_reply(
                "NO_ACTIVE_LOANS",
                {"limit": borrower.get("borrowing_limit", 2000)},
                language=language
            )
            action_taken = "NO_ACTIVE_LOANS"
        else:
            target_loan = active_loans[0]
            rem_due = max(0.0, round(target_loan.get("total_due", 0.0) - target_loan.get("amount_repaid", 0.0), 2))
            
            repay_amt = None
            if result.entities.get("pay_all"):
                repay_amt = rem_due
            elif result.entities.get("amount"):
                repay_amt = min(float(result.entities["amount"]), rem_due)

            if repay_amt and repay_amt > 0:
                try:
                    repay_res = await loan_service.repay_loan(db, str(target_loan["_id"]), borrower, repay_amt)
                    new_rem = max(0.0, round(rem_due - repay_amt, 2))
                    tx_hash = repay_res.get("repayment", {}).get("tx_hash", "0x")
                    
                    reply = _format_localized_reply(
                        "REPAY_LOAN",
                        {"amount": repay_amt, "remaining_due": new_rem},
                        language=language
                    )
                    
                    action_taken = "LOAN_REPAID"
                    action_data = {
                        "loan_id": str(target_loan["_id"]),
                        "amount": repay_amt,
                        "remaining_due": new_rem,
                        "tx_hash": tx_hash
                    }
                except HTTPException as he:
                    action_taken = "INSUFFICIENT_BALANCE"
                    wbal = float(borrower.get("wallet_balance") or 0.0)
                    if "insufficient" in str(he.detail).lower() or "balance" in str(he.detail).lower():
                        if "te" in language:
                            reply = f"మీ బ్యాంక్ వాలెట్ బ్యాలెన్స్ చాలదు (ప్రస్తుత బ్యాలెన్స్ ₹{wbal:,.2f}). లోన్ ₹{repay_amt:,.2f} చెల్లించడానికి దయచేసి ముందుగా డిపాజిట్ చేయండి."
                        elif "hi" in language:
                            reply = f"आपके बैंक वॉलेट में पर्याप्त बैलेंस नहीं है (वर्तमान बैलेंस ₹{wbal:,.2f})। ₹{repay_amt:,.2f} चुकाने के लिए कृपया पहले पैसे जमा करें।"
                        else:
                            reply = f"Insufficient bank wallet balance (current balance ₹{wbal:,.2f}). Please deposit funds first to repay ₹{repay_amt:,.2f}."
                    else:
                        reply = str(he.detail)
                except Exception as e:
                    reply = f"Could not complete repayment: {str(e)}"
                    action_taken = "REPAY_ERROR"

            else:
                reply = _format_localized_reply(
                    "REPAY_PROMPT",
                    {"amount": target_loan.get("amount", 0), "remaining_due": rem_due},
                    language=language
                )
                result.needs_clarification = True
                result.clarification_question = reply

    # ── ACTION B: DEPOSIT_FUNDS ───────────────────────────────────────
    elif result.intent == "DEPOSIT_FUNDS":
        deposit_amt = None
        if result.entities.get("amount"):
            try:
                deposit_amt = float(result.entities["amount"])
            except (ValueError, TypeError):
                deposit_amt = None

        if deposit_amt and deposit_amt > 0:
            try:
                updated_user = await db.users.find_one_and_update(
                    {"_id": borrower["_id"]},
                    {"$inc": {"wallet_balance": deposit_amt}},
                    return_document=True,
                )
                new_bal = round(float((updated_user or {}).get("wallet_balance", 0.0)), 2)

                await db.transactions.insert_one({
                    "user_id": borrower["_id"],
                    "type": "DEPOSIT",
                    "amount": deposit_amt,
                    "balance_after": new_bal,
                    "source": "VOICE_AGENT",
                    "created_at": datetime.now(timezone.utc),
                })

                from app.services.realtime_service import get_realtime_service
                realtime = get_realtime_service()
                await realtime.notify_user(str(borrower["_id"]), "wallet_balance_updated", {
                    "user_id": str(borrower["_id"]),
                    "wallet_balance": new_bal,
                    "balance": new_bal,
                    "amount": deposit_amt,
                    "action": "DEPOSIT",
                    "message": f"Deposited ₹{deposit_amt:,.2f} via FinLend Voice Assistant.",
                })

                if "te" in language:
                    reply = f"మీ బ్యాంక్ వాలెట్‌లో ₹{deposit_amt:,.2f} విజయవంతంగా జమ చేయబడింది. మీ ప్రస్తుత బ్యాలెన్స్ ₹{new_bal:,.2f}."
                elif "hi" in language:
                    reply = f"आपके बैंक वॉलेट में ₹{deposit_amt:,.2f} सफलतापूर्वक जमा कर दिए गए हैं। वर्तमान बैलेंस ₹{new_bal:,.2f} है।"
                else:
                    reply = f"Successfully deposited ₹{deposit_amt:,.2f} into your account. Your new balance is ₹{new_bal:,.2f}."

                action_taken = "FUNDS_DEPOSITED"
                action_data = {"amount": deposit_amt, "new_balance": new_bal}
            except Exception as e:
                reply = f"Error depositing funds: {str(e)}"
                action_taken = "DEPOSIT_ERROR"
        else:
            if "te" in language:
                reply = "మీరు ఎంత మొత్తం డిపాజిట్ చేయాలనుకుంటున్నారు?"
            elif "hi" in language:
                reply = "आप अपने बैंक वॉलेट में कितने पैसे जमा करना चाहते हैं?"
            else:
                reply = "How much money would you like to deposit into your bank wallet?"
            result.needs_clarification = True
            result.clarification_question = reply

    # ── ACTION C: WITHDRAW_FUNDS ──────────────────────────────────────
    elif result.intent == "WITHDRAW_FUNDS":
        w_amt = None
        if result.entities.get("amount"):
            try:
                w_amt = float(result.entities["amount"])
            except (ValueError, TypeError):
                w_amt = None

        if w_amt and w_amt > 0:
            fresh_user = await db.users.find_one({"_id": borrower["_id"]})
            wbal = float((fresh_user or borrower).get("wallet_balance") or 0.0)

            if w_amt > wbal + 1e-6:
                action_taken = "INSUFFICIENT_BALANCE"
                if "te" in language:
                    reply = f"మీ బ్యాంక్ వాలెట్ బ్యాలెన్స్ చాలదు (ప్రస్తుత బ్యాలెన్స్ ₹{wbal:,.2f}). మీరు ₹{w_amt:,.2f} విత్‌డ్రా చేయలేరు."
                elif "hi" in language:
                    reply = f"आपके बैंक वॉलेट में पर्याप्त बैलेंस नहीं है (वर्तमान बैलेंस ₹{wbal:,.2f})। आप ₹{w_amt:,.2f} नहीं निकाल सकते।"
                else:
                    reply = f"Insufficient wallet balance (current balance ₹{wbal:,.2f}). Cannot withdraw ₹{w_amt:,.2f}."
            else:
                updated_user = await db.users.find_one_and_update(
                    {"_id": borrower["_id"], "wallet_balance": {"$gte": w_amt}},
                    {"$inc": {"wallet_balance": -w_amt}},
                    return_document=True,
                )
                if updated_user:
                    new_bal = round(float(updated_user.get("wallet_balance", 0.0)), 2)
                    await db.transactions.insert_one({
                        "user_id": borrower["_id"],
                        "type": "WITHDRAWAL",
                        "amount": w_amt,
                        "balance_after": new_bal,
                        "source": "VOICE_AGENT",
                        "created_at": datetime.now(timezone.utc),
                    })

                    from app.services.realtime_service import get_realtime_service
                    realtime = get_realtime_service()
                    await realtime.notify_user(str(borrower["_id"]), "wallet_balance_updated", {
                        "user_id": str(borrower["_id"]),
                        "wallet_balance": new_bal,
                        "balance": new_bal,
                        "amount": w_amt,
                        "action": "WITHDRAW",
                        "message": f"Withdrew ₹{w_amt:,.2f} via FinLend Voice Assistant.",
                    })

                    if "te" in language:
                        reply = f"మీ వాలెట్ నుండి ₹{w_amt:,.2f} విజయవంతంగా విత్‌డ్రా చేయబడింది. మిగిలిన బ్యాలెన్స్ ₹{new_bal:,.2f}."
                    elif "hi" in language:
                        reply = f"आपके बैंक वॉलेट से ₹{w_amt:,.2f} सफलतापूर्वक निकाल लिए गए हैं। शेष बैलेंस ₹{new_bal:,.2f} है।"
                    else:
                        reply = f"Successfully withdrew ₹{w_amt:,.2f} from your wallet. Your remaining balance is ₹{new_bal:,.2f}."

                    action_taken = "FUNDS_WITHDRAWN"
                    action_data = {"amount": w_amt, "new_balance": new_bal}
                else:
                    reply = "Withdrawal could not be processed due to a concurrent transaction."
                    action_taken = "WITHDRAW_ERROR"
        else:
            if "te" in language:
                reply = "మీరు ఎంత మొత్తం విత్‌డ్రా చేయాలనుకుంటున్నారు?"
            elif "hi" in language:
                reply = "आप अपने बैंक वॉलेट से कितने पैसे निकालना चाहते हैं?"
            else:
                reply = "How much money would you like to withdraw from your wallet?"
            result.needs_clarification = True
            result.clarification_question = reply

    # ── ACTION D: REQUEST_LOAN ────────────────────────────────────────
    elif result.intent == "REQUEST_LOAN":
        has_amount = bool(result.entities.get("amount"))
        has_duration = bool(result.entities.get("duration_days"))
        
        if has_amount and has_duration and borrower.get("role") == "borrower":
            try:
                loan = await loan_service.create_loan_request(
                    db,
                    borrower,
                    float(result.entities["amount"]),
                    int(result.entities["duration_days"]),
                    result.entities.get("purpose", "voice-initiated loan"),
                    source_label,
                )
                
                if loan["status"] == "REJECTED":
                    reason = loan.get("rejection_reason", "limit reached")
                    if "te" in language:
                        reply = f"క్షమించండి, మీ ₹{loan['amount']:,.0f} లోన్ ఆమోదించబడలేదు. కారణం: {reason}."
                    elif "hi" in language:
                        reply = f"क्षमा करें, आपका ₹{loan['amount']:,.0f} का लोन स्वीकृत नहीं हुआ। कारण: {reason}."
                    else:
                        reply = f"Sorry, your loan request for ₹{loan['amount']:,.0f} could not be approved. Reason: {reason}."
                    action_taken = "LOAN_REJECTED"
                else:
                    if "te" in language:
                        reply = f"అద్భుతం! మీ ₹{loan['amount']:,.0f} లోన్ రిక్వెస్ట్ ఆమోదించబడింది మరియు మార్కెట్‌ప్లేస్‌లో ఫండింగ్ కోసం తెరవబడింది."
                    elif "hi" in language:
                        reply = f"बहुत अच्छा! आपका ₹{loan['amount']:,.0f} का लोन स्वीकृत हो गया है और फंडिंग के लिए उपलब्ध है।"
                    else:
                        reply = f"Great! Your loan request for ₹{loan['amount']:,.0f} for {loan['duration_days']} days has been approved and opened for funding."
                    action_taken = "LOAN_CREATED"
                    action_data = {"loan_id": str(loan["_id"]), "amount": loan["amount"]}

                from app.services.notification_service import emit_notification
                await emit_notification(
                    db,
                    user_id=str(borrower["_id"]),
                    notif_type="LOAN_APPROVED" if loan["status"] in ("APPROVED", "OPEN_FOR_FUNDING") else "LOAN_REJECTED",
                    title="Voice Agent - Loan Processed",
                    body=reply,
                    loan_id=str(loan["_id"]),
                )
            except Exception as e:
                reply = f"Error processing loan: {str(e)}"
                action_taken = "LOAN_ERROR"
        else:
            if not has_amount and not has_duration:
                reply = "మీకు ఎంత మొత్తం లోన్ కావాలి మరియు ఎన్ని రోజుల కోసం?" if "te" in language else "आपको कितना लोन चाहिए और कितने दिनों के लिए?" if "hi" in language else "Sure, how much loan amount do you need and for how many days?"
            elif not has_amount:
                reply = f"మీకు ఎంత లోన్ మొత్తం కావాలి?" if "te" in language else "आपको कितना लोन अमाउंट चाहिए?" if "hi" in language else f"How much loan amount do you need for {result.entities.get('duration_days')} days?"
            else:
                reply = f"₹{result.entities.get('amount'):,.0f} లోన్ ఎన్ని రోజుల కోసం కావాలి?" if "te" in language else f"₹{result.entities.get('amount'):,.0f} का लोन कितने दिनों के लिए चाहिए?" if "hi" in language else f"For how many days or months do you need the ₹{result.entities.get('amount'):,.0f} loan?"
            result.needs_clarification = True

    # ── ACTION C: CHECK_LOAN_STATUS ───────────────────────────────────
    elif result.intent == "CHECK_LOAN_STATUS":
        if active_loans:
            target = active_loans[0]
            rem = max(0.0, round(target.get("total_due", 0.0) - target.get("amount_repaid", 0.0), 2))
            reply = _format_localized_reply(
                "CHECK_LOAN_STATUS",
                {"amount": target.get("amount", 0), "status": target.get("status"), "remaining_due": rem},
                language=language
            )
        else:
            reply = _format_localized_reply(
                "NO_ACTIVE_LOANS",
                {"limit": borrower.get("borrowing_limit", 2000)},
                language=language
            )
        action_taken = "LOANS_STATUS"

    # ── ACTION D: CHECK_BALANCE ───────────────────────────────────────
    elif result.intent == "CHECK_BALANCE":
        if borrower.get("role") == "lender":
            bal = borrower.get("lending_balance", 0)
            reply = f"మీ అందుబాటులో ఉన్న బ్యాలెన్స్ ₹{bal:,.2f}." if "te" in language else f"आपका उपलब्ध बैलेंस ₹{bal:,.2f} है।" if "hi" in language else f"Your available lending balance is ₹{bal:,.2f}."
        else:
            wbal = borrower.get("wallet_balance", 0.0) or 0.0
            reply = (
                f"మీ బ్యాంక్ వాలెట్ బ్యాలెన్స్ ₹{wbal:,.2f}, మరియు క్రెడిట్ పరిమితి ₹{borrower.get('borrowing_limit', 2000):,.0f}."
                if "te" in language
                else f"आपका बैंक वॉलेट बैलेंस ₹{wbal:,.2f} है और उधार सीमा ₹{borrower.get('borrowing_limit', 2000):,.0f} है।"
                if "hi" in language
                else f"Your real-time bank wallet balance is ₹{wbal:,.2f} with borrowing limit of ₹{borrower.get('borrowing_limit', 2000):,.0f}."
            )
        action_taken = "BALANCE_CHECKED"


    # ── ACTION E: CHECK_CREDIT_SCORE ──────────────────────────────────
    elif result.intent == "CHECK_CREDIT_SCORE":
        reply = _format_localized_reply(
            "CHECK_CREDIT_SCORE",
            {"score": borrower.get("credit_score", 500)},
            language=language
        )
        action_taken = "SCORE_CHECKED"

    # ── ACTION F: CALCULATE_EMI ───────────────────────────────────────
    elif result.intent == "CALCULATE_EMI":
        amt = float(result.entities.get("amount") or 5000)
        days = int(result.entities.get("duration_days") or 30)
        months = max(1, days // 30)
        interest = round(amt * 0.12 * (days / 365), 2)
        total = round(amt + interest, 2)
        emi = round(total / months, 2)
        if "te" in language:
            reply = f"₹{amt:,.0f} లోన్ కోసం {days} రోజులకు అంచనా వేసిన మొత్తం ₹{total:,.0f}, నెలకు సుమారుగా ₹{emi:,.0f} EMI అవుతుంది."
        elif "hi" in language:
            reply = f"₹{amt:,.0f} के लोन के लिए {days} दिनों में कुल ₹{total:,.0f} चुकाना होगा, प्रति माह लगभग ₹{emi:,.0f} ईएमआई होगी।"
        else:
            reply = f"For a loan of ₹{amt:,.0f} for {days} days, estimated total is ₹{total:,.0f} with an EMI of approximately ₹{emi:,.0f} per month."
        action_taken = "EMI_CALCULATED"

    # ── ACTION G: END_CALL ────────────────────────────────────────────
    elif result.intent == "END_CALL" or end_call:
        reply = _format_localized_reply("END_CALL", {}, language=language)
        end_call = True
        action_taken = "CALL_ENDED"

    # 5. Language TTS synthesis
    lang_map = {"en": "en-IN", "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN"}
    tts = voice_service.synthesize_reply(reply, language=lang_map.get(language, "en-IN"))

    # 6. Persist conversation turn in DB
    await db.voice_sessions.insert_one({
        "user_id": borrower["_id"],
        "session_id": result.session_id,
        "transcript": result.transcript,
        "intent": result.intent,
        "entities": result.entities,
        "reply_text": reply,
        "action_taken": action_taken,
        "source": source_label,
        "language": language,
        "created_at": datetime.now(timezone.utc),
    })

    return VoiceResponse(
        transcript=result.transcript,
        intent=result.intent,
        entities=result.entities,
        reply_text=reply,
        audio_available=True,
        session_id=result.session_id,
        language=tts.get("language", "en-IN"),
        use_browser_tts=True,
        needs_clarification=result.needs_clarification,
        clarification_question=result.clarification_question,
        action_taken=action_taken,
        end_call=end_call,
        data=action_data
    )
