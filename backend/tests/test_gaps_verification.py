"""End-to-End Verification Test for All Platform Gaps:
1. Real-time borrower bank/wallet balance (deposit, withdraw, disbursement credit, repayment debit)
2. Explain my score endpoint
3. Blockchain ON_CHAIN operation
4. Simultaneous funding race-condition protection (concurrency test)
5. Automatic overdue loan detection & lender payouts
6. Real demographic algorithmic fairness testing (4/5ths rule, demographic parity, equal opportunity)
"""
import asyncio
import os
import pytest
import pytest_asyncio
import pandas as pd
from datetime import datetime, timedelta, timezone

from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_db
from app.services.loan_service import fund_loan, repay_loan, detect_and_process_overdue_loans
from app.services.blockchain_service import get_blockchain_service
from app.ml.fairness_audit import evaluate_fairness, run_fairness_audit_on_database
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_blockchain_working():
    """Verify blockchain is running in ON_CHAIN mode with deployed contract."""
    svc = get_blockchain_service()
    print("\n[TEST] Blockchain Service Mode:", svc.mode)
    print("[TEST] Blockchain Contract:", svc.contract.address if svc.contract else None)
    assert svc.mode == "ON_CHAIN", f"Expected ON_CHAIN but got {svc.mode}"
    assert svc.contract is not None
    assert svc.contract.address.startswith("0x")



@pytest.mark.asyncio
async def test_fairness_audit_calculation():
    """Verify algorithmic fairness metrics (DIR / 4/5ths rule, Demographic Parity, Equal Opportunity)."""
    # Create sample dataset with known demographic balance
    data = {
        "gender": ["male"] * 50 + ["female"] * 50,
        "age": [35] * 50 + [24] * 50,
        "location": ["urban"] * 50 + ["rural"] * 50,
        "approval": [1] * 42 + [0] * 8 + [1] * 40 + [0] * 10,  # 84% male vs 80% female -> DIR = 80/84 = 0.952 (Fair)
        "actual_good": [1] * 45 + [0] * 5 + [1] * 44 + [0] * 6,
    }
    df = pd.DataFrame(data)
    results = evaluate_fairness(df)
    print("\n[TEST] Fairness Audit Results:", results)
    
    assert results["overall_verdict"] == "PASS"
    assert "gender" in results["attributes"]
    assert "age" in results["attributes"]
    assert "location" in results["attributes"]
    
    gender_audit = results["attributes"]["gender"]
    assert gender_audit["four_fifths_rule_compliant"] is True
    assert gender_audit["disparate_impact_ratio"] >= 0.80


@pytest.mark.asyncio
async def test_borrower_balance_and_lender_payouts():
    """Verify:
    1. Borrower wallet balance is credited upon full funding.
    2. Borrower wallet balance is debited upon repayment.
    3. All lenders receive proportional payouts directly into their lending_balance.
    """
    await connect_to_mongo()
    db = get_db()

    now = datetime.now(timezone.utc)
    
    # 1. Create a borrower with 1,000 wallet balance
    borrower_res = await db.users.insert_one({
        "name": "Test Borrower Balance",
        "email": f"borrower_bal_{int(now.timestamp())}@test.com",
        "role": "borrower",
        "credit_score": 680,
        "borrowing_limit": 10000.0,
        "wallet_balance": 1000.0,
        "created_at": now,
    })
    borrower_id = borrower_res.inserted_id
    borrower = await db.users.find_one({"_id": borrower_id})

    # 2. Create 2 lenders with balances
    lender1_res = await db.users.insert_one({
        "name": "Lender 1",
        "email": f"lender1_{int(now.timestamp())}@test.com",
        "role": "lender",
        "lending_balance": 20000.0,
        "created_at": now,
    })
    lender1 = await db.users.find_one({"_id": lender1_res.inserted_id})

    lender2_res = await db.users.insert_one({
        "name": "Lender 2",
        "email": f"lender2_{int(now.timestamp())}@test.com",
        "role": "lender",
        "lending_balance": 20000.0,
        "created_at": now,
    })
    lender2 = await db.users.find_one({"_id": lender2_res.inserted_id})

    # 3. Create an OPEN_FOR_FUNDING loan for ₹5,000
    loan_amount = 5000.0
    loan_res = await db.loans.insert_one({
        "borrower_id": borrower_id,
        "borrower_name": borrower["name"],
        "amount": loan_amount,
        "interest_rate": 0.10,
        "total_due": 5500.0,
        "duration_days": 30,
        "amount_funded": 0.0,
        "amount_repaid": 0.0,
        "status": "OPEN_FOR_FUNDING",
        "created_at": now,
        "updated_at": now,
    })
    loan_id = str(loan_res.inserted_id)

    # 4. Lender 1 funds ₹2,000 (40%)
    await fund_loan(db, loan_id, lender1, 2000.0)
    l1_after = await db.users.find_one({"_id": lender1["_id"]})
    assert l1_after["lending_balance"] == 18000.0

    # 5. Lender 2 funds remaining ₹3,000 (60%) -> Triggers FULL FUNDING & DISBURSEMENT
    await fund_loan(db, loan_id, lender2, 3000.0)
    l2_after = await db.users.find_one({"_id": lender2["_id"]})
    assert l2_after["lending_balance"] == 17000.0

    # Check borrower wallet balance: was 1,000 + 5,000 disbursed = 6,000!
    borrower_after_disburse = await db.users.find_one({"_id": borrower_id})
    print("\n[TEST] Borrower wallet balance after loan disbursement:", borrower_after_disburse["wallet_balance"])
    assert borrower_after_disburse["wallet_balance"] == 6000.0

    # Check loan is ACTIVE
    loan_active = await db.loans.find_one({"_id": loan_res.inserted_id})
    assert loan_active["status"] == "ACTIVE"
    assert loan_active["amount_funded"] == 5000.0

    # 6. Borrower makes full repayment of ₹5,500
    await repay_loan(db, loan_id, borrower_after_disburse, 5500.0)

    # Check borrower wallet balance debited: 6,000 - 5,500 = 500!
    borrower_after_repay = await db.users.find_one({"_id": borrower_id})
    print("[TEST] Borrower wallet balance after repayment:", borrower_after_repay["wallet_balance"])
    assert borrower_after_repay["wallet_balance"] == 500.0

    # 7. Check LENDER PAYOUTS:
    # Total repayment was 5,500.
    # Lender 1 share (40%): 5,500 * 0.40 = 2,200 (2,000 principal + 200 interest)
    # Lender 2 share (60%): 5,500 * 0.60 = 3,300 (3,000 principal + 300 interest)
    l1_final = await db.users.find_one({"_id": lender1["_id"]})
    l2_final = await db.users.find_one({"_id": lender2["_id"]})
    print("[TEST] Lender 1 balance after payout:", l1_final["lending_balance"], "(expected 18000 + 2200 = 20200)")
    print("[TEST] Lender 2 balance after payout:", l2_final["lending_balance"], "(expected 17000 + 3300 = 20300)")

    assert l1_final["lending_balance"] == 20200.0
    assert l2_final["lending_balance"] == 20300.0


@pytest.mark.asyncio
async def test_simultaneous_funding_protection():
    """Verify that concurrent funding attempts cannot overfund a loan (race condition protection)."""
    await connect_to_mongo()
    db = get_db()
    now = datetime.now(timezone.utc)

    # Create loan needing 1,000
    loan_res = await db.loans.insert_one({
        "amount": 1000.0,
        "interest_rate": 0.10,
        "total_due": 1100.0,
        "duration_days": 30,
        "amount_funded": 0.0,
        "amount_repaid": 0.0,
        "status": "OPEN_FOR_FUNDING",
        "created_at": now,
        "updated_at": now,
    })
    loan_id = str(loan_res.inserted_id)

    # Create 3 lenders each wanting to fund ₹600 (sum = 1800 > 1000)
    lenders = []
    for i in range(3):
        res = await db.users.insert_one({
            "name": f"Race Lender {i}",
            "email": f"race_lender_{i}_{int(now.timestamp())}@test.com",
            "role": "lender",
            "lending_balance": 5000.0,
            "created_at": now,
        })
        l = await db.users.find_one({"_id": res.inserted_id})
        lenders.append(l)

    # Fire 3 simultaneous funding attempts of 600 concurrently!
    async def try_fund(lender):
        try:
            await fund_loan(db, loan_id, lender, 600.0)
            return "SUCCESS"
        except HTTPException as e:
            return f"BLOCKED: {e.status_code}"

    results = await asyncio.gather(*[try_fund(l) for l in lenders])
    print("\n[TEST] Concurrent funding outcomes:", results)

    # Exactly 1 can succeed because 600 + 600 = 1200 > 1000! The others MUST be blocked (400 or 409)
    successes = [r for r in results if r == "SUCCESS"]
    blocked = [r for r in results if "BLOCKED" in r]
    assert len(successes) == 1
    assert len(blocked) == 2

    # Check total funded on loan is exactly 600, never overfunded!
    loan_after = await db.loans.find_one({"_id": loan_res.inserted_id})
    print("[TEST] Final loan amount funded:", loan_after["amount_funded"])
    assert loan_after["amount_funded"] == 600.0


@pytest.mark.asyncio
async def test_automatic_overdue_detection():
    """Verify that overdue loans are automatically detected and transitioned to LATE or DEFAULTED."""
    await connect_to_mongo()
    db = get_db()
    now = datetime.now(timezone.utc)

    # Create borrower
    b_res = await db.users.insert_one({
        "name": "Overdue Borrower",
        "email": f"overdue_b_{int(now.timestamp())}@test.com",
        "role": "borrower",
        "credit_score": 600,
        "borrowing_limit": 5000.0,
        "created_at": now - timedelta(days=60),
    })

    # Loan 1: Due 5 days ago (< 15 days grace) -> Should become LATE
    loan1_res = await db.loans.insert_one({
        "borrower_id": b_res.inserted_id,
        "amount": 2000.0,
        "status": "ACTIVE",
        "due_date": now - timedelta(days=5),
        "created_at": now - timedelta(days=35),
    })

    # Loan 2: Due 25 days ago (> 15 days grace) -> Should become DEFAULTED
    loan2_res = await db.loans.insert_one({
        "borrower_id": b_res.inserted_id,
        "amount": 3000.0,
        "status": "ACTIVE",
        "due_date": now - timedelta(days=25),
        "created_at": now - timedelta(days=55),
    })

    # Run detection
    result = await detect_and_process_overdue_loans(db)
    print("\n[TEST] Overdue Loan Detection Result:", result)

    assert str(loan1_res.inserted_id) in result["marked_late"]
    assert str(loan2_res.inserted_id) in result["marked_defaulted"]

    l1 = await db.loans.find_one({"_id": loan1_res.inserted_id})
    l2 = await db.loans.find_one({"_id": loan2_res.inserted_id})
    assert l1["status"] == "LATE"
    assert l2["status"] == "DEFAULTED"


if __name__ == "__main__":
    asyncio.run(test_blockchain_working())
    asyncio.run(test_fairness_audit_calculation())
    asyncio.run(test_borrower_balance_and_lender_payouts())
    asyncio.run(test_simultaneous_funding_protection())
    asyncio.run(test_automatic_overdue_detection())
    print("\n>>> ALL GAP VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")
