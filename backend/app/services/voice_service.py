"""100% FREE Voice Agent Layer - Powered by Groq Whisper & Groq LLMs.

Pipeline:
    Browser Web Speech STT / Groq Whisper -> Groq AI Financial Agent -> Context & Execution -> Web Speech TTS / Audio

100% Free Stack:
  - Groq Whisper (whisper-large-v3-turbo) for audio transcription - FREE
  - Browser Web Speech API for real-time live streaming STT (English, Hindi, Telugu) - FREE
  - Groq API (openai/gpt-oss-120b & 20b) for autonomous multi-turn conversation & tool/action intent - FREE
  - Browser SpeechSynthesis API for natural, zero-latency voice output - FREE
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

# Groq System prompt for autonomous Financial Voice Agent
VOICE_ASSISTANT_SYSTEM_PROMPT = """You are FinLend's autonomous, conversational Voice Agent for peer-to-peer micro-lending.
You speak naturally with borrowers and lenders in real-time, just like a helpful, friendly loan officer on a live phone call.

You support English, Hindi, and Telugu (including mixed language speech like Hinglish/Tenglish).

**Your core capabilities & actions:**
1. REPAY_LOAN:
   - Handle loan repayment requests (e.g. "I want to repay my loan", "pay 500 rupees", "repay in full", "clear my debt", "రుణం తిరిగి చెల్లించాలి", "लोन चुकाना है").
   - Extract `amount` (number if specified) and `pay_all` (true if user says full, all, clear, everything).
   - If user doesn't specify amount, ask them how much of their remaining balance they'd like to pay today.
2. DEPOSIT_FUNDS:
   - Add/deposit money into the user's bank wallet (e.g. "deposit 5000", "add 1000 rupees", "deposit money", "వాలెట్‌లో 1000 డిపాజిట్ చేయి", "5000 జమ కరో").
   - Extract `amount` (number). If user doesn't mention amount, ask how much to deposit.
3. WITHDRAW_FUNDS:
   - Withdraw/transfer money from the user's bank wallet (e.g. "withdraw 2000", "withdraw money", "డబ్బులు విత్‌డ్రా చెయ్యి", "పैसे निकालो").
   - Extract `amount` (number). If user doesn't mention amount, ask how much to withdraw.
4. REQUEST_LOAN:
   - Help borrowers apply for a microloan (extract `amount` in rupees, `duration_days` in days, `purpose`).
   - If info is missing, ask for the missing piece.
5. CHECK_LOAN_STATUS:
   - Check user's active loans, amount owed, remaining balance, and repayment due dates.
6. CHECK_BALANCE:
   - Tell user their bank wallet balance, borrowing limit (if borrower), or lending balance (if lender).
7. CHECK_CREDIT_SCORE:
   - Check current credit score and explain how on-time repayments boost borrowing limits.
8. CALCULATE_EMI:
   - Calculate EMI or interest for a given amount and duration.
9. END_CALL:
   - If user says goodbye, bye, hang up, stop call, end call ("టాటా", "अलविदा", "కాల్ ఆపు", "ఫోన్ పెట్టేయ్"), acknowledge politely and set end_call: true.
10. GREETING / GENERAL_QUERY:
   - Answer platform questions warmly and concisely (1-2 sentences, suitable for speech).

**Live User Context (injected with each turn):**
- Role, credit score, borrowing limit, bank wallet balance, and active loan details (amount, total due, remaining due, due date).

**Conversation Style Guidelines:**
- Speak like you are ON A PHONE CALL: natural, warm, crisp, and concise (1 to 2 spoken sentences).
- Do NOT use long bullet points, markdown tables, or emojis in your speech response text.
- If user wants to repay and you see an active loan in their profile, acknowledge their current remaining balance.
- Respond in the user's spoken language.

**Output Format (STRICT JSON ONLY):**
{
  "intent": "REPAY_LOAN|DEPOSIT_FUNDS|WITHDRAW_FUNDS|REQUEST_LOAN|CHECK_LOAN_STATUS|CHECK_BALANCE|CHECK_CREDIT_SCORE|CALCULATE_EMI|END_CALL|GREETING|HELP|GENERAL_QUERY",
  "entities": {
    "amount": <number or null>,
    "duration_days": <number or null>,
    "purpose": "<string or null>",
    "pay_all": <true or false>,
    "language": "en|hi|te"
  },
  "response": "<natural, conversational spoken response for the user>",
  "needs_clarification": <true if missing critical info for intent, false otherwise>,
  "clarification_question": "<question to ask if needs_clarification=true>",
  "end_call": <true if user wants to end/hang up the call, false otherwise>
}
"""

DTMF_INTENT_MAP = {
    "1": "CHECK_BALANCE",
    "2": "CHECK_CREDIT_SCORE",
    "3": "CHECK_LOAN_STATUS",
    "4": "REQUEST_LOAN",
    "5": "CHECK_REPAYMENT",
    "6": "REPAY_LOAN",
    "0": "HELP",
}


def get_conversation_context(session_id: str, max_turns: int = 6) -> List[Dict[str, Any]]:
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
    
    if len(_conversation_contexts[session_id]) > 20:
        _conversation_contexts[session_id] = _conversation_contexts[session_id][-20:]


def transcribe_with_whisper(audio_bytes: bytes, filename: str = "audio.wav", language: Optional[str] = None) -> str:
    """
    Transcribe audio using Groq Whisper (whisper-large-v3-turbo) - 100% FREE tier.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        return ""
    
    try:
        files = {
            "file": (filename, audio_bytes, "audio/wav")
        }
        data = {
            "model": "whisper-large-v3-turbo",
            "response_format": "json"
        }
        if language and language in ("en", "hi", "te", "ta"):
            data["language"] = language

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                files=files,
                data=data
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get("text", "").strip()
            else:
                print(f"Whisper transcription failed with status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Whisper transcription exception: {e}")
    
    return ""


def groq_conversation(
    user_input: str,
    user_profile: dict,
    conversation_history: List[Dict[str, Any]],
    language: str = "en"
) -> dict:
    """
    Groq Conversational Voice Agent.
    Evaluates multi-turn context and extracts actions.
    """
    settings = get_settings()
    
    if not settings.groq_api_key:
        return _fallback_intent_detection(user_input, user_profile)
    
    try:
        fallback_entities = _extract_entities_simple(user_input)
        
        # Build active loans summary string
        active_loans = user_profile.get("active_loans", [])
        if active_loans:
            loans_summary = "\n".join([
                f"- Active Loan #{i+1}: Original: ₹{l.get('amount', 0):,.0f}, Total Due: ₹{l.get('total_due', 0):,.0f}, "
                f"Remaining Due: ₹{l.get('remaining_due', 0):,.0f}, Status: {l.get('status')}"
                for i, l in enumerate(active_loans)
            ])
        else:
            loans_summary = "None (No outstanding loans)"

        user_message = f"""User Profile:
- Role: {user_profile.get('role', 'borrower')}
- Credit Score: {user_profile.get('credit_score', 'N/A')}
- Borrowing Limit: ₹{user_profile.get('borrowing_limit', 0):,.0f}
- Active Loans:
{loans_summary}

User says: "{user_input}"

Identify user's intent:
- If user wants to repay loan or pay money -> REPAY_LOAN
- If user asks for loan / borrow money -> REQUEST_LOAN
- If user asks about their loan status or amount due -> CHECK_LOAN_STATUS
- If user asks for credit score -> CHECK_CREDIT_SCORE
- If user asks for limit / balance -> CHECK_BALANCE
- If user says goodbye or hang up -> END_CALL
- If user asks platform/financial question -> GENERAL_QUERY

Output valid JSON only with keys: intent, entities (amount, duration_days, purpose, pay_all, language), response, needs_clarification, clarification_question, end_call."""

        messages = [
            {"role": "system", "content": VOICE_ASSISTANT_SYSTEM_PROMPT}
        ]
        
        for turn in conversation_history:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": json.dumps(turn["assistant"])})
        
        messages.append({"role": "user", "content": user_message})
        
        models_to_try = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
        response = None
        for model_name in models_to_try:
            try:
                response = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.groq_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": 400,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=15.0
                )
                if response.status_code == 200:
                    break
            except Exception:
                continue

        if not response or response.status_code != 200:
            return _fallback_intent_detection(user_input, user_profile)

        result_content = response.json()["choices"][0]["message"]["content"]
        result_json = json.loads(result_content)
        
        entities = result_json.get("entities", {})
        if not entities.get("amount") and fallback_entities.get("amount"):
            entities["amount"] = fallback_entities["amount"]
        if not entities.get("duration_days") and fallback_entities.get("duration_days"):
            entities["duration_days"] = fallback_entities["duration_days"]
        if fallback_entities.get("pay_all"):
            entities["pay_all"] = True

        intent = result_json.get("intent", "GENERAL_QUERY").upper()

        # Handle explicit keywords if Groq misclassified
        text_lower = user_input.lower()
        if any(w in text_lower for w in ["repay", "pay loan", "clear loan", "pay debt", "चुकाना", "भरना", "చెల్లించ", "కట్టాలి"]):
            intent = "REPAY_LOAN"
        elif any(w in text_lower for w in ["bye", "hang up", "end call", "stop call", "goodbye", "अलविदा", "కాల్ ఆపు", "ఫోన్ పెట్టు"]):
            intent = "END_CALL"
            result_json["end_call"] = True

        return {
            "intent": intent,
            "entities": entities,
            "response": result_json.get("response", "I am here to assist you with your loans."),
            "needs_clarification": result_json.get("needs_clarification", False),
            "clarification_question": result_json.get("clarification_question", ""),
            "end_call": result_json.get("end_call", False)
        }
        
    except Exception as e:
        print(f"Groq API error in voice agent: {e}")
        return _fallback_intent_detection(user_input, user_profile)


def _extract_entities_simple(text: str) -> dict:
    """Robust regex-based entity extractor."""
    entities = {}
    clean_text = re.sub(r'(\d+),(\d+)', r'\1\2', text.lower())

    if any(w in clean_text for w in ["full", "entire", "all", "clear all", "पूरा", "మొత్తం"]):
        entities["pay_all"] = True

    # 1. 'k' notation (e.g. 5k -> 5000)
    k_match = re.search(r'\b(\d+(?:\.\d+)?)\s*k\b', clean_text)
    if k_match:
        entities["amount"] = float(k_match.group(1)) * 1000

    # 2. Duration in months, weeks, days
    month_match = re.search(r'(\d+)\s*(?:months?|month|మంత్స్|నెలలు|महीने)', clean_text)
    if month_match:
        entities["duration_days"] = int(month_match.group(1)) * 30
    else:
        week_match = re.search(r'(\d+)\s*(?:weeks?|week|వీక్స్|వారాలు|सप्ताह)', clean_text)
        if week_match:
            entities["duration_days"] = int(week_match.group(1)) * 7
        else:
            day_match = re.search(r'(\d+)\s*(?:days?|day|డేస్|దినాలు|రోజులు|दिन|दिनों)', clean_text)
            if day_match:
                entities["duration_days"] = int(day_match.group(1))

    # 3. Direct amount
    if "amount" not in entities:
        amt_match = re.search(r'(?:amount\s*(?:is|:|=)?\s*|rupees|rupee|rs\.?|₹|रुपये|రుపీస్|రూపాయల)\s*(\d+)', clean_text)
        if not amt_match:
            amt_match = re.search(r'(\d+)\s*(?:rupees|rupee|rs|₹|रुपये|రుపీస్|రూపాయల)', clean_text)
        if amt_match:
            try:
                amt = float(amt_match.group(1))
                if amt >= 50:
                    entities["amount"] = amt
            except Exception:
                pass

    # 4. Fallback: collect standalone numbers
    all_numbers = [int(n) for n in re.findall(r'\b(\d+)\b', clean_text)]
    if "duration_days" in entities:
        dur_orig = entities["duration_days"]
        for cand in [dur_orig, dur_orig // 30, dur_orig // 7]:
            if cand in all_numbers:
                all_numbers.remove(cand)

    if "amount" not in entities and all_numbers:
        for num in sorted(all_numbers, reverse=True):
            if num >= 100:
                entities["amount"] = float(num)
                all_numbers.remove(num)
                break

    if "duration_days" not in entities and all_numbers:
        for num in all_numbers:
            if 7 <= num <= 365:
                entities["duration_days"] = num
                break
    
    return entities


def _fallback_intent_detection(user_input: str, user_profile: dict = None) -> dict:
    """Robust fallback intent detection."""
    text = user_input.lower()
    entities = _extract_entities_simple(user_input)
    user_profile = user_profile or {}
    
    # 1. Repayment intent
    if any(w in text for w in ["repay", "pay loan", "clear loan", "pay debt", "चुकाना", "वापस", "చెల్లించ", "కట్టాలి"]):
        has_amt = bool(entities.get("amount")) or bool(entities.get("pay_all"))
        return {
            "intent": "REPAY_LOAN",
            "entities": entities,
            "response": f"Processing your loan repayment of ₹{entities.get('amount', 'due amount')}." if has_amt else "How much would you like to repay towards your loan today?",
            "needs_clarification": not has_amt,
            "clarification_question": "How much amount do you want to repay?" if not has_amt else "",
            "end_call": False
        }

    # 2. Deposit Funds
    if any(w in text for w in ["deposit", "add money", "add balance", "top up", "జమా", "డిపాజిట్", "డబ్బులు వేయి", "जमा", "पैसे जोड़ें"]):
        has_amt = bool(entities.get("amount"))
        return {
            "intent": "DEPOSIT_FUNDS",
            "entities": entities,
            "response": f"Depositing ₹{entities.get('amount'):,.0f} to your bank wallet." if has_amt else "How much amount would you like to deposit into your wallet?",
            "needs_clarification": not has_amt,
            "clarification_question": "How much amount do you want to deposit?" if not has_amt else "",
            "end_call": False
        }

    # 3. Withdraw Funds
    if any(w in text for w in ["withdraw", "take out", "transfer out", "విత్‌డ్రా", "డబ్బులు తీయి", "తీసుకో", "निकालो", "पैसे निकालें"]):
        has_amt = bool(entities.get("amount"))
        return {
            "intent": "WITHDRAW_FUNDS",
            "entities": entities,
            "response": f"Withdrawing ₹{entities.get('amount'):,.0f} from your bank wallet." if has_amt else "How much amount would you like to withdraw from your wallet?",
            "needs_clarification": not has_amt,
            "clarification_question": "How much amount do you want to withdraw?" if not has_amt else "",
            "end_call": False
        }

    # 4. End Call
    if any(w in text for w in ["bye", "hang up", "end call", "goodbye", "अलविदा", "కాల్ ఆపు", "ఫోన్ పెట్టు"]):
        return {
            "intent": "END_CALL",
            "entities": {},
            "response": "Thank you for calling FinLend. Have a great day! Goodbye.",
            "needs_clarification": False,
            "clarification_question": "",
            "end_call": True
        }

    # 3. Loan Status
    if any(w in text for w in ["status", "active loan", "due date", "how much do i owe", "స్టేటస్", "బాకీ", "बकाया"]):
        return {
            "intent": "CHECK_LOAN_STATUS",
            "entities": {},
            "response": "Let me look up your active loan status and due date.",
            "needs_clarification": False,
            "clarification_question": "",
            "end_call": False
        }

    # 4. Request Loan
    loan_keywords = ["borrow", "need money", "take loan", "apply loan", "పैसे चाहिए", "లోన్ కావాలి", "ఉధార్"]
    has_loan_info = bool(entities.get("amount")) and bool(entities.get("duration_days"))
    if any(w in text for w in loan_keywords) or has_loan_info:
        needs_clarification = not has_loan_info
        if not needs_clarification:
            resp = f"Creating your loan request for ₹{entities['amount']:,.0f} for {entities['duration_days']} days."
        elif not entities.get("amount"):
            resp = "How much loan amount do you need?"
        else:
            resp = f"Got ₹{entities['amount']:,.0f}. For how many days or months do you need it?"

        return {
            "intent": "REQUEST_LOAN",
            "entities": entities,
            "response": resp,
            "needs_clarification": needs_clarification,
            "clarification_question": "Please specify amount and duration." if needs_clarification else "",
            "end_call": False
        }

    # 5. Balance / Limit
    if any(w in text for w in ["balance", "limit", "బ్యాలెన్స్", "बैलेंस"]):
        return {
            "intent": "CHECK_BALANCE",
            "entities": {},
            "response": "Let me check your borrowing limit and balance.",
            "needs_clarification": False,
            "clarification_question": "",
            "end_call": False
        }

    # 6. Credit Score
    if any(w in text for w in ["credit score", "score", "స్కోర్", "स्कोर"]):
        return {
            "intent": "CHECK_CREDIT_SCORE",
            "entities": {},
            "response": "Let me check your credit score.",
            "needs_clarification": False,
            "clarification_question": "",
            "end_call": False
        }

    return {
        "intent": "GENERAL_QUERY",
        "entities": entities,
        "response": "I am your FinLend Voice Assistant. You can ask me to request a loan, repay your active loan, check your balance, or check your credit score.",
        "needs_clarification": False,
        "clarification_question": "",
        "end_call": False
    }


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
    end_call: bool = False
    action_taken: Optional[str] = None
    data: Optional[dict] = None


def process_voice_turn(
    raw_input: str | bytes,
    session_id: str | None = None,
    is_audio: bool = False,
    language: str = "en",
    user_profile: dict = None
) -> VoiceTurnResult:
    """
    Process voice input using Groq Free Whisper & Conversational AI.
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    if is_audio and isinstance(raw_input, bytes):
        transcript = transcribe_with_whisper(raw_input, language=language)
        if not transcript:
            transcript = "Hello, I want help with my loan."
    else:
        transcript = raw_input if isinstance(raw_input, str) else raw_input.decode('utf-8', errors='ignore')
        transcript = transcript.strip()
    
    conversation_history = get_conversation_context(session_id)
    if user_profile is None:
        user_profile = {}
    
    result = groq_conversation(transcript, user_profile, conversation_history, language)
    
    turn_result = VoiceTurnResult(
        transcript=transcript,
        intent=result["intent"],
        entities=result["entities"],
        response=result["response"],
        needs_clarification=result["needs_clarification"],
        clarification_question=result["clarification_question"],
        session_id=session_id,
        end_call=result.get("end_call", False)
    )
    
    update_conversation_context(session_id, transcript, result)
    return turn_result


def synthesize_reply(text: str, language: str = "en-IN") -> dict:
    """Browser-based SpeechSynthesis metadata."""
    return {
        "text": text,
        "language": language,
        "audio_available": True,
        "use_browser_tts": True
    }
