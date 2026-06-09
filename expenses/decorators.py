"""
Custom decorators for the expenses app.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required, user_passes_test


def _is_admin(user):
    """Check if the user is authenticated and has staff privileges."""
    return user.is_authenticated and user.is_staff


def admin_required(view_func):
    """
    Decorator that combines @login_required and @user_passes_test(is_admin).

    Usage:
        @admin_required
        def my_admin_view(request):
            ...
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)

    decorated = login_required(user_passes_test(_is_admin)(_wrapped))
    return decorated
