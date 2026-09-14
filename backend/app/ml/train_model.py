"""Train and persist the scikit-learn borrower risk classifier (req #7B).

Run:
    python -m app.ml.train_model
This will (re)generate the synthetic dataset if missing, train a
RandomForestClassifier, print evaluation metrics, and save:
  - app/ml/artifacts/risk_model.joblib
  - app/ml/artifacts/metrics.json
"""
import json
import os

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split

from app.ml.feature_engineering import FEATURE_COLUMNS
from app.ml.generate_synthetic_data import generate

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
DATASET_PATH = os.path.join(ARTIFACT_DIR, "dataset.csv")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "risk_model.joblib")
METRICS_PATH = os.path.join(ARTIFACT_DIR, "metrics.json")

RANDOM_SEED = 42


def load_or_create_dataset() -> pd.DataFrame:
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    if os.path.exists(DATASET_PATH):
        return pd.read_csv(DATASET_PATH)
    df = generate(n=2000, seed=RANDOM_SEED)
    df.to_csv(DATASET_PATH, index=False)
    return df


def train() -> dict:
    df = load_or_create_dataset()
    X = df[FEATURE_COLUMNS]
    y = df["risk_category"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=RANDOM_SEED,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True)
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "f1_macro": f1_score(y_test, y_pred, average="macro"),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "classification_report": report,
        "feature_importances": dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist())),
    }

    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS}, MODEL_PATH)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Model saved to {MODEL_PATH}")
    print(f"Accuracy: {metrics['accuracy']:.3f}  F1-macro: {metrics['f1_macro']:.3f}")
    return metrics


if __name__ == "__main__":
    train()
