"""EMI Calculator and Loan Simulator Service.

Provides accurate loan calculations with various repayment methods:
- Reducing balance (most common)
- Flat rate
- Bullet repayment

Supports interactive simulations and comparisons.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Literal

from app.core.config import SIMULATED_INTEREST_RATE


@dataclass
class EMIScheduleEntry:
    """Single EMI installment details."""
    installment_number: int
    emi_amount: float
    principal_component: float
    interest_component: float
    outstanding_balance: float
    due_date_offset_days: int  # Days from loan start


@dataclass
class LoanCalculation:
    """Complete loan calculation result."""
    principal: float
    interest_rate: float
    tenure_months: int
    tenure_days: int
    repayment_method: str
    
    emi_amount: float
    total_interest: float
    total_payment: float
    
    schedule: List[EMIScheduleEntry]
    
    # Additional metrics
    effective_interest_rate: float
    total_cost_ratio: float  # total_payment / principal


class EMICalculatorService:
    """Service for loan and EMI calculations."""
    
    @staticmethod
    def calculate_reducing_balance_emi(
        principal: float,
        annual_rate: float,
        tenure_months: int,
    ) -> float:
        """
        Calculate EMI using reducing balance method (most accurate).
        
        Formula: EMI = P × r × (1 + r)^n / ((1 + r)^n - 1)
        where:
        - P = Principal loan amount
        - r = Monthly interest rate (annual_rate / 12)
        - n = Number of months
        """
        if tenure_months == 0:
            return principal
        
        monthly_rate = annual_rate / 12
        if monthly_rate == 0:
            return principal / tenure_months
        
        numerator = principal * monthly_rate * math.pow(1 + monthly_rate, tenure_months)
        denominator = math.pow(1 + monthly_rate, tenure_months) - 1
        
        return round(numerator / denominator, 2)
    
    @staticmethod
    def calculate_flat_rate_emi(
        principal: float,
        annual_rate: float,
        tenure_months: int,
    ) -> float:
        """
        Calculate EMI using flat rate method (simple interest).
        
        Total Interest = Principal × Rate × Tenure
        EMI = (Principal + Total Interest) / Tenure
        """
        total_interest = principal * annual_rate * (tenure_months / 12)
        total_amount = principal + total_interest
        return round(total_amount / tenure_months, 2)
    
    def calculate_loan(
        self,
        principal: float,
        annual_rate: float,
        tenure_days: int,
        repayment_method: Literal["reducing", "flat", "bullet"] = "reducing",
    ) -> LoanCalculation:
        """
        Calculate complete loan with amortization schedule.
        
        Args:
            principal: Loan amount
            annual_rate: Annual interest rate (e.g., 0.10 for 10%)
            tenure_days: Loan duration in days
            repayment_method: "reducing", "flat", or "bullet"
        
        Returns:
            LoanCalculation with EMI, schedule, and metrics
        """
        # Convert days to months (approximately)
        tenure_months = max(1, round(tenure_days / 30))
        
        schedule: List[EMIScheduleEntry] = []
        
        if repayment_method == "bullet":
            # Bullet: pay everything at the end
            total_interest = principal * annual_rate * (tenure_days / 365)
            total_payment = principal + total_interest
            emi_amount = total_payment  # Single payment
            
            schedule.append(EMIScheduleEntry(
                installment_number=1,
                emi_amount=round(total_payment, 2),
                principal_component=principal,
                interest_component=round(total_interest, 2),
                outstanding_balance=0.0,
                due_date_offset_days=tenure_days,
            ))
            
        elif repayment_method == "flat":
            emi_amount = self.calculate_flat_rate_emi(principal, annual_rate, tenure_months)
            total_interest = principal * annual_rate * (tenure_months / 12)
            total_payment = principal + total_interest
            
            interest_per_month = total_interest / tenure_months
            principal_per_month = principal / tenure_months
            
            for i in range(tenure_months):
                schedule.append(EMIScheduleEntry(
                    installment_number=i + 1,
                    emi_amount=emi_amount,
                    principal_component=round(principal_per_month, 2),
                    interest_component=round(interest_per_month, 2),
                    outstanding_balance=round(principal - principal_per_month * (i + 1), 2),
                    due_date_offset_days=round((tenure_days / tenure_months) * (i + 1)),
                ))
        
        else:  # reducing (default)
            emi_amount = self.calculate_reducing_balance_emi(principal, annual_rate, tenure_months)
            
            outstanding = principal
            total_interest = 0.0
            
            for i in range(tenure_months):
                monthly_rate = annual_rate / 12
                interest_component = outstanding * monthly_rate
                principal_component = emi_amount - interest_component
                
                # Handle last installment rounding
                if i == tenure_months - 1:
                    principal_component = outstanding
                    emi_final = principal_component + interest_component
                    emi_amount_actual = round(emi_final, 2)
                else:
                    emi_amount_actual = emi_amount
                
                outstanding = max(0, outstanding - principal_component)
                total_interest += interest_component
                
                schedule.append(EMIScheduleEntry(
                    installment_number=i + 1,
                    emi_amount=round(emi_amount_actual, 2),
                    principal_component=round(principal_component, 2),
                    interest_component=round(interest_component, 2),
                    outstanding_balance=round(outstanding, 2),
                    due_date_offset_days=round((tenure_days / tenure_months) * (i + 1)),
                ))
            
            total_payment = principal + total_interest
        
        # Calculate metrics
        effective_rate = (total_payment / principal - 1) / (tenure_days / 365)
        cost_ratio = total_payment / principal
        
        return LoanCalculation(
            principal=principal,
            interest_rate=annual_rate,
            tenure_months=tenure_months,
            tenure_days=tenure_days,
            repayment_method=repayment_method,
            emi_amount=round(emi_amount, 2) if repayment_method != "bullet" else 0.0,
            total_interest=round(total_interest if repayment_method != "bullet" else total_payment - principal, 2),
            total_payment=round(total_payment, 2),
            schedule=schedule,
            effective_interest_rate=round(effective_rate, 4),
            total_cost_ratio=round(cost_ratio, 4),
        )
    
    def compare_loan_options(
        self,
        principal: float,
        tenure_days: int,
        rate_options: List[float] = None,
    ) -> List[LoanCalculation]:
        """
        Compare different loan configurations.
        
        Returns calculations for different interest rates or methods.
        """
        if rate_options is None:
            rate_options = [0.08, 0.10, 0.12, 0.15]  # 8%, 10%, 12%, 15%
        
        results = []
        for rate in rate_options:
            calc = self.calculate_loan(principal, rate, tenure_days, "reducing")
            results.append(calc)
        
        return results
    
    def calculate_max_affordable_loan(
        self,
        monthly_repayment_capacity: float,
        annual_rate: float,
        tenure_months: int,
    ) -> float:
        """
        Calculate maximum loan amount given affordable EMI.
        
        Inverts the EMI formula to solve for principal.
        """
        monthly_rate = annual_rate / 12
        
        if monthly_rate == 0:
            return monthly_repayment_capacity * tenure_months
        
        denominator = monthly_rate * math.pow(1 + monthly_rate, tenure_months)
        numerator = math.pow(1 + monthly_rate, tenure_months) - 1
        
        principal = monthly_repayment_capacity * (numerator / denominator)
        return round(principal, 2)
    
    def explain_calculation(
        self,
        calculation: LoanCalculation,
        language: str = "en",
    ) -> str:
        """
        Generate human-readable explanation of the calculation.
        
        Supports multiple languages for accessibility.
        """
        if language == "hi":
            return (
                f"ऋण राशि: ₹{calculation.principal:,.0f}, अवधि: {calculation.tenure_months} महीने\n"
                f"मासिक किस्त (EMI): ₹{calculation.emi_amount:,.2f}\n"
                f"कुल ब्याज: ₹{calculation.total_interest:,.2f}\n"
                f"कुल भुगतान: ₹{calculation.total_payment:,.2f}\n"
                f"विधि: {calculation.repayment_method}"
            )
        elif language == "te":
            return (
                f"రుణ మొత్తం: ₹{calculation.principal:,.0f}, వ్యవధి: {calculation.tenure_months} నెలలు\n"
                f"నెలవారీ వాయిదా (EMI): ₹{calculation.emi_amount:,.2f}\n"
                f"మొత్తం వడ్డీ: ₹{calculation.total_interest:,.2f}\n"
                f"మొత్తం చెల్లింపు: ₹{calculation.total_payment:,.2f}"
            )
        elif language == "ta":
            return (
                f"கடன் தொகை: ₹{calculation.principal:,.0f}, காலம்: {calculation.tenure_months} மாதங்கள்\n"
                f"மாதாந்திர தவணை (EMI): ₹{calculation.emi_amount:,.2f}\n"
                f"மொத்த வட்டி: ₹{calculation.total_interest:,.2f}\n"
                f"மொத்த செலுத்துதல்: ₹{calculation.total_payment:,.2f}"
            )
        else:  # English
            return (
                f"Loan Amount: ₹{calculation.principal:,.0f}, Tenure: {calculation.tenure_months} months\n"
                f"Monthly EMI: ₹{calculation.emi_amount:,.2f}\n"
                f"Total Interest: ₹{calculation.total_interest:,.2f}\n"
                f"Total Payment: ₹{calculation.total_payment:,.2f}\n"
                f"Method: {calculation.repayment_method}"
            )


# Global service instance
_emi_service: EMICalculatorService | None = None


def get_emi_calculator() -> EMICalculatorService:
    """Get singleton EMI calculator service."""
    global _emi_service
    if _emi_service is None:
        _emi_service = EMICalculatorService()
    return _emi_service
