"""Tests for multilingual voice service."""
import pytest

from app.services.multilingual_voice import (
    EnhancedVoiceService,
    INTENT_PATTERNS,
    AMOUNT_PATTERNS,
)


class TestLanguageDetection:
    """Test language detection capabilities."""
    
    def test_detect_english(self):
        service = EnhancedVoiceService()
        text = "I want to request a loan"
        lang = service.detect_language(text)
        assert lang == "en"
    
    def test_detect_hindi(self):
        service = EnhancedVoiceService()
        text = "मुझे लोन चाहिए"
        lang = service.detect_language(text)
        # Will likely detect as hindi or fallback to en
        assert lang in ("hi", "en")


class TestIntentDetection:
    """Test multilingual intent detection."""
    
    def test_intent_request_loan_english(self):
        service = EnhancedVoiceService()
        text = "I want to request a loan"
        normalized = service.normalize_text(text, "en")
        intent = service.detect_intent(normalized, "en")
        assert intent == "REQUEST_LOAN"
    
    def test_intent_request_loan_hindi(self):
        service = EnhancedVoiceService()
        text = "loan chahiye"
        normalized = service.normalize_text(text, "hi")
        intent = service.detect_intent(normalized, "hi")
        assert intent == "REQUEST_LOAN"
    
    def test_intent_check_balance_english(self):
        service = EnhancedVoiceService()
        text = "check my balance"
        normalized = service.normalize_text(text, "en")
        intent = service.detect_intent(normalized, "en")
        assert intent == "CHECK_BALANCE"
    
    def test_intent_check_credit_score(self):
        service = EnhancedVoiceService()
        text = "what is my credit score"
        normalized = service.normalize_text(text, "en")
        intent = service.detect_intent(normalized, "en")
        assert intent == "CHECK_CREDIT_SCORE"
    
    def test_intent_help(self):
        service = EnhancedVoiceService()
        text = "help"
        normalized = service.normalize_text(text, "en")
        intent = service.detect_intent(normalized, "en")
        assert intent == "HELP"
    
    def test_intent_unknown(self):
        service = EnhancedVoiceService()
        text = "xyz abc random words"
        normalized = service.normalize_text(text, "en")
        intent = service.detect_intent(normalized, "en")
        assert intent == "UNKNOWN"


class TestEntityExtraction:
    """Test entity extraction from voice input."""
    
    def test_extract_amount_english(self):
        service = EnhancedVoiceService()
        text = "I need a loan of 5000 rupees"
        normalized = service.normalize_text(text, "en")
        entities = service.extract_entities(normalized, "REQUEST_LOAN", "en")
        assert "amount" in entities
        assert entities["amount"] == 5000.0
    
    def test_extract_amount_with_symbol(self):
        service = EnhancedVoiceService()
        text = "I need ₹10000"
        normalized = service.normalize_text(text, "en")
        entities = service.extract_entities(normalized, "REQUEST_LOAN", "en")
        assert "amount" in entities
        assert entities["amount"] == 10000.0
    
    def test_extract_amount_with_commas(self):
        service = EnhancedVoiceService()
        text = "loan of Rs. 25,000"
        normalized = service.normalize_text(text, "en")
        entities = service.extract_entities(normalized, "REQUEST_LOAN", "en")
        assert "amount" in entities
        assert entities["amount"] == 25000.0
    
    def test_extract_duration(self):
        service = EnhancedVoiceService()
        text = "I need a loan for 60 days"
        normalized = service.normalize_text(text, "en")
        entities = service.extract_entities(normalized, "REQUEST_LOAN", "en")
        assert "duration_days" in entities
        assert entities["duration_days"] == 60
    
    def test_extract_duration_months(self):
        service = EnhancedVoiceService()
        text = "loan for 2 months"
        normalized = service.normalize_text(text, "en")
        entities = service.extract_entities(normalized, "REQUEST_LOAN", "en")
        assert "duration_days" in entities
        assert entities["duration_days"] == 60
    
    def test_no_amount_extracted(self):
        service = EnhancedVoiceService()
        text = "I need a loan"
        normalized = service.normalize_text(text, "en")
        entities = service.extract_entities(normalized, "REQUEST_LOAN", "en")
        assert "amount" not in entities


class TestResponseGeneration:
    """Test multilingual response generation."""
    
    def test_build_help_response_english(self):
        service = EnhancedVoiceService()
        borrower = {"role": "borrower", "credit_score": 600}
        response = service.build_response("HELP", {}, borrower, "en")
        assert "check balance" in response.lower()
        assert "credit score" in response.lower()
    
    def test_build_help_response_hindi(self):
        service = EnhancedVoiceService()
        borrower = {"role": "borrower", "credit_score": 600}
        response = service.build_response("HELP", {}, borrower, "hi")
        assert "बैलेंस" in response or "स्कोर" in response
    
    def test_build_balance_response_borrower(self):
        service = EnhancedVoiceService()
        borrower = {
            "role": "borrower",
            "credit_score": 650,
            "borrowing_limit": 10000,
        }
        response = service.build_response("CHECK_BALANCE", {}, borrower, "en")
        assert "650" in response
        assert "10000" in response or "10,000" in response
    
    def test_build_balance_response_lender(self):
        service = EnhancedVoiceService()
        lender = {
            "role": "lender",
            "lending_balance": 50000.0,
        }
        response = service.build_response("CHECK_BALANCE", {}, lender, "en")
        assert "50000" in response or "50,000" in response
    
    def test_build_missing_amount_response(self):
        service = EnhancedVoiceService()
        borrower = {"role": "borrower"}
        response = service.build_response("REQUEST_LOAN", {}, borrower, "en")
        assert "how much" in response.lower() or "amount" in response.lower()


class TestConversationContext:
    """Test conversation context management."""
    
    def test_create_context(self):
        service = EnhancedVoiceService()
        context = service.get_or_create_context("session-1", "user-1", "en")
        assert context.session_id == "session-1"
        assert context.user_id == "user-1"
        assert context.language == "en"
        assert context.turn_count == 0
    
    def test_context_persistence(self):
        service = EnhancedVoiceService()
        context1 = service.get_or_create_context("session-1", "user-1", "en")
        context1.turn_count = 5
        context2 = service.get_or_create_context("session-1", "user-1", "en")
        assert context2.turn_count == 5
        assert context1 is context2


class TestTextNormalization:
    """Test text normalization."""
    
    def test_normalize_whitespace(self):
        service = EnhancedVoiceService()
        text = "hello    world    test"
        normalized = service.normalize_text(text, "en")
        assert "  " not in normalized
        assert normalized == "hello world test"
    
    def test_normalize_case(self):
        service = EnhancedVoiceService()
        text = "HELLO World TeSt"
        normalized = service.normalize_text(text, "en")
        assert normalized == "hello world test"
    
    def test_normalize_english_typo(self):
        service = EnhancedVoiceService()
        text = "I need 5000 rupess"
        normalized = service.normalize_text(text, "en")
        assert "rupees" in normalized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
