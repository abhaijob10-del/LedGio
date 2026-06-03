from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from .models import SupportRequest

from .expense_engine import (
    add_transaction,
    get_transactions,
    get_insights,
    get_balance,
    delete_transaction,
    update_transaction,
    get_monthly_analytics
)


@login_required
def dashboard(request):

    balance = get_balance(request.user)
    insights = get_insights(request.user)
    monthly_analytics = get_monthly_analytics(request.user)
    recent_transactions = get_transactions(request.user)[:5]

    return render(request, 'dashboard.html', {
        'balance': balance,
        'insights': insights,
        'monthly_analytics': monthly_analytics,
        'recent_transactions': recent_transactions
    })


@login_required
def transactions_views(request):

    search = request.GET.get("search")
    month = request.GET.get("month")
    trans_type = request.GET.get("type")

    data = get_transactions(
        request.user,
        search=search,
        month=month,
        trans_type=trans_type
    )

    return render(request, 'transactions.html', {
        'transactions': data,
        'search_query': search,
        'selected_month': month,
        'selected_type': trans_type
    })


@login_required
def add_transaction_view(request):

    if request.method == "POST":

        amount = request.POST.get("amount")
        description = request.POST.get("description")
        transaction_date = request.POST.get("date")
        trans_type = request.POST.get("type")

        if trans_type == "expense":
            amount = -abs(float(amount))
        else:
            amount = abs(float(amount))

        add_transaction(
            request.user,
            amount,
            description,
            transaction_date,
            trans_type
        )

        return redirect('/transactions/')

    return render(request, 'add_transaction.html')


@login_required
def insights(request):

    data = get_insights(request.user)

    return render(request, 'insights.html', {
        'insights': data
    })


@login_required
def delete(request, id):

    delete_transaction(id)

    return redirect('/transactions/')


@login_required
def edit(request, id):

    transactions = get_transactions(request.user)

    transaction = next(
        t for t in transactions
        if t['id'] == id
    )

    if request.method == "POST":

        amount = request.POST.get("amount")
        description = request.POST.get("description")
        transaction_date = request.POST.get("date")
        trans_type = request.POST.get("type")

        if trans_type == "expense":
            amount = -abs(float(amount))
        else:
            amount = abs(float(amount))

        update_transaction(
            id,
            amount,
            description,
            transaction_date,
            trans_type
        )

        return redirect('/transactions/')

    return render(request, 'edit_transaction.html', {
        'transaction': transaction
    })


@login_required
def balance_view(request):

    balance = get_balance(request.user)

    return render(request, 'balance.html', {
        'balance': balance
    })


def register_view(request):

    error = None

    if request.method == "POST":

        username = request.POST["username"].strip()
        email = request.POST["email"].strip()
        password = request.POST["password"]
        confirm_password = request.POST["confirm_password"]

        if password != confirm_password:

            error = "Passwords do not match."

        elif len(password) < 8:

            error = "Password must be at least 8 characters long."

        elif password.isdigit():

            error = "Password cannot contain only numbers."

        elif User.objects.filter(username=username).exists():

            error = "Username already exists."

        elif User.objects.filter(email=email).exists():

            error = "Email already registered."

        else:

            User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            return redirect('/login/')

    return render(request, 'register.html', {
        'error': error
    })

def logout_view(request):

    logout(request)

    return redirect('/login/')
def check_user_availability(request):

    username = request.GET.get("username", "").strip()
    email = request.GET.get("email", "").strip()

    data = {
        "username_exists": False,
        "email_exists": False
    }

    if username:
        data["username_exists"] = User.objects.filter(username=username).exists()

    if email:
        data["email_exists"] = User.objects.filter(email=email).exists()

    return JsonResponse(data)

@login_required
def profile_view(request):

    return render(request, 'profile.html')

def is_admin(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_admin)
def ledgio_admin_view(request):

    users = User.objects.all().order_by('-date_joined')

    support_requests = SupportRequest.objects.all().order_by('-created_at')

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    staff_users = User.objects.filter(is_staff=True).count()
    open_requests = SupportRequest.objects.filter(status="open").count()

    return render(request, 'ledgio_admin.html', {
        'users': users,
        'support_requests': support_requests,
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'staff_users': staff_users,
        'open_requests': open_requests
    })

@login_required
@user_passes_test(is_admin)
def toggle_user_status(request, id):

    user = User.objects.get(id=id)

    if user != request.user:
        user.is_active = not user.is_active
        user.save()

    return redirect('/ledgio-admin/')

def support_view(request):

    success = None

    if request.method == "POST":

        username_or_email = request.POST.get("username_or_email")
        issue_type = request.POST.get("issue_type")
        message = request.POST.get("message")

        SupportRequest.objects.create(
            username_or_email=username_or_email,
            issue_type=issue_type,
            message=message
        )

        success = "Your support request has been submitted successfully."

    return render(request, 'support.html', {
        'success': success
    })


@login_required
@user_passes_test(is_admin)
def resolve_support_request(request, id):

    support_request = SupportRequest.objects.get(id=id)

    support_request.status = "resolved"

    support_request.save()

    return redirect('/ledgio-admin/')


@login_required
@user_passes_test(is_admin)
def activate_user_from_request(request, id):

    support_request = SupportRequest.objects.get(id=id)

    user = User.objects.filter(
        username=support_request.username_or_email
    ).first()

    if user is None:
        user = User.objects.filter(
            email=support_request.username_or_email
        ).first()

    if user:
        user.is_active = True
        user.save()

        support_request.status = "resolved"
        support_request.save()

    return redirect('/ledgio-admin/')

@login_required
@user_passes_test(is_admin)
def users_view(request):

    users = User.objects.all().order_by('-date_joined')

    search = request.GET.get('search')

    if search:
        users = users.filter(
            username__icontains=search
        ) | users.filter(
            email__icontains=search
        )

    return render(request, 'users.html', {
        'users': users
    })
