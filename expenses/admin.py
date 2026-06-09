from django.contrib import admin

from .models import SupportRequest, Transaction


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