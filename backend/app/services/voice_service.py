"""100% FREE voice layer - NO PAID APIs.

Pipeline:
    Browser STT -> Groq LLM (FREE) -> Context Management -> Browser TTS

FREE stack:
  - Browser Web Speech API for STT (Hindi, Telugu, English) - FREE
  - Groq API for conversational AI (FREE unlimited) - FREE
  - Browser Web Speech API for TTS - FREE
  - No OpenAI, no paid services
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx

from app.core.config import get_settings

# Conversation context storage
_conversation_contexts: Dict[str, List[Dict[str, Any]]] = {}

# Groq System prompt (FREE API, same quality as GPT-4)
VOICE_ASSISTANT_SYSTEM_PROMPT = """You are a voice assistant for FinLend, a peer-to-peer micro-lending platform for rural and financially underserved users. Your role is to help users through voice conversations in their preferred language (English, Hindi, or Telugu).

**Your capabilities:**
1. Help borrowers request loans (extract: amount, duration in days, purpose)
2. Check credit scores and borrowing limits
3. Check loan status and repayment schedules
4. Guide through repayment process
5. Provide balance information
6. Answer questions about the platform

**User Profile Context (provided in each request):**
- role: borrower or lender
- credit_score: current score
- borrowing_limit: maximum loan amount
- lending_balance: available for lenders

**Conversation Guidelines:**
- Be warm, friendly, and patient
- Speak simply for low-literacy users
- Ask clarifying questions if information is incomplete
- Extract specific details: loan amount (in rupees), duration (in days), purpose
- Confirm understanding before taking action
- Respond in the user's language (match their input language)

**CRITICAL: HANDLE NATURAL MIXED-LANGUAGE SPEECH**
Users often mix languages naturally:
- "నాకు 5000 రుపీస్ లోన్ కావాలి 10 డేస్ కి" (Telugu + English words)
- "मुझे 5000 rupees loan चाहिए 30 days के लिए" (Hindi + English)
- Numbers are often in English even in native language speech
- Words like "days", "rupees", "loan" may be in English

**Entity Extraction Rules:**
1. Extract ANY number that looks like a loan amount (3+ digits)
2. Extract ANY number that looks like duration (typically 7-365 days)
3. Recognize mixed vocabulary: "డేస్"="days", "రుపీస్"="rupees", "లోన్"="loan"
4. If you see TWO numbers, the larger is usually amount, smaller is duration
5. Duration can be: days/డేస్/दिन, weeks/వీక్స్/सप्ताह, months/మంత్స్/महीने

**Output Format (STRICT JSON):**
{
  "intent": "REQUEST_LOAN|CHECK_BALANCE|CHECK_CREDIT_SCORE|CHECK_LOAN_STATUS|CHECK_REPAYMENT|MAKE_REPAYMENT|HELP|CLARIFY|GREETING|UNKNOWN",
  "entities": {
    "amount": <number or null>,
    "duration_days": <number or null>,
    "purpose": "<string or null>",
    "language": "en|hi|te"
  },
  "response": "<natural language response in user's language>",
  "needs_clarification": <true if more info needed, false if ready to proceed>,
  "clarification_question": "<question to ask user if needs_clarification=true>"
}

**Examples of Natural Speech to Handle:**
- "నాకు 5000 రుపీస్ లోన్ కావాలి 10 డేస్ కి" → amount: 5000, duration_days: 10
- "मुझे 10000 का loan चाहिए 60 दिन के लिए" → amount: 10000, duration_days: 60
- "I need 5k loan for 2 months" → amount: 5000, duration_days: 60
- "3000 రూపాయల 15 రోజుల లోన్" → amount: 3000, duration_days: 15

**Important:**
- Extract entities even from mixed-language casual speech
- Be flexible with word order and phrasing
- If unsure, ask for confirmation but include your best guess
- Always respond in the same language the user spoke (or primary language used)
"""

# DTMF keypad fallback
DTMF_INTENT_MAP = {
    "1": "CHECK_BALANCE",
    "2": "CHECK_CREDIT_SCORE",
    "3": "CHECK_LOAN_STATUS",
    "4": "REQUEST_LOAN",
    "5": "CHECK_REPAYMENT",
    "6": "MAKE_REPAYMENT",
    "0": "HELP",
}


def get_conversation_context(session_id: str, max_turns: int = 5) -> List[Dict[str, Any]]:
    """Retrieve recent conversation history for context."""
    return _conversation_contexts.get(session_id, [])[-max_turns:]


def update_conversation_context(session_id: str, user_input: str, assistant_response: dict):
    """Store conversation turn in context."""
    if session_id not in _conversation_contexts:
        _conversation_contexts[session_id] = []
    
    _conversation_contexts[session_id].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user_input,
        "assistant": assistant_response
    })
    
    # Keep only last 20 turns
    if len(_conversation_contexts[session_id]) > 20:
        _conversation_contexts[session_id] = _conversation_contexts[session_id][-20:]


def groq_conversation(
    user_input: str,
    user_profile: dict,
    conversation_history: List[Dict[str, Any]],
    language: str = "en"
) -> dict:
    """
    Use Groq FREE API for natural conversation and intent understanding.
    Groq is FREE unlimited and as good as GPT-4.
    
    Args:
        user_input: What the user said
        user_profile: User's credit score, limits, balance, role
        conversation_history: Recent conversation turns
        language: Preferred language code
    
    Returns:
        {
            "intent": str,
            "entities": dict,
            "response": str,
            "needs_clarification": bool,
            "clarification_question": str
        }
    """
    settings = get_settings()
    
    if not settings.groq_api_key:
        # Fallback to basic pattern matching
        return _fallback_intent_detection(user_input)
    
    try:
        # PRE-PROCESS: Extract entities ourselves as backup (Groq sometimes misses mixed language)
        fallback_entities = _extract_entities_simple(user_input)
        
        # Build conversation messages
        messages = [
            {"role": "system", "content": VOICE_ASSISTANT_SYSTEM_PROMPT}
        ]
        
        # Add conversation history
        for turn in conversation_history:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": json.dumps(turn["assistant"])})
        
        # Add current user input with profile context
        user_message = f"""User Profile:
- Role: {user_profile.get('role', 'borrower')}
- Credit Score: {user_profile.get('credit_score', 'N/A')}
- Borrowing Limit: ₹{user_profile.get('borrowing_limit', 0):,.0f}
- Balance: ₹{user_profile.get('balance', 0):,.0f}

User says: "{user_input}"

IMPORTANT: Extract ALL numbers you see. If there are 2 numbers, the larger is amount, smaller is days.
Example: "నాకు 5000 రుపీస్ లోన్ కావాలి 10 డేస్ కి" should extract amount=5000, duration_days=10

Respond in JSON format with intent, entities, and natural response in {language} language."""
        
        messages.append({"role": "user", "content": user_message})
        
        # Call Groq FREE API
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",  # FREE, fast, excellent quality
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500,
                "response_format": {"type": "json_object"}
            },
            timeout=30.0
        )
        
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]
        result_json = json.loads(result)
        
        # MERGE: Use fallback entities if Groq didn't extract them
        entities = result_json.get("entities", {})
        if not entities.get("amount") and fallback_entities.get("amount"):
            entities["amount"] = fallback_entities["amount"]
        if not entities.get("duration_days") and fallback_entities.get("duration_days"):
            entities["duration_days"] = fallback_entities["duration_days"]
        
        # Validate and normalize result
        return {
            "intent": result_json.get("intent", "UNKNOWN"),
            "entities": entities,
            "response": result_json.get("response", "मुझे समझ नहीं आया। कृपया फिर से बताएं।"),
            "needs_clarification": result_json.get("needs_clarification", False),
            "clarification_question": result_json.get("clarification_question", "")
        }
        
    except Exception as e:
        print(f"Groq API error: {e}")
        return _fallback_intent_detection(user_input)


def _extract_entities_simple(text: str) -> dict:
    """Simple entity extraction as backup for Groq."""
    entities = {}
    text_lower = text.lower()
    
    # Find all numbers
    numbers = [int(n) for n in re.findall(r'\b(\d+)\b', text_lower)]
    
    if len(numbers) >= 2:
        # Likely have both amount and duration
        numbers_sorted = sorted(numbers, reverse=True)
        entities["amount"] = float(numbers_sorted[0])
        # Duration is typically 7-365 days
        for num in numbers_sorted[1:]:
            if 7 <= num <= 365:
                entities["duration_days"] = num
                break
    elif len(numbers) == 1:
        num = numbers[0]
        # Guess based on magnitude
        if num >= 1000:  # Likely amount
            entities["amount"] = float(num)
        elif 7 <= num <= 365:  # Likely duration
            entities["duration_days"] = num
    
    return entities


def _fallback_intent_detection(user_input: str) -> dict:
    """
    Fallback to basic pattern matching if Groq fails.
    HANDLES MIXED LANGUAGE NATURAL SPEECH.
    """
    text = user_input.lower()
    
    # Enhanced amount extraction - handles mixed language
    amount_patterns = [
        r'(\d+(?:,\d{3})*)\s*(?:rupees|rupee|rs|₹|रुपये|రుపీస్|రూపాయల)',
        r'(\d{3,})',  # Any 3+ digit number
    ]
    
    amount = None
    for pattern_str in amount_patterns:
        match = re.search(pattern_str, text)
        if match:
            try:
                amount = float(match.group(1).replace(',', ''))
                if amount >= 100:
                    break
            except:
                continue
    
    # Enhanced duration extraction - handles "డేస్", "days", "రోజులు"
    duration_days = None
    
    # Try multiple patterns
    duration_patterns = [
        r'(\d+)\s*(?:days?|డేస్|దినాలు|రోజులు|दिन|दिनों)',  # Mixed language days
        r'(\d+)\s*(?:weeks?|వీక్స్|వారాలు|सप्ताह)',  # Weeks
        r'(\d+)\s*(?:months?|మంత్స్|నెలలు|महीने)',  # Months
        r'(\d+)\s*కి',  # Telugu possessive (number + ki)
        r'(\d+)\s*के\s*लिए',  # Hindi (for)
    ]
    
    for pattern_str in duration_patterns:
        match = re.search(pattern_str, text, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(0).lower()
            
            # Convert to days
            if any(x in unit for x in ['month', 'మంత్స్', 'నెలలు', 'महीने']):
                duration_days = value * 30
            elif any(x in unit for x in ['week', 'వీక్స్', 'వారాలు', 'सप्ताह']):
                duration_days = value * 7
            else:
                duration_days = value
            break
    
    # SMART FALLBACK: If we have amount but no duration, find other number
    if amount and not duration_days:
        all_numbers = re.findall(r'\b(\d+)\b', text)
        for num_str in all_numbers:
            num = int(num_str)
            # Reasonable duration range
            if 7 <= num <= 365 and num != amount:
                duration_days = num
                break
    
    entities = {}
    if amount:
        entities["amount"] = amount
    if duration_days:
        entities["duration_days"] = duration_days
    
    # Intent detection (flexible with mixed language)
    loan_keywords = ["loan", "borrow", "need money", "ముझे पैसे चाहिए", "లోన్", "उधार", "కావాలి", "चाहिए"]
    if any(word in text for word in loan_keywords):
        needs_clarification = not (entities.get("amount") and entities.get("duration_days"))
        return {
            "intent": "REQUEST_LOAN",
            "entities": entities,
            "response": "I'll help you with a loan. Please tell me the amount and duration." if needs_clarification else f"Creating your loan for ₹{entities.get('amount', 0):.0f} for {entities.get('duration_days', 0)} days.",
            "needs_clarification": needs_clarification,
            "clarification_question": "How much amount and for how many days?" if needs_clarification else ""
        }
    elif any(word in text for word in ["balance", "బ్యాలెన్స్", "बैलेंस", "खाता", "account"]):
        return {
            "intent": "CHECK_BALANCE",
            "entities": {},
            "response": "Let me check your balance.",
            "needs_clarification": False,
            "clarification_question": ""
        }
    elif any(word in text for word in ["credit score", "score", "స్కోర్", "स्कोर", "rating", "रेटिंग"]):
        return {
            "intent": "CHECK_CREDIT_SCORE",
            "entities": {},
            "response": "Let me check your credit score.",
            "needs_clarification": False,
            "clarification_question": ""
        }
    
    return {
        "intent": "UNKNOWN",
        "entities": {},
        "response": "I didn't understand. Can you please repeat?",
        "needs_clarification": True,
        "clarification_question": "How can I help you today?"
    }


def transcribe_demo(text_payload: str) -> str:
    """Browser handles STT, we just receive text."""
    return text_payload.strip()


def dtmf_to_text(digit: str) -> str:
    intent = DTMF_INTENT_MAP.get(digit, "HELP")
    return intent.replace("_", " ").lower()


@dataclass
class VoiceTurnResult:
    transcript: str
    intent: str
    entities: dict
    response: str
    needs_clarification: bool
    clarification_question: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def process_voice_turn(
    raw_input: str | bytes,
    session_id: str | None = None,
    is_audio: bool = False,
    language: str = "en",
    user_profile: dict = None
) -> VoiceTurnResult:
    """
    Process voice input using Groq FREE conversation.
    
    Args:
        raw_input: Text string (browser handles audio)
        session_id: Session identifier
        is_audio: Ignored (browser handles audio)
        language: Language code
        user_profile: User's profile
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    # Get text (browser already transcribed)
    transcript = transcribe_demo(raw_input if isinstance(raw_input, str) else raw_input.decode('utf-8'))
    
    # Get conversation context
    conversation_history = get_conversation_context(session_id)
    
    # Use Groq FREE API for intelligent conversation
    if user_profile is None:
        user_profile = {}
    
    result = groq_conversation(transcript, user_profile, conversation_history, language)
    
    # Create turn result
    turn_result = VoiceTurnResult(
        transcript=transcript,
        intent=result["intent"],
        entities=result["entities"],
        response=result["response"],
        needs_clarification=result["needs_clarification"],
        clarification_question=result["clarification_question"],
        session_id=session_id,
    )
    
    # Update conversation context
    update_conversation_context(session_id, transcript, result)
    
    return turn_result


def synthesize_reply(text: str, language: str = "en-IN") -> dict:
    """
    Return text for browser-based TTS (FREE).
    
    Args:
        text: Text to synthesize
        language: Language code (en-IN, hi-IN, te-IN)
    
    Returns:
        Dict with text and language info for browser TTS
    """
    return {
        "text": text,
        "language": language,
        "audio_available": True,  # Browser will handle TTS
        "use_browser_tts": True
    }
