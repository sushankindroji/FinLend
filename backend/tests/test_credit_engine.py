from app.services import credit_engine


def test_initial_score():
    assert credit_engine.initial_score() == 500


def test_on_time_repayment_increases_score():
    score, events = credit_engine.score_for_repayment(500, is_early=False, is_on_time=True, is_default=False)
    assert score == 540
    assert events == ["on_time_repayment"]


def test_early_repayment_adds_bonus():
    score, events = credit_engine.score_for_repayment(500, is_early=True, is_on_time=True, is_default=False)
    assert score == 570
    assert "early_repayment" in events


def test_late_repayment_decreases_score():
    score, events = credit_engine.score_for_repayment(500, is_early=False, is_on_time=False, is_default=False)
    assert score == 470


def test_default_penalty():
    score, events = credit_engine.score_for_repayment(500, is_early=False, is_on_time=False, is_default=True)
    assert score == 400
    assert events == ["default"]


def test_score_clamped_to_bounds():
    score = credit_engine.clamp_score(1000)
    assert score == 850
    score = credit_engine.clamp_score(0)
    assert score == 300


def test_borrowing_limit_tiers():
    assert credit_engine.borrowing_limit_for_score(300) == 2000
    assert credit_engine.borrowing_limit_for_score(499) == 2000
    assert credit_engine.borrowing_limit_for_score(500) == 5000
    assert credit_engine.borrowing_limit_for_score(649) == 5000
    assert credit_engine.borrowing_limit_for_score(650) == 10000
    assert credit_engine.borrowing_limit_for_score(750) == 25000
    assert credit_engine.borrowing_limit_for_score(850) == 25000
