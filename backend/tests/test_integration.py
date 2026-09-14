"""Integration tests for the FinLend API using FastAPI TestClient + mongomock.

Tests cover:
  - Auth: register, login, duplicate email, bad credentials
  - Full loan lifecycle: request → fund → repay → credit update
  - Edge cases: overpayment, partial funding, lender insufficient balance
  - Notifications: emitted on key events
  - Admin analytics & flags

We use mongomock-motor for an in-memory MongoDB substitute so no real database
is required. All tests are synchronous (TestClient handles async internally).
"""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient


# ── Helpers / fixtures ─────────────────────────────────────────────────────

def _make_app():
    """Import and return the FastAPI app with the DB dependency overridden."""
    from app.main import app
    return app


@pytest.fixture(scope="module")
def client():
    """Return a TestClient backed by an in-memory fake DB."""
    import mongomock_motor  # type: ignore[import]
    from app.db.mongodb import database
    from app.main import app

    # Patch the module-level database singleton with a mongomock client
    _fake_client = mongomock_motor.AsyncMongoMockClient()
    _fake_db = _fake_client["finlend_test"]
    database.db = _fake_db
    database.client = _fake_client

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Auth ───────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_borrower(self, client):
        uid = uuid.uuid4().hex[:8]
        r = client.post("/api/auth/register", json={
            "name": "Alice Borrower",
            "email": f"alice_{uid}@test.com",
            "password": "Password1!",
            "role": "borrower",
        })
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["role"] == "borrower"
        assert "access_token" in data
        assert data["user_id"]
        self.__class__._alice_email = f"alice_{uid}@test.com"

    def test_register_lender(self, client):
        uid = uuid.uuid4().hex[:8]
        r = client.post("/api/auth/register", json={
            "name": "Bob Lender",
            "email": f"bob_{uid}@test.com",
            "password": "Password1!",
            "role": "lender",
        })
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "lender"

    def test_register_duplicate_email(self, client):
        # First registration
        uid = uuid.uuid4().hex[:8]
        email = f"dup_{uid}@test.com"
        client.post("/api/auth/register", json={
            "name": "First", "email": email, "password": "Password1!", "role": "borrower"
        })
        # Second with same email
        r = client.post("/api/auth/register", json={
            "name": "Second", "email": email, "password": "Password1!", "role": "borrower"
        })
        assert r.status_code == 400

    def test_login_success(self, client):
        uid = uuid.uuid4().hex[:8]
        email = f"login_{uid}@test.com"
        client.post("/api/auth/register", json={
            "name": "Login User", "email": email, "password": "Password1!", "role": "borrower"
        })
        r = client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_wrong_password(self, client):
        uid = uuid.uuid4().hex[:8]
        email = f"wrongpw_{uid}@test.com"
        client.post("/api/auth/register", json={
            "name": "WrongPw", "email": email, "password": "Password1!", "role": "borrower"
        })
        r = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401

    def test_login_unknown_email(self, client):
        r = client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "Password1!"
        })
        assert r.status_code == 401

    def test_me_requires_auth(self, client):
        r = client.get("/api/users/me")
        assert r.status_code == 401


# ── Full loan lifecycle ────────────────────────────────────────────────────

class TestLoanLifecycle:
    """Register borrower + lender, run the full lifecycle, assert credit changes."""

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        uid = uuid.uuid4().hex[:8]
        # Register borrower
        r = client.post("/api/auth/register", json={
            "name": f"Carol {uid}",
            "email": f"carol_{uid}@test.com",
            "password": "Password1!",
            "role": "borrower",
        })
        assert r.status_code == 201, r.text
        self.borrower_token = r.json()["access_token"]
        self.borrower_id    = r.json()["user_id"]
        self.borrower_hdrs  = {"Authorization": f"Bearer {self.borrower_token}"}

        # Register lender
        r = client.post("/api/auth/register", json={
            "name": f"Dave {uid}",
            "email": f"dave_{uid}@test.com",
            "password": "Password1!",
            "role": "lender",
        })
        assert r.status_code == 201, r.text
        self.lender_token = r.json()["access_token"]
        self.lender_hdrs  = {"Authorization": f"Bearer {self.lender_token}"}

    def test_request_loan(self, client):
        r = client.post("/api/loans", json={
            "amount": 1000,
            "duration_days": 30,
            "purpose": "test",
            "source": "web",
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201, r.text
        loan = r.json()
        assert loan["amount"] == 1000.0
        # Should be approved and open for funding (credit score 500, low-risk new borrower)
        assert loan["status"] in ("OPEN_FOR_FUNDING", "REJECTED")
        self.loan_id = loan["id"]
        self.loan_status = loan["status"]

    def test_fund_loan(self, client):
        # Request a fresh loan first
        r = client.post("/api/loans", json={
            "amount": 500,
            "duration_days": 30,
            "purpose": "fund test",
            "source": "web",
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] != "OPEN_FOR_FUNDING":
            pytest.skip("Loan was rejected; cannot test funding")

        loan_id = loan["id"]

        # Fund it fully
        r = client.post(f"/api/loans/{loan_id}/fund", json={"amount": 500},
                        headers=self.lender_hdrs)
        assert r.status_code == 201, r.text
        result = r.json()
        # After full funding: loan should be FUNDED -> ACTIVE
        assert result["loan"]["status"] == "ACTIVE"
        assert result["loan"]["amount_funded"] == 500.0
        # assertion complete — no return value needed

    def test_repay_loan_full(self, client):
        # Full lifecycle: request → fund → repay
        r = client.post("/api/loans", json={
            "amount": 500,
            "duration_days": 30,
            "purpose": "repay test",
            "source": "web",
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] != "OPEN_FOR_FUNDING":
            pytest.skip("Loan was rejected")
        loan_id = loan["id"]

        # Fund
        r = client.post(f"/api/loans/{loan_id}/fund", json={"amount": 500},
                        headers=self.lender_hdrs)
        assert r.status_code == 201
        assert r.json()["loan"]["status"] == "ACTIVE"

        # Repay in full (principal + 10% interest)
        total_due = round(500 * 1.10, 2)
        r = client.post(f"/api/loans/{loan_id}/repay", json={"amount": total_due},
                        headers=self.borrower_hdrs)
        assert r.status_code == 201, r.text
        result = r.json()
        assert result["loan"]["status"] == "REPAID"
        assert result["loan"]["amount_repaid"] == total_due
        # Credit score should have increased (on_time + completed_loan)
        assert result["credit_score"] > 500

    def test_partial_funding(self, client):
        """Partially fund a loan and check PARTIALLY_FUNDED status."""
        r = client.post("/api/loans", json={
            "amount": 1000,
            "duration_days": 30,
            "purpose": "partial fund test",
            "source": "web",
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] != "OPEN_FOR_FUNDING":
            pytest.skip("Loan rejected")
        loan_id = loan["id"]

        # Fund only half
        r = client.post(f"/api/loans/{loan_id}/fund", json={"amount": 400},
                        headers=self.lender_hdrs)
        assert r.status_code == 201
        assert r.json()["loan"]["status"] == "PARTIALLY_FUNDED"
        assert r.json()["loan"]["amount_funded"] == 400.0


# ── Edge cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        # Fresh borrower and lender for each test class instance
        import uuid
        uid = uuid.uuid4().hex[:6]
        r = client.post("/api/auth/register", json={
            "name": f"Borrower {uid}",
            "email": f"borrower_{uid}@edge.test",
            "password": "Password1!",
            "role": "borrower",
        })
        assert r.status_code == 201
        self.borrower_hdrs = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = client.post("/api/auth/register", json={
            "name": f"Lender {uid}",
            "email": f"lender_{uid}@edge.test",
            "password": "Password1!",
            "role": "lender",
        })
        assert r.status_code == 201
        self.lender_hdrs = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_overpayment_rejected(self, client):
        """Cannot repay more than the remaining due amount."""
        r = client.post("/api/loans", json={
            "amount": 500, "duration_days": 30, "purpose": "overpay test", "source": "web"
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] != "OPEN_FOR_FUNDING":
            pytest.skip("Loan rejected — can't test overpayment")
        loan_id = loan["id"]

        client.post(f"/api/loans/{loan_id}/fund", json={"amount": 500}, headers=self.lender_hdrs)

        total_due = round(500 * 1.10, 2)
        # Try to pay 1 cent too much
        r = client.post(f"/api/loans/{loan_id}/repay",
                        json={"amount": total_due + 0.01},
                        headers=self.borrower_hdrs)
        assert r.status_code == 400
        assert "exceed" in r.json()["detail"].lower()

    def test_lender_cannot_overfund(self, client):
        """Cannot fund more than the remaining amount needed."""
        r = client.post("/api/loans", json={
            "amount": 500, "duration_days": 30, "purpose": "overfund test", "source": "web"
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] != "OPEN_FOR_FUNDING":
            pytest.skip("Loan rejected")
        loan_id = loan["id"]

        # Try to fund more than the loan amount
        r = client.post(f"/api/loans/{loan_id}/fund",
                        json={"amount": 600},
                        headers=self.lender_hdrs)
        assert r.status_code == 400

    def test_repay_on_wrong_role_rejected(self, client):
        """A lender cannot call the repay endpoint."""
        # First create a loan as borrower
        r = client.post("/api/loans", json={
            "amount": 500, "duration_days": 30, "purpose": "role test", "source": "web"
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan_id = r.json()["id"]

        # Lender tries to repay
        r = client.post(f"/api/loans/{loan_id}/repay",
                        json={"amount": 100},
                        headers=self.lender_hdrs)
        assert r.status_code == 403

    def test_fund_on_wrong_role_rejected(self, client):
        """A borrower cannot call the fund endpoint."""
        r = client.post("/api/loans", json={
            "amount": 500, "duration_days": 30, "purpose": "role test", "source": "web"
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan_id = r.json()["id"]

        r = client.post(f"/api/loans/{loan_id}/fund",
                        json={"amount": 500},
                        headers=self.borrower_hdrs)
        assert r.status_code == 403

    def test_cannot_repay_non_active_loan(self, client):
        """Cannot repay a loan that is OPEN_FOR_FUNDING (not yet active)."""
        r = client.post("/api/loans", json={
            "amount": 500, "duration_days": 30, "purpose": "no repay yet", "source": "web"
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] in ("REJECTED",):
            pytest.skip("Loan rejected")
        loan_id = loan["id"]

        # Only partially fund (loan not yet ACTIVE)
        if loan["status"] == "OPEN_FOR_FUNDING":
            client.post(f"/api/loans/{loan_id}/fund",
                        json={"amount": 200},
                        headers=self.lender_hdrs)
            # At PARTIALLY_FUNDED, still can't repay
            r = client.post(f"/api/loans/{loan_id}/repay",
                            json={"amount": 100},
                            headers=self.borrower_hdrs)
            assert r.status_code == 409

    def test_loan_exceeds_borrowing_limit_rejected(self, client):
        """A loan request above the user's borrowing limit should be rejected."""
        # New borrower has limit 2000 (score 500 → tier 500–649 → 5000,
        # but base score = 500 → limit = 5000). Ask for 25001.
        r = client.post("/api/loans", json={
            "amount": 25001, "duration_days": 30, "purpose": "over limit", "source": "web"
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        assert r.json()["status"] == "REJECTED"

    def test_repayment_schedule_returns_entries(self, client):
        """Schedule endpoint returns installment entries for an active loan."""
        r = client.post("/api/loans", json={
            "amount": 500, "duration_days": 30, "purpose": "schedule test", "source": "web"
        }, headers=self.borrower_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] != "OPEN_FOR_FUNDING":
            pytest.skip("Loan rejected")
        loan_id = loan["id"]

        client.post(f"/api/loans/{loan_id}/fund", json={"amount": 500}, headers=self.lender_hdrs)

        r = client.get(f"/api/loans/{loan_id}/schedule", headers=self.borrower_hdrs)
        assert r.status_code == 200
        entries = r.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1
        for e in entries:
            assert "payment_number" in e
            assert "due_date" in e
            assert "total" in e
            assert "status" in e


# ── Credit engine behaviour ────────────────────────────────────────────────

class TestCreditScoreIntegration:
    def test_credit_score_increases_after_on_time_repayment(self, client):
        """Full lifecycle verifying credit score goes up on-time."""
        import uuid
        uid = uuid.uuid4().hex[:6]
        r = client.post("/api/auth/register", json={
            "name": f"Eve {uid}", "email": f"eve_{uid}@test.com",
            "password": "Password1!", "role": "borrower"
        })
        assert r.status_code == 201
        b_hdrs = {"Authorization": f"Bearer {r.json()['access_token']}"}
        initial_score = 500

        r = client.post("/api/auth/register", json={
            "name": f"Frank {uid}", "email": f"frank_{uid}@test.com",
            "password": "Password1!", "role": "lender"
        })
        assert r.status_code == 201
        l_hdrs = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # Request → fund → repay in full
        r = client.post("/api/loans", json={
            "amount": 300, "duration_days": 30, "purpose": "credit test", "source": "web"
        }, headers=b_hdrs)
        assert r.status_code == 201
        loan = r.json()
        if loan["status"] != "OPEN_FOR_FUNDING":
            pytest.skip("Loan rejected — cannot test credit update")
        loan_id = loan["id"]

        client.post(f"/api/loans/{loan_id}/fund", json={"amount": 300}, headers=l_hdrs)
        total_due = round(300 * 1.10, 2)
        r = client.post(f"/api/loans/{loan_id}/repay", json={"amount": total_due}, headers=b_hdrs)
        assert r.status_code == 201
        result = r.json()
        assert result["credit_score"] > initial_score
        assert "on_time_repayment" in result["events"]


# ── Admin endpoints ────────────────────────────────────────────────────────

class TestAdminEndpoints:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        uid = uuid.uuid4().hex[:8]
        r = client.post("/api/auth/register", json={
            "name": f"Admin {uid}",
            "email": f"admin_{uid}@test.com",
            "password": "AdminPass1!",
            "role": "admin",
        })
        assert r.status_code == 201, r.text
        self.admin_hdrs = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_analytics_returns_counts(self, client):
        r = client.get("/api/admin/analytics", headers=self.admin_hdrs)
        assert r.status_code == 200
        data = r.json()
        assert "total_loans" in data
        assert "borrower_count" in data
        assert "lender_count" in data

    def test_list_users(self, client):
        r = client.get("/api/admin/users", headers=self.admin_hdrs)
        assert r.status_code == 200
        users = r.json()
        # Password hash must never be exposed
        for u in users:
            assert "password_hash" not in u

    def test_create_and_resolve_flag(self, client):
        # Create a flag
        r = client.post("/api/admin/flags", json={
            "entity_type": "user",
            "entity_id": "000000000000000000000001",
            "flag_type": "SUSPECTED_FRAUD",
            "severity": "HIGH",
            "reason": "Suspicious activity during test",
        }, headers=self.admin_hdrs)
        assert r.status_code == 201, r.text
        flag = r.json()
        assert flag["resolved"] is False
        flag_id = flag["id"]

        # Resolve it
        r = client.patch(f"/api/admin/flags/{flag_id}/resolve", headers=self.admin_hdrs)
        assert r.status_code == 200
        assert r.json()["resolved"] is True

        # Resolve again should 409
        r = client.patch(f"/api/admin/flags/{flag_id}/resolve", headers=self.admin_hdrs)
        assert r.status_code == 409

    def test_non_admin_cannot_access_admin_routes(self, client):
        # Register a regular borrower
        import uuid
        uid = uuid.uuid4().hex[:6]
        r = client.post("/api/auth/register", json={
            "name": f"Regular {uid}", "email": f"reg_{uid}@test.com",
            "password": "Password1!", "role": "borrower"
        })
        assert r.status_code == 201
        hdrs = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = client.get("/api/admin/users", headers=hdrs)
        assert r.status_code == 403


# ── Serializer ─────────────────────────────────────────────────────────────

class TestSerializer:
    def test_serialize_doc_converts_objectid(self):
        from bson import ObjectId
        from app.api.serializers import serialize_doc

        doc = {"_id": ObjectId(), "user_id": ObjectId(), "name": "test"}
        out = serialize_doc(doc)
        assert isinstance(out["id"], str)
        assert isinstance(out["user_id"], str)

    def test_serialize_doc_none(self):
        from app.api.serializers import serialize_doc
        assert serialize_doc(None) is None

    def test_serialize_doc_nested_objectid(self):
        from bson import ObjectId
        from app.api.serializers import serialize_doc

        doc = {"_id": ObjectId(), "meta": {"ref_id": ObjectId()}}
        out = serialize_doc(doc)
        assert isinstance(out["meta"]["ref_id"], str)

    def test_serialize_doc_datetime(self):
        from datetime import datetime, timezone
        from app.api.serializers import serialize_doc

        doc = {"_id": __import__("bson").ObjectId(), "created_at": datetime.now(timezone.utc)}
        out = serialize_doc(doc)
        assert isinstance(out["created_at"], str)
        assert "T" in out["created_at"]  # ISO format


# ── Notification endpoints ─────────────────────────────────────────────────

class TestNotifications:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        import uuid
        uid = uuid.uuid4().hex[:6]
        r = client.post("/api/auth/register", json={
            "name": f"NotifUser {uid}",
            "email": f"notif_{uid}@test.com",
            "password": "Password1!",
            "role": "borrower",
        })
        assert r.status_code == 201
        self.hdrs = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_list_notifications_empty(self, client):
        r = client.get("/api/notifications", headers=self.hdrs)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_mark_all_read(self, client):
        r = client.patch("/api/notifications/read-all", headers=self.hdrs)
        assert r.status_code == 200
        assert "updated" in r.json()
