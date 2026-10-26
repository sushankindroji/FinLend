from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends

from app.api.serializers import serialize_doc
from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import CREDIT_SCORE_CONFIG
from app.db.mongodb import get_db
from app.models.schemas import TokenResponse, UserLogin, UserRegister, UserPublic
from app.services.credit_engine import borrowing_limit_for_score

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: UserRegister, db: AsyncIOMotorDatabase = Depends(get_db)):
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    initial_score = CREDIT_SCORE_CONFIG["base_score"]
    doc = {
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "password_hash": hash_password(payload.password),
        "role": payload.role.value,
        "credit_score": initial_score if payload.role.value == "borrower" else None,
        "borrowing_limit": borrowing_limit_for_score(initial_score) if payload.role.value == "borrower" else None,
        "lending_balance": 50000.0 if payload.role.value == "lender" else None,
        "wallet_balance": 1000.0 if payload.role.value == "borrower" else None,
        "stats": {},
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(doc)
    token = create_access_token(str(result.inserted_id), payload.role.value)
    return TokenResponse(access_token=token, role=payload.role.value, user_id=str(result.inserted_id))


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user["_id"]), user["role"])
    return TokenResponse(access_token=token, role=user["role"], user_id=str(user["_id"]))
