"""Centralized application configuration.

All tunable constants (credit scoring deltas, borrowing limit tiers,
interest rate, etc.) live here so they are not scattered across the
codebase, per academic-project requirement #7 / #8.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Mongo
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "finlend"

    # Auth
    jwt_secret_key: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # App
    app_env: str = "development"
    cors_origins: str = "http://localhost:4200"
    port: int = 8000

    # Blockchain
    web3_provider_uri: str = "http://127.0.0.1:8545"
    contract_address: str = ""
    deployer_private_key: str = ""
    blockchain_enabled: bool = True
    blockchain_network_name: str = "hardhat-local"
    block_explorer_base_url: str = ""

    # Voice
    voice_provider: str = "demo"
    openai_api_key: str = ""
    google_tts_api_key: str = ""

    # ML
    model_path: str = "app/ml/artifacts/risk_model.joblib"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Domain configuration constants (NOT secrets) - kept together so the
# behavioral-scoring rules and borrowing-limit tiers are easy to audit/tune.
# ---------------------------------------------------------------------------

CREDIT_SCORE_CONFIG = {
    "base_score": 500,
    "min_score": 300,
    "max_score": 850,
    "on_time_repayment": 40,
    "completed_loan": 25,
    "early_repayment": 30,
    "late_repayment": -30,
    "default": -100,
}

# Ordered low -> high. Each tier: (min_score_inclusive, max_score_inclusive, limit)
BORROWING_LIMIT_TIERS = [
    (300, 499, 2000),
    (500, 649, 5000),
    (650, 749, 10000),
    (750, 850, 25000),
]

# Simulated interest rate applied to every new loan (prototype only).
SIMULATED_INTEREST_RATE = 0.10

# A repayment made this many days (or more) before the due date counts as
# "early" for behavioral scoring purposes.
EARLY_REPAYMENT_THRESHOLD_DAYS = 3
# A repayment made after the due date, up to this many days late, is "late"
# rather than a default.
LATE_GRACE_PERIOD_DAYS = 15

VALID_LOAN_STATUSES = [
    "REQUESTED",
    "CREDIT_CHECK",
    "APPROVED",
    "REJECTED",
    "OPEN_FOR_FUNDING",
    "PARTIALLY_FUNDED",
    "FUNDED",
    "ACTIVE",
    "LATE",
    "REPAID",
    "DEFAULTED",
]

# Allowed forward transitions of the loan state machine (req #6).
LOAN_STATE_TRANSITIONS = {
    "REQUESTED": {"CREDIT_CHECK"},
    "CREDIT_CHECK": {"APPROVED", "REJECTED"},
    "APPROVED": {"OPEN_FOR_FUNDING"},
    "REJECTED": set(),
    "OPEN_FOR_FUNDING": {"PARTIALLY_FUNDED", "FUNDED"},
    "PARTIALLY_FUNDED": {"PARTIALLY_FUNDED", "FUNDED"},
    "FUNDED": {"ACTIVE"},
    "ACTIVE": {"LATE", "REPAID", "DEFAULTED"},
    "LATE": {"REPAID", "DEFAULTED"},
    "REPAID": set(),
    "DEFAULTED": set(),
}
