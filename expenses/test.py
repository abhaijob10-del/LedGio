from django.test import TestCase
from django.contrib.auth.models import User
from .models import Transaction


class UserTest(TestCase):

    def test_user_creation(self):

        user = User.objects.create_user(
            username="testuser",
            email="test@gmail.com",
            password="Test123@"
        )

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@gmail.com")

class TransactionTest(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="user1",
            password="pass123"
        )

    def test_transaction_creation(self):

        transaction = Transaction.objects.create(
            user=self.user,
            amount=1000,
            description="Salary",
            category="Income",
            trans_type="income"
        )

        self.assertEqual(transaction.amount, 1000)
        self.assertEqual(transaction.category, "Income")        

from .expense_engine import get_balance


class BalanceTest(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="balanceuser",
            password="Test123@"
        )

    def test_balance_calculation(self):

        Transaction.objects.create(
            user=self.user,
            amount=30000,
            description="Salary",
            category="Income",
            trans_type="income"
        )

        Transaction.objects.create(
            user=self.user,
            amount=-500,
            description="KFC",
            category="Food",
            trans_type="expense"
        )

        Transaction.objects.create(
            user=self.user,
            amount=-1000,
            description="Amazon",
            category="Shopping",
            trans_type="expense"
        )

        result = get_balance(self.user)

        self.assertEqual(result["income"], 30000)
        self.assertEqual(result["expense"], 1500)
        self.assertEqual(result["balance"], 28500)

class AuthenticationTest(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="loginuser",
            password="Test123@"
        )

    def test_valid_login(self):

        login_successful = self.client.login(
            username="loginuser",
            password="Test123@"
        )

        self.assertTrue(login_successful)

    def test_invalid_login(self):

        login_successful = self.client.login(
            username="loginuser",
            password="wrongpassword"
        )

        self.assertFalse(login_successful)