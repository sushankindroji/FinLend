"""Generate a reproducible synthetic dataset of borrower repayment histories
used to train the scikit-learn risk classifier (req #7B).

Run:
    python -m app.ml.generate_synthetic_data --n 2000 --seed 42 --out app/ml/artifacts/dataset.csv
"""
import argparse
import os

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "completed_loans",
    "on_time_repayments",
    "late_repayments",
    "defaults",
    "average_delay_days",
    "total_borrowed",
    "total_repaid",
    "repayment_ratio",
    "loan_duration",
    "previous_credit_score",
]

RISK_LABELS = ["LOW", "MEDIUM", "HIGH"]

# Borrower archetypes mirror the seed script profiles (req #12) so the ML
# model and the seeded demo data are consistent with each other.
ARCHETYPES = {
    "excellent": dict(on_time_p=0.97, default_p=0.005, delay_mean=0.5, n_loans_range=(6, 20)),
    "good": dict(on_time_p=0.88, default_p=0.02, delay_mean=1.5, n_loans_range=(4, 15)),
    "average": dict(on_time_p=0.72, default_p=0.05, delay_mean=4.0, n_loans_range=(2, 10)),
    "late_payer": dict(on_time_p=0.45, default_p=0.08, delay_mean=9.0, n_loans_range=(2, 10)),
    "high_risk": dict(on_time_p=0.30, default_p=0.20, delay_mean=14.0, n_loans_range=(1, 8)),
    "defaulting": dict(on_time_p=0.15, default_p=0.45, delay_mean=20.0, n_loans_range=(1, 6)),
    "new_borrower": dict(on_time_p=0.6, default_p=0.05, delay_mean=3.0, n_loans_range=(0, 1)),
}


def _label_from_archetype(name: str) -> str:
    return {
        "excellent": "LOW",
        "good": "LOW",
        "average": "MEDIUM",
        "late_payer": "MEDIUM",
        "high_risk": "HIGH",
        "defaulting": "HIGH",
        "new_borrower": "MEDIUM",
    }[name]


def generate(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    archetype_names = list(ARCHETYPES.keys())

    for _ in range(n):
        archetype_name = archetype_names[rng.integers(0, len(archetype_names))]
        cfg = ARCHETYPES[archetype_name]

        n_loans = int(rng.integers(cfg["n_loans_range"][0], cfg["n_loans_range"][1] + 1))
        on_time = 0
        late = 0
        defaults = 0
        delays = []
        total_borrowed = 0.0
        total_repaid = 0.0

        for _ in range(n_loans):
            loan_amount = float(rng.integers(1000, 25000))
            total_borrowed += loan_amount
            r = rng.random()
            if r < cfg["default_p"]:
                defaults += 1
                total_repaid += loan_amount * rng.uniform(0, 0.5)
            elif r < cfg["default_p"] + (1 - cfg["on_time_p"]):
                late += 1
                delay = max(1, rng.poisson(cfg["delay_mean"]))
                delays.append(delay)
                total_repaid += loan_amount * 1.10
            else:
                on_time += 1
                total_repaid += loan_amount * 1.10

        completed_loans = on_time + late
        avg_delay = float(np.mean(delays)) if delays else 0.0
        repayment_ratio = (total_repaid / total_borrowed) if total_borrowed > 0 else 1.0
        loan_duration = int(rng.integers(15, 90))
        previous_credit_score = int(
            np.clip(rng.normal(
                {"excellent": 760, "good": 680, "average": 560, "late_payer": 500,
                 "high_risk": 420, "defaulting": 340, "new_borrower": 500}[archetype_name],
                40), 300, 850)
        )

        rows.append({
            "completed_loans": completed_loans,
            "on_time_repayments": on_time,
            "late_repayments": late,
            "defaults": defaults,
            "average_delay_days": round(avg_delay, 2),
            "total_borrowed": round(total_borrowed, 2),
            "total_repaid": round(total_repaid, 2),
            "repayment_ratio": round(repayment_ratio, 4),
            "loan_duration": loan_duration,
            "previous_credit_score": previous_credit_score,
            "risk_category": _label_from_archetype(archetype_name),
            "archetype": archetype_name,
        })

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="app/ml/artifacts/dataset.csv")
    args = parser.parse_args()

    df = generate(args.n, args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out}")


if __name__ == "__main__":
    main()
