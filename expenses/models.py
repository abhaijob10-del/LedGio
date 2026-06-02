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

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.description} - ₹{self.amount}"