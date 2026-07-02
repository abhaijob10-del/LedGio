"""
context_processors.py — Injects user currency data into every template context.

Registered in settings.py → TEMPLATES → context_processors.
After this, every template can use {{ currency_symbol }} and {{ currency_code }}
without any view needing to pass them explicitly.
"""

from .models import UserProfile


def currency_context(request):
    """
    Return the authenticated user's currency symbol and code.
    Falls back to INR / ₹ for unauthenticated pages (login, register, etc.).
    """
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            return {
                "currency_symbol": profile.currency_symbol or "₹",
                "currency_code":   profile.currency_code   or "INR",
                "user_country":    profile.country          or "India",
            }
        except UserProfile.DoesNotExist:
            # Graceful fallback — profile signal may not have fired yet
            pass

    return {
        "currency_symbol": "₹",
        "currency_code":   "INR",
        "user_country":    "India",
    }
