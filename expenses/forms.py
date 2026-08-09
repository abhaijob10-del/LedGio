"""
Django forms for the expenses app.

Provides proper server-side validation for transactions,
user registration, support requests, savings goals, and profile updates.
"""

from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import password_validation

from .models import Transaction, SupportRequest, SavingsGoal
from .country_data import get_country_choices


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
    country = forms.ChoiceField(
        choices=get_country_choices(),
        error_messages={"required": "Please select your country."},
    )
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


class SavingsGoalForm(forms.ModelForm):
    """Form to create or update a monthly savings goal — extended with name and deadline."""

    class Meta:
        model = SavingsGoal
        fields = ["goal_name", "target_amount", "deadline"]

    goal_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Emergency Fund, Vacation, New Laptop"}),
    )

    deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean_target_amount(self):
        amount = self.cleaned_data["target_amount"]
        if amount <= 0:
            raise forms.ValidationError("Target amount must be greater than zero.")
        return amount


class ProfileUpdateForm(forms.Form):
    """Validates profile updates — username, email, picture."""

    username = forms.CharField(max_length=150, min_length=1)
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username=username)
        if self.current_user:
            qs = qs.exclude(pk=self.current_user.pk)
        if qs.exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        qs = User.objects.filter(email=email)
        if self.current_user:
            qs = qs.exclude(pk=self.current_user.pk)
        if qs.exists():
            raise forms.ValidationError("That email is already registered.")
        return email


class PasswordChangeForm(forms.Form):
    """Secure password change — requires current password."""

    current_password = forms.CharField(min_length=1)
    new_password = forms.CharField(min_length=8)
    confirm_password = forms.CharField(min_length=8)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data["current_password"]
        if self.user and not self.user.check_password(current):
            raise forms.ValidationError("Current password is incorrect.")
        return current

    def clean_new_password(self):
        password = self.cleaned_data["new_password"]
        if password.isdigit():
            raise forms.ValidationError("Password cannot be all numbers.")
        if self.user:
            password_validation.validate_password(password, self.user)
        return password

    def clean(self):
        cleaned = super().clean()
        new_pw = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if new_pw and confirm and new_pw != confirm:
            raise forms.ValidationError("New passwords do not match.")
        return cleaned


class SupportReplyForm(forms.Form):
    """Admin reply to a support request (future use placeholder)."""
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=2000,
        min_length=10,
    )
