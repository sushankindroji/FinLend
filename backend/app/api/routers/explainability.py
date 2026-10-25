"""Explainability API endpoints.

Provides credit score explanations and AI transparency.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import get_current_user
from app.db.mongodb import get_db
from app.services import loan_service
from app.services.explainable_ai import get_explainable_ai_service

router = APIRouter(prefix="/api/explainability", tags=["explainability"])


@router.get("/credit-score")
async def explain_my_credit_score(
    language: str = Query("en", pattern="^(en|hi|te|ta)$"),
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get detailed explanation of current credit score.
    
    Returns feature importance, contributing factors, and recommendations
    in the requested language.
    """
    # Get borrower data
    borrower = await db.users.find_one({"_id": loan_service.oid(user["id"])})
    if not borrower:
        raise HTTPException(status_code=404, detail="User not found")
    
    if borrower.get("role") != "borrower":
        raise HTTPException(status_code=403, detail="Only borrowers have credit scores")
    
    # Get explanation
    explainer = get_explainable_ai_service()
    explanation = explainer.explain_credit_score(borrower, language)
    
    return explanation


@router.get("/loan-decision/{loan_id}")
async def explain_loan_decision(
    loan_id: str,
    language: str = Query("en", pattern="^(en|hi|te|ta)$"),
    user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get explanation for a specific loan approval/rejection decision.
    
    Shows which factors influenced the decision and how to improve.
    """
    # Get loan
    loan = await db.loans.find_one({"_id": loan_service.oid(loan_id)})
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    # Verify access
    borrower_id = str(loan.get("borrower_id", ""))
    if borrower_id != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get borrower data at time of decision
    borrower = await db.users.find_one({"_id": loan.get("borrower_id")})
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    
    # Build features from borrower stats
    stats = borrower.get("stats", {})
    features = {
        "completed_loans": stats.get("completed_loans", 0),
        "on_time_repayments": stats.get("on_time_repayments", 0),
        "late_repayments": stats.get("late_repayments", 0),
        "defaults": stats.get("defaults", 0),
        "total_borrowed": stats.get("total_borrowed", 0.0),
        "total_repaid": stats.get("total_repaid", 0.0),
        "repayment_ratio": stats.get("total_repaid", 0.0) / max(stats.get("total_borrowed", 1.0), 1.0),
        "average_delay_days": stats.get("average_delay_days", 0.0),
    }
    
    # Get explanation
    explainer = get_explainable_ai_service()
    decision = "rejected" if loan["status"] == "REJECTED" else "approved"
    
    explanation = explainer.explain_credit_decision(
        features=features,
        credit_score=borrower.get("credit_score", 500),
        risk_category=loan.get("risk_category", "MEDIUM"),
        decision=decision,
        language=language,
    )
    
    # Add loan-specific context
    explanation["loan_id"] = loan_id
    explanation["loan_amount"] = loan["amount"]
    explanation["loan_status"] = loan["status"]
    if loan["status"] == "REJECTED":
        explanation["rejection_reason"] = loan.get("rejection_reason", "Unknown")
    
    return explanation


@router.get("/factors")
async def get_credit_factors(
    language: str = Query("en", pattern="^(en|hi|te|ta)$"),
    user=Depends(get_current_user),
):
    """
    Get information about factors that affect credit scores.
    
    Educational endpoint explaining the credit scoring system.
    """
    # Multilingual factor descriptions
    factors_info = {
        "en": [
            {
                "name": "On-Time Payments",
                "impact": "positive",
                "weight": "high",
                "description": "Paying your installments on or before the due date significantly improves your score.",
            },
            {
                "name": "Completed Loans",
                "impact": "positive",
                "weight": "medium",
                "description": "Successfully repaying loans in full demonstrates reliability.",
            },
            {
                "name": "Early Repayments",
                "impact": "positive",
                "weight": "medium",
                "description": "Paying ahead of schedule shows strong financial discipline.",
            },
            {
                "name": "Late Payments",
                "impact": "negative",
                "weight": "high",
                "description": "Missing due dates reduces your score and borrowing limit.",
            },
            {
                "name": "Defaults",
                "impact": "negative",
                "weight": "very high",
                "description": "Defaulting on a loan severely damages your credit score.",
            },
            {
                "name": "Repayment Ratio",
                "impact": "varies",
                "weight": "high",
                "description": "The proportion of your borrowed amount that you've repaid. Higher is better.",
            },
        ],
        "hi": [
            {
                "name": "समय पर भुगतान",
                "impact": "positive",
                "weight": "high",
                "description": "नियत तारीख पर या उससे पहले भुगतान करने से आपका स्कोर काफी बढ़ता है।",
            },
            {
                "name": "पूर्ण ऋण",
                "impact": "positive",
                "weight": "medium",
                "description": "ऋण पूरी तरह चुकाना विश्वसनीयता दर्शाता है।",
            },
            {
                "name": "समय से पहले भुगतान",
                "impact": "positive",
                "weight": "medium",
                "description": "समय से पहले भुगतान करना मजबूत वित्तीय अनुशासन दर्शाता है।",
            },
            {
                "name": "विलंबित भुगतान",
                "impact": "negative",
                "weight": "high",
                "description": "नियत तारीख चूकने से आपका स्कोर और उधार सीमा कम होती है।",
            },
            {
                "name": "चूक",
                "impact": "negative",
                "weight": "very high",
                "description": "ऋण पर चूक करना आपके क्रेडिट स्कोर को गंभीर रूप से नुकसान पहुंचाता है।",
            },
        ],
        "te": [
            {
                "name": "సమయానికి చెల్లింపులు",
                "impact": "positive",
                "weight": "high",
                "description": "గడువు తేదీకి లేదా ముందే చెల్లించడం మీ స్కోర్‌ను గణనీయంగా మెరుగుపరుస్తుంది.",
            },
            {
                "name": "పూర్తయిన రుణాలు",
                "impact": "positive",
                "weight": "medium",
                "description": "రుణాలను పూర్తిగా తిరిగి చెల్లించడం విశ్వసనీయతను ప్రదర్శిస్తుంది.",
            },
            {
                "name": "ముందస్తు చెల్లింపులు",
                "impact": "positive",
                "weight": "medium",
                "description": "షెడ్యూల్ కంటే ముందే చెల్లించడం బలమైన ఆర్థిక క్రమశిక్షణను చూపిస్తుంది.",
            },
            {
                "name": "ఆలస్యమైన చెల్లింపులు",
                "impact": "negative",
                "weight": "high",
                "description": "గడువు తేదీలను కోల్పోవడం మీ స్కోర్ మరియు రుణం తీసుకునే పరిమితిని తగ్గిస్తుంది.",
            },
        ],
        "ta": [
            {
                "name": "சரியான நேர பணம்",
                "impact": "positive",
                "weight": "high",
                "description": "காலக்கெடுவில் அல்லது அதற்கு முன் செலுத்துவது உங்கள் மதிப்பெண்ணை கணிசமாக மேம்படுத்துகிறது.",
            },
            {
                "name": "முடிந்த கடன்கள்",
                "impact": "positive",
                "weight": "medium",
                "description": "கடன்களை முழுமையாக திருப்பிச் செலுத்துவது நம்பகத்தன்மையை நிரூபிக்கிறது.",
            },
            {
                "name": "முன்கூட்டிய திருப்பிச் செலுத்துதல்",
                "impact": "positive",
                "weight": "medium",
                "description": "திட்டமிடலுக்கு முன்பே செலுத்துவது வலுவான நிதி ஒழுக்கத்தைக் காட்டுகிறது.",
            },
            {
                "name": "தாமதமான பணம்",
                "impact": "negative",
                "weight": "high",
                "description": "காலக்கெடுவைத் தவறவிடுவது உங்கள் மதிப்பெண்ணையும் கடன் வரம்பையும் குறைக்கிறது.",
            },
        ],
    }
    
    return {
        "factors": factors_info.get(language, factors_info["en"]),
        "language": language,
        "scoring_range": {
            "min": 300,
            "max": 850,
            "base": 500,
        },
    }
