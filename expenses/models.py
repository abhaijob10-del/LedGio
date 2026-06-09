from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Transaction(models.Model):
    """A financial transaction (income or expense) belonging to a user."""

    TRANSACTION_TYPES = [
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    CATEGORY_CHOICES = [
        ("Income", "Income"),
        ("Food", "Food"),
        ("Transportation", "Transportation"),
        ("Shopping", "Shopping"),
        ("Household", "Household"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Positive for income, negative for expense.",
    )

    description = models.CharField(max_length=255)

    category = models.CharField(
        max_length=100,
        choices=CATEGORY_CHOICES,
    )

    trans_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    transaction_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        ordering = ["-transaction_date"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        indexes = [
            models.Index(fields=["user", "trans_type"]),
            models.Index(fields=["user", "transaction_date"]),
        ]

    def __str__(self):
        return f"{self.description} - ₹{self.amount}"


class SupportRequest(models.Model):
    """A support request submitted by a user (or guest)."""

    ISSUE_CHOICES = [
        ("improvement", "Improvement"),
        ("concern", "Concern"),
        ("account_deactivated", "Account Deactivated"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("resolved", "Resolved"),
    ]

    username_or_email = models.CharField(max_length=150)

    issue_type = models.CharField(
        max_length=50,
        choices=ISSUE_CHOICES,
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Support Request"
        verbose_name_plural = "Support Requests"

    def __str__(self):
        return f"{self.username_or_email} - {self.issue_type}"