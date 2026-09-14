from app.services import voice_service


def test_request_loan_variations_map_to_same_intent():
    variations = [
        "I want to request a loan",
        "can I apply for a loan of 5000 rupees",
        "I need a loan",
        "I want to borrow some money",
        "please get me a loan",
    ]
    for text in variations:
        result = voice_service.process_voice_turn(text)
        assert result.intent == "REQUEST_LOAN", text


def test_amount_extraction():
    result = voice_service.process_voice_turn("request a loan of 5000 rupees")
    assert result.entities.get("amount") == 5000.0


def test_check_balance_intent():
    result = voice_service.process_voice_turn("what's my balance")
    assert result.intent == "CHECK_BALANCE"


def test_unknown_intent_fallback():
    result = voice_service.process_voice_turn("tell me a joke about bananas")
    assert result.intent == "UNKNOWN"


def test_dtmf_mapping():
    text = voice_service.dtmf_to_text("4")
    result = voice_service.process_voice_turn(text)
    assert result.intent == "REQUEST_LOAN"


def test_help_intent():
    result = voice_service.process_voice_turn("help")
    assert result.intent == "HELP"
