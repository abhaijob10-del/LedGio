from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Transaction(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    amount = models.FloatField()

    description = models.CharField(max_length=255)

    category = models.CharField(max_length=100)

    trans_type = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)

    transaction_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.description} - ₹{self.amount}"


class SupportRequest(models.Model):

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
        choices=ISSUE_CHOICES
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username_or_email} - {self.issue_type}"