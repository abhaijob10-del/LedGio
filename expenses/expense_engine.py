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
    "Mandatory Expenses": {
        "Rent": ["rent", "office rent", "rental bill"],
        "Loan": ["loan", "loan payment", "emi"],
        "Insurance": ["insurance"],
        "Tax": ["tax"],
        "Utilities": [
            "electricity bill", "water bill", "current bill", "gas bill"
        ],
    },

    "Maintenance": {
        "Vehicle Maintenance": [
            "car maintenance", "car repair", "vehicle insurance",
            "puc certificate", "engine oil"
        ],
        "Mobile Maintenance": [
            "mobile maintenance", "mobile repair"
        ],
        "Electronics Repair": [
            "electronics repair"
        ],
        "General Maintenance": [
            "maintenance"
        ],
    },

    "Unexpected Expenses": {
        "Emergency": [
            "emergency", "emergency fund", "medical emergencies"
        ],
        "Lost/Damage": [
            "lost item", "hostel damages"
        ],
        "Fines": [
            "traffic fines", "fine"
        ],
        "Vehicle Emergency": [
            "emergency cab ride", "vehicle accident repairs"
        ],
    },

    "Education": {
        "Fees": [
            "tuition fees", "course fees", "exam re-registration fees",
            "backlog fees", "supplementary exam fees",
            "certification course fees"
        ],
        "Study Materials": [
            "books", "stationery"
        ],
        "Project Expenses": [
            "project printing", "project binding", "printing and binding"
        ],
        "Student Essentials": [
            "laptop repair", "lost id card replacement"
        ],
    },

    "Food": {
        "Daily Food": [
            "breakfast", "lunch", "dinner", "snacks", "tea", "coffee", "juice","brunch"
        ],
        "Eating Out": [
            "restaurant", "fast food", "cafe", "food court", "street food",
            "mcdonalds", "kfc", "burger king", "subway", "dominos",
            "pizza hut", "starbucks", "wow momo", "burger singh", "faasos"
        ],
        "Food Delivery": [
            "swiggy", "zomato", "delivery charges", "platform fees",
            "tips to delivery partners"
        ],
        "Groceries": [
            "rice", "vegetables", "fruits", "milk", "eggs", "bread",
            "cooking oil", "spices"
        ],
        "Beverages": [
            "soft drinks", "packaged juices", "coconut water",
            "milkshakes", "bottled water"
        ],
        "Snacks": [
            "chips", "nuts", "chocolates", "biscuits",
            "crackers", "popcorn", "snack bars"
        ],
        "Health & Fitness Food": [
            "protein powder", "protein bars", "energy drinks",
            "electrolytes", "supplements"
        ],
        "Special Occasions": [
            "birthday treats", "party food", "festival food purchases",
            "family dinners", "office treats", "college treats"
        ],
    },

    "Transportation": {
        "Fuel": [
            "petrol", "diesel", "fuel", "ev charging"
        ],
        "Public Transport": [
            "bus", "city bus", "ksrtc bus", "bmtc bus", "best bus",
            "metro", "train", "local train", "suburban train"
        ],
        "Ride Hailing": [
            "uber", "ola", "rapido", "taxi", "cab", "auto"
        ],
        "Parking & Tolls": [
            "parking fees", "parking", "toll charges", "toll"
        ],
        "Travel Tickets": [
            "train tickets", "bus tickets", "flight tickets", "flights"
        ],
    },

    "Travel": {
        "Trip": [
            "trip", "hotel", "accommodation"
        ],
        "Rebooking": [
            "missed train rebooking", "missed flight rebooking",
            "train rebooking", "flight rebooking"
        ],
    },

    "Shopping": {
        "Mall & Hypermarkets" : ["lulu hypermarket","dmart","reliance smart","reliance fresh","more retail","spencer's",
        "star bazaar","big bazaar","lulu mall kochi","phoenix marketcity bengaluru","phoenix marketcity mumbai",
        "forum mall","orion mall","lulu"],
        "Online Shopping": [
            "amazon", "flipkart","meesho","snapdeal","myntra","ajio","nykaa fashion","h&m","zara","purplle"
        ],
        "Clothing": [
            "dress", "shirt", "tshirt", "jeans", "pants",
            "jacket", "hoodie"
        ],
        "Footwear": [
            "shoe", "shoes", "sandals"
        ],
        "Accessories": [
            "watch"
        ],
        "Assets & Major Purchases": [
            "car","bike","motorcycle","scooter","vehicle purchase","laptop",
            "computer","pc","mobile phone","iphone","smartphone","tablet",
            "television","tv","refrigerator","fridge","washing machine",
            "air conditioner","ac","furniture","sofa","bed","wardrobe"
        ]
    },

    "Household": {
        "Cleaning Supplies": [
            "detergent", "soap", "cleaner"
        ],
        "Toiletries": [
            "toothpaste", "toilet paper"
        ],
        "Home Items": [
            "utensils", "bucket", "bedsheet", "pillow", "furniture"
        ],
        "Household Delivery" :["blinkit","zepto","instamart","bigbasket"],

    },

    "Healthcare": {
        "Medical": [
            "hospital", "clinic", "doctor", "medicine", "pharmacy"
        ],
        "Tests": [
            "lab test", "blood test", "scan", "xray"
        ],
        "Special Care": [
            "dental", "physiotherapy", "health checkup"
        ],
    },

    "Personal Care": {
        "Grooming": [
            "salon", "haircut", "shaving"
        ],
        "Skincare & Cosmetics": [
            "cosmetics", "skincare", "toiletries"
        ],
    },

    "Communication": {
        "Mobile": [
            "mobile recharge", "phone bill", "mobile bill",
            "postpaid", "postpaid bill", "data pack",
            "airtel", "jio", "vi", "bsnl"
        ],
        "Internet": [
            "internet", "wifi", "broadband"
        ],
    },

    "Subscriptions": {
        "Entertainment Subscription": [
            "netflix", "spotify", "prime"
        ],
        "General Subscription": [
            "subscription"
        ],
        "Tech Subscription": [
            "hosting"
        ],
    },

    "Entertainment": {
        "Movies & Gaming & Party": [
            "movies", "gaming", "entertainment", "amusement",
        ],
        "Streaming": [
            "streaming"
        ],
    },

    "Investment": {
        "Investments": [
            "stock", "investment", "crypto", "mutual fund"
        ],
    },

    "Business Related": {
        "Work": [
            "work", "office", "travel-work"
        ],
        "Software": [
            "software"
        ],
    },

    "Family Support": {
        "Family": [
            "parents", "family support", "allowance",
            "home transfer", "family expense"
        ],
    },

    "Pets": {
        "Pet Care": [
            "dog food", "cat food", "pet care",
            "veterinary", "pet grooming"
        ],
    },

    "Donations": {
        "Donation": [
            "donation", "charity", "offering",
            "church", "temple", "mosque", "ngo"
        ],
    },

    "Bank Charges": {
        "Charges": [
            "bank charge", "atm fee", "processing fee",
            "transaction fee", "annual fee", "interest charge"
        ],
    },

    "Miscellaneous": {
        "Others": [
            "other", "misc", "miscellaneous", "unknown"
        ],
    },
    "Smoking & Alcohol":{ 
        "Items":[
    "cigarette","cigarettes","smoking","cigar","tobacco","beedi","vape","hookah",
    "beer","wine","whisky","whiskey","vodka","rum","brandy","gin","alcohol","liquor","drinks","bar","pub"
    ],
    },
    "Extra Curricular":{
        "Hobbies": [
    "football","cricket","gym equipment","books","music","photography"
    ],
    },
    "Events & Celebrations": {
        "Events":[
    "wedding","birthday","anniversary","party"
    ]
    }
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
    Auto-detect main category and subcategory from the transaction description.

    Returns:
        (main_category, subcategory)

    Example:
        "kfc dinner" -> ("Food", "Eating Out")
    """

    desc_lower = description.lower()

    for main_category, subcategories in CATEGORY_KEYWORDS.items():

        for subcategory, keywords in subcategories.items():

            if any(keyword in desc_lower for keyword in keywords):

                return main_category, subcategory

    return "Miscellaneous", "Others"


# ---------------------------------------------------------------------------
# Add Transaction
# ---------------------------------------------------------------------------

def add_transaction(user, amount, description, transaction_date, trans_type=None):
    """
    Create a new Transaction for the given user.

    If *trans_type* is not provided, it is auto-detected from the description
    using INCOME_KEYWORDS.
    """

    desc_lower = description.lower()

    if trans_type is None:
        if any(word in desc_lower for word in INCOME_KEYWORDS):
            trans_type = "income"
        else:
            trans_type = "expense"

    if trans_type == "income":
        category = "Income"
        subcategory = "Income"
    else:
        category, subcategory = categorize(description)

    Transaction.objects.create(
        user=user,
        amount=Decimal(str(amount)),
        description=description,
        category=category,
        subcategory=subcategory,
        trans_type=trans_type,
        transaction_date=transaction_date,
    )


# ---------------------------------------------------------------------------
# Get Transactions
# ---------------------------------------------------------------------------

def get_transactions(user, search=None, month=None, trans_type=None):
    """
    Return a list of transaction dicts for the given user.
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
            "subcategory": t.subcategory,
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
    Delete a transaction by ID, scoped to the given user.
    """

    deleted_count, _ = Transaction.objects.filter(
        id=transaction_id,
        user=user
    ).delete()

    return deleted_count > 0


# ---------------------------------------------------------------------------
# Update Transaction
# ---------------------------------------------------------------------------

def update_transaction(transaction_id, user, amount, description,
                       transaction_date, trans_type):
    """
    Update a transaction by ID, scoped to the given user.
    """

    transaction = Transaction.objects.get(
        id=transaction_id,
        user=user
    )

    if trans_type == "income":
        category = "Income"
        subcategory = "Income"
    else:
        category, subcategory = categorize(description)

    transaction.amount = Decimal(str(amount))
    transaction.description = description
    transaction.trans_type = trans_type
    transaction.category = category
    transaction.subcategory = subcategory
    transaction.transaction_date = transaction_date
    transaction.save()


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def get_insights(user):

    expense_qs = Transaction.objects.filter(
        user=user,
        trans_type="expense"
    )

    category_rows = (
        expense_qs
        .values("category")
        .annotate(total=Sum("amount"))
    )

    category_totals = {}
    total_spending = Decimal("0")

    for row in category_rows:
        abs_total = abs(row["total"])
        category_totals[row["category"]] = abs_total
        total_spending += abs_total

    category_totals = dict(
        sorted(
            category_totals.items(),
            key=lambda item: item[1],
            reverse=True
        )
    )

    highest = None

    if category_totals:
        highest = next(iter(category_totals))

    return {
        "total_spending": total_spending,
        "category_totals": category_totals,
        "highest_category": highest,
    }


# ---------------------------------------------------------------------------
# Subcategory Insights
# ---------------------------------------------------------------------------

def get_subcategory_insights(user):
    """
    Return spending totals grouped by subcategory.

    Example:
        Eating Out -> 1200
        Fuel -> 800
    """

    expense_qs = Transaction.objects.filter(
        user=user,
        trans_type="expense"
    )

    subcategory_rows = (
        expense_qs
        .values("subcategory")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    subcategory_totals = {}
    total_spending = Decimal("0")

    for row in subcategory_rows:
        subcategory = row["subcategory"] or "Others"
        abs_total = abs(row["total"])
        subcategory_totals[subcategory] = abs_total
        total_spending += abs_total

    highest_subcategory = None

    if subcategory_totals:
        highest_subcategory = max(
            subcategory_totals,
            key=subcategory_totals.get
        )

    return {
        "total_spending": total_spending,
        "subcategory_totals": subcategory_totals,
        "highest_subcategory": highest_subcategory,
    }


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

def get_balance(user):

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

    if income > 0:
        expense_usage = (expense / income) * 100
        savings_rate = (balance / income) * 100
    else:
        expense_usage = Decimal("0")
        savings_rate = Decimal("0")

    if expense_usage > 100:
        progress_width = 100
    else:
        progress_width = round(expense_usage, 2)

    if balance < 0:
        health_status = "Risk"
        health_title = "Overspending alert"
        health_message = "Your expenses are higher than your income. Review your top spending categories immediately."
    elif balance == 0:
        health_status = "Neutral"
        health_title = "Balanced but tight"
        health_message = "Your income and expenses are equal. Try reducing small recurring expenses to build savings."
    elif savings_rate >= 30:
        health_status = "Excellent"
        health_title = "Excellent position"
        health_message = "You are saving a strong portion of your income. Keep maintaining this habit."
    elif savings_rate >= 10:
        health_status = "Good"
        health_title = "Good position"
        health_message = "You are maintaining a positive balance. Try increasing your savings gradually."
    else:
        health_status = "Needs Attention"
        health_title = "Low savings warning"
        health_message = "Your balance is positive, but savings are low. Review unnecessary expenses."

    return {
        "income": income,
        "expense": expense,
        "balance": balance,
        "expense_usage": round(expense_usage, 2),
        "savings_rate": round(savings_rate, 2),
        "progress_width": progress_width,
        "health_status": health_status,
        "health_title": health_title,
        "health_message": health_message,
    }

# ---------------------------------------------------------------------------
# Monthly Analytics
# ---------------------------------------------------------------------------

def get_monthly_analytics(user):
    """
    Return month-by-month income, expense, and balance.
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


# ---------------------------------------------------------------------------
# Savings Goal Progress
# ---------------------------------------------------------------------------

def get_savings_progress(user):
    """
    Return progress data for the user's current-month savings goal.

    Returns a dict with:
        goal_set       — bool, whether a goal exists for this month
        target         — Decimal, the goal amount (0 if none)
        saved          — Decimal, net balance this month (income - expenses)
        remaining      — Decimal, how much still needed (0 if achieved)
        percentage     — int, progress percentage capped at 100
        bar_width      — int, same as percentage (used in CSS width)
        message        — str, motivational message
        goal_obj       — SavingsGoal instance or None
    """
    from decimal import Decimal
    from django.utils import timezone
    from django.db.models import Sum, Case, When, Value, DecimalField
    from .models import SavingsGoal

    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Fetch this month's goal if it exists
    try:
        goal = SavingsGoal.objects.get(user=user, month=current_month_start.date())
    except SavingsGoal.DoesNotExist:
        goal = None

    if goal is None:
        return {
            "goal_set":  False,
            "target":    Decimal("0"),
            "saved":     Decimal("0"),
            "remaining": Decimal("0"),
            "percentage": 0,
            "bar_width":  0,
            "message":   "Set a savings goal for this month to track your progress.",
            "goal_obj":  None,
        }

    # Income - expenses for the current calendar month
    result = Transaction.objects.filter(
        user=user,
        transaction_date__year=now.year,
        transaction_date__month=now.month,
    ).aggregate(
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

    income  = result["income"]  or Decimal("0")
    expense = abs(result["expense"] or Decimal("0"))
    saved   = income - expense

    target    = goal.target_amount
    remaining = max(target - saved, Decimal("0"))

    if target > 0:
        raw_pct = int((saved / target) * 100)
        percentage = max(0, min(raw_pct, 100))
    else:
        percentage = 0

    bar_width = percentage

    if saved <= 0:
        message = "Start saving this month — every rupee counts! 💪"
    elif percentage >= 100:
        message = "🎉 Goal achieved! Outstanding financial discipline!"
    elif percentage >= 75:
        message = f"Almost there! Just {remaining:.0f} more to go. You've got this! 🚀"
    elif percentage >= 50:
        message = f"Great progress — halfway there! Keep it up! 💡"
    else:
        message = f"You're building momentum. {remaining:.0f} remaining this month."

    # Update status if achieved
    if percentage >= 100 and goal.status != "achieved":
        goal.status = "achieved"
        goal.save(update_fields=["status"])

    return {
        "goal_set":   True,
        "target":     target,
        "saved":      max(saved, Decimal("0")),
        "remaining":  remaining,
        "percentage": percentage,
        "bar_width":  bar_width,
        "message":    message,
        "goal_obj":   goal,
    }