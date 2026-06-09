"""
Views for the LedGio expenses application.

Handles dashboard, transactions CRUD, user auth, admin panel,
support requests, and staff management.
"""

import logging

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from datetime import timedelta

from .decorators import admin_required
from .forms import RegistrationForm, SupportRequestForm, TransactionForm
from .models import SupportRequest, Transaction
from .expense_engine import (
    add_transaction,
    get_transactions,
    get_insights,
    get_balance,
    delete_transaction,
    update_transaction,
    get_monthly_analytics,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """Main dashboard showing balance, insights, analytics, and recent transactions."""

    balance = get_balance(request.user)
    insights = get_insights(request.user)
    monthly_analytics = get_monthly_analytics(request.user)
    recent_transactions = get_transactions(request.user)[:5]

    return render(request, "dashboard.html", {
        "balance": balance,
        "insights": insights,
        "monthly_analytics": monthly_analytics,
        "recent_transactions": recent_transactions,
    })


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@login_required
def transactions_views(request):
    """List all transactions with optional search, month, and type filters."""

    search = request.GET.get("search")
    month = request.GET.get("month")
    trans_type = request.GET.get("type")

    data = get_transactions(
        request.user,
        search=search,
        month=month,
        trans_type=trans_type,
    )

    return render(request, "transactions.html", {
        "transactions": data,
        "search_query": search,
        "selected_month": month,
        "selected_type": trans_type,
    })


@login_required
def add_transaction_view(request):
    """Add a new transaction (GET = show form, POST = create)."""

    if request.method == "POST":
        form = TransactionForm(request.POST)

        if form.is_valid():
            signed_amount = form.get_signed_amount()

            add_transaction(
                request.user,
                signed_amount,
                form.cleaned_data["description"],
                form.cleaned_data["date"],
                form.cleaned_data["type"],
            )

            messages.success(request, "Transaction added successfully.")
            return redirect(reverse("transactions"))

        # If form is invalid, re-render with errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")

    return render(request, "add_transaction.html")


@login_required
@require_POST
def delete(request, id):
    """Delete a transaction (POST only, scoped to current user)."""

    deleted = delete_transaction(id, request.user)

    if not deleted:
        raise Http404("Transaction not found.")

    messages.success(request, "Transaction deleted.")
    return redirect(reverse("transactions"))


@login_required
def edit(request, id):
    """Edit an existing transaction (GET = show form, POST = update)."""

    # Fetch the transaction scoped to the current user (IDOR protection)
    transaction_obj = get_object_or_404(
        Transaction, id=id, user=request.user
    )

    # Build a template-friendly dict matching the existing template contract
    transaction = {
        "id": transaction_obj.id,
        "amount": transaction_obj.amount,
        "description": transaction_obj.description,
        "category": transaction_obj.category,
        "trans_type": transaction_obj.trans_type,
        "date": transaction_obj.transaction_date,
    }

    if request.method == "POST":
        form = TransactionForm(request.POST)

        if form.is_valid():
            signed_amount = form.get_signed_amount()

            update_transaction(
                id,
                request.user,
                signed_amount,
                form.cleaned_data["description"],
                form.cleaned_data["date"],
                form.cleaned_data["type"],
            )

            messages.success(request, "Transaction updated successfully.")
            return redirect(reverse("transactions"))

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")

    return render(request, "edit_transaction.html", {
        "transaction": transaction,
    })


# ---------------------------------------------------------------------------
# Balance & Insights
# ---------------------------------------------------------------------------

@login_required
def balance_view(request):
    """Show the user's income/expense/balance summary."""

    balance = get_balance(request.user)
    return render(request, "balance.html", {"balance": balance})


@login_required
def insights(request):
    """Show spending insights by category."""

    data = get_insights(request.user)
    return render(request, "insights.html", {"insights": data})


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def register_view(request):
    """User registration (GET = show form, POST = create account)."""

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            messages.success(
                request, "Account created successfully. Please log in."
            )
            return redirect(reverse("login"))

        # Collect all form errors into a single string for the template
        error_list = []
        for field, errors in form.errors.items():
            for error in errors:
                error_list.append(str(error))

        error = " ".join(error_list) if error_list else None

        return render(request, "register.html", {"error": error})

    return render(request, "register.html", {"error": None})


@login_required
def logout_view(request):
    """Log the user out and redirect to login page."""

    logout(request)
    return redirect(reverse("login"))


def check_user_availability(request):
    """AJAX endpoint to check if a username/email is already taken."""

    username = request.GET.get("username", "").strip()
    email = request.GET.get("email", "").strip()

    data = {
        "username_exists": False,
        "email_exists": False,
    }

    if username:
        data["username_exists"] = User.objects.filter(
            username=username
        ).exists()

    if email:
        data["email_exists"] = User.objects.filter(email=email).exists()

    return JsonResponse(data)


@login_required
def profile_view(request):
    """Show the user's profile page."""
    return render(request, "profile.html")


# ---------------------------------------------------------------------------
# Admin — Auto-deactivation
# ---------------------------------------------------------------------------

def auto_deactivate_inactive_users():
    """
    Deactivate non-staff users who haven't logged in for 6+ months.

    NOTE: Ideally this should be a management command run via cron/celery,
    not triggered on every admin page load. Kept inline for now to preserve
    existing behaviour.
    """
    six_months_ago = timezone.now() - timedelta(days=180)

    count = User.objects.filter(
        is_staff=False,
        is_active=True,
        last_login__lt=six_months_ago,
    ).update(is_active=False)

    if count:
        logger.info("Auto-deactivated %d inactive user(s).", count)


# ---------------------------------------------------------------------------
# Admin — Dashboard
# ---------------------------------------------------------------------------

@admin_required
def ledgio_admin_view(request):
    """Admin overview dashboard with user stats and support requests."""

    auto_deactivate_inactive_users()

    users = User.objects.all().order_by("-date_joined")
    support_requests = SupportRequest.objects.all().order_by("-created_at")

    # Single aggregate query instead of 4 separate COUNT queries
    user_stats = User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        staff=Count("id", filter=Q(is_staff=True)),
    )

    open_requests = SupportRequest.objects.filter(status="open").count()

    return render(request, "ledgio_admin.html", {
        "users": users,
        "support_requests": support_requests,
        "total_users": user_stats["total"],
        "active_users": user_stats["active"],
        "inactive_users": user_stats["inactive"],
        "staff_users": user_stats["staff"],
        "open_requests": open_requests,
    })


# ---------------------------------------------------------------------------
# Admin — User Management
# ---------------------------------------------------------------------------

@admin_required
@require_POST
def toggle_user_status(request, id):
    """Toggle a user's active/inactive status (POST only)."""

    user = get_object_or_404(User, id=id)

    if user == request.user:
        messages.error(request, "You cannot deactivate yourself.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        status = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User '{user.username}' {status}.")

    return redirect(reverse("ledgio_admin"))


@admin_required
def users_view(request):
    """List all users with optional search by username or email."""

    auto_deactivate_inactive_users()

    users = User.objects.all().order_by("-date_joined")

    search = request.GET.get("search")
    if search:
        users = users.filter(
            Q(username__icontains=search) | Q(email__icontains=search)
        )

    return render(request, "users.html", {"users": users})


# ---------------------------------------------------------------------------
# Admin — Support
# ---------------------------------------------------------------------------

def support_view(request):
    """Public support form (GET = show form, POST = submit request)."""

    if request.method == "POST":
        form = SupportRequestForm(request.POST)

        if form.is_valid():
            form.save()
            success = "Your support request has been submitted successfully."
            return render(request, "support.html", {"success": success})

        # If invalid, show errors
        messages.error(request, "Please fix the errors below.")
        return render(request, "support.html", {"success": None})

    return render(request, "support.html", {"success": None})


@admin_required
@require_POST
def resolve_support_request(request, id):
    """Mark a support request as resolved (POST only)."""

    support_request = get_object_or_404(SupportRequest, id=id)
    support_request.status = "resolved"
    support_request.save(update_fields=["status"])

    messages.success(request, "Support request resolved.")
    return redirect(reverse("ledgio_admin"))


@admin_required
@require_POST
def activate_user_from_request(request, id):
    """Activate a user referenced in a support request (POST only)."""

    support_request = get_object_or_404(SupportRequest, id=id)

    user = User.objects.filter(
        Q(username=support_request.username_or_email)
        | Q(email=support_request.username_or_email)
    ).first()

    if user:
        user.is_active = True
        user.save(update_fields=["is_active"])

        support_request.status = "resolved"
        support_request.save(update_fields=["status"])

        messages.success(
            request, f"User '{user.username}' activated and request resolved."
        )
    else:
        messages.error(request, "No matching user found for this request.")

    return redirect(reverse("ledgio_admin"))


@admin_required
def support_inbox_view(request):
    """List all support requests for admin review."""

    support_requests = SupportRequest.objects.all().order_by("-created_at")
    return render(request, "support_inbox.html", {
        "support_requests": support_requests,
    })


# ---------------------------------------------------------------------------
# Admin — Staff Management
# ---------------------------------------------------------------------------

@admin_required
def staff_management_view(request):
    """List all users for staff role management."""

    users = User.objects.all().order_by("-date_joined")
    return render(request, "staff_management.html", {"users": users})


@admin_required
@require_POST
def toggle_staff_status(request, id):
    """Toggle a user's staff status (POST only)."""

    user = get_object_or_404(User, id=id)

    if user == request.user:
        messages.error(request, "You cannot change your own staff status.")
    else:
        user.is_staff = not user.is_staff
        user.save(update_fields=["is_staff"])
        status = "promoted to staff" if user.is_staff else "removed from staff"
        messages.success(request, f"User '{user.username}' {status}.")

    return redirect(reverse("staff_management"))