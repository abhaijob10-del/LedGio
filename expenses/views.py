"""
Views for the LedGio expenses application.

Handles dashboard, transactions CRUD, user auth, admin panel,
support requests, staff management, savings goals, and support detail.
"""

import logging
import os
import smtplib
from datetime import timedelta, date

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.core.cache import cache
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings as django_settings
from django.db.models import Count, Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash

from .decorators import admin_required
from .forms import RegistrationForm, SupportRequestForm, TransactionForm, SavingsGoalForm, ProfileUpdateForm, PasswordChangeForm
from .models import SupportRequest, Transaction, UserProfile, SavingsGoal
from .country_data import get_currency_for_country
from .expense_engine import (
    add_transaction,
    get_transactions,
    get_insights,
    get_balance,
    delete_transaction,
    update_transaction,
    get_monthly_analytics,
    get_savings_progress,
    get_financial_alerts,
    categorize_with_explanation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API — Category Suggestion (used by add/edit transaction JS preview)
# ---------------------------------------------------------------------------

@login_required
def api_categorize(request):
    """Lightweight JSON endpoint returning the category suggestion for a
    transaction description.  Called client-side for the live preview box.

    GET /api/categorize/?q=<description>
    Returns: {category, subcategory, confidence, matching_method}
    """
    desc = request.GET.get("q", "").strip()
    result = categorize_with_explanation(desc)
    return JsonResponse({
        "category":        result["category"],
        "subcategory":     result["subcategory"],
        "confidence":      result["confidence"],
        "matching_method": result["matching_method"],
    })


# ---------------------------------------------------------------------------
# Password Reset — Custom View with structured logging
# ---------------------------------------------------------------------------

class LedGioPasswordResetView(PasswordResetView):
    """Wraps Django's PasswordResetView to add structured logging around
    the email send step.  Never alters the reset logic itself.

    Logs:
      - The email address submitted
      - Whether the address matched a user account
      - SMTP success / full exception on failure
    """

    def form_valid(self, form):
        email = form.cleaned_data.get("email", "")
        users = list(form.get_users(email))
        if users:
            logger.info(
                "[password-reset] Email submitted: %s | Matched user: %s",
                email,
                users[0].username,
            )
        else:
            logger.info(
                "[password-reset] Email submitted: %s | No matching active user found",
                email,
            )

        try:
            response = super().form_valid(form)
            if users:
                logger.info(
                    "[password-reset] Reset email dispatched successfully to: %s",
                    email,
                )
            return response
        except smtplib.SMTPAuthenticationError as exc:
            logger.error(
                "[password-reset] SMTP Authentication FAILED for %s: %s",
                email, exc,
            )
            raise
        except smtplib.SMTPException as exc:
            logger.error(
                "[password-reset] SMTP error sending to %s: %s",
                email, exc,
            )
            raise
        except Exception as exc:
            logger.exception(
                "[password-reset] Unexpected error sending reset email to %s",
                email,
            )
            raise


# ---------------------------------------------------------------------------
# /test-email/ — Staff-only SMTP diagnostic view (Step 6 of audit)
# ---------------------------------------------------------------------------

@login_required
def test_email_view(request):
    """Staff-only diagnostic view.  Attempts a real send_mail() and returns
    the result as JSON.  Remove or restrict this view after debugging.

    GET /test-email/
    Returns JSON: {ok: true} or {ok: false, error: "...", type: "..."}
    """
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "Staff only"}, status=403)

    recipient = request.GET.get("to") or request.user.email
    if not recipient:
        return JsonResponse({"ok": False, "error": "No recipient email address set on your account or ?to= param"}, status=400)

    logger.info("[test-email] Sending test email to: %s", recipient)

    try:
        send_mail(
            subject="LedGio SMTP Test",
            message=(
                "This is a test email from LedGio.\n"
                f"Backend: {django_settings.EMAIL_BACKEND}\n"
                f"Host:    {django_settings.EMAIL_HOST}:{django_settings.EMAIL_PORT}\n"
                f"User:    {django_settings.EMAIL_HOST_USER}\n"
            ),
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info("[test-email] Test email sent successfully to: %s", recipient)
        return JsonResponse({"ok": True, "message": f"Test email sent to {recipient}"})

    except smtplib.SMTPAuthenticationError as exc:
        logger.error("[test-email] SMTP Auth failed: %s", exc)
        return JsonResponse({
            "ok": False,
            "error": str(exc),
            "type": "SMTPAuthenticationError",
            "fix": "Gmail App Password is expired or revoked. Go to myaccount.google.com/apppasswords to generate a new one, then update EMAIL_HOST_PASSWORD in .env",
        }, status=500)

    except smtplib.SMTPException as exc:
        logger.error("[test-email] SMTP error: %s", exc)
        return JsonResponse({"ok": False, "error": str(exc), "type": type(exc).__name__}, status=500)

    except BadHeaderError as exc:
        logger.error("[test-email] Bad header: %s", exc)
        return JsonResponse({"ok": False, "error": str(exc), "type": "BadHeaderError"}, status=400)

    except Exception as exc:
        logger.exception("[test-email] Unexpected error")
        return JsonResponse({"ok": False, "error": str(exc), "type": type(exc).__name__}, status=500)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """Main dashboard showing balance, insights, analytics, and recent transactions."""

    balance = get_balance(request.user)
    insights = get_insights(request.user)
    monthly_analytics = get_monthly_analytics(request.user)
    recent_transactions = get_transactions(request.user, limit=5)
    savings_progress = get_savings_progress(request.user)
    financial_alerts = get_financial_alerts(request.user, balance_data=balance)

    # Count open support tickets for dashboard widget (staff only)
    open_support_count = (
        SupportRequest.objects.filter(status="open").count()
        if request.user.is_staff
        else 0
    )

    return render(request, "dashboard.html", {
        "balance": balance,
        "insights": insights,
        "monthly_analytics": monthly_analytics,
        "recent_transactions": recent_transactions,
        "savings_progress": savings_progress,
        "financial_alerts": financial_alerts,
        "open_support_count": open_support_count,
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
    """Show the user's income/expense/balance summary with savings goal."""

    balance = get_balance(request.user)
    savings_progress = get_savings_progress(request.user)

    return render(request, "balance.html", {
        "balance": balance,
        "savings_progress": savings_progress,
    })


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
            country = form.cleaned_data["country"]
            symbol, code = get_currency_for_country(country)

            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                # Account is INACTIVE until email is verified
                is_active=False,
            )

            # Save country + currency to the auto-created UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.country         = country
            profile.currency_symbol = symbol
            profile.currency_code   = code
            profile.save()

            # Send verification email via allauth
            try:
                from allauth.account.utils import send_email_confirmation
                send_email_confirmation(request, user, signup=True)
                messages.success(
                    request,
                    "Account created! Please check your email to verify your account before logging in.",
                )
            except Exception:
                # Fallback: activate immediately if allauth email fails
                user.is_active = True
                user.save(update_fields=["is_active"])
                messages.success(
                    request,
                    "Account created successfully. Please log in.",
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
    """Show and update the user's profile: info, picture, and password."""

    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user)

    savings_progress = get_savings_progress(request.user)

    profile_form = ProfileUpdateForm(
        initial={"username": request.user.username, "email": request.user.email},
        current_user=request.user,
    )
    password_form = PasswordChangeForm(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "")

        # ── Update profile info ──────────────────────────────────────────────
        if action == "update_profile":
            profile_form = ProfileUpdateForm(
                request.POST,
                current_user=request.user,
            )
            if profile_form.is_valid():
                request.user.username = profile_form.cleaned_data["username"]
                request.user.email    = profile_form.cleaned_data["email"]
                request.user.save(update_fields=["username", "email"])
                messages.success(request, "Profile updated successfully.")
                return redirect(reverse("profile"))
            else:
                for field, errs in profile_form.errors.items():
                    for e in errs:
                        messages.error(request, e)

        # ── Upload / remove picture ──────────────────────────────────────────
        elif action == "upload_picture":
            if "profile_picture" in request.FILES:
                pic = request.FILES["profile_picture"]
                # Validate basic image type
                if pic.content_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                    messages.error(request, "Please upload a valid image (JPEG, PNG, GIF, WebP).")
                else:
                    # Remove old picture to save storage
                    if user_profile.profile_picture:
                        try:
                            import os
                            if os.path.isfile(user_profile.profile_picture.path):
                                os.remove(user_profile.profile_picture.path)
                        except Exception:
                            pass
                    user_profile.profile_picture = pic
                    user_profile.save(update_fields=["profile_picture"])
                    messages.success(request, "Profile picture updated.")
            else:
                messages.error(request, "No image file was selected.")
            return redirect(reverse("profile"))

        elif action == "remove_picture":
            if user_profile.profile_picture:
                try:
                    import os
                    if os.path.isfile(user_profile.profile_picture.path):
                        os.remove(user_profile.profile_picture.path)
                except Exception:
                    pass
                user_profile.profile_picture = None
                user_profile.save(update_fields=["profile_picture"])
                messages.success(request, "Profile picture removed.")
            return redirect(reverse("profile"))

        # ── Change password ──────────────────────────────────────────────────
        elif action == "change_password":
            password_form = PasswordChangeForm(request.POST, user=request.user)
            if password_form.is_valid():
                request.user.set_password(password_form.cleaned_data["new_password"])
                request.user.save()
                # Re-authenticate so session stays valid
                update_session_auth_hash(request, request.user)
                messages.success(request, "Password changed successfully.")
                return redirect(reverse("profile"))
            else:
                for field, errs in password_form.errors.items():
                    for e in errs:
                        messages.error(request, e)

    return render(request, "profile.html", {
        "user_profile":  user_profile,
        "savings_progress": savings_progress,
        "profile_form":  profile_form,
        "password_form": password_form,
    })

@require_POST
@login_required
def ajax_change_password(request):
    """AJAX endpoint for changing password (no page reload)."""
    password_form = PasswordChangeForm(request.POST, user=request.user)

    if not password_form.is_valid():
        return JsonResponse({
            "success": False,
            "errors": {field: errs[0] for field, errs in password_form.errors.items()},
        })

    request.user.set_password(password_form.cleaned_data["new_password"])
    request.user.save()
    update_session_auth_hash(request, request.user)

    return JsonResponse({
        "success": True,
        "message": "Password changed successfully.",
    })


# ---------------------------------------------------------------------------
# Savings Goal
# ---------------------------------------------------------------------------

@login_required
def savings_goal_view(request):
    """Set or update the current month's savings goal (with name and deadline)."""

    now = timezone.now()
    current_month = now.replace(day=1).date()

    # Get existing goal for this month if any
    existing_goal = SavingsGoal.objects.filter(
        user=request.user, month=current_month
    ).first()

    if request.method == "POST":
        form = SavingsGoalForm(request.POST, instance=existing_goal)

        if form.is_valid():
            goal = form.save(commit=False)
            goal.user  = request.user
            goal.month = current_month

            if existing_goal:
                goal.pk = existing_goal.pk

            goal.save()
            goal_label = goal.goal_name or f"{now.strftime('%B %Y')} Goal"
            messages.success(
                request,
                f"Savings goal \u2018{goal_label}\u2019 set for {now.strftime('%B %Y')}!"
            )
            return redirect(reverse("balance"))

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")

    else:
        form = SavingsGoalForm(instance=existing_goal)

    savings_progress = get_savings_progress(request.user)

    goal_status = "No Goal"
    days_left = None

    if existing_goal:

        if existing_goal.deadline:
            days_left = (existing_goal.deadline - date.today()).days

        progress = savings_progress.get("progress_percent", 0)

        if progress >= 100:
            goal_status = "Achieved"

        elif days_left is not None and days_left < 0:
            goal_status = "Missed"

        elif progress >= 75:
            goal_status = "On Track"

        else:
            goal_status = "Needs Attention"

    return render(request, "savings_goal.html", {
        "form": form,
        "existing_goal": existing_goal,
        "savings_progress": savings_progress,
        "current_month": now.strftime("%B %Y"),
        "goal_status": goal_status,
        "days_left": days_left,
    })


@login_required
@require_POST
def delete_goal_view(request):
    """Delete the current month's savings goal (POST only)."""

    now = timezone.now()
    current_month = now.replace(day=1).date()

    goal = SavingsGoal.objects.filter(
        user=request.user, month=current_month
    ).first()

    if goal:
        goal_label = goal.goal_name or f"{now.strftime('%B %Y')} Goal"
        goal.delete()
        messages.success(request, f"Goal \u2018{goal_label}\u2019 has been deleted.")
    else:
        messages.error(request, "No active goal found to delete.")

    return redirect(reverse("savings_goal"))


# ---------------------------------------------------------------------------
# Admin — Auto-deactivation
# ---------------------------------------------------------------------------

def auto_deactivate_inactive_users():
    """
    Deactivate non-staff users who haven't logged in for 6+ months.

    Throttled using cache so it runs at most once per hour.
    """
    cache_key = "auto_deactivate_users_last_run"
    if cache.get(cache_key):
        return

    six_months_ago = timezone.now() - timedelta(days=180)

    count = User.objects.filter(
        is_staff=False,
        is_active=True,
        last_login__lt=six_months_ago,
    ).update(is_active=False)

    cache.set(cache_key, True, 3600)

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


@admin_required
def support_detail_view(request, id):
    """Detailed view of a single support request — Feature 6."""

    support_request = get_object_or_404(SupportRequest, id=id)

    # Try to find associated user account from the submitted username/email
    associated_user = User.objects.filter(
        Q(username=support_request.username_or_email)
        | Q(email=support_request.username_or_email)
    ).first()

    # Resolve user profile if found
    user_profile = None
    if associated_user:
        try:
            user_profile = associated_user.profile
        except UserProfile.DoesNotExist:
            pass

    return render(request, "support_detail.html", {
        "support_request": support_request,
        "associated_user": associated_user,
        "user_profile": user_profile,
    })


@admin_required
@require_POST
def update_support_status(request, id):
    """Update the status of a support request (open/pending/resolved)."""

    support_request = get_object_or_404(SupportRequest, id=id)
    new_status = request.POST.get("status", "open")

    valid_statuses = ["open", "pending", "resolved"]
    if new_status in valid_statuses:
        support_request.status = new_status
        support_request.save(update_fields=["status"])
        messages.success(request, f"Request marked as {new_status}.")
    else:
        messages.error(request, "Invalid status.")

    return redirect(reverse("support_detail", args=[id]))


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