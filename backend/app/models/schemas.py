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
    wallet_balance: Optional[float] = 0.0
    gender: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    created_at: datetime


class WalletAction(BaseModel):
    amount: float = Field(gt=0, description="Amount to deposit or withdraw")



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
    language: Optional[str] = "en"


class VoiceResponse(BaseModel):
    transcript: str
    intent: str
    entities: dict
    reply_text: str
    audio_available: bool
    session_id: str
    needs_clarification: Optional[bool] = False
    clarification_question: Optional[str] = ""
    action_taken: Optional[str] = None
    end_call: Optional[bool] = False
    data: Optional[dict] = None
    language: Optional[str] = "en-IN"
    use_browser_tts: Optional[bool] = True


# ---------------------------------------------------------------------------
# EMI Calculator
# ---------------------------------------------------------------------------
class EMICalculationRequest(BaseModel):
    principal: float = Field(gt=0, description="Loan amount")
    annual_rate: float = Field(gt=0, lt=1, description="Annual interest rate (e.g., 0.10 for 10%)")
    tenure_days: int = Field(gt=0, description="Loan tenure in days")
    repayment_method: str = Field(default="reducing", pattern="^(reducing|flat|bullet)$")


class EMIScheduleEntry(BaseModel):
    installment_number: int
    emi_amount: float
    principal_component: float
    interest_component: float
    outstanding_balance: float
    due_date_offset_days: int


class EMICalculationResponse(BaseModel):
    principal: float
    interest_rate: float
    tenure_months: int
    tenure_days: int
    repayment_method: str
    emi_amount: float
    total_interest: float
    total_payment: float
    schedule: List[EMIScheduleEntry]
    effective_interest_rate: float
    total_cost_ratio: float


# ---------------------------------------------------------------------------
# Voice / Multilingual
# ---------------------------------------------------------------------------
class EnhancedVoiceRequest(BaseModel):
    """Request for enhanced multilingual voice processing."""
    text: Optional[str] = None
    audio_base64: Optional[str] = None
    language: Optional[str] = "en"
    session_id: Optional[str] = None


class EnhancedVoiceResponse(BaseModel):
    """Response from enhanced voice processing."""
    transcript: str
    detected_language: str
    intent: str
    entities: dict
    reply_text: str
    audio_base64: Optional[str] = None
    audio_available: bool
    session_id: str
    context_maintained: bool = False
