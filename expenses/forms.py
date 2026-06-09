"""
Django forms for the expenses app.

Provides proper server-side validation for transactions,
user registration, and support requests.
"""

from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.models import User

from .models import Transaction, SupportRequest


class TransactionForm(forms.Form):
    """Validates and cleans transaction input from the user."""

    amount = forms.CharField(max_length=20)
    description = forms.CharField(max_length=255, min_length=1)
    date = forms.DateTimeField()
    type = forms.ChoiceField(choices=Transaction.TRANSACTION_TYPES)

    def clean_amount(self):
        """Ensure amount is a valid positive number."""
        raw = self.cleaned_data["amount"]
        try:
            value = Decimal(raw)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Enter a valid numeric amount.")

        if value <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")

        return value

    def get_signed_amount(self):
        """Return the amount with correct sign based on transaction type."""
        amount = self.cleaned_data["amount"]
        trans_type = self.cleaned_data["type"]

        if trans_type == "expense":
            return -abs(amount)
        return abs(amount)


class RegistrationForm(forms.Form):
    """Validates user registration input."""

    username = forms.CharField(max_length=150, min_length=1)
    email = forms.EmailField()
    password = forms.CharField(min_length=8)
    confirm_password = forms.CharField(min_length=8)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already registered.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        if password.isdigit():
            raise forms.ValidationError(
                "Password cannot contain only numbers."
            )
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")

        if password and confirm and password != confirm:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned


class SupportRequestForm(forms.ModelForm):
    """Validates support request submissions."""

    class Meta:
        model = SupportRequest
        fields = ["username_or_email", "issue_type", "message"]

    def clean_username_or_email(self):
        value = self.cleaned_data["username_or_email"].strip()
        if not value:
            raise forms.ValidationError("This field is required.")
        return value

    def clean_message(self):
        value = self.cleaned_data["message"].strip()
        if not value:
            raise forms.ValidationError("Please describe your issue.")
        return value
