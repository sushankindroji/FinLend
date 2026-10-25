"""Tests for EMI calculator service."""
import math

import pytest

from app.services.emi_calculator import EMICalculatorService, get_emi_calculator


class TestEMICalculations:
    """Test EMI calculation accuracy."""
    
    def test_reducing_balance_emi(self):
        """Test standard reducing balance EMI calculation."""
        service = EMICalculatorService()
        emi = service.calculate_reducing_balance_emi(
            principal=10000,
            annual_rate=0.12,  # 12% annual
            tenure_months=12,
        )
        # Expected EMI ≈ 888.49
        assert 885 < emi < 892
    
    def test_flat_rate_emi(self):
        """Test flat rate EMI calculation."""
        service = EMICalculatorService()
        emi = service.calculate_flat_rate_emi(
            principal=10000,
            annual_rate=0.12,
            tenure_months=12,
        )
        # Total = 10000 + (10000 * 0.12 * 1) = 11200
        # EMI = 11200 / 12 = 933.33
        assert 930 < emi < 936
    
    def test_zero_interest(self):
        """Test EMI with zero interest rate."""
        service = EMICalculatorService()
        emi = service.calculate_reducing_balance_emi(
            principal=12000,
            annual_rate=0.0,
            tenure_months=12,
        )
        # EMI should be exactly principal / months
        assert emi == 1000.0
    
    def test_single_month_tenure(self):
        """Test EMI for single month tenure."""
        service = EMICalculatorService()
        emi = service.calculate_reducing_balance_emi(
            principal=5000,
            annual_rate=0.10,
            tenure_months=1,
        )
        # Should be approximately principal + one month's interest
        assert 5000 < emi < 5050


class TestLoanCalculation:
    """Test full loan calculation with schedule."""
    
    def test_reducing_balance_calculation(self):
        """Test complete reducing balance loan calculation."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=10000,
            annual_rate=0.12,
            tenure_days=360,  # ~12 months
            repayment_method="reducing",
        )
        
        assert result.principal == 10000
        assert result.interest_rate == 0.12
        assert result.tenure_months == 12
        assert result.emi_amount > 0
        assert result.total_interest > 0
        assert result.total_payment == result.principal + result.total_interest
        assert len(result.schedule) == 12
        
        # Verify schedule
        for i, entry in enumerate(result.schedule):
            assert entry.installment_number == i + 1
            assert entry.emi_amount > 0
            assert entry.principal_component > 0
            assert entry.interest_component >= 0
        
        # Last entry should have zero outstanding
        assert result.schedule[-1].outstanding_balance == 0.0
    
    def test_flat_rate_calculation(self):
        """Test flat rate loan calculation."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=10000,
            annual_rate=0.12,
            tenure_days=360,
            repayment_method="flat",
        )
        
        # Total interest = 10000 * 0.12 * 1 = 1200
        assert 1195 < result.total_interest < 1205
        assert result.total_payment == result.principal + result.total_interest
        
        # All EMIs should be equal in flat rate
        emis = [entry.emi_amount for entry in result.schedule]
        assert len(set(emis)) <= 2  # At most 2 unique values (due to rounding)
    
    def test_bullet_repayment(self):
        """Test bullet repayment (single payment at end)."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=10000,
            annual_rate=0.10,
            tenure_days=365,
            repayment_method="bullet",
        )
        
        # Should have only one payment
        assert len(result.schedule) == 1
        assert result.schedule[0].installment_number == 1
        
        # Total payment should be principal + interest
        expected_interest = 10000 * 0.10 * (365 / 365)
        assert abs(result.total_interest - expected_interest) < 10
        assert result.schedule[0].outstanding_balance == 0.0
    
    def test_schedule_totals_match(self):
        """Verify schedule components sum to totals."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=15000,
            annual_rate=0.15,
            tenure_days=180,
            repayment_method="reducing",
        )
        
        total_principal = sum(e.principal_component for e in result.schedule)
        total_interest = sum(e.interest_component for e in result.schedule)
        
        # Total principal should equal loan amount
        assert abs(total_principal - result.principal) < 1.0
        # Total interest should match
        assert abs(total_interest - result.total_interest) < 1.0


class TestLoanComparison:
    """Test loan comparison features."""
    
    def test_compare_rates(self):
        """Test comparing loans at different interest rates."""
        calculator = get_emi_calculator()
        results = calculator.compare_loan_options(
            principal=20000,
            tenure_days=360,
            rate_options=[0.08, 0.10, 0.12],
        )
        
        assert len(results) == 3
        
        # EMI should increase with interest rate
        emis = [r.emi_amount for r in results]
        assert emis[0] < emis[1] < emis[2]
        
        # Total interest should increase
        interests = [r.total_interest for r in results]
        assert interests[0] < interests[1] < interests[2]


class TestMaxAffordableLoan:
    """Test maximum affordable loan calculation."""
    
    def test_max_affordable_basic(self):
        """Test basic max affordable calculation."""
        calculator = get_emi_calculator()
        max_loan = calculator.calculate_max_affordable_loan(
            monthly_repayment_capacity=1000,
            annual_rate=0.12,
            tenure_months=12,
        )
        
        # Should be able to afford a loan < 12000
        assert 10000 < max_loan < 12000
        
        # Verify by calculating EMI
        emi = calculator.calculate_reducing_balance_emi(
            principal=max_loan,
            annual_rate=0.12,
            tenure_months=12,
        )
        assert abs(emi - 1000) < 1.0
    
    def test_max_affordable_zero_rate(self):
        """Test max affordable with zero interest."""
        calculator = get_emi_calculator()
        max_loan = calculator.calculate_max_affordable_loan(
            monthly_repayment_capacity=500,
            annual_rate=0.0,
            tenure_months=10,
        )
        # Should be exactly capacity * months
        assert max_loan == 5000.0


class TestCalculationExplanation:
    """Test explanation generation."""
    
    def test_explain_english(self):
        """Test English explanation."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=10000,
            annual_rate=0.12,
            tenure_days=360,
            repayment_method="reducing",
        )
        
        explanation = calculator.explain_calculation(result, "en")
        assert "10000" in explanation or "10,000" in explanation
        assert "EMI" in explanation
        assert "12" in explanation  # months
    
    def test_explain_hindi(self):
        """Test Hindi explanation."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=5000,
            annual_rate=0.10,
            tenure_days=180,
            repayment_method="reducing",
        )
        
        explanation = calculator.explain_calculation(result, "hi")
        # Should contain Hindi text
        assert "ऋण" in explanation or "किस्त" in explanation or "महीने" in explanation


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_very_short_tenure(self):
        """Test loan with very short tenure."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=1000,
            annual_rate=0.15,
            tenure_days=10,
            repayment_method="reducing",
        )
        
        # Should have at least 1 payment
        assert len(result.schedule) >= 1
        assert result.total_payment > result.principal
    
    def test_very_long_tenure(self):
        """Test loan with long tenure."""
        calculator = get_emi_calculator()
        result = calculator.calculate_loan(
            principal=50000,
            annual_rate=0.10,
            tenure_days=900,  # ~30 months
            repayment_method="reducing",
        )
        
        assert result.tenure_months == 30
        assert len(result.schedule) == 30
        # Interest should be substantial (reducing balance means lower interest than flat rate)
        assert result.total_interest > 5000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
