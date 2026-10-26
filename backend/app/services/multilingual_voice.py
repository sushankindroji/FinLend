"""Enhanced multilingual voice service with real STT/TTS providers.

This module implements a complete voice processing pipeline:
1. Speech-to-text using OpenAI Whisper
2. Language detection and translation
3. Intent detection with contextual understanding
4. Text-to-speech using Google Cloud TTS

Supports: English (en), Hindi (hi), Telugu (te), Tamil (ta)
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings

logger = logging.getLogger("finlend.voice")

# Language configurations
LANGUAGE_CONFIGS = {
    "en": {
        "name": "English",
        "google_voice": "en-IN-Standard-A",
        "whisper_language": "en",
    },
    "hi": {
        "name": "Hindi",
        "google_voice": "hi-IN-Standard-A",
        "whisper_language": "hi",
    },
    "te": {
        "name": "Telugu",
        "google_voice": "te-IN-Standard-A",
        "whisper_language": "en",  # Whisper doesn't support Telugu natively
    },
    "ta": {
        "name": "Tamil",
        "google_voice": "ta-IN-Standard-A",
        "whisper_language": "ta",
    },
}

# Multilingual intent patterns
INTENT_PATTERNS = {
    "REQUEST_LOAN": {
        "en": [
            r"\brequest (a )?loan\b", r"\bapply for (a )?loan\b", r"\bneed (a )?loan\b",
            r"\bwant to borrow\b", r"\btake (a )?loan\b", r"\bborrow (some )?money\b",
            r"\bget (me )?(a )?loan\b", r"\bcan i (get|have) (a )?loan\b",
        ],
        "hi": [
            r"\bऋण चाहिए\b", r"\bलोन चाहिए\b", r"\bउधार चाहिए\b", 
            r"\bकर्ज़ चाहिए\b", r"\bपैसे उधार\b", r"\bloan chahiye\b",
            r"\bhum loan lena chahte hain\b", r"\bkarza chahiye\b",
        ],
        "te": [
            r"\bరుణం కావాలి\b", r"\bలోన్ కావాలి\b", r"\bఅప్పు కావాలి\b",
            r"\brunam kavali\b", r"\bloan kavali\b", r"\bappu kavali\b",
        ],
        "ta": [
            r"\bகடன் வேண்டும்\b", r"\bலோன் வேண்டும்\b", r"\bஎடுக்க வேண்டும்\b",
            r"\bkadan vendum\b", r"\bloan vendum\b", r"\bvang vendum\b",
        ],
    },
    "CHECK_BALANCE": {
        "en": [
            r"\bcheck (my )?balance\b", r"\bwhat.?s my balance\b", r"\baccount balance\b",
            r"\bhow much (money )?do i have\b", r"\bshow balance\b",
        ],
        "hi": [
            r"\bबैलेंस चेक करें\b", r"\bबैलेंस दिखाओ\b", r"\bखाते में कितना है\b",
            r"\bbalance check karo\b", r"\bmera balance kya hai\b", r"\bbalance dikhao\b",
        ],
        "te": [
            r"\bబ్యాలెన్స్ చూడండి\b", r"\bఖాతా బ్యాలెన్స్\b", r"\bbalance chudandi\b",
            r"\bkhata balance\b", r"\bnaa balance ento\b",
        ],
        "ta": [
            r"\bநிலுவை பார்க்க\b", r"\bபேலன்ஸ் பார்க்க\b", r"\bbalance parkka\b",
            r"\bennai ullathu\b", r"\bkhatavil evvalavu\b",
        ],
    },
    "CHECK_CREDIT_SCORE": {
        "en": [
            r"\bcredit score\b", r"\bmy score\b", r"\bhow.?s my credit\b", 
            r"\brating\b", r"\bcredit rating\b",
        ],
        "hi": [
            r"\bक्रेडिट स्कोर\b", r"\bमेरा स्कोर\b", r"\bरेटिंग\b",
            r"\bcredit score kya hai\b", r"\bmera score dikhao\b",
        ],
        "te": [
            r"\bక్రెడిట్ స్కోర్\b", r"\bనా స్కోర్\b", r"\bcredit score\b",
            r"\bnaa score ento\b", r"\brating ento\b",
        ],
        "ta": [
            r"\bகடன் மதிப்பெண்\b", r"\bஎன் மதிப்பெண்\b", r"\bcredit score\b",
            r"\ben mattippennu\b",
        ],
    },
    "CHECK_LOAN_STATUS": {
        "en": [
            r"\bloan status\b", r"\bstatus of my loan\b", r"\bis my loan (approved|funded)\b",
            r"\bwhere is my loan\b", r"\bcheck loan\b",
        ],
        "hi": [
            r"\bलोन स्टेटस\b", r"\bलोन की स्थिति\b", r"\bमेरा लोन कहां है\b",
            r"\bloan status kya hai\b", r"\bloan approved hua\b",
        ],
        "te": [
            r"\bలోన్ స్థితి\b", r"\bలోన్ స్టేటస్\b", r"\bloan status\b",
            r"\bnaa loan ela undi\b",
        ],
        "ta": [
            r"\bகடன் நிலை\b", r"\bலோன் நிலை\b", r"\bloan status\b",
            r"\ben kadan nilai\b",
        ],
    },
    "CHECK_REPAYMENT": {
        "en": [
            r"\brepayment schedule\b", r"\bwhen (is|do i) (pay|repay)\b", 
            r"\bhow much (do i|to) (owe|repay)\b", r"\bnext payment\b",
        ],
        "hi": [
            r"\bभुगतान समय\b", r"\bकब चुकाना है\b", r"\bअगली किस्त\b",
            r"\brepayment schedule\b", r"\bkab payment karni hai\b",
        ],
        "te": [
            r"\bచెల్లింపు షెడ్యూల్\b", r"\bఎప్పుడు చెల్లించాలి\b",
            r"\brepayment schedule\b", r"\beppudu chellinchal\b",
        ],
        "ta": [
            r"\bசெலுத்தும் அட்டவணை\b", r"\bஎப்போது செலுத்த\b",
            r"\brepayment schedule\b", r"\beppo seluttha\b",
        ],
    },
    "MAKE_REPAYMENT": {
        "en": [
            r"\bmake (a )?repayment\b", r"\bpay (my )?loan\b", r"\brepay\b", 
            r"\bpay back\b", r"\bmake (a )?payment\b",
        ],
        "hi": [
            r"\bभुगतान करें\b", r"\bलोन चुकाएं\b", r"\bपैसे दें\b",
            r"\bpayment karo\b", r"\bloan chukao\b", r"\brepayment karna hai\b",
        ],
        "te": [
            r"\bచెల్లింపు చేయండి\b", r"\bలోన్ చెల్లించండి\b",
            r"\brepayment cheyandi\b", r"\bloan chellinchand\b",
        ],
        "ta": [
            r"\bசெலுத்துங்கள்\b", r"\bகடன் செலுத்து\b",
            r"\brepayment seyyungal\b", r"\bloan selutthu\b",
        ],
    },
    "HELP": {
        "en": [
            r"\bhelp\b", r"\bwhat can (you|i) do\b", r"\bmenu\b", r"\boptions\b",
        ],
        "hi": [
            r"\bमदद\b", r"\bसहायता\b", r"\bक्या कर सकते हैं\b",
            r"\bhelp\b", r"\bmadad chahiye\b",
        ],
        "te": [
            r"\bసహాయం\b", r"\bసహాయం కావాలి\b", r"\bhelp\b",
            r"\bsahayam kavali\b",
        ],
        "ta": [
            r"\bஉதவி\b", r"\bஉதவி வேண்டும்\b", r"\bhelp\b",
            r"\butavi vendum\b",
        ],
    },
}

# Multilingual responses
RESPONSES = {
    "HELP": {
        "en": "You can say: check balance, check credit score, check loan status, request a loan of [amount], check repayment, or make a repayment.",
        "hi": "आप कह सकते हैं: बैलेंस चेक करें, क्रेडिट स्कोर चेक करें, लोन स्टेटस चेक करें, [राशि] का लोन चाहिए, भुगतान समय चेक करें, या भुगतान करें।",
        "te": "మీరు చెప్పవచ్చు: బ్యాలెన్స్ చూడండి, క్రెడిట్ స్కోర్ చూడండి, లోన్ స్థితి చూడండి, [మొత్తం] లోన్ కావాలి, చెల్లింపు షెడ్యూల్ చూడండి, లేదా చెల్లింపు చేయండి.",
        "ta": "நீங்கள் சொல்லலாம்: நிலுவை பார்க்க, கடன் மதிப்பெண் பார்க்க, கடன் நிலை பார்க்க, [தொகை] கடன் வேண்டும், செலுத்தும் அட்டவணை பார்க்க, அல்லது செலுத்துங்கள்.",
    },
    "UNKNOWN": {
        "en": "Sorry, I didn't understand that. Say 'help' to hear what you can do.",
        "hi": "क्षमा करें, मैं समझ नहीं पाया। 'मदद' कहें यह जानने के लिए कि आप क्या कर सकते हैं।",
        "te": "క్షమించండి, నాకు అర్థం కాలేదు. మీరు ఏం చేయవచ్చో తెలుసుకోవడానికి 'సహాయం' అని చెప్పండి.",
        "ta": "மன்னிக்கவும், எனக்கு புரியவில்லை. நீங்கள் என்ன செய்யலாம் என்பதை அறிய 'உதவி' என்று சொல்லுங்கள்.",
    },
    "ACCOUNT_ERROR": {
        "en": "I couldn't verify your account. Please try signing in again.",
        "hi": "मैं आपके खाते की पुष्टि नहीं कर सका। कृपया फिर से साइन इन करें।",
        "te": "మీ ఖాతాను ధృవీకరించలేకపోయాను. దయచేసి మళ్లీ సైన్ ఇన్ చేయండి.",
        "ta": "உங்கள் கணக்கை சரிபார்க்க முடியவில்லை. தயவுசெய்து மீண்டும் உள்நுழையவும்.",
    },
}

# Amount patterns for different formats
AMOUNT_PATTERNS = {
    "en": re.compile(r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:rupees|rs\.?|inr)?", re.IGNORECASE),
    "hi": re.compile(r"(?:रुपये|रुपया|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:रुपये|रुपया)?", re.IGNORECASE),
    "te": re.compile(r"(?:రూపాయలు|రూపాయి|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:రూపాయలు)?", re.IGNORECASE),
    "ta": re.compile(r"(?:ரூபாய்|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:ரூபாய்)?", re.IGNORECASE),
}


@dataclass
class ConversationContext:
    """Maintains conversation state for contextual understanding."""
    session_id: str
    user_id: str
    language: str = "en"
    last_intent: Optional[str] = None
    pending_confirmation: Optional[Dict] = None
    entity_memory: Dict = field(default_factory=dict)
    turn_count: int = 0


class EnhancedVoiceService:
    """Production-grade voice service with real STT/TTS and multilingual support."""

    def __init__(self):
        self.settings = get_settings()
        self.contexts: Dict[str, ConversationContext] = {}
        
        # Initialize provider clients
        self.openai_client = None
        self.google_tts_client = None
        
        if self.settings.voice_provider == "openai" and self.settings.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.settings.openai_api_key)
                logger.info("OpenAI Whisper client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
        
        if self.settings.google_application_credentials:
            try:
                from google.cloud import texttospeech
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.settings.google_application_credentials
                self.google_tts_client = texttospeech.TextToSpeechClient()
                logger.info("Google TTS client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Google TTS client: {e}")

    def detect_language(self, text: str) -> str:
        """Detect language from text input."""
        try:
            from langdetect import detect
            detected = detect(text)
            # Map detected languages
            lang_map = {"hi": "hi", "te": "te", "ta": "ta"}
            return lang_map.get(detected, "en")
        except Exception:
            return self.settings.default_voice_language

    def transcribe_audio(self, audio_data: bytes, language: Optional[str] = None) -> Tuple[str, str]:
        """
        Transcribe audio to text using OpenAI Whisper.
        
        Returns: (transcript, detected_language)
        """
        if self.openai_client is None:
            # Fallback: return empty transcript
            logger.warning("OpenAI client not initialized, cannot transcribe audio")
            return "", language or "en"
        
        try:
            # Create audio file in memory
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.mp3"
            
            # Call Whisper API
            response = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=LANGUAGE_CONFIGS.get(language or "en", {}).get("whisper_language", "en"),
            )
            
            transcript = response.text.strip()
            detected_lang = self.detect_language(transcript)
            
            logger.info(f"Transcribed audio: '{transcript[:50]}...' (lang: {detected_lang})")
            return transcript, detected_lang
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return "", language or "en"

    def normalize_text(self, text: str, language: str = "en") -> str:
        """Normalize text for processing."""
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        
        # Language-specific normalizations
        if language == "hi":
            text = text.replace("रुपया", "रुपये")
        elif language == "en":
            text = text.replace("rupess", "rupees")
        
        return text

    def detect_intent(self, normalized_text: str, language: str = "en", context: Optional[ConversationContext] = None) -> str:
        """
        Detect intent with contextual understanding.
        
        Supports follow-up questions and contextual clarifications.
        """
        # Check patterns for detected language
        for intent, lang_patterns in INTENT_PATTERNS.items():
            patterns = lang_patterns.get(language, lang_patterns.get("en", []))
            for pattern in patterns:
                if re.search(pattern, normalized_text):
                    return intent
        
        # Contextual intent detection
        if context and context.last_intent:
            # Handle confirmation words
            confirmation_words = {
                "en": ["yes", "yeah", "sure", "ok", "confirm", "proceed"],
                "hi": ["हां", "जी", "ठीक है", "yes", "han"],
                "te": ["అవును", "సరే", "yes", "avunu"],
                "ta": ["ஆம்", "சரி", "yes", "aam"],
            }
            
            denial_words = {
                "en": ["no", "nope", "cancel", "stop"],
                "hi": ["नहीं", "no", "रोको"],
                "te": ["కాదు", "no", "aagipo"],
                "ta": ["இல்லை", "no", "venda"],
            }
            
            words = confirmation_words.get(language, confirmation_words["en"])
            deny_words = denial_words.get(language, denial_words["en"])
            
            if any(word in normalized_text for word in words):
                return "CONFIRM"
            elif any(word in normalized_text for word in deny_words):
                return "CANCEL"
        
        return "UNKNOWN"

    def extract_entities(self, normalized_text: str, intent: str, language: str = "en") -> Dict:
        """
        Extract entities like amounts, durations, etc.
        NATURAL SPEECH UNDERSTANDING - handles mixed language, casual speech, English numbers in native language.
        """
        entities: Dict = {}
        text_lower = normalized_text.lower()
        
        # ============= AMOUNT EXTRACTION (SMART) =============
        # Extract ANY number that looks like a loan amount
        # Handles: "5000", "5000 rupees", "5000 రుపీస్", "5000 रुपये", "५०००", etc.
        if intent in ("REQUEST_LOAN", "MAKE_REPAYMENT"):
            # Multiple strategies to find amount
            amount_patterns = [
                r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:rupees|rupee|rs|₹|रुपये|रुपया|రుపీస్|రూపాయల|ரூபாய்)',  # With currency
                r'(?:loan|lend|borrow|उधार|లోన్|கடன்).*?(\d+(?:,\d{3})*)',  # After loan keywords
                r'(\d+(?:,\d{3})*)\s*(?:का|కి|க்கு)',  # Before possessive markers
                r'(\d{3,})',  # Any 3+ digit number (likely an amount)
            ]
            
            for pattern_str in amount_patterns:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                match = pattern.search(text_lower)
                if match:
                    raw = match.group(1).replace(",", "").strip()
                    try:
                        amount = float(raw)
                        if amount >= 100:  # Reasonable loan minimum
                            entities["amount"] = amount
                            break
                    except ValueError:
                        continue
        
        # ============= DURATION EXTRACTION (SUPER FLEXIBLE) =============
        # Handles mixed language: "10 days", "10 డేస్", "10 రోజులు", "दस दिन", etc.
        
        # Strategy 1: English words (days, weeks, months) - works with Telugu/Hindi text too!
        english_duration = re.compile(
            r'(\d+)\s*(?:days?|weeks?|months?|డేస్|వీక్స్|మంత్స్)',  # Mixed Telugu-English
            re.IGNORECASE
        )
        match = english_duration.search(text_lower)
        if match:
            value = int(match.group(1))
            unit = match.group(0).lower()
            
            if 'month' in unit or 'మంత్స్' in unit:
                entities["duration_days"] = value * 30
            elif 'week' in unit or 'వీక్స్' in unit:
                entities["duration_days"] = value * 7
            else:  # days/డేస్
                entities["duration_days"] = value
        
        # Strategy 2: Pure native language words
        if "duration_days" not in entities:
            native_patterns = {
                "hi": re.compile(r'(\d+)\s*(?:दिन|महीने|सप्ताह|दिनों|महीनों)', re.IGNORECASE),
                "te": re.compile(r'(\d+)\s*(?:రోజులు|రోజుల|నెలలు|నెలల|వారాలు|వారాల)', re.IGNORECASE),
                "ta": re.compile(r'(\d+)\s*(?:நாட்கள்|மாதங்கள்|வாரங்கள்)', re.IGNORECASE),
            }
            
            pattern = native_patterns.get(language)
            if pattern:
                match = pattern.search(normalized_text)
                if match:
                    value = int(match.group(1))
                    unit = match.group(0).lower()
                    
                    # Convert to days
                    if any(x in unit for x in ['महीने', 'నెలలు', 'நாட்கள்', 'month']):
                        entities["duration_days"] = value * 30
                    elif any(x in unit for x in ['सप्ताह', 'వారాలు', 'வாரங்கள்', 'week']):
                        entities["duration_days"] = value * 7
                    else:  # days
                        entities["duration_days"] = value
        
        # Strategy 3: SMART FALLBACK - Look for "number + ki/కి/के लिए" pattern
        # This handles: "10 కి", "30 దినాలకు", "60 के लिए"
        if "duration_days" not in entities and "amount" in entities:
            # Find any OTHER number in the sentence (not the amount)
            all_numbers = re.findall(r'\b(\d+)\b', text_lower)
            for num_str in all_numbers:
                num = int(num_str)
                # Reasonable duration range for microloans (7 days to 365 days)
                if 7 <= num <= 365 and num != entities["amount"]:
                    entities["duration_days"] = num
                    break
        
        return entities

    def synthesize_speech(self, text: str, language: str = "en") -> Optional[bytes]:
        """
        Convert text to speech using Google Cloud TTS.
        
        Returns: audio bytes (MP3 format) or None if unavailable
        """
        if self.google_tts_client is None:
            logger.warning("Google TTS client not initialized")
            return None
        
        try:
            from google.cloud import texttospeech
            
            # Configure voice
            voice_config = LANGUAGE_CONFIGS.get(language, LANGUAGE_CONFIGS["en"])
            voice = texttospeech.VoiceSelectionParams(
                language_code=language + "-IN",
                name=voice_config["google_voice"],
            )
            
            # Configure audio
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.95,  # Slightly slower for clarity
            )
            
            # Synthesize
            synthesis_input = texttospeech.SynthesisInput(text=text)
            response = self.google_tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            
            logger.info(f"Synthesized speech for text: '{text[:50]}...' (lang: {language})")
            return response.audio_content
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None

    def get_or_create_context(self, session_id: str, user_id: str, language: str = "en") -> ConversationContext:
        """Get or create conversation context."""
        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext(
                session_id=session_id,
                user_id=user_id,
                language=language,
            )
        return self.contexts[session_id]

    def build_response(
        self,
        intent: str,
        entities: Dict,
        borrower: Optional[Dict],
        language: str = "en",
        context: Optional[ConversationContext] = None,
    ) -> str:
        """Build contextual response in the target language."""
        
        # Handle special intents
        if intent in RESPONSES:
            return RESPONSES[intent].get(language, RESPONSES[intent]["en"])
        
        if borrower is None:
            return RESPONSES["ACCOUNT_ERROR"].get(language, RESPONSES["ACCOUNT_ERROR"]["en"])
        
        role = borrower.get("role", "")
        
        # Build language-specific responses
        if intent == "CHECK_BALANCE":
            if role == "lender":
                bal = borrower.get("lending_balance", 0)
                if language == "hi":
                    return f"आपका उपलब्ध उधार देने का बैलेंस ₹{bal:,.2f} है।"
                elif language == "te":
                    return f"మీ అందుబాటులో ఉన్న రుణం ఇచ్చే బ్యాలెన్స్ ₹{bal:,.2f}."
                elif language == "ta":
                    return f"உங்கள் கடன் வழங்கும் நிலுவை ₹{bal:,.2f}."
                else:
                    return f"Your available lending balance is ₹{bal:,.2f}."
            
            wallet_bal = borrower.get("wallet_balance", 0.0) or 0.0
            credit_score = borrower.get("credit_score", 500)
            limit = borrower.get("borrowing_limit", 2000)
            if language == "hi":
                return f"आपका वॉलेट बैलेंस ₹{wallet_bal:,.2f} है, क्रेडिट स्कोर {credit_score} और उधार सीमा ₹{limit:,.0f} है।"
            elif language == "te":
                return f"మీ వాలెట్ బ్యాలెన్స్ ₹{wallet_bal:,.2f}, క్రెడిట్ స్కోర్ {credit_score} మరియు రుణం పరిమితి ₹{limit:,.0f}."
            elif language == "ta":
                return f"உங்கள் பணப்பை நிலுவை ₹{wallet_bal:,.2f}, கடன் மதிப்பெண் {credit_score} மற்றும் கடன் வரம்பு ₹{limit:,.0f}."
            else:
                return f"Your bank wallet balance is ₹{wallet_bal:,.2f}, credit score is {credit_score}, and borrowing limit is ₹{limit:,.0f}."

        
        if intent == "CHECK_CREDIT_SCORE":
            score = borrower.get("credit_score")
            if score is None:
                if language == "hi":
                    return "अभी तक कोई क्रेडिट स्कोर नहीं है। यह आपकी पहली लोन गतिविधि के बाद दिखाई देगा।"
                elif language == "te":
                    return "ఇంకా క్రెడిట్ స్కోర్ లేదు. మీ మొదటి లోన్ కార్యాచరణ తర్వాత ఇది కనిపిస్తుంది."
                elif language == "ta":
                    return "இன்னும் கடன் மதிப்பெண் இல்லை. உங்கள் முதல் கடன் செயல்பாட்டிற்குப் பிறகு இது தோன்றும்."
                else:
                    return "No credit score on file yet. It will appear after your first loan activity."
            
            if language == "hi":
                return f"आपका वर्तमान क्रेडिट स्कोर 850 में से {score} है।"
            elif language == "te":
                return f"మీ ప్రస్తుత క్రెడిట్ స్కోర్ 850లో {score}."
            elif language == "ta":
                return f"உங்கள் தற்போதைய கடன் மதிப்பெண் 850-இல் {score}."
            else:
                return f"Your current credit score is {score} out of 850."
        
        if intent == "REQUEST_LOAN":
            if "amount" not in entities:
                if language == "hi":
                    return "आप कितना उधार लेना चाहते हैं? उदाहरण के लिए, कहें '5000 रुपये का लोन चाहिए'।"
                elif language == "te":
                    return "మీరు ఎంత రుణం తీసుకోవాలనుకుంటున్నారు? ఉదాహరణకు, '5000 రూపాయల లోన్ కావాలి' అని చెప్పండి."
                elif language == "ta":
                    return "நீங்கள் எவ்வளவு கடன் பெற விரும்புகிறீர்கள்? உதாரணமாக, '5000 ரூபாய் கடன் வேண்டும்' என்று சொல்லுங்கள்."
                else:
                    return "How much would you like to borrow? For example, say 'request a loan of 5000 rupees'."
            
            if language == "hi":
                return "आपका लोन अनुरोध संसाधित हो रहा है..."
            elif language == "te":
                return "మీ లోన్ అభ్యర్థనను ప్రాసెస్ చేస్తున్నాము..."
            elif language == "ta":
                return "உங்கள் கடன் கோரிக்கையை செயலாக்குகிறோம்..."
            else:
                return "Processing your loan request..."
        
        # Default fallback
        return RESPONSES["UNKNOWN"].get(language, RESPONSES["UNKNOWN"]["en"])


# Global service instance
_enhanced_service: Optional[EnhancedVoiceService] = None


def get_enhanced_voice_service() -> EnhancedVoiceService:
    """Get singleton instance of enhanced voice service."""
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = EnhancedVoiceService()
    return _enhanced_service
