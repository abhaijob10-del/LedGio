from django.apps import AppConfig


class ExpensesConfig(AppConfig):
    """Configuration for the expenses application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "expenses"
    verbose_name = "Expenses"
