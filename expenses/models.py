from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .country_data import get_currency_for_country


class Transaction(models.Model):
    """A financial transaction (income or expense) belonging to a user."""

    TRANSACTION_TYPES = [
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    CATEGORY_CHOICES = [
    ("Income", "Income"),
    ("Mandatory Expenses", "Mandatory Expenses"),
    ("Maintenance", "Maintenance"),
    ("Unexpected Expenses", "Unexpected Expenses"),
    ("Education", "Education"),
    ("Food", "Food"),
    ("Transportation", "Transportation"),
    ("Travel", "Travel"),
    ("Shopping", "Shopping"),
    ("Household", "Household"),
    ("Healthcare", "Healthcare"),
    ("Personal Care", "Personal Care"),
    ("Communication", "Communication"),
    ("Subscriptions", "Subscriptions"),
    ("Entertainment", "Entertainment"),
    ("Investment", "Investment"),
    ("Business Related", "Business Related"),
    ("Family Support", "Family Support"),
    ("Pets", "Pets"),
    ("Donations", "Donations"),
    ("Bank Charges", "Bank Charges"),
    ("Miscellaneous", "Miscellaneous"),
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

    subcategory = models.CharField(
        max_length=100,
        blank=True,
        null=True
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
        return f"{self.description} - {self.amount}"


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
        ("pending", "Pending"),
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


# ---------------------------------------------------------------------------
# UserProfile — Stores country + currency per user
# ---------------------------------------------------------------------------

class UserProfile(models.Model):
    """Extended profile for a Django User — stores country and currency."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        default="India",
    )

    currency_symbol = models.CharField(
        max_length=10,
        blank=True,
        default="₹",
    )

    currency_code = models.CharField(
        max_length=10,
        blank=True,
        default="INR",
    )

    # When True the user has completed email verification
    email_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} — {self.country} ({self.currency_code})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Auto-create a UserProfile whenever a new User is created."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
    else:
        # Ensure profile exists for legacy users (e.g. superusers created via CLI)
        UserProfile.objects.get_or_create(user=instance)


# ---------------------------------------------------------------------------
# SavingsGoal — Monthly savings target per user
# ---------------------------------------------------------------------------

class SavingsGoal(models.Model):
    """A monthly savings target set by a user."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("achieved", "Achieved"),
        ("missed", "Missed"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="savings_goals",
    )

    # Stored as the first day of the target month (e.g. 2026-07-01)
    month = models.DateField(db_index=True)

    target_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    class Meta:
        # One goal per user per month
        unique_together = (("user", "month"),)
        ordering = ["-month"]
        verbose_name = "Savings Goal"
        verbose_name_plural = "Savings Goals"

    def __str__(self):
        return f"{self.user.username} — {self.month.strftime('%B %Y')} goal"