"""Reproducible seed script (req #12).

Usage:
    python scripts/seed_db.py --borrowers 50 --lenders 20 --loans 100 --seed 42
    python scripts/seed_db.py --reset          # wipes all collections first
"""
import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faker import Faker
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings, CREDIT_SCORE_CONFIG
from app.core.security import hash_password
from app.services.credit_engine import borrowing_limit_for_score

PROFILES = {
    "excellent": {"score_range": (740, 830), "on_time_rate": 0.97},
    "good": {"score_range": (650, 739), "on_time_rate": 0.88},
    "average": {"score_range": (550, 649), "on_time_rate": 0.72},
    "late_payer": {"score_range": (450, 549), "on_time_rate": 0.45},
    "high_risk": {"score_range": (350, 449), "on_time_rate": 0.30},
    "defaulting": {"score_range": (300, 380), "on_time_rate": 0.15},
    "new_borrower": {"score_range": (500, 500), "on_time_rate": 0.6},
}
PROFILE_NAMES = list(PROFILES.keys())


async def reset_database(db):
    collections = [
        "users", "loans", "loan_fundings", "repayments",
        "credit_scores", "transactions", "voice_sessions", "audit_logs",
    ]
    for c in collections:
        await db[c].delete_many({})
    print("Database reset: all collections cleared.")


async def seed_users(db, fake: Faker, rng: random.Random, n_borrowers: int, n_lenders: int):
    borrowers = []
    for i in range(n_borrowers):
        profile = PROFILE_NAMES[i % len(PROFILE_NAMES)]
        cfg = PROFILES[profile]
        score = rng.randint(*cfg["score_range"])
        doc = {
            "name": fake.name(),
            "email": f"borrower{i+1}@demo.finlend.test",
            "phone": fake.msisdn()[:10],
            "password_hash": hash_password("Password123!"),
            "role": "borrower",
            "credit_score": score,
            "borrowing_limit": borrowing_limit_for_score(score),
            "lending_balance": None,
            "profile_archetype": profile,
            "stats": {
                "completed_loans": 0, "on_time_repayments": 0, "late_repayments": 0,
                "defaults": 0, "average_delay_days": 0.0, "total_borrowed": 0.0,
                "total_repaid": 0.0, "avg_loan_duration": 30,
            },
            "created_at": datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 400)),
        }
        result = await db.users.insert_one(doc)
        doc["_id"] = result.inserted_id
        borrowers.append(doc)

    lenders = []
    for i in range(n_lenders):
        doc = {
            "name": fake.name(),
            "email": f"lender{i+1}@demo.finlend.test",
            "phone": fake.msisdn()[:10],
            "password_hash": hash_password("Password123!"),
            "role": "lender",
            "credit_score": None,
            "borrowing_limit": None,
            "lending_balance": round(rng.uniform(10000, 100000), 2),
            "stats": {},
            "created_at": datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 400)),
        }
        result = await db.users.insert_one(doc)
        doc["_id"] = result.inserted_id
        lenders.append(doc)

    admin_doc = {
        "name": "System Admin",
        "email": "admin@demo.finlend.test",
        "phone": None,
        "password_hash": hash_password("AdminPass123!"),
        "role": "admin",
        "credit_score": None,
        "borrowing_limit": None,
        "lending_balance": None,
        "stats": {},
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(admin_doc)

    return borrowers, lenders


async def seed_historical_loans(db, rng: random.Random, borrowers: list, lenders: list, n_loans: int):
    """Create ~n_loans historical (completed/repaid/defaulted) loans with
    fundings + repayments, so admin analytics and the ML dataset story have
    real, queryable backing data (not just live-created loans)."""
    statuses_terminal = ["REPAID", "REPAID", "REPAID", "DEFAULTED"]  # weighted
    repayment_count = 0

    for i in range(n_loans):
        borrower = rng.choice(borrowers)
        amount = round(rng.uniform(1000, 20000), 2)
        interest = 0.10
        total_due = round(amount * (1 + interest), 2)
        created_at = datetime.now(timezone.utc) - timedelta(days=rng.randint(10, 300))
        due_date = created_at + timedelta(days=30)

        cfg = PROFILES[borrower.get("profile_archetype", "average")]
        on_time = rng.random() < cfg["on_time_rate"]
        is_default = rng.random() < (0.25 if not on_time else 0.02)
        final_status = "DEFAULTED" if is_default else "REPAID"

        loan_doc = {
            "borrower_id": borrower["_id"],
            "borrower_name": borrower["name"],
            "amount": amount,
            "duration_days": 30,
            "interest_rate": interest,
            "total_due": total_due,
            "amount_funded": amount,
            "amount_repaid": 0 if is_default else total_due,
            "status": final_status,
            "risk_category": "HIGH" if is_default else ("LOW" if on_time else "MEDIUM"),
            "purpose": "seeded historical loan",
            "source": "seed",
            "due_date": due_date,
            "created_at": created_at,
            "updated_at": created_at + timedelta(days=30),
        }
        loan_result = await db.loans.insert_one(loan_doc)
        loan_id = loan_result.inserted_id

        # funding split across 1-3 random lenders
        remaining = amount
        chosen_lenders = rng.sample(lenders, k=min(len(lenders), rng.randint(1, 3)))
        for idx, lender in enumerate(chosen_lenders):
            if idx == len(chosen_lenders) - 1:
                contribution = round(remaining, 2)
            else:
                contribution = round(remaining * rng.uniform(0.3, 0.6), 2)
            remaining -= contribution
            if contribution <= 0:
                continue
            await db.loan_fundings.insert_one({
                "loan_id": loan_id,
                "lender_id": lender["_id"],
                "amount": contribution,
                "expected_return": round(contribution * (1 + interest), 2),
                "tx_hash": f"SIMULATED-SEED-FUND-{loan_id}-{idx}",
                "chain_mode": "LOCAL_SIMULATION",
                "created_at": created_at,
            })

        if not is_default:
            days_late = 0 if on_time else rng.randint(1, 14)
            repay_time = due_date + timedelta(days=days_late)
            await db.repayments.insert_one({
                "loan_id": loan_id,
                "borrower_id": borrower["_id"],
                "amount": total_due,
                "is_on_time": on_time,
                "is_early": False,
                "days_late": days_late,
                "tx_hash": f"SIMULATED-SEED-REPAY-{loan_id}",
                "chain_mode": "LOCAL_SIMULATION",
                "created_at": repay_time,
            })
            repayment_count += 1

            stats = borrower.setdefault("stats", {})
            stats["completed_loans"] = stats.get("completed_loans", 0) + 1
            stats["total_borrowed"] = stats.get("total_borrowed", 0.0) + amount
            stats["total_repaid"] = stats.get("total_repaid", 0.0) + total_due
            if on_time:
                stats["on_time_repayments"] = stats.get("on_time_repayments", 0) + 1
            else:
                stats["late_repayments"] = stats.get("late_repayments", 0) + 1
        else:
            stats = borrower.setdefault("stats", {})
            stats["defaults"] = stats.get("defaults", 0) + 1
            stats["total_borrowed"] = stats.get("total_borrowed", 0.0) + amount

    # persist accumulated stats back to users
    for b in borrowers:
        await db.users.update_one({"_id": b["_id"]}, {"$set": {"stats": b.get("stats", {})}})

    print(f"Seeded {n_loans} historical loans, ~{repayment_count} repayment records.")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--borrowers", type=int, default=50)
    parser.add_argument("--lenders", type=int, default=20)
    parser.add_argument("--loans", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    Faker.seed(args.seed)
    fake = Faker()
    rng = random.Random(args.seed)

    if args.reset:
        await reset_database(db)

    borrowers, lenders = await seed_users(db, fake, rng, args.borrowers, args.lenders)
    await seed_historical_loans(db, rng, borrowers, lenders, args.loans)

    print("Seeding complete.")
    print(f"  Borrowers: {len(borrowers)}  (password: Password123!)")
    print(f"  Lenders:   {len(lenders)}  (password: Password123!)")
    print("  Admin:     admin@demo.finlend.test / AdminPass123!")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
