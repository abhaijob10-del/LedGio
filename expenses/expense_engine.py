from .models import Transaction
from django.db.models import Sum
from django.db.models.functions import TruncMonth

# CATEGORY DETECTION

def categorize(description):

    description = description.lower()

    if any(word in description for word in [
        "kfc", "pizza", "burger", "food",
        "hotel", "restaurant", "tea",
        "snacks", "mandhi"
    ]):
        return "Food"

    elif any(word in description for word in [
        "uber", "bus", "taxi", "petrol",
        "diesel", "auto", "train"
    ]):
        return "Transportation"

    elif any(word in description for word in [
        "amazon", "lulu", "mall",
        "dress", "shoes", "shoe"
    ]):
        return "Shopping"

    elif any(word in description for word in [
        "grocery", "furniture", "gas",
        "fridge", "curtains",
        "electricity", "water bill"
    ]):
        return "Household"

    return "Other"


# ADD TRANSACTION

def add_transaction(user, amount, description, transaction_date, trans_type=None):

    income_keywords = [
        "salary", "bonus", "income",
        "freelance", "profit"
    ]

    desc = description.lower()

    if trans_type is None:

        if any(word in desc for word in income_keywords):
            trans_type = "income"
        else:
            trans_type = "expense"

    category = "Income" if trans_type == "income" else categorize(description)

    Transaction.objects.create(
        user=user,
        amount=float(amount),
        description=description,
        category=category,
        trans_type=trans_type,
        transaction_date=transaction_date
    )

# GET ALL TRANSACTIONS


def get_transactions(user, search=None, month=None, trans_type=None):

    transactions = Transaction.objects.filter(user=user)

    if search:
        transactions = transactions.filter(
            description__icontains=search
        )

    if month:
        year, month_num = month.split("-")

        transactions = transactions.filter(
            transaction_date__year=year,
            transaction_date__month=month_num
        )

    if trans_type:
        transactions = transactions.filter(
            trans_type=trans_type
        )

    transactions = transactions.order_by('-transaction_date')

    data = []

    for t in transactions:

        data.append({
            "id": t.id,
            "amount": t.amount,
            "description": t.description,
            "category": t.category,
            "trans_type": t.trans_type,
            "date": t.transaction_date
        })

    return data

# DELETE TRANSACTION

def delete_transaction(transaction_id):

    Transaction.objects.filter(id=transaction_id).delete()


# UPDATE TRANSACTION

def update_transaction(transaction_id,amount,description,transaction_date,trans_type):

     transaction = Transaction.objects.get(id=transaction_id)

     category = (
        "Income"
        if trans_type == "income"
        else categorize(description)
     )

     transaction.amount = float(amount)

     transaction.description = description

     transaction.trans_type = trans_type

     transaction.category = category

     transaction.transaction_date = transaction_date
     
     transaction.save()


# INSIGHTS

def get_insights(user):

    transactions = Transaction.objects.filter(user=user)

    expense_transactions = transactions.filter(
        trans_type="expense"
    )

    category_totals = {}
    total_spending = 0

    for t in expense_transactions:

        amount = abs(float(t.amount))

        category_totals[t.category] = (
            category_totals.get(t.category, 0) + amount
        )

        total_spending += amount

    highest = None

    if category_totals:
        highest = max(
            category_totals,
            key=category_totals.get
        )

    return {
        "total_spending": total_spending,
        "category_totals": category_totals,
        "highest_category": highest
    }
# BALANCE

# BALANCE

def get_balance(user):

    transactions = Transaction.objects.filter(user=user)

    income = sum(
        float(t.amount)
        for t in transactions
        if t.trans_type == "income"
    )

    expense = sum(
        abs(float(t.amount))
        for t in transactions
        if t.trans_type == "expense"
    )

    balance = income - expense

    return {
        "income": income,
        "expense": expense,
        "balance": balance
    }


def get_monthly_analytics(user):

    transactions = Transaction.objects.filter(user=user)

    monthly_data = (
        transactions
        .annotate(month=TruncMonth('transaction_date'))
        .values('month', 'trans_type')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    analytics = {}

    for item in monthly_data:

        month = item['month'].strftime("%B %Y")

        if month not in analytics:
            analytics[month] = {
                "income": 0,
                "expense": 0,
                "balance": 0
            }

        if item['trans_type'] == 'income':
            analytics[month]["income"] = item['total']
        else:
            analytics[month]["expense"] = abs(item['total'])

        analytics[month]["balance"] = (
            analytics[month]["income"] - analytics[month]["expense"]
        )

    return analytics