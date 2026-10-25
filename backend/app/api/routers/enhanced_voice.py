"""Enhanced multilingual voice API with real STT/TTS.

This router implements the complete voice pipeline:
- Audio transcription (Whisper)
- Language detection
- Intent classification
- Entity extraction
- Response generation
- Speech synthesis (Google TTS)
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import get_current_user
from app.db.mongodb import get_db
from app.models.schemas import EnhancedVoiceRequest, EnhancedVoiceResponse
from app.services import loan_service
from app.services.multilingual_voice import get_enhanced_voice_service

logger = logging.getLogger("finlend.voice_api")

router = APIRouter(prefix="/api/voice/enhanced", tags=["voice"])


@router.post("/process", response_model=EnhancedVoiceResponse)
async def process_voice_enhanced(
    payload: EnhancedVoiceRequest,
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Process voice input with full multilingual support.
    
    Accepts:
    - text: Direct text input (for testing or typing)
    - audio_base64: Base64-encoded audio (MP3, WAV, etc.)
    - language: Preferred language (en, hi, te, ta)
    
    Returns:
    - Transcript (from STT or input text)
    - Detected language
    - Intent and entities
    - Response text and audio
    """
    service = get_enhanced_voice_service()
    
    # Get user document
    borrower = await db.users.find_one({"_id": loan_service.oid(user["id"])})
    if not borrower:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create conversation context
    session_id = payload.session_id or f"session-{user['id']}-{int(datetime.now(timezone.utc).timestamp())}"
    context = service.get_or_create_context(
        session_id=session_id,
        user_id=user["id"],
        language=payload.language or "en",
    )
    
    context.turn_count += 1
    
    # Step 1: Transcription
    if payload.audio_base64:
        # Decode audio
        try:
            audio_bytes = base64.b64decode(payload.audio_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid audio data: {e}")
        
        # Transcribe
        transcript, detected_lang = service.transcribe_audio(
            audio_data=audio_bytes,
            language=context.language,
        )
        
        if not transcript:
            transcript = ""
            detected_lang = context.language
    else:
        # Use text input
        transcript = payload.text or ""
        detected_lang = service.detect_language(transcript) if transcript else context.language
    
    # Update context language
    context.language = detected_lang
    
    if not transcript:
        # Empty input
        response_text = service.build_response("HELP", {}, borrower, detected_lang, context)
        audio_bytes_out = service.synthesize_speech(response_text, detected_lang)
        
        return EnhancedVoiceResponse(
            transcript="",
            detected_language=detected_lang,
            intent="HELP",
            entities={},
            reply_text=response_text,
            audio_base64=base64.b64encode(audio_bytes_out).decode() if audio_bytes_out else None,
            audio_available=audio_bytes_out is not None,
            session_id=session_id,
            context_maintained=True,
        )
    
    # Step 2: Normalize and detect intent
    normalized = service.normalize_text(transcript, detected_lang)
    intent = service.detect_intent(normalized, detected_lang, context)
    
    # Step 3: Extract entities
    entities = service.extract_entities(normalized, intent, detected_lang)
    
    # Step 4: Handle confirmation/cancellation
    if intent == "CONFIRM" and context.pending_confirmation:
        # Execute pending action
        pending = context.pending_confirmation
        if pending["action"] == "REQUEST_LOAN":
            loan = await loan_service.create_loan_request(
                db,
                borrower,
                pending["amount"],
                pending.get("duration_days", 30),
                "voice-initiated loan",
                "enhanced-voice",
            )
            response_text = _build_loan_reply(loan, detected_lang)
            context.pending_confirmation = None
        else:
            response_text = service.build_response("UNKNOWN", {}, borrower, detected_lang, context)
    
    elif intent == "CANCEL":
        context.pending_confirmation = None
        if detected_lang == "hi":
            response_text = "ठीक है, रद्द किया गया। मैं और कैसे मदद कर सकता हूं?"
        elif detected_lang == "te":
            response_text = "సరే, రద్దు చేయబడింది. నేను మరెలా సహాయం చేయగలను?"
        elif detected_lang == "ta":
            response_text = "சரி, ரத்து செய்யப்பட்டது. நான் எப்படி உதவ முடியும்?"
        else:
            response_text = "Okay, cancelled. How else can I help you?"
    
    elif intent == "REQUEST_LOAN":
        if "amount" in entities:
            # Check if we need confirmation
            amount = entities["amount"]
            duration_days = entities.get("duration_days", 30)
            
            if borrower.get("role") == "borrower" and amount <= borrower.get("borrowing_limit", 2000):
                # Store pending confirmation
                context.pending_confirmation = {
                    "action": "REQUEST_LOAN",
                    "amount": amount,
                    "duration_days": duration_days,
                }
                
                if detected_lang == "hi":
                    response_text = f"क्या आप {amount:,.0f} रुपये का {duration_days} दिनों के लिए ऋण लेना चाहते हैं? पुष्टि करें या रद्द करें।"
                elif detected_lang == "te":
                    response_text = f"మీరు {amount:,.0f} రూపాయల {duration_days} రోజుల రుణం తీసుకోవాలనుకుంటున్నారా? దృఢీకరించండి లేదా రద్దు చేయండి."
                elif detected_lang == "ta":
                    response_text = f"நீங்கள் {amount:,.0f} ரூபாய் {duration_days} நாட்களுக்கு கடன் பெற விரும்புகிறீர்களா? உறுதிப்படுத்து அல்லது ரத்து செய்."
                else:
                    response_text = f"Do you want to request a loan of ₹{amount:,.0f} for {duration_days} days? Say 'yes' to confirm or 'no' to cancel."
            else:
                # Immediate response for ineligible
                response_text = service.build_response(intent, entities, borrower, detected_lang, context)
        else:
            response_text = service.build_response(intent, entities, borrower, detected_lang, context)
    
    else:
        # Standard intent handling
        response_text = service.build_response(intent, entities, borrower, detected_lang, context)
    
    # Update context
    context.last_intent = intent
    if entities:
        context.entity_memory.update(entities)
    
    # Step 5: Synthesize speech
    audio_bytes_out = service.synthesize_speech(response_text, detected_lang)
    
    # Step 6: Persist session
    await db.voice_sessions.insert_one({
        "user_id": borrower["_id"],
        "session_id": session_id,
        "turn_number": context.turn_count,
        "transcript": transcript,
        "detected_language": detected_lang,
        "intent": intent,
        "entities": entities,
        "reply_text": response_text,
        "source": "enhanced-voice",
        "created_at": datetime.now(timezone.utc),
    })
    
    return EnhancedVoiceResponse(
        transcript=transcript,
        detected_language=detected_lang,
        intent=intent,
        entities=entities,
        reply_text=response_text,
        audio_base64=base64.b64encode(audio_bytes_out).decode() if audio_bytes_out else None,
        audio_available=audio_bytes_out is not None,
        session_id=session_id,
        context_maintained=True,
    )


def _build_loan_reply(loan: dict, language: str) -> str:
    """Build loan creation response in target language."""
    status = loan["status"]
    amount = loan["amount"]
    
    if status == "REJECTED":
        reason = loan.get("rejection_reason", "risk check failed")
        if language == "hi":
            return f"क्षमा करें, आपका {amount:,.0f} रुपये का ऋण अनुरोध स्वीकृत नहीं हुआ। कारण: {reason}।"
        elif language == "te":
            return f"క్షమించండి, మీ {amount:,.0f} రూపాయల రుణ అభ్యర్థన ఆమోదించబడలేదు. కారణం: {reason}."
        elif language == "ta":
            return f"மன்னிக்கவும், உங்கள் {amount:,.0f} ரூபாய் கடன் கோரிக்கை அங்கீகரிக்கப்படவில்லை. காரணம்: {reason}."
        else:
            return f"Sorry, your loan request for ₹{amount:,.0f} was not approved. Reason: {reason}."
    
    if language == "hi":
        return f"आपका {amount:,.0f} रुपये का ऋण अनुरोध स्वीकार किया गया है और अब बाजार में फंडिंग के लिए खुला है।"
    elif language == "te":
        return f"మీ {amount:,.0f} రూపాయల రుణ అభ్యర్థన ఆమోదించబడింది మరియు ఇప్పుడు మార్కెట్‌లో ఫండింగ్ కోసం తెరవబడింది."
    elif language == "ta":
        return f"உங்கள் {amount:,.0f} ரூபாய் கடன் கோரிக்கை ஏற்றுக்கொள்ளப்பட்டது மற்றும் இப்போது சந்தையில் நிதிக்கு திறக்கப்பட்டுள்ளது."
    else:
        return f"Your loan request for ₹{amount:,.0f} has been accepted and is now open for funding in the marketplace."
