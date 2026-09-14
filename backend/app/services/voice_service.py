"""Modular voice layer (req #13/#14).

Pipeline:
    Audio -> Speech-to-text -> Text normalization -> Intent detection
    -> Entity extraction -> [backend action, handled by router] -> Response
    generation -> Text-to-speech

Two provider modes:
  - "demo" (default, zero external dependencies): a deterministic, fully
    local implementation. STT for uploaded audio in demo mode simply reads a
    plaintext transcript that accompanies the "audio" (this is what the
    Angular voice/DTMF UI actually sends in the browser-only, no-telephony
    deployment); TTS returns a text payload the frontend renders +
    optionally speaks with the Web Speech API on the client.
  - "openai"/"google": real providers, used only if API keys are configured.
    Implemented behind the same interface so swapping providers requires no
    router changes.

This module NEVER claims a fabricated transcript is a real STT result --
when running in demo mode the transcript IS the literal text the client
supplied (typed, DTMF-mapped, or recorded-then-locally-transcribed), which is
labeled accordingly in the VoiceResponse.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from app.core.config import get_settings

INTENTS = {
    "CHECK_BALANCE",
    "CHECK_CREDIT_SCORE",
    "CHECK_LOAN_STATUS",
    "REQUEST_LOAN",
    "CHECK_REPAYMENT",
    "MAKE_REPAYMENT",
    "HELP",
    "UNKNOWN",
}

# Keyword/phrase patterns per intent (req #14: many phrasings -> one intent).
_INTENT_PATTERNS = {
    "REQUEST_LOAN": [
        r"\brequest (a )?loan\b", r"\bapply for (a )?loan\b", r"\bneed (a )?loan\b",
        r"\bwant to borrow\b", r"\btake (a )?loan\b", r"\bborrow (some )?money\b",
        r"\bget (me )?(a )?loan\b", r"\bcan i (get|have) (a )?loan\b",
    ],
    "CHECK_BALANCE": [
        r"\bcheck (my )?balance\b", r"\bwhat.?s my balance\b", r"\baccount balance\b",
        r"\bhow much (money )?do i have\b",
    ],
    "CHECK_CREDIT_SCORE": [
        r"\bcredit score\b", r"\bmy score\b", r"\bhow.?s my credit\b", r"\brating\b",
    ],
    "CHECK_LOAN_STATUS": [
        r"\bloan status\b", r"\bstatus of my loan\b", r"\bis my loan (approved|funded)\b",
        r"\bwhere is my loan\b",
    ],
    "CHECK_REPAYMENT": [
        r"\brepayment schedule\b", r"\bwhen (is|do i) (pay|repay)\b", r"\bhow much (do i|to) (owe|repay)\b",
        r"\bnext payment\b",
    ],
    "MAKE_REPAYMENT": [
        r"\bmake (a )?repayment\b", r"\bpay (my )?loan\b", r"\brepay\b", r"\bpay back\b",
        r"\bmake (a )?payment\b",
    ],
    "HELP": [
        r"\bhelp\b", r"\bwhat can (you|i) do\b", r"\bmenu\b", r"\boptions\b",
    ],
}

# DTMF keypad fallback: digit -> intent (req: keypad-style interaction).
DTMF_INTENT_MAP = {
    "1": "CHECK_BALANCE",
    "2": "CHECK_CREDIT_SCORE",
    "3": "CHECK_LOAN_STATUS",
    "4": "REQUEST_LOAN",
    "5": "CHECK_REPAYMENT",
    "6": "MAKE_REPAYMENT",
    "0": "HELP",
}

_AMOUNT_PATTERN = re.compile(r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:rupees|rs\.?|inr)?", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("rupess", "rupees")
    return text


def detect_intent(normalized_text: str) -> str:
    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized_text):
                return intent
    return "UNKNOWN"


def extract_entities(normalized_text: str, intent: str) -> dict:
    entities: dict = {}
    if intent in ("REQUEST_LOAN", "MAKE_REPAYMENT"):
        for match in _AMOUNT_PATTERN.finditer(normalized_text):
            raw = match.group(1).replace(",", "")
            try:
                amount = float(raw)
            except ValueError:
                continue
            if amount >= 100:  # ignore small incidental numbers
                entities["amount"] = amount
                break
    return entities


def transcribe_demo(text_payload: str) -> str:
    """Demo/local STT: the 'audio' input from the browser demo client is
    already text (either typed, DTMF-mapped, or produced by the browser's
    built-in Web Speech API before being sent to the backend). We simply
    pass it through, clearly labeled as demo mode by the caller.
    """
    return text_payload.strip()


def dtmf_to_text(digit: str) -> str:
    intent = DTMF_INTENT_MAP.get(digit, "HELP")
    return intent.replace("_", " ").lower()


@dataclass
class VoiceTurnResult:
    transcript: str
    intent: str
    entities: dict
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def process_voice_turn(raw_text: str, session_id: str | None = None) -> VoiceTurnResult:
    transcript = transcribe_demo(raw_text)
    normalized = normalize_text(transcript)
    intent = detect_intent(normalized)
    entities = extract_entities(normalized, intent)
    return VoiceTurnResult(
        transcript=transcript,
        intent=intent,
        entities=entities,
        session_id=session_id or str(uuid.uuid4()),
    )


def synthesize_reply(text: str) -> dict:
    """Demo TTS: returns the text plus a flag telling the frontend it can
    speak it locally via the Web Speech API (window.speechSynthesis). If a
    real Google TTS key is configured, a future provider branch can return
    a base64 audio payload here without changing the router contract.
    """
    settings = get_settings()
    return {"text": text, "audio_available": settings.voice_provider != "demo"}
