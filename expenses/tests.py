"""
Comprehensive test suite for the LedGio expenses application.

Covers: models, expense_engine logic, views (auth, IDOR, POST-only),
registration validation, and admin access control.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from .expense_engine import (
    categorize,
    add_transaction,
    get_balance,
    get_insights,
    get_transactions,
)
from .models import Transaction, SupportRequest


# ===================================================================
# Model Tests
# ===================================================================

class UserModelTest(TestCase):
    """Tests for Django User model creation."""

    def test_user_creation(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@gmail.com",
            password="Test123@",
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@gmail.com")
        self.assertTrue(user.check_password("Test123@"))


class TransactionModelTest(TestCase):
    """Tests for the Transaction model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            password="pass12345",
        )

    def test_transaction_creation(self):
        transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("1000.00"),
            description="Salary",
            category="Income",
            trans_type="income",
        )
        self.assertEqual(transaction.amount, Decimal("1000.00"))
        self.assertEqual(transaction.category, "Income")

    def test_transaction_str(self):
        transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("500.00"),
            description="Groceries",
            category="Household",
            trans_type="expense",
        )
        self.assertIn("Groceries", str(transaction))
        self.assertIn("500", str(transaction))

    def test_default_ordering(self):
        """Transactions should be ordered by -transaction_date by default."""
        t1 = Transaction.objects.create(
            user=self.user,
            amount=Decimal("100"),
            description="First",
            category="Other",
            trans_type="expense",
        )
        t2 = Transaction.objects.create(
            user=self.user,
            amount=Decimal("200"),
            description="Second",
            category="Other",
            trans_type="expense",
        )
        transactions = list(Transaction.objects.filter(user=self.user))
        # Most recent (t2) should come first
        self.assertEqual(transactions[0].id, t2.id)


class SupportRequestModelTest(TestCase):
    """Tests for the SupportRequest model."""

    def test_support_request_creation(self):
        sr = SupportRequest.objects.create(
            username_or_email="testuser@example.com",
            issue_type="concern",
            message="I have a concern about my account.",
        )
        self.assertEqual(sr.status, "open")
        self.assertIn("testuser@example.com", str(sr))


# ===================================================================
# Expense Engine Tests
# ===================================================================

class CategorizeTest(TestCase):
    """Tests for the categorize() auto-detection function."""

    def test_food_keywords(self):
        self.assertEqual(categorize("KFC dinner"), ("Food", "Daily Food"))
        self.assertEqual(categorize("pizza hut order"), ("Food", "Eating Out"))
        self.assertEqual(categorize("snacks from store"), ("Food", "Daily Food"))

    def test_transportation_keywords(self):
        self.assertEqual(categorize("uber ride"), ("Transportation", "Ride Hailing"))
        self.assertEqual(categorize("bus ticket"), ("Transportation", "Public Transport"))
        self.assertEqual(categorize("petrol fill"), ("Transportation", "Fuel"))

    def test_shopping_keywords(self):
        self.assertEqual(categorize("amazon order"), ("Shopping", "Online Shopping"))
        self.assertEqual(categorize("new shoes"), ("Shopping", "Footwear"))

    def test_household_keywords(self):
        self.assertEqual(categorize("furniture purchase"), ("Shopping", "Assets & Major Purchases"))
        self.assertEqual(categorize("detergent"), ("Household", "Cleaning Supplies"))

    def test_unknown_defaults_to_miscellaneous(self):
        self.assertEqual(categorize("random stuff"), ("Miscellaneous", "Others"))
        self.assertEqual(categorize(""), ("Miscellaneous", "Others"))

    def test_case_insensitive(self):
        self.assertEqual(categorize("KFC DINNER"), ("Food", "Daily Food"))
        self.assertEqual(categorize("UBER ride"), ("Transportation", "Ride Hailing"))


class BalanceTest(TestCase):
    """Tests for the get_balance() function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="balanceuser",
            password="Test123@",
        )

    def test_balance_calculation(self):
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("30000"),
            description="Salary",
            category="Income",
            trans_type="income",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-500"),
            description="KFC",
            category="Food",
            trans_type="expense",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-1000"),
            description="Amazon",
            category="Shopping",
            trans_type="expense",
        )

        result = get_balance(self.user)

        self.assertEqual(result["income"], Decimal("30000"))
        self.assertEqual(result["expense"], Decimal("1500"))
        self.assertEqual(result["balance"], Decimal("28500"))

    def test_zero_balance_no_transactions(self):
        result = get_balance(self.user)
        self.assertEqual(result["income"], Decimal("0"))
        self.assertEqual(result["expense"], Decimal("0"))
        self.assertEqual(result["balance"], Decimal("0"))


class InsightsTest(TestCase):
    """Tests for the get_insights() function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="insightuser",
            password="Test123@",
        )

    def test_insights_with_expenses(self):
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-500"),
            description="KFC",
            category="Food",
            trans_type="expense",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-2000"),
            description="Amazon",
            category="Shopping",
            trans_type="expense",
        )

        result = get_insights(self.user)

        self.assertEqual(result["total_spending"], Decimal("2500"))
        self.assertEqual(result["highest_category"], "Shopping")
        self.assertIn("Food", result["category_totals"])
        self.assertIn("Shopping", result["category_totals"])

    def test_insights_no_expenses(self):
        result = get_insights(self.user)
        self.assertEqual(result["total_spending"], Decimal("0"))
        self.assertIsNone(result["highest_category"])

    def test_income_excluded_from_insights(self):
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("50000"),
            description="Salary",
            category="Income",
            trans_type="income",
        )
        result = get_insights(self.user)
        self.assertEqual(result["total_spending"], Decimal("0"))


class GetTransactionsTest(TestCase):
    """Tests for the get_transactions() function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="txnuser",
            password="Test123@",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-100"),
            description="KFC lunch",
            category="Food",
            trans_type="expense",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("5000"),
            description="Freelance income",
            category="Income",
            trans_type="income",
        )

    def test_returns_all_user_transactions(self):
        result = get_transactions(self.user)
        self.assertEqual(len(result), 2)

    def test_search_filter(self):
        result = get_transactions(self.user, search="kfc")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["description"], "KFC lunch")

    def test_type_filter(self):
        result = get_transactions(self.user, trans_type="income")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["trans_type"], "income")

    def test_user_isolation(self):
        """Users should not see each other's transactions."""
        other_user = User.objects.create_user(
            username="other", password="Test123@",
        )
        result = get_transactions(other_user)
        self.assertEqual(len(result), 0)


# ===================================================================
# Authentication Tests
# ===================================================================

class AuthenticationTest(TestCase):
    """Tests for login functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser",
            password="Test123@",
        )

    def test_valid_login(self):
        login_successful = self.client.login(
            username="loginuser",
            password="Test123@",
        )
        self.assertTrue(login_successful)

    def test_invalid_login(self):
        login_successful = self.client.login(
            username="loginuser",
            password="wrongpassword",
        )
        self.assertFalse(login_successful)


# ===================================================================
# View Tests
# ===================================================================

class DashboardViewTest(TestCase):
    """Tests for the dashboard view."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="dashuser",
            password="Test123@",
        )
        self.client = Client()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_dashboard_accessible_when_logged_in(self):
        self.client.login(username="dashuser", password="Test123@")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)


class DeleteViewSecurityTest(TestCase):
    """Tests for delete transaction IDOR and POST-only protection."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner", password="Test123@",
        )
        self.other_user = User.objects.create_user(
            username="attacker", password="Test123@",
        )
        self.transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("-100"),
            description="My expense",
            category="Other",
            trans_type="expense",
        )
        self.client = Client()

    def test_delete_requires_post(self):
        """GET requests to delete should return 405."""
        self.client.login(username="owner", password="Test123@")
        response = self.client.get(
            reverse("delete", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_delete_idor_protection(self):
        """Another user should not be able to delete someone else's transaction."""
        self.client.login(username="attacker", password="Test123@")
        response = self.client.post(
            reverse("delete", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 404)
        # Transaction should still exist
        self.assertTrue(
            Transaction.objects.filter(id=self.transaction.id).exists()
        )

    def test_owner_can_delete(self):
        """Owner should be able to delete their own transaction."""
        self.client.login(username="owner", password="Test123@")
        response = self.client.post(
            reverse("delete", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Transaction.objects.filter(id=self.transaction.id).exists()
        )


class EditViewSecurityTest(TestCase):
    """Tests for edit transaction IDOR protection."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner", password="Test123@",
        )
        self.other_user = User.objects.create_user(
            username="attacker", password="Test123@",
        )
        self.transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("-100"),
            description="My expense",
            category="Other",
            trans_type="expense",
        )
        self.client = Client()

    def test_edit_idor_protection(self):
        """Another user should get 404 when trying to edit someone else's transaction."""
        self.client.login(username="attacker", password="Test123@")
        response = self.client.get(
            reverse("edit", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 404)


class AdminViewAccessTest(TestCase):
    """Tests for admin-only view access control."""

    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular", password="Test123@",
        )
        self.admin_user = User.objects.create_user(
            username="admin", password="Test123@", is_staff=True,
        )
        self.client = Client()

    def test_admin_view_blocked_for_regular_user(self):
        self.client.login(username="regular", password="Test123@")
        response = self.client.get(reverse("ledgio_admin"))
        # Should redirect (302) — user_passes_test sends to login
        self.assertNotEqual(response.status_code, 200)

    def test_admin_view_accessible_for_staff(self):
        self.client.login(username="admin", password="Test123@")
        response = self.client.get(reverse("ledgio_admin"))
        self.assertEqual(response.status_code, 200)


class RegistrationViewTest(TestCase):
    """Tests for the registration form validation."""

    def test_password_mismatch(self):
        response = self.client.post(reverse("register"), {
            "username": "newuser",
            "email": "new@example.com",
            "password": "StrongPass1!",
            "confirm_password": "DifferentPass1!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "do not match")

    def test_short_password(self):
        response = self.client.post(reverse("register"), {
            "username": "newuser",
            "email": "new@example.com",
            "password": "short",
            "confirm_password": "short",
        })
        self.assertEqual(response.status_code, 200)

    def test_duplicate_username(self):
        User.objects.create_user(
            username="taken", password="Test123@",
        )
        response = self.client.post(reverse("register"), {
            "username": "taken",
            "email": "unique@example.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_successful_registration(self):
        response = self.client.post(reverse("register"), {
            "username": "brandnew",
            "email": "brandnew@example.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "country": "India",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="brandnew").exists())


class ToggleUserStatusSecurityTest(TestCase):
    """Tests for POST-only toggle endpoints."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="Test123@", is_staff=True,
        )
        self.target = User.objects.create_user(
            username="target", password="Test123@",
        )
        self.client = Client()

    def test_toggle_user_requires_post(self):
        self.client.login(username="admin", password="Test123@")
        response = self.client.get(
            reverse("toggle_user_status", args=[self.target.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_toggle_user_works_with_post(self):
        self.client.login(username="admin", password="Test123@")
        response = self.client.post(
            reverse("toggle_user_status", args=[self.target.id])
        )
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
