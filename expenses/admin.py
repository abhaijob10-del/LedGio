from django.contrib import admin

from .models import SupportRequest, Transaction, UserProfile, SavingsGoal


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin configuration for Transaction model."""

    list_display = (
        "id",
        "user",
        "description",
        "amount",
        "category",
        "trans_type",
        "transaction_date",
    )
    list_filter = ("trans_type", "category", "transaction_date")
    search_fields = ("description", "user__username", "user__email")
    date_hierarchy = "transaction_date"
    list_per_page = 25
    ordering = ("-transaction_date",)


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    """Admin configuration for SupportRequest model."""

    list_display = (
        "id",
        "username_or_email",
        "issue_type",
        "status",
        "created_at",
    )
    list_filter = ("status", "issue_type", "created_at")
    search_fields = ("username_or_email", "message")
    list_per_page = 25
    ordering = ("-created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for UserProfile model."""

    list_display = (
        "user",
        "country",
        "currency_symbol",
        "currency_code",
        "email_verified",
    )
    list_filter = ("country", "currency_code", "email_verified")
    search_fields = ("user__username", "user__email", "country")
    list_per_page = 25
    ordering = ("user__username",)


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    """Admin configuration for SavingsGoal model."""

    list_display = (
        "user",
        "month",
        "target_amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "month")
    search_fields = ("user__username", "user__email")
    list_per_page = 25
    ordering = ("-month",)