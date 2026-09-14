import pytest
from fastapi import HTTPException

from app.services.loan_service import _assert_transition


def test_valid_transition_passes():
    _assert_transition("REQUESTED", "CREDIT_CHECK")
    _assert_transition("CREDIT_CHECK", "APPROVED")
    _assert_transition("APPROVED", "OPEN_FOR_FUNDING")
    _assert_transition("ACTIVE", "REPAID")


def test_repaid_loan_cannot_transition_further():
    with pytest.raises(HTTPException):
        _assert_transition("REPAID", "ACTIVE")


def test_rejected_loan_cannot_be_funded():
    with pytest.raises(HTTPException):
        _assert_transition("REJECTED", "OPEN_FOR_FUNDING")


def test_cannot_skip_credit_check():
    with pytest.raises(HTTPException):
        _assert_transition("REQUESTED", "APPROVED")


def test_defaulted_loan_is_terminal():
    with pytest.raises(HTTPException):
        _assert_transition("DEFAULTED", "REPAID")
