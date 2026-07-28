"""Tests for the Add Expense feature (Step 07)."""

import pytest
import re


class TestAddExpenseAuth:
    """Test authentication guards for /expenses/add route."""

    def test_get_requires_login(self, client):
        """GET /expenses/add redirects to /login when not authenticated."""
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_post_requires_login(self, client):
        """POST /expenses/add redirects to /login when not authenticated."""
        response = client.post("/expenses/add", data={"amount": "50"})
        assert response.status_code == 302
        assert "/login" in response.location


class TestAddExpenseGet:
    """Test GET /expenses/add behavior."""

    def test_get_renders_form(self, auth_client):
        """GET /expenses/add renders the expense form when authenticated."""
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200

    def test_get_form_has_amount_field(self, auth_client):
        """Form includes amount input field."""
        response = auth_client.get("/expenses/add")
        assert b'name="amount"' in response.data

    def test_get_form_has_category_select(self, auth_client):
        """Form includes category dropdown with all categories."""
        response = auth_client.get("/expenses/add")
        assert b'name="category"' in response.data
        # Check all 7 categories are present
        assert b"Food" in response.data
        assert b"Transport" in response.data
        assert b"Bills" in response.data
        assert b"Health" in response.data
        assert b"Entertainment" in response.data
        assert b"Shopping" in response.data
        assert b"Other" in response.data

    def test_get_form_has_date_field(self, auth_client):
        """Form includes date input field."""
        response = auth_client.get("/expenses/add")
        assert b'name="date"' in response.data

    def test_get_form_has_description_field(self, auth_client):
        """Form includes optional description input field."""
        response = auth_client.get("/expenses/add")
        assert b'name="description"' in response.data

    def test_get_form_has_submit_button(self, auth_client):
        """Form includes submit button."""
        response = auth_client.get("/expenses/add")
        assert b"Save Expense" in response.data


def _get_csrf_token(response):
    """Extract CSRF token from a form response."""
    match = re.search(r'name="csrf_token"[^>]*value="([^"]*)"', response.data.decode('utf-8'))
    return match.group(1) if match else ""


class TestAddExpensePost:
    """Test POST /expenses/add behavior with valid and invalid data."""

    def test_post_valid_expense_redirects_to_profile(self, auth_client):
        """POST with valid data redirects to /profile."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "50.00",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 302
        assert "/profile" in response.location

    def test_post_valid_expense_creates_record(self, auth_client, app):
        """POST with valid data creates expense record in database."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        auth_client.post(
            "/expenses/add",
            data={
                "amount": "50.00",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
                "csrf_token": csrf_token,
            },
        )
        with app.app_context():
            from database.db import get_db
            db = get_db()
            row = db.execute(
                "SELECT * FROM expenses WHERE user_id = 1 AND amount = 50.00 AND category = 'Food'",
            ).fetchone()
            assert row is not None
            assert row["date"] == "2026-03-20"
            assert row["description"] == "Lunch"

    def test_post_missing_amount_shows_error(self, auth_client):
        """POST with missing amount re-renders form with error."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "",
                "category": "Food",
                "date": "2026-03-20",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"Please" in response.data

    def test_post_zero_amount_shows_error(self, auth_client):
        """POST with zero amount shows validation error."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "0",
                "category": "Food",
                "date": "2026-03-20",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"Please" in response.data or b"zero" in response.data.lower()

    def test_post_negative_amount_shows_error(self, auth_client):
        """POST with negative amount shows validation error."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "-50",
                "category": "Food",
                "date": "2026-03-20",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"Please" in response.data or b"positive" in response.data.lower()

    def test_post_invalid_category_shows_error(self, auth_client):
        """POST with invalid category shows validation error."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "50",
                "category": "InvalidCategory",
                "date": "2026-03-20",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"category" in response.data.lower()

    def test_post_missing_date_shows_error(self, auth_client):
        """POST with missing date shows validation error."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "50",
                "category": "Food",
                "date": "",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"date" in response.data.lower()

    def test_post_invalid_date_shows_error(self, auth_client):
        """POST with invalid date format shows validation error."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "50",
                "category": "Food",
                "date": "not-a-date",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"date" in response.data.lower()

    def test_post_no_description_saves_expense(self, auth_client):
        """POST without optional description saves expense with NULL description."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "50.00",
                "category": "Food",
                "date": "2026-03-20",
                "description": "",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 302
        assert "/profile" in response.location

    def test_post_repopulates_form_on_error(self, auth_client):
        """On validation error, form is re-rendered with previous values."""
        # First get the form to obtain CSRF token
        form_response = auth_client.get("/expenses/add")
        csrf_token = _get_csrf_token(form_response)

        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "abc",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Test",
                "csrf_token": csrf_token,
            },
        )
        assert response.status_code == 200
        # The form should be re-rendered, check it contains the values
        assert b"Food" in response.data


class TestInsertExpenseFunction:
    """Unit tests for the insert_expense database helper."""

    def test_insert_expense_creates_record(self, app):
        """insert_expense creates a new expense record."""
        with app.app_context():
            from database.queries import insert_expense
            from database.db import get_db

            expense_id = insert_expense(
                user_id=1,
                amount=75.50,
                category="Transport",
                date="2026-03-15",
                description="Taxi fare",
            )

            db = get_db()
            row = db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
            assert row is not None
            assert row["user_id"] == 1
            assert row["amount"] == 75.50
            assert row["category"] == "Transport"
            assert row["date"] == "2026-03-15"
            assert row["description"] == "Taxi fare"

    def test_insert_expense_with_null_description(self, app):
        """insert_expense stores None description as NULL."""
        with app.app_context():
            from database.queries import insert_expense
            from database.db import get_db

            expense_id = insert_expense(
                user_id=1,
                amount=100.00,
                category="Bills",
                date="2026-03-10",
                description=None,
            )

            db = get_db()
            row = db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
            assert row is not None
            assert row["description"] is None

    def test_insert_expense_with_empty_description(self, app):
        """insert_expense treats empty string as None."""
        with app.app_context():
            from database.queries import insert_expense
            from database.db import get_db

            expense_id = insert_expense(
                user_id=1,
                amount=50.00,
                category="Other",
                date="2026-03-05",
                description="",
            )

            db = get_db()
            row = db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
            assert row is not None
            assert row["description"] is None
