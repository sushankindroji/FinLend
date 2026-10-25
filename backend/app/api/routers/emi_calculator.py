"""EMI Calculator API endpoints.

Provides loan simulation and EMI calculation services.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.models.schemas import EMICalculationRequest, EMICalculationResponse
from app.services.emi_calculator import get_emi_calculator

router = APIRouter(prefix="/api/emi-calculator", tags=["emi-calculator"])


@router.post("/calculate", response_model=EMICalculationResponse)
async def calculate_emi(
    payload: EMICalculationRequest,
    user=Depends(get_current_user),
):
    """
    Calculate EMI and generate loan repayment schedule.
    
    Supports different repayment methods:
    - reducing: Reducing balance (most common)
    - flat: Flat rate
    - bullet: Single payment at end
    """
    calculator = get_emi_calculator()
    
    result = calculator.calculate_loan(
        principal=payload.principal,
        annual_rate=payload.annual_rate,
        tenure_days=payload.tenure_days,
        repayment_method=payload.repayment_method,
    )
    
    # Convert schedule to dict
    schedule_dicts = [
        {
            "installment_number": entry.installment_number,
            "emi_amount": entry.emi_amount,
            "principal_component": entry.principal_component,
            "interest_component": entry.interest_component,
            "outstanding_balance": entry.outstanding_balance,
            "due_date_offset_days": entry.due_date_offset_days,
        }
        for entry in result.schedule
    ]
    
    return {
        "principal": result.principal,
        "interest_rate": result.interest_rate,
        "tenure_months": result.tenure_months,
        "tenure_days": result.tenure_days,
        "repayment_method": result.repayment_method,
        "emi_amount": result.emi_amount,
        "total_interest": result.total_interest,
        "total_payment": result.total_payment,
        "schedule": schedule_dicts,
        "effective_interest_rate": result.effective_interest_rate,
        "total_cost_ratio": result.total_cost_ratio,
    }


@router.get("/compare")
async def compare_loan_options(
    principal: float = Query(..., gt=0, description="Loan amount"),
    tenure_days: int = Query(..., gt=0, description="Loan tenure in days"),
    rates: Optional[str] = Query(None, description="Comma-separated interest rates (e.g., 0.08,0.10,0.12)"),
    user=Depends(get_current_user),
):
    """
    Compare loan options at different interest rates.
    
    Returns calculations for multiple rate scenarios.
    """
    calculator = get_emi_calculator()
    
    # Parse rates
    if rates:
        rate_list = [float(r.strip()) for r in rates.split(",")]
    else:
        rate_list = None
    
    results = calculator.compare_loan_options(
        principal=principal,
        tenure_days=tenure_days,
        rate_options=rate_list,
    )
    
    comparisons = []
    for result in results:
        comparisons.append({
            "interest_rate": result.interest_rate,
            "emi_amount": result.emi_amount,
            "total_interest": result.total_interest,
            "total_payment": result.total_payment,
            "effective_interest_rate": result.effective_interest_rate,
        })
    
    return {"comparisons": comparisons}


@router.get("/max-affordable")
async def calculate_max_affordable(
    monthly_emi: float = Query(..., gt=0, description="Affordable monthly EMI"),
    annual_rate: float = Query(..., gt=0, lt=1, description="Annual interest rate"),
    tenure_months: int = Query(..., gt=0, description="Loan tenure in months"),
    user=Depends(get_current_user),
):
    """
    Calculate maximum affordable loan amount given EMI capacity.
    
    Useful for pre-qualification and affordability assessment.
    """
    calculator = get_emi_calculator()
    
    max_loan = calculator.calculate_max_affordable_loan(
        monthly_repayment_capacity=monthly_emi,
        annual_rate=annual_rate,
        tenure_months=tenure_months,
    )
    
    return {
        "max_loan_amount": max_loan,
        "monthly_emi": monthly_emi,
        "annual_rate": annual_rate,
        "tenure_months": tenure_months,
    }


@router.post("/explain")
async def explain_calculation(
    payload: EMICalculationRequest,
    language: str = Query("en", pattern="^(en|hi|te|ta)$"),
    user=Depends(get_current_user),
):
    """
    Get plain-language explanation of loan calculation.
    
    Supports multiple languages for accessibility.
    """
    calculator = get_emi_calculator()
    
    result = calculator.calculate_loan(
        principal=payload.principal,
        annual_rate=payload.annual_rate,
        tenure_days=payload.tenure_days,
        repayment_method=payload.repayment_method,
    )
    
    explanation = calculator.explain_calculation(result, language)
    
    return {
        "explanation": explanation,
        "language": language,
        "summary": {
            "emi_amount": result.emi_amount,
            "total_interest": result.total_interest,
            "total_payment": result.total_payment,
        },
    }
