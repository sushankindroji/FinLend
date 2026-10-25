"""Tests for explainable AI service."""
import pytest

from app.services.explainable_ai import ExplainableAIService


class TestRuleBasedExplanations:
    """Test rule-based credit explanations (when SHAP unavailable)."""
    
    def test_explain_good_borrower(self):
        """Test explanation for borrower with good history."""
        service = ExplainableAIService()
        
        features = {
            "completed_loans": 5,
            "on_time_repayments": 10,
            "late_repayments": 0,
            "defaults": 0,
            "total_borrowed": 50000.0,
            "total_repaid": 50000.0,
            "repayment_ratio": 1.0,
            "average_delay_days": 0.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=750,
            risk_category="LOW",
            decision="approved",
            language="en",
        )
        
        assert result["decision"] == "approved"
        assert result["credit_score"] == 750
        assert result["risk_category"] == "LOW"
        assert len(result["top_factors"]) > 0
        
        # Should have positive factors
        positive_factors = [f for f in result["top_factors"] if f["impact"] == "positive"]
        assert len(positive_factors) > 0
    
    def test_explain_risky_borrower(self):
        """Test explanation for borrower with defaults."""
        service = ExplainableAIService()
        
        features = {
            "completed_loans": 0,
            "on_time_repayments": 1,
            "late_repayments": 3,
            "defaults": 2,
            "total_borrowed": 20000.0,
            "total_repaid": 10000.0,
            "repayment_ratio": 0.5,
            "average_delay_days": 20.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=350,
            risk_category="HIGH",
            decision="rejected",
            language="en",
        )
        
        assert result["decision"] == "rejected"
        assert result["credit_score"] == 350
        assert result["risk_category"] == "HIGH"
        
        # Should have negative factors
        negative_factors = [f for f in result["top_factors"] if f["impact"] == "negative"]
        assert len(negative_factors) > 0
        
        # Should have recommendations
        assert len(result["recommendations"]) > 0
    
    def test_explain_new_borrower(self):
        """Test explanation for new borrower with no history."""
        service = ExplainableAIService()
        
        features = {
            "completed_loans": 0,
            "on_time_repayments": 0,
            "late_repayments": 0,
            "defaults": 0,
            "total_borrowed": 0.0,
            "total_repaid": 0.0,
            "repayment_ratio": 1.0,
            "average_delay_days": 0.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=500,
            risk_category="MEDIUM",
            decision="approved",
            language="en",
        )
        
        assert result["decision"] == "approved"
        assert result["credit_score"] == 500
        assert result["explanation_type"] == "rule_based"


class TestMultilingualExplanations:
    """Test multilingual explanation support."""
    
    def test_explain_hindi(self):
        """Test Hindi explanations."""
        service = ExplainableAIService()
        
        features = {
            "completed_loans": 3,
            "on_time_repayments": 6,
            "late_repayments": 1,
            "defaults": 0,
            "total_borrowed": 30000.0,
            "total_repaid": 28000.0,
            "repayment_ratio": 0.93,
            "average_delay_days": 3.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=650,
            risk_category="MEDIUM",
            decision="approved",
            language="hi",
        )
        
        # Explanation should contain Hindi text
        explanation = result["explanation"]
        assert any(char in explanation for char in "अआइईउऋएओकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह")
    
    def test_explain_telugu(self):
        """Test Telugu explanations."""
        service = ExplainableAIService()
        
        features = {
            "completed_loans": 2,
            "on_time_repayments": 4,
            "late_repayments": 0,
            "defaults": 0,
            "total_borrowed": 15000.0,
            "total_repaid": 15000.0,
            "repayment_ratio": 1.0,
            "average_delay_days": 0.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=700,
            risk_category="LOW",
            decision="approved",
            language="te",
        )
        
        # Should have Telugu characters
        explanation = result["explanation"]
        assert any(char in explanation for char in "అఆఇఈఉఊఋౠఎఏఐఒఓఔకఖగఘఙచఛజఝఞటఠడఢణతథదధనపఫబభమయరలవశషసహళ")
    
    def test_explain_tamil(self):
        """Test Tamil explanations."""
        service = ExplainableAIService()
        
        features = {
            "completed_loans": 1,
            "on_time_repayments": 2,
            "late_repayments": 0,
            "defaults": 0,
            "total_borrowed": 10000.0,
            "total_repaid": 10000.0,
            "repayment_ratio": 1.0,
            "average_delay_days": 0.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=600,
            risk_category="MEDIUM",
            decision="approved",
            language="ta",
        )
        
        # Should have Tamil characters
        explanation = result["explanation"]
        assert any(char in explanation for char in "அஆஇஈஉஊஎஏஐஒஓஔகஙசஞடணதநபமயரலவழளறன")


class TestRecommendations:
    """Test recommendation generation."""
    
    def test_recommendations_for_defaults(self):
        """Test recommendations when borrower has defaults."""
        service = ExplainableAIService()
        
        features = {
            "defaults": 1,
            "late_repayments": 2,
            "on_time_repayments": 3,
            "completed_loans": 2,
            "total_borrowed": 20000.0,
            "total_repaid": 15000.0,
            "repayment_ratio": 0.75,
            "average_delay_days": 10.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=450,
            risk_category="HIGH",
            decision="rejected",
            language="en",
        )
        
        recommendations = result["recommendations"]
        assert len(recommendations) > 0
        # Should recommend avoiding defaults
        rec_text = " ".join(recommendations).lower()
        assert "default" in rec_text or "timely" in rec_text or "payment" in rec_text
    
    def test_recommendations_for_late_payments(self):
        """Test recommendations for late payments."""
        service = ExplainableAIService()
        
        features = {
            "defaults": 0,
            "late_repayments": 3,
            "on_time_repayments": 2,
            "completed_loans": 1,
            "total_borrowed": 10000.0,
            "total_repaid": 9000.0,
            "repayment_ratio": 0.9,
            "average_delay_days": 8.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=550,
            risk_category="MEDIUM",
            decision="approved",
            language="en",
        )
        
        recommendations = result["recommendations"]
        assert len(recommendations) > 0
    
    def test_recommendations_good_borrower(self):
        """Test recommendations for good borrower (positive reinforcement)."""
        service = ExplainableAIService()
        
        features = {
            "defaults": 0,
            "late_repayments": 0,
            "on_time_repayments": 10,
            "completed_loans": 5,
            "total_borrowed": 50000.0,
            "total_repaid": 50000.0,
            "repayment_ratio": 1.0,
            "average_delay_days": 0.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=800,
            risk_category="LOW",
            decision="approved",
            language="en",
        )
        
        recommendations = result["recommendations"]
        # Should still have at least one recommendation (positive reinforcement)
        assert len(recommendations) > 0


class TestCreditScoreExplanation:
    """Test credit score explanation for borrower."""
    
    def test_explain_borrower_score(self):
        """Test explaining current credit score."""
        service = ExplainableAIService()
        
        borrower = {
            "credit_score": 680,
            "borrowing_limit": 10000,
            "risk_category": "MEDIUM",
            "stats": {
                "completed_loans": 3,
                "on_time_repayments": 6,
                "late_repayments": 1,
                "defaults": 0,
                "total_borrowed": 25000.0,
                "total_repaid": 24000.0,
                "average_delay_days": 2.0,
            },
        }
        
        result = service.explain_credit_score(borrower, "en")
        
        assert result["credit_score"] == 680
        assert result["borrowing_limit"] == 10000
        assert len(result["top_factors"]) > 0
        assert result["explanation"] != ""


class TestFactorImportance:
    """Test feature importance ranking."""
    
    def test_defaults_most_important(self):
        """Test that defaults are ranked as most important negative factor."""
        service = ExplainableAIService()
        
        features = {
            "defaults": 1,
            "late_repayments": 1,
            "on_time_repayments": 2,
            "completed_loans": 1,
            "total_borrowed": 10000.0,
            "total_repaid": 8000.0,
            "repayment_ratio": 0.8,
            "average_delay_days": 5.0,
        }
        
        result = service.explain_credit_decision(
            features=features,
            credit_score=400,
            risk_category="HIGH",
            decision="rejected",
            language="en",
        )
        
        # Defaults should be in top factors
        top_feature_names = [f["feature"] for f in result["top_factors"]]
        assert "defaults" in top_feature_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
