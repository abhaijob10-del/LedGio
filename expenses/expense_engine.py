"""
Expense Engine — Core business logic for LedGio transactions.

All database queries and financial calculations are centralized here,
keeping views thin and logic testable in isolation.
"""

from decimal import Decimal

from django.db.models import Case, DecimalField, Sum, Value, When
from django.db.models.functions import TruncMonth

from .models import Transaction

# ---------------------------------------------------------------------------
# Category keywords — single source of truth for auto-categorization
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "Food": [
        "kfc", "pizza", "burger", "food",
        "hotel", "restaurant", "tea",
        "snacks", "mandhi",
    ],
    "Transportation": [
        "uber", "bus", "taxi", "petrol",
        "diesel", "auto", "train",
    ],
    "Shopping": [
        "amazon", "lulu", "mall",
        "dress", "shoes", "shoe",
    ],
    "Household": [
        "grocery", "furniture", "gas",
        "fridge", "curtains",
        "electricity", "water bill",
    ],
}

INCOME_KEYWORDS = [
    "salary", "bonus", "income",
    "freelance", "profit",
]


# ---------------------------------------------------------------------------
# Category Detection
# ---------------------------------------------------------------------------

def categorize(description):
    """
    Auto-detect a spending category from the transaction description.

    Matches keywords defined in CATEGORY_KEYWORDS against the
    lowercased description. Returns 'Other' if no match is found.
    """
    desc_lower = description.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(word in desc_lower for word in keywords):
            return category

    return "Other"


# ---------------------------------------------------------------------------
# Add Transaction
# ---------------------------------------------------------------------------

def add_transaction(user, amount, description, transaction_date, trans_type=None):
    """
    Create a new Transaction for the given user.

    If *trans_type* is not provided, it is auto-detected from the description
    using INCOME_KEYWORDS. The category is likewise auto-detected.
    """
    desc_lower = description.lower()

    if trans_type is None:
        if any(word in desc_lower for word in INCOME_KEYWORDS):
            trans_type = "income"
        else:
            trans_type = "expense"

    category = "Income" if trans_type == "income" else categorize(description)

    Transaction.objects.create(
        user=user,
        amount=Decimal(str(amount)),
        description=description,
        category=category,
        trans_type=trans_type,
        transaction_date=transaction_date,
    )


# ---------------------------------------------------------------------------
# Get Transactions
# ---------------------------------------------------------------------------

def get_transactions(user, search=None, month=None, trans_type=None):
    """
    Return a list of transaction dicts for the given user.

    Supports optional filtering by:
    - *search*: case-insensitive substring match on description
    - *month*: string in 'YYYY-MM' format
    - *trans_type*: 'income' or 'expense'
    """
    qs = Transaction.objects.filter(user=user)

    if search:
        qs = qs.filter(description__icontains=search)

    if month:
        year, month_num = month.split("-")
        qs = qs.filter(
            transaction_date__year=int(year),
            transaction_date__month=int(month_num),
        )

    if trans_type:
        qs = qs.filter(trans_type=trans_type)

    qs = qs.order_by("-transaction_date")

    return [
        {
            "id": t.id,
            "amount": t.amount,
            "description": t.description,
            "category": t.category,
            "trans_type": t.trans_type,
            "date": t.transaction_date,
        }
        for t in qs
    ]


# ---------------------------------------------------------------------------
# Delete Transaction
# ---------------------------------------------------------------------------

def delete_transaction(transaction_id, user):
    """
    Delete a transaction by ID, scoped to the given user (IDOR protection).

    Returns True if a row was deleted, False otherwise.
    """
    deleted_count, _ = Transaction.objects.filter(
        id=transaction_id, user=user
    ).delete()
    return deleted_count > 0


# ---------------------------------------------------------------------------
# Update Transaction
# ---------------------------------------------------------------------------

def update_transaction(transaction_id, user, amount, description,
                       transaction_date, trans_type):
    """
    Update a transaction by ID, scoped to the given user (IDOR protection).

    Raises Transaction.DoesNotExist if not found.
    """
    transaction = Transaction.objects.get(id=transaction_id, user=user)

    category = "Income" if trans_type == "income" else categorize(description)

    transaction.amount = Decimal(str(amount))
    transaction.description = description
    transaction.trans_type = trans_type
    transaction.category = category
    transaction.transaction_date = transaction_date
    transaction.save()


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def get_insights(user):
    """
    Return spending insights for the user.

    Uses DB-level aggregation instead of Python loops for efficiency.
    Returns a dict with:
    - total_spending: sum of all expense amounts (positive)
    - category_totals: dict mapping category → total (positive)
    - highest_category: the category with the largest spend, or None
    """
    expense_qs = Transaction.objects.filter(user=user, trans_type="expense")

    # Aggregate totals per category at the DB level
    category_rows = (
        expense_qs
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    category_totals = {}
    total_spending = Decimal("0")

    for row in category_rows:
        # amounts are stored negative for expenses; take abs
        abs_total = abs(row["total"])
        category_totals[row["category"]] = abs_total
        total_spending += abs_total

    highest = None
    if category_totals:
        highest = max(category_totals, key=category_totals.get)

    return {
        "total_spending": total_spending,
        "category_totals": category_totals,
        "highest_category": highest,
    }


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

def get_balance(user):
    """
    Calculate income, expense, and net balance for the user.

    Uses a single DB query with conditional aggregation.
    """
    result = Transaction.objects.filter(user=user).aggregate(
        income=Sum(
            Case(
                When(trans_type="income", then="amount"),
                default=Value(0),
                output_field=DecimalField(),
            )
        ),
        expense=Sum(
            Case(
                When(trans_type="expense", then="amount"),
                default=Value(0),
                output_field=DecimalField(),
            )
        ),
    )

    income = result["income"] or Decimal("0")
    expense = abs(result["expense"] or Decimal("0"))
    balance = income - expense

    return {
        "income": income,
        "expense": expense,
        "balance": balance,
    }


# ---------------------------------------------------------------------------
# Monthly Analytics
# ---------------------------------------------------------------------------

def get_monthly_analytics(user):
    """
    Return a month-by-month breakdown of income, expense, and balance.

    Returns an OrderedDict-style dict keyed by 'Month YYYY' strings.
    """
    monthly_data = (
        Transaction.objects.filter(user=user)
        .annotate(month=TruncMonth("transaction_date"))
        .values("month", "trans_type")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    analytics = {}

    for item in monthly_data:
        month_label = item["month"].strftime("%B %Y")

        if month_label not in analytics:
            analytics[month_label] = {
                "income": Decimal("0"),
                "expense": Decimal("0"),
                "balance": Decimal("0"),
            }

        if item["trans_type"] == "income":
            analytics[month_label]["income"] = item["total"]
        else:
            analytics[month_label]["expense"] = abs(item["total"])

        analytics[month_label]["balance"] = (
            analytics[month_label]["income"]
            - analytics[month_label]["expense"]
        )

    return analytics