"""Pydantic request/response models shared across API routers."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Role(str, Enum):
    borrower = "borrower"
    lender = "lender"
    admin = "admin"


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------
class UserRegister(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=6)
    role: Role = Role.borrower
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str


class UserPublic(BaseModel):
    id: str
    name: str
    email: str
    role: Role
    phone: Optional[str] = None
    credit_score: Optional[int] = None
    borrowing_limit: Optional[float] = None
    lending_balance: Optional[float] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------
class LoanRequestCreate(BaseModel):
    amount: float = Field(gt=0)
    duration_days: int = Field(gt=0, default=30)
    purpose: Optional[str] = None
    source: str = "web"  # web | voice | dtmf


class LoanFundingCreate(BaseModel):
    amount: float = Field(gt=0)


class RepaymentCreate(BaseModel):
    amount: float = Field(gt=0)


class LoanOut(BaseModel):
    id: str
    borrower_id: str
    borrower_name: Optional[str] = None
    amount: float
    duration_days: int
    interest_rate: float
    total_due: float
    amount_funded: float
    amount_repaid: float
    status: str
    risk_category: Optional[str] = None
    purpose: Optional[str] = None
    source: str
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class FundingOut(BaseModel):
    id: str
    loan_id: str
    lender_id: str
    amount: float
    expected_return: float
    created_at: datetime
    tx_hash: Optional[str] = None


class RepaymentOut(BaseModel):
    id: str
    loan_id: str
    amount: float
    is_on_time: bool
    is_early: bool
    days_late: int
    created_at: datetime
    tx_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# Credit
# ---------------------------------------------------------------------------
class CreditScoreOut(BaseModel):
    user_id: str
    credit_score: int
    risk_category: str
    borrowing_limit: float
    explanation: str
    history: List[dict] = []


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------
class VoiceTextRequest(BaseModel):
    """Used both for real audio-derived text and for the DTMF/demo text path."""
    text: str
    session_id: Optional[str] = None


class VoiceResponse(BaseModel):
    transcript: str
    intent: str
    entities: dict
    reply_text: str
    audio_available: bool
    session_id: str
