"""Train SHAP explainer for model interpretability.

This script trains a SHAP TreeExplainer for the RandomForest risk model,
enabling feature importance analysis and credit decision explanations.

Run after training the main model:
    python -m app.ml.train_model
    python -m app.ml.train_explainer
"""
import os
import sys

import joblib
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.feature_engineering import build_feature_frame


def train_shap_explainer():
    """Train and save SHAP explainer."""
    import shap
    
    print("Training SHAP explainer...")
    
    # Load trained model
    artifact_dir = os.path.join(os.path.dirname(__file__), "artifacts")
    model_path = os.path.join(artifact_dir, "risk_model.joblib")
    
    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        print("Please run 'python -m app.ml.train_model' first")
        return False
    
    print(f"Loading model from {model_path}...")
    bundle = joblib.load(model_path)
    model = bundle["model"]
    
    # Generate sample data for explainer training
    # Use a diverse set of borrower profiles
    sample_profiles = [
        # Good borrower
        {
            "completed_loans": 5,
            "on_time_repayments": 10,
            "late_repayments": 0,
            "defaults": 0,
            "total_borrowed": 50000.0,
            "total_repaid": 50000.0,
            "repayment_ratio": 1.0,
            "average_delay_days": 0.0,
        },
        # Average borrower
        {
            "completed_loans": 2,
            "on_time_repayments": 4,
            "late_repayments": 1,
            "defaults": 0,
            "total_borrowed": 20000.0,
            "total_repaid": 18000.0,
            "repayment_ratio": 0.9,
            "average_delay_days": 5.0,
        },
        # Risky borrower
        {
            "completed_loans": 1,
            "on_time_repayments": 1,
            "late_repayments": 3,
            "defaults": 1,
            "total_borrowed": 10000.0,
            "total_repaid": 6000.0,
            "repayment_ratio": 0.6,
            "average_delay_days": 15.0,
        },
        # New borrower
        {
            "completed_loans": 0,
            "on_time_repayments": 0,
            "late_repayments": 0,
            "defaults": 0,
            "total_borrowed": 0.0,
            "total_repaid": 0.0,
            "repayment_ratio": 1.0,
            "average_delay_days": 0.0,
        },
        # Defaulted borrower
        {
            "completed_loans": 0,
            "on_time_repayments": 2,
            "late_repayments": 5,
            "defaults": 2,
            "total_borrowed": 30000.0,
            "total_repaid": 15000.0,
            "repayment_ratio": 0.5,
            "average_delay_days": 25.0,
        },
    ]
    
    # Build feature frames
    X_samples = []
    for profile in sample_profiles:
        X = build_feature_frame(profile)
        X_samples.append(X)
    
    X_background = pd.concat(X_samples, ignore_index=True)
    
    print(f"Training explainer with {len(X_background)} background samples...")
    
    # Create SHAP explainer
    # TreeExplainer is optimized for tree-based models (RandomForest, XGBoost, etc.)
    explainer = shap.TreeExplainer(model, X_background)
    
    # Save explainer
    explainer_path = os.path.join(artifact_dir, "shap_explainer.joblib")
    joblib.dump(explainer, explainer_path)
    
    print(f"✓ SHAP explainer saved to {explainer_path}")
    
    # Test the explainer
    print("\nTesting explainer...")
    test_profile = sample_profiles[0]  # Good borrower
    X_test = build_feature_frame(test_profile)
    
    shap_values = explainer(X_test)
    
    if hasattr(shap_values, 'values'):
        values = shap_values.values[0]
    else:
        values = shap_values[0]
    
    print("Feature importance for test profile:")
    for feature, value in zip(X_test.columns, values):
        print(f"  {feature:25s}: {value:+.4f}")
    
    print("\n✓ SHAP explainer training complete!")
    return True


if __name__ == "__main__":
    success = train_shap_explainer()
    sys.exit(0 if success else 1)
