"""
Expense Engine — Core business logic for LedGio transactions.

All database queries and financial calculations are centralized here,
keeping views thin and logic testable in isolation.
"""

from decimal import Decimal

from django.db.models import Case, DecimalField, Max, Sum, Value, When
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import SavingsGoal, Transaction, UnknownTransaction

# rapidfuzz for fuzzy matching (installed); difflib as fallback
try:
    from rapidfuzz import fuzz as _rapidfuzz_fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False
    import difflib


# ---------------------------------------------------------------------------
# Category keywords — single source of truth for auto-categorization
# ---------------------------------------------------------------------------

import re

# ---------------------------------------------------------------------------
# Text Normalization Architecture
# ---------------------------------------------------------------------------

class TextNormalizer:
    """Normalizes raw transaction descriptions for robust token & phrase matching.

    Pipeline (applied in order):
    1. Lowercase.
    2. Strip UPI / payment-gateway prefixes  (e.g. 'UPI/123456/SWIGGY' -> 'swiggy').
    3. Convert separators (/ - _ . *) to spaces.
    4. Remove long numeric strings (8+ consecutive digits) and standalone noise numbers.
    5. Collapse whitespace.
    """

    # Matches UPI-style prefixes: UPI/12345/MERCHANT or UPI-REF-MERCHANT
    # The middle group only consumes digits and separators (not letters),
    # so merchant words like SPOTIFY are not swallowed as 'reference IDs'.
    _UPI_PREFIX_RE = re.compile(
        r'\b(?:upi|paytm|gpay|phonepe|phonpe|bhim|neft|imps|rtgs|nach|ecs|pos|nfs|atm)'
        r'[/\-_ ]*[0-9/\-_ ]{0,20}?[/\-_ ]+',
        re.IGNORECASE,
    )
    # Standalone long numeric strings (transaction IDs, reference numbers 8+ digits)
    _LONG_NUMERIC_RE = re.compile(r'\b\d{8,}\b')
    # Short standalone numbers that carry no meaning (1-4 digits that are not
    # part of a brand name — removed AFTER brand matching so brands like '1mg'
    # survive the later normalised pipeline).
    _NOISE_SHORT_NUM_RE = re.compile(r'(?<![a-z])\b\d{1,4}\b(?![a-z])')
    # Separators to convert to spaces
    _SEPARATOR_RE = re.compile(r'[/\-_.*]')

    @classmethod
    def normalize(cls, text):
        if not text:
            return ""
        cleaned = str(text).strip()
        # 1. UPI / gateway prefix stripping (before lowercasing for regex clarity)
        cleaned = cls._UPI_PREFIX_RE.sub(' ', cleaned)
        # 2. Lowercase
        cleaned = cleaned.lower()
        # 3. Separators -> spaces
        cleaned = cls._SEPARATOR_RE.sub(' ', cleaned)
        # 4. Remove long numeric noise (transaction IDs)
        cleaned = cls._LONG_NUMERIC_RE.sub('', cleaned)
        # 5. Keep only alphanumeric, spaces, and '&'
        cleaned = re.sub(r'[^a-z0-9\s&]', ' ', cleaned)
        # 6. Collapse whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @staticmethod
    def tokenize(text):
        normalized = TextNormalizer.normalize(text)
        return normalized.split() if normalized else []


# ---------------------------------------------------------------------------
# Large Keyword Database — 350+ Merchant Names & Financial Keywords
# ---------------------------------------------------------------------------

KEYWORD_RULES = [
    # --- FOOD & DINING ---
    ("mcdonalds", "Food", "Eating Out", 1.0),
    ("mcdonald's", "Food", "Eating Out", 1.0),
    ("kfc", "Food", "Eating Out", 1.0),
    ("dominos", "Food", "Eating Out", 1.0),
    ("domino's", "Food", "Eating Out", 1.0),
    ("pizza hut", "Food", "Eating Out", 1.0),
    ("subway", "Food", "Eating Out", 1.0),
    ("burger king", "Food", "Eating Out", 1.0),
    ("burger singh", "Food", "Eating Out", 1.0),
    ("wow momo", "Food", "Eating Out", 1.0),
    ("faasos", "Food", "Eating Out", 1.0),
    ("dunkin", "Food", "Eating Out", 1.0),
    ("taco bell", "Food", "Eating Out", 1.0),
    ("barbeque nation", "Food", "Eating Out", 1.0),
    ("barbeque", "Food", "Eating Out", 0.9),
    ("barbecue", "Food", "Eating Out", 0.9),
    ("starbucks", "Food", "Eating Out", 1.0),
    ("cafe coffee day", "Food", "Eating Out", 1.0),
    ("ccd", "Food", "Eating Out", 0.8),
    ("chai point", "Food", "Eating Out", 0.95),
    ("chaayos", "Food", "Eating Out", 0.95),
    ("tea post", "Food", "Eating Out", 0.9),
    ("baskin robbins", "Food", "Eating Out", 0.95),
    ("cream stone", "Food", "Eating Out", 0.95),
    ("haldiram", "Food", "Eating Out", 0.95),
    ("bikano", "Food", "Eating Out", 0.95),
    ("saravana bhavan", "Food", "Eating Out", 0.95),
    ("ovenstory", "Food", "Eating Out", 0.95),
    ("behrouz", "Food", "Eating Out", 0.95),

    ("swiggy", "Food", "Food Delivery", 1.0),
    ("zomato", "Food", "Food Delivery", 1.0),
    ("food delivery", "Food", "Food Delivery", 0.9),
    ("delivery charges", "Food", "Food Delivery", 0.85),

    ("restaurant", "Food", "Eating Out", 0.9),
    ("cafe", "Food", "Eating Out", 0.9),
    ("coffee", "Food", "Daily Food", 0.85),
    ("tea", "Food", "Daily Food", 0.85),
    ("chai", "Food", "Daily Food", 0.85),
    ("pizza", "Food", "Eating Out", 0.85),
    ("burger", "Food", "Eating Out", 0.85),
    ("biryani", "Food", "Eating Out", 0.9),
    ("biriyani", "Food", "Eating Out", 0.9),
    ("bakery", "Food", "Eating Out", 0.85),
    ("ice cream", "Food", "Eating Out", 0.85),
    ("juice", "Food", "Beverages", 0.8),
    ("mess", "Food", "Daily Food", 0.85),
    ("canteen", "Food", "Daily Food", 0.85),
    ("breakfast", "Food", "Daily Food", 0.85),
    ("lunch", "Food", "Daily Food", 0.85),
    ("dinner", "Food", "Daily Food", 0.85),
    ("brunch", "Food", "Daily Food", 0.85),
    ("snacks", "Food", "Snacks", 0.85),
    ("snack", "Food", "Snacks", 0.8),

    # --- GROCERIES & HYPERMARKETS ---
    ("dmart", "Shopping", "Mall & Hypermarkets", 1.0),
    ("reliance fresh", "Shopping", "Mall & Hypermarkets", 1.0),
    ("reliance smart", "Shopping", "Mall & Hypermarkets", 1.0),
    ("big bazaar", "Shopping", "Mall & Hypermarkets", 1.0),
    ("more retail", "Shopping", "Mall & Hypermarkets", 1.0),
    ("more supermarket", "Shopping", "Mall & Hypermarkets", 1.0),
    ("spencers", "Shopping", "Mall & Hypermarkets", 0.95),
    ("spencer's", "Shopping", "Mall & Hypermarkets", 0.95),
    ("star bazaar", "Shopping", "Mall & Hypermarkets", 0.95),
    ("lulu hypermarket", "Shopping", "Mall & Hypermarkets", 1.0),
    ("lulu mall", "Shopping", "Mall & Hypermarkets", 0.95),
    ("lulu", "Shopping", "Mall & Hypermarkets", 0.85),
    ("blinkit", "Household", "Household Delivery", 0.95),
    ("zepto", "Household", "Household Delivery", 0.95),
    ("instamart", "Household", "Household Delivery", 0.95),
    ("bigbasket", "Household", "Household Delivery", 0.95),
    ("grocery", "Household", "Home Items", 0.85),
    ("groceries", "Household", "Home Items", 0.85),
    ("supermarket", "Shopping", "Mall & Hypermarkets", 0.85),
    ("vegetables", "Food", "Groceries", 0.85),
    ("veggies", "Food", "Groceries", 0.85),
    ("fruits", "Food", "Groceries", 0.85),
    ("milk", "Food", "Groceries", 0.85),
    ("rice", "Food", "Groceries", 0.85),
    ("dal", "Food", "Groceries", 0.85),
    ("pulses", "Food", "Groceries", 0.85),
    ("eggs", "Food", "Groceries", 0.85),
    ("bread", "Food", "Groceries", 0.85),

    ("protein powder", "Food", "Health & Fitness Food", 0.95),
    ("protein bar", "Food", "Health & Fitness Food", 0.95),
    ("supplements", "Food", "Health & Fitness Food", 0.85),
    ("whey", "Food", "Health & Fitness Food", 0.9),

    # --- TRANSPORTATION & TRAVEL ---
    ("uber", "Transportation", "Ride Hailing", 1.0),
    ("ola", "Transportation", "Ride Hailing", 1.0),
    ("rapido", "Transportation", "Ride Hailing", 1.0),
    ("indrive", "Transportation", "Ride Hailing", 0.95),
    ("bluesmart", "Transportation", "Ride Hailing", 0.95),
    ("taxi", "Transportation", "Ride Hailing", 0.85),
    ("cab", "Transportation", "Ride Hailing", 0.85),
    ("auto", "Transportation", "Ride Hailing", 0.8),
    ("auto rickshaw", "Transportation", "Ride Hailing", 0.9),
    ("airport taxi", "Transportation", "Ride Hailing", 0.95),

    ("petrol", "Transportation", "Fuel", 0.95),
    ("diesel", "Transportation", "Fuel", 0.95),
    ("fuel", "Transportation", "Fuel", 0.9),
    ("ev charging", "Transportation", "Fuel", 0.9),
    ("hp petrol", "Transportation", "Fuel", 0.95),
    ("indian oil", "Transportation", "Fuel", 0.95),
    ("iocl", "Transportation", "Fuel", 0.9),
    ("bpcl", "Transportation", "Fuel", 0.9),
    ("bharat petroleum", "Transportation", "Fuel", 0.95),
    ("shell petrol", "Transportation", "Fuel", 0.95),

    ("bus", "Transportation", "Public Transport", 0.85),
    ("bus ticket", "Transportation", "Travel Tickets", 0.95),
    ("ksrtc", "Transportation", "Public Transport", 0.95),
    ("bmtc", "Transportation", "Public Transport", 0.95),
    ("best bus", "Transportation", "Public Transport", 0.95),
    ("metro", "Transportation", "Public Transport", 0.9),
    ("train", "Transportation", "Public Transport", 0.85),
    ("train ticket", "Transportation", "Travel Tickets", 0.95),
    ("railway", "Transportation", "Public Transport", 0.85),
    ("railway ticket", "Transportation", "Travel Tickets", 0.95),
    ("irctc", "Transportation", "Travel Tickets", 0.95),

    ("flight", "Transportation", "Travel Tickets", 0.9),
    ("flights", "Transportation", "Travel Tickets", 0.9),
    ("flight ticket", "Transportation", "Travel Tickets", 0.95),
    ("flight booking", "Transportation", "Travel Tickets", 0.95),
    ("air india", "Transportation", "Travel Tickets", 0.95),
    ("indigo", "Transportation", "Travel Tickets", 0.95),
    ("spicejet", "Transportation", "Travel Tickets", 0.95),
    ("vistara", "Transportation", "Travel Tickets", 0.95),
    ("akasa", "Transportation", "Travel Tickets", 0.9),

    ("parking", "Transportation", "Parking & Tolls", 0.9),
    ("parking fee", "Transportation", "Parking & Tolls", 0.95),
    ("toll", "Transportation", "Parking & Tolls", 0.9),
    ("toll fee", "Transportation", "Parking & Tolls", 0.95),
    ("fastag", "Transportation", "Parking & Tolls", 0.95),

    ("trip", "Travel", "Trip", 0.85),
    ("hotel", "Travel", "Trip", 0.75),
    ("hotel booking", "Travel", "Trip", 0.95),
    ("accommodation", "Travel", "Trip", 0.9),

    # --- SHOPPING & ELECTRONICS ---
    ("amazon", "Shopping", "Online Shopping", 1.0),
    ("flipkart", "Shopping", "Online Shopping", 1.0),
    ("myntra", "Shopping", "Online Shopping", 1.0),
    ("ajio", "Shopping", "Online Shopping", 1.0),
    ("meesho", "Shopping", "Online Shopping", 1.0),
    ("nykaa", "Shopping", "Online Shopping", 0.95),
    ("snapdeal", "Shopping", "Online Shopping", 0.95),
    ("tata cliq", "Shopping", "Online Shopping", 0.95),

    ("croma", "Shopping", "Assets & Major Purchases", 0.95),
    ("vijay sales", "Shopping", "Assets & Major Purchases", 0.95),
    ("reliance digital", "Shopping", "Assets & Major Purchases", 0.95),
    ("apple store", "Shopping", "Assets & Major Purchases", 0.95),

    ("laptop", "Shopping", "Assets & Major Purchases", 0.9),
    ("laptop purchase", "Shopping", "Assets & Major Purchases", 0.95),
    ("phone", "Shopping", "Assets & Major Purchases", 0.85),
    ("iphone", "Shopping", "Assets & Major Purchases", 0.95),
    ("smartphone", "Shopping", "Assets & Major Purchases", 0.9),
    ("tablet", "Shopping", "Assets & Major Purchases", 0.85),
    ("ipad", "Shopping", "Assets & Major Purchases", 0.95),
    ("electronics", "Shopping", "Assets & Major Purchases", 0.85),
    ("headphones", "Shopping", "Assets & Major Purchases", 0.85),
    ("earphones", "Shopping", "Assets & Major Purchases", 0.85),
    ("television", "Shopping", "Assets & Major Purchases", 0.9),
    ("refrigerator", "Shopping", "Assets & Major Purchases", 0.9),
    ("fridge", "Shopping", "Assets & Major Purchases", 0.85),
    ("washing machine", "Shopping", "Assets & Major Purchases", 0.9),
    ("air conditioner", "Shopping", "Assets & Major Purchases", 0.9),

    ("shoes", "Shopping", "Footwear", 0.9),
    ("shoe", "Shopping", "Footwear", 0.85),
    ("footwear", "Shopping", "Footwear", 0.85),
    ("sandals", "Shopping", "Footwear", 0.85),
    ("sneakers", "Shopping", "Footwear", 0.85),

    ("clothes", "Shopping", "Clothing", 0.85),
    ("clothing", "Shopping", "Clothing", 0.85),
    ("dress", "Shopping", "Clothing", 0.85),
    ("shirt", "Shopping", "Clothing", 0.85),
    ("tshirt", "Shopping", "Clothing", 0.85),
    ("t-shirt", "Shopping", "Clothing", 0.85),
    ("jeans", "Shopping", "Clothing", 0.85),
    ("pants", "Shopping", "Clothing", 0.85),
    ("jacket", "Shopping", "Clothing", 0.85),

    ("watch", "Shopping", "Accessories", 0.85),

    ("furniture", "Shopping", "Assets & Major Purchases", 0.9),
    ("sofa", "Shopping", "Assets & Major Purchases", 0.85),
    ("bed", "Shopping", "Assets & Major Purchases", 0.85),

    ("bookstore", "Education", "Study Materials", 0.9),
    ("books", "Education", "Study Materials", 0.85),
    ("stationery", "Education", "Study Materials", 0.85),

    # --- ENTERTAINMENT & SUBSCRIPTIONS ---
    ("netflix", "Subscriptions", "Entertainment Subscription", 1.0),
    ("spotify", "Subscriptions", "Entertainment Subscription", 1.0),
    ("prime video", "Subscriptions", "Entertainment Subscription", 1.0),
    ("amazon prime", "Subscriptions", "Entertainment Subscription", 1.0),
    ("disney+", "Subscriptions", "Entertainment Subscription", 1.0),
    ("disney hotstar", "Subscriptions", "Entertainment Subscription", 1.0),
    ("hotstar", "Subscriptions", "Entertainment Subscription", 0.95),
    ("youtube premium", "Subscriptions", "Entertainment Subscription", 0.95),
    ("sonyliv", "Subscriptions", "Entertainment Subscription", 0.95),
    ("zee5", "Subscriptions", "Entertainment Subscription", 0.95),

    ("movie", "Entertainment", "Movies & Gaming & Party", 0.85),
    ("movies", "Entertainment", "Movies & Gaming & Party", 0.85),
    ("cinema", "Entertainment", "Movies & Gaming & Party", 0.85),
    ("movie ticket", "Entertainment", "Movies & Gaming & Party", 0.95),
    ("bookmyshow", "Entertainment", "Movies & Gaming & Party", 0.95),
    ("pvr", "Entertainment", "Movies & Gaming & Party", 0.95),
    ("inox", "Entertainment", "Movies & Gaming & Party", 0.95),

    ("game", "Entertainment", "Movies & Gaming & Party", 0.85),
    ("gaming", "Entertainment", "Movies & Gaming & Party", 0.85),
    ("steam", "Entertainment", "Movies & Gaming & Party", 0.95),
    ("playstation", "Entertainment", "Movies & Gaming & Party", 0.95),
    ("xbox", "Entertainment", "Movies & Gaming & Party", 0.95),

    ("concert", "Entertainment", "Movies & Gaming & Party", 0.9),
    ("music festival", "Entertainment", "Movies & Gaming & Party", 0.9),

    # --- HEALTHCARE ---
    ("hospital", "Healthcare", "Medical", 0.95),
    ("clinic", "Healthcare", "Medical", 0.9),
    ("doctor", "Healthcare", "Medical", 0.85),
    ("medicine", "Healthcare", "Medical", 0.9),
    ("medical", "Healthcare", "Medical", 0.85),
    ("medical store", "Healthcare", "Medical", 0.95),
    ("pharmacy", "Healthcare", "Medical", 0.9),
    ("apollo", "Healthcare", "Medical", 0.95),
    ("medplus", "Healthcare", "Medical", 0.95),
    ("pharmeasy", "Healthcare", "Medical", 0.95),

    ("lab test", "Healthcare", "Tests", 0.9),
    ("blood test", "Healthcare", "Tests", 0.95),
    ("scan", "Healthcare", "Tests", 0.85),
    ("xray", "Healthcare", "Tests", 0.85),
    ("health checkup", "Healthcare", "Special Care", 0.9),
    ("dental", "Healthcare", "Special Care", 0.9),
    ("dental clinic", "Healthcare", "Special Care", 0.95),
    ("eye clinic", "Healthcare", "Special Care", 0.9),

    # --- EDUCATION ---
    ("college", "Education", "Fees", 0.85),
    ("school", "Education", "Fees", 0.85),
    ("tuition", "Education", "Fees", 0.9),
    ("tuition fee", "Education", "Fees", 0.95),
    ("exam fee", "Education", "Fees", 0.95),
    ("course fee", "Education", "Fees", 0.9),

    ("udemy", "Education", "Fees", 0.95),
    ("coursera", "Education", "Fees", 0.95),
    ("skillshare", "Education", "Fees", 0.95),
    ("unacademy", "Education", "Fees", 0.95),
    ("certificate", "Education", "Fees", 0.85),
    ("workshop", "Education", "Fees", 0.85),

    # --- UTILITIES & MANDATORY ---
    ("electricity", "Mandatory Expenses", "Utilities", 0.9),
    ("electricity bill", "Mandatory Expenses", "Utilities", 0.95),
    ("current bill", "Mandatory Expenses", "Utilities", 0.95),
    ("water bill", "Mandatory Expenses", "Utilities", 0.95),
    ("gas bill", "Mandatory Expenses", "Utilities", 0.95),
    ("lpg", "Mandatory Expenses", "Utilities", 0.9),

    ("internet", "Communication", "Internet", 0.85),
    ("internet bill", "Communication", "Internet", 0.95),
    ("wifi", "Communication", "Internet", 0.85),
    ("broadband", "Communication", "Internet", 0.9),

    ("airtel", "Communication", "Mobile", 0.95),
    ("jio", "Communication", "Mobile", 0.95),
    ("bsnl", "Communication", "Mobile", 0.95),
    ("vi", "Communication", "Mobile", 0.9),
    ("mobile recharge", "Communication", "Mobile", 0.95),
    ("phone recharge", "Communication", "Mobile", 0.95),
    ("phone bill", "Communication", "Mobile", 0.9),

    ("rent", "Mandatory Expenses", "Rent", 0.95),
    ("house rent", "Mandatory Expenses", "Rent", 0.95),
    ("flat rent", "Mandatory Expenses", "Rent", 0.95),
    ("office rent", "Mandatory Expenses", "Rent", 0.95),
    ("maintenance", "Maintenance", "General Maintenance", 0.85),

    # --- FINANCE & INCOME ---
    ("salary", "Income", "Income", 1.0),
    ("monthly salary", "Income", "Income", 1.0),
    ("bonus", "Income", "Income", 0.95),
    ("freelance", "Income", "Income", 0.95),
    ("freelancing", "Income", "Income", 0.95),
    ("dividend", "Income", "Income", 0.95),
    ("interest", "Income", "Income", 0.85),
    ("refund", "Income", "Income", 0.85),
    ("upi refund", "Income", "Income", 0.9),
    ("cashback", "Income", "Income", 0.85),

    ("investment", "Investment", "Investments", 0.9),
    ("stocks", "Investment", "Investments", 0.9),
    ("stock", "Investment", "Investments", 0.85),
    ("mutual fund", "Investment", "Investments", 0.95),
    ("sip", "Investment", "Investments", 0.9),

    # --- PERSONAL CARE & OTHER ---
    ("salon", "Personal Care", "Grooming", 0.9),
    ("haircut", "Personal Care", "Grooming", 0.9),
    ("spa", "Personal Care", "Grooming", 0.9),
    ("cosmetics", "Personal Care", "Skincare & Cosmetics", 0.9),
    ("skin care", "Personal Care", "Skincare & Cosmetics", 0.9),
    ("skincare", "Personal Care", "Skincare & Cosmetics", 0.9),

    ("gym", "Personal Care", "Grooming", 0.9),
    ("gym membership", "Personal Care", "Grooming", 0.95),
    ("cult fit", "Personal Care", "Grooming", 0.95),
    ("cult.fit", "Personal Care", "Grooming", 0.95),
    ("cult fit gym", "Personal Care", "Grooming", 1.0),
    ("fitness", "Personal Care", "Grooming", 0.85),

    ("bank charge", "Bank Charges", "Charges", 0.9),
    ("atm fee", "Bank Charges", "Charges", 0.9),
    ("dog food", "Pets", "Pet Care", 0.9),
    ("cat food", "Pets", "Pet Care", 0.9),
    ("donation", "Donations", "Donation", 0.9),

    # --- Beverages & Cooking Staples ---
    ("cooking oil", "Food", "Groceries", 0.85),
    ("sunflower oil", "Food", "Groceries", 0.85),
    ("soft drink", "Food", "Beverages", 0.85),
    ("soft drinks", "Food", "Beverages", 0.85),
    ("cola", "Food", "Beverages", 0.8),
    ("coca cola", "Food", "Beverages", 0.9),
    ("pepsi", "Food", "Beverages", 0.85),
    ("energy drink", "Food", "Beverages", 0.85),
    ("cold drink", "Food", "Beverages", 0.85),
    ("spices", "Food", "Groceries", 0.85),
    ("masala", "Food", "Groceries", 0.85),
    ("atta", "Food", "Groceries", 0.85),
    ("wheat flour", "Food", "Groceries", 0.85),
    ("flour", "Food", "Groceries", 0.8),
    ("lentils", "Food", "Groceries", 0.85),
    ("textbooks", "Education", "Study Materials", 0.85),
    ("textbook", "Education", "Study Materials", 0.8),

    # --- Events & Celebrations ---
    ("birthday party", "Events & Celebrations", "Events", 0.9),
    ("anniversary", "Events & Celebrations", "Events", 0.85),
    ("wedding", "Events & Celebrations", "Events", 0.85),
    ("wedding gift", "Events & Celebrations", "Events", 0.9),
    ("celebration", "Events & Celebrations", "Events", 0.85),
    ("amusement park", "Entertainment", "Movies & Gaming & Party", 0.9),
    ("bowling", "Entertainment", "Movies & Gaming & Party", 0.85),
    ("bowling alley", "Entertainment", "Movies & Gaming & Party", 0.9),
    ("festival", "Entertainment", "Movies & Gaming & Party", 0.8),
    ("gift", "Events & Celebrations", "Events", 0.75),
    ("party", "Events & Celebrations", "Events", 0.8),

    # --- Smoking & Alcohol ---
    ("cigarette", "Smoking & Alcohol", "Items", 0.9),
    ("cigar", "Smoking & Alcohol", "Items", 0.85),
    ("tobacco", "Smoking & Alcohol", "Items", 0.85),
    ("beer", "Smoking & Alcohol", "Items", 0.85),
    ("liquor", "Smoking & Alcohol", "Items", 0.9),
    ("wine", "Smoking & Alcohol", "Items", 0.85),
    ("alcohol", "Smoking & Alcohol", "Items", 0.85),
    ("pub", "Smoking & Alcohol", "Items", 0.85),
    ("whisky", "Smoking & Alcohol", "Items", 0.9),
    ("whiskey", "Smoking & Alcohol", "Items", 0.9),
    ("vodka", "Smoking & Alcohol", "Items", 0.9),
    ("gin", "Smoking & Alcohol", "Items", 0.9),

    # --- Hobbies & Extra Curricular ---
    ("yoga", "Personal Care", "Grooming", 0.85),
    ("yoga class", "Personal Care", "Grooming", 0.9),
    ("cricket", "Extra Curricular", "Hobbies", 0.85),
    ("camera", "Extra Curricular", "Hobbies", 0.8),
    ("photography", "Extra Curricular", "Hobbies", 0.85),

    # --- Family Support ---
    ("family allowance", "Family Support", "Family", 0.9),
    ("allowance", "Family Support", "Family", 0.8),
    ("home transfer", "Family Support", "Family", 0.8),
    ("parents allowance", "Family Support", "Family", 0.9),
    ("monthly allowance", "Family Support", "Family", 0.85),

    # --- Pets ---
    ("veterinary", "Pets", "Pet Care", 0.9),
    ("vet", "Pets", "Pet Care", 0.85),
    ("pet food", "Pets", "Pet Care", 0.9),

    # --- Maintenance subtypes ---
    ("vehicle maintenance", "Maintenance", "Vehicle Maintenance", 0.9),
    ("car service", "Maintenance", "Vehicle Maintenance", 0.9),
    ("bike service", "Maintenance", "Vehicle Maintenance", 0.9),
    ("bike wash", "Maintenance", "Vehicle Maintenance", 0.9),
    ("car wash", "Maintenance", "Vehicle Maintenance", 0.9),
    ("engine oil", "Maintenance", "Vehicle Maintenance", 0.9),
    ("puc", "Maintenance", "Vehicle Maintenance", 0.85),
    ("insurance", "Maintenance", "Vehicle Maintenance", 0.8),
    ("repair", "Maintenance", "General Maintenance", 0.8),
    ("screen guard", "Maintenance", "Mobile Maintenance", 0.85),
    ("phone repair", "Maintenance", "Mobile Maintenance", 0.9),
    ("mobile repair", "Maintenance", "Mobile Maintenance", 0.9),
    ("electronics repair", "Maintenance", "Electronics Repair", 0.9),

    # --- Unexpected Expenses / Fines ---
    ("fine", "Unexpected Expenses", "Fines", 0.85),
    ("penalty", "Unexpected Expenses", "Fines", 0.85),
    ("traffic fine", "Unexpected Expenses", "Fines", 0.95),
    ("hostel damage", "Unexpected Expenses", "Lost/Damage", 0.9),
    ("damage", "Unexpected Expenses", "Lost/Damage", 0.75),

    # --- Household Cleaning ---
    ("detergent", "Household", "Cleaning Supplies", 0.9),
    ("cleaning supplies", "Household", "Cleaning Supplies", 0.9),
    ("washing powder", "Household", "Cleaning Supplies", 0.9),
    ("cleaning", "Household", "Cleaning Supplies", 0.75),

    # --- Additional Healthcare ---
    ("netmeds", "Healthcare", "Medical", 0.95),
    ("practo", "Healthcare", "Medical", 0.95),
    ("1mg", "Healthcare", "Medical", 0.95),
    ("ambulance", "Healthcare", "Medical", 0.9),
    ("physiotherapy", "Healthcare", "Special Care", 0.9),
    ("optician", "Healthcare", "Special Care", 0.85),

    # --- Additional Subscriptions & Streaming ---
    ("apple music", "Subscriptions", "Entertainment Subscription", 0.95),
    ("jiosaavn", "Subscriptions", "Entertainment Subscription", 0.95),
    ("gaana", "Subscriptions", "Entertainment Subscription", 0.85),
    ("cinepolis", "Entertainment", "Movies & Gaming & Party", 0.95),

    # --- Additional Education ---
    ("byjus", "Education", "Fees", 0.95),
    ("chegg", "Education", "Fees", 0.85),

    # --- Additional Investments ---
    ("zerodha", "Investment", "Investments", 0.95),
    ("groww", "Investment", "Investments", 0.95),
    ("upstox", "Investment", "Investments", 0.95),
    ("angel one", "Investment", "Investments", 0.9),
    ("crypto", "Investment", "Investments", 0.9),
    ("shares", "Investment", "Investments", 0.85),
    ("equity", "Investment", "Investments", 0.85),
    ("stipend", "Income", "Income", 0.85),

    # --- Gas Brands ---
    ("indane gas", "Mandatory Expenses", "Utilities", 0.95),
    ("bharatgas", "Mandatory Expenses", "Utilities", 0.95),
    ("hp gas", "Mandatory Expenses", "Utilities", 0.95),
]


# Backward-compatibility dictionary structure mapping Category -> Subcategory -> Keywords list
CATEGORY_KEYWORDS = {}
for kw, cat, subcat, _ in KEYWORD_RULES:
    if cat not in CATEGORY_KEYWORDS:
        CATEGORY_KEYWORDS[cat] = {}
    if subcat not in CATEGORY_KEYWORDS[cat]:
        CATEGORY_KEYWORDS[cat][subcat] = []
    if kw not in CATEGORY_KEYWORDS[cat][subcat]:
        CATEGORY_KEYWORDS[cat][subcat].append(kw)


# ---------------------------------------------------------------------------
# Pre-computed normalized keyword rules — built ONCE at module load time.
# Eliminates 380+ TextNormalizer.normalize() calls per categorization call.
# ---------------------------------------------------------------------------

NORMALIZED_KEYWORD_RULES = tuple(
    (TextNormalizer.normalize(kw), kw, cat, subcat, weight)
    for kw, cat, subcat, weight in KEYWORD_RULES
    if TextNormalizer.normalize(kw)  # skip any empty normalizations
)


INCOME_KEYWORDS = [
    "salary", "bonus", "income",
    "freelance", "freelancing", "profit", "dividend", "cashback", "refund",
]


# ---------------------------------------------------------------------------
# Merchant Alias Table
# ---------------------------------------------------------------------------
# Each entry: (alias_pattern, category, subcategory, base_confidence, priority)
# Priority 1 = highest (checked first). Multi-word aliases must appear before
# single-word overlapping aliases (e.g. 'amazon prime video' before 'amazon prime'
# before 'amazon') so more-specific rules win.
#
# alias_pattern is matched as a whole-word substring against the normalized text.
# ---------------------------------------------------------------------------

MERCHANT_ALIASES = [
    # --- Multi-word, highest specificity (priority 1) ---
    ("amazon prime video",  "Subscriptions", "Entertainment Subscription", 1.00, 1),
    ("prime video",          "Subscriptions", "Entertainment Subscription", 1.00, 1),
    ("amazon prime",         "Subscriptions", "Entertainment Subscription", 1.00, 1),
    ("amazon refund",        "Income",         "Income",                     1.00, 1),
    ("netflix autopay",      "Subscriptions", "Entertainment Subscription", 1.00, 1),
    ("netflix india",        "Subscriptions", "Entertainment Subscription", 1.00, 1),
    ("swiggy instamart",     "Food",           "Groceries",                  1.00, 1),
    ("cafe coffee day",      "Food",           "Eating Out",                 1.00, 1),
    ("mc donalds",           "Food",           "Eating Out",                 1.00, 1),
    ("burger king",          "Food",           "Eating Out",                 1.00, 1),
    ("amazon seller",        "Shopping",       "Online Shopping",            0.95, 1),
    ("amazon pay",           "Shopping",       "Online Shopping",            0.95, 1),
    ("swiggy delivery",      "Food",           "Food Delivery",              1.00, 1),
    ("ksrtc bus",            "Transportation", "Public Transport",           1.00, 1),
    ("bmtc bus",             "Transportation", "Public Transport",           1.00, 1),
    ("best bus",             "Transportation", "Public Transport",           1.00, 1),
    # --- Single-word brand aliases (priority 2) ---
    ("amazon",     "Shopping",       "Online Shopping",             1.00, 2),
    ("amzn",       "Shopping",       "Online Shopping",             0.95, 2),
    ("netflix",    "Subscriptions",  "Entertainment Subscription",  1.00, 2),
    ("swiggy",     "Food",           "Food Delivery",               1.00, 2),
    ("instamart",  "Food",           "Groceries",                   0.95, 2),
    ("zomato",     "Food",           "Food Delivery",               1.00, 2),
    ("uber",       "Transportation", "Ride Hailing",                1.00, 2),
    ("ola",        "Transportation", "Ride Hailing",                1.00, 2),
    ("rapido",     "Transportation", "Ride Hailing",                1.00, 2),
    ("starbucks",  "Food",           "Eating Out",                  1.00, 2),
    ("ccd",        "Food",           "Eating Out",                  0.90, 2),
    ("mcdonalds",  "Food",           "Eating Out",                  1.00, 2),
    ("mcd",        "Food",           "Eating Out",                  0.90, 2),
]

# Pre-normalise alias patterns once at module load — same as KEYWORD_RULES.
_NORMALIZED_ALIASES = tuple(
    (TextNormalizer.normalize(alias), cat, subcat, conf, priority)
    for alias, cat, subcat, conf, priority in MERCHANT_ALIASES
    if TextNormalizer.normalize(alias)
)


# ---------------------------------------------------------------------------
# Fuzzy similarity helper
# ---------------------------------------------------------------------------

def _fuzzy_similarity(a: str, b: str) -> float:
    """Return token-set similarity ratio (0-100) between two normalised strings."""
    if _RAPIDFUZZ_AVAILABLE:
        return _rapidfuzz_fuzz.token_set_ratio(a, b)
    # difflib fallback — returns 0-1, scale to 0-100
    return difflib.SequenceMatcher(None, a, b).ratio() * 100.0


# ---------------------------------------------------------------------------
# Scoring-based Categorization Engine
# ---------------------------------------------------------------------------

class CategorizationEngine:
    """Scoring-based intelligent categorization engine with confidence evaluation.

    Rule priority architecture:
        P0 — Merchant Alias exact/substring match (highest specificity)
        P1 — KEYWORD_RULES exact match
        P2 — KEYWORD_RULES multi-word phrase match
        P3 — KEYWORD_RULES single-word token match
        P4 — Fuzzy matching via rapidfuzz (threshold >= 90.0)
        P5 — Fallback: Miscellaneous / Others
    """

    SHORT_WORDS = {"ac", "tv", "pc", "bus", "bar", "car", "vi", "jio", "hp", "tax", "fee", "gym", "tea", "spa"}
    FUZZY_THRESHOLD = 90.0

    @classmethod
    def categorize_with_explanation(cls, description):
        """Full categorization with explainability.

        Returns a dict with keys:
            category, subcategory, confidence,
            matched_keyword, matching_method
        where matching_method is one of:
            'Alias', 'Exact', 'Substring', 'Fuzzy', 'Fallback'
        """
        if not description:
            return {
                "category": "Miscellaneous", "subcategory": "Others",
                "confidence": 0.0, "matched_keyword": None,
                "matching_method": "Fallback",
            }

        norm_text = TextNormalizer.normalize(description)
        tokens = norm_text.split() if norm_text else []

        if not norm_text or not tokens:
            return {
                "category": "Miscellaneous", "subcategory": "Others",
                "confidence": 0.0, "matched_keyword": None,
                "matching_method": "Fallback",
            }

        # ------------------------------------------------------------------
        # P0 — Merchant Alias matching (highest priority)
        # Aliases are stored sorted by priority (1 first) so the first match
        # wins when multiple aliases overlap.
        # ------------------------------------------------------------------
        for norm_alias, cat, subcat, conf, _priority in _NORMALIZED_ALIASES:
            # Exact match
            if norm_alias == norm_text:
                return {
                    "category": cat, "subcategory": subcat,
                    "confidence": round(conf * 100, 1),
                    "matched_keyword": norm_alias,
                    "matching_method": "Alias",
                }
            # Whole-word substring
            pattern = r'\b' + re.escape(norm_alias) + r'\b'
            if re.search(pattern, norm_text):
                return {
                    "category": cat, "subcategory": subcat,
                    "confidence": round(conf * 95, 1),
                    "matched_keyword": norm_alias,
                    "matching_method": "Alias",
                }

        # ------------------------------------------------------------------
        # P1-P3 — KEYWORD_RULES (exact, multi-word, single-word)
        # ------------------------------------------------------------------
        best_category = "Miscellaneous"
        best_subcategory = "Others"
        best_score = 0.0
        best_kw = None
        best_method = "Fallback"

        for norm_kw, _orig_kw, cat, subcat, weight in NORMALIZED_KEYWORD_RULES:
            score = 0.0
            method = ""

            # P1 — Exact match
            if norm_kw == norm_text:
                score = 100.0 * weight
                method = "Exact"

            # Short-word strict token boundary check
            elif norm_kw in cls.SHORT_WORDS:
                if norm_kw in tokens:
                    score = 75.0 * weight
                    method = "Substring"

            # P2 — Multi-word phrase match
            elif " " in norm_kw:
                pat = r'\b' + re.escape(norm_kw) + r'\b'
                if re.search(pat, norm_text):
                    score = 88.0 * weight + min(10.0, len(norm_kw) * 0.4)
                    method = "Substring"

            # P3 — Single token word-boundary match
            else:
                if norm_kw in tokens:
                    score = 75.0 * weight + min(8.0, len(norm_kw) * 0.5)
                    method = "Substring"

            if score > best_score:
                best_score = score
                best_category = cat
                best_subcategory = subcat
                best_kw = norm_kw
                best_method = method

        if best_score >= 40.0:
            return {
                "category": best_category, "subcategory": best_subcategory,
                "confidence": round(min(best_score, 100.0), 1),
                "matched_keyword": best_kw,
                "matching_method": best_method,
            }

        # ------------------------------------------------------------------
        # P4 — Fuzzy matching (threshold >= FUZZY_THRESHOLD)
        # Compare the normalised input against every normalised keyword.
        # ------------------------------------------------------------------
        fuzzy_best_score = 0.0
        fuzzy_cat = "Miscellaneous"
        fuzzy_subcat = "Others"
        fuzzy_kw = None

        for norm_kw, _orig_kw, cat, subcat, weight in NORMALIZED_KEYWORD_RULES:
            sim = _fuzzy_similarity(norm_text, norm_kw)
            if sim >= cls.FUZZY_THRESHOLD and sim * weight > fuzzy_best_score:
                fuzzy_best_score = sim * weight
                fuzzy_cat = cat
                fuzzy_subcat = subcat
                fuzzy_kw = norm_kw

        if fuzzy_best_score >= cls.FUZZY_THRESHOLD * 0.85:  # adjusted for weight dampening
            return {
                "category": fuzzy_cat, "subcategory": fuzzy_subcat,
                "confidence": round(min(fuzzy_best_score, 100.0), 1),
                "matched_keyword": fuzzy_kw,
                "matching_method": "Fuzzy",
            }

        # ------------------------------------------------------------------
        # P5 — Fallback
        # ------------------------------------------------------------------
        return {
            "category": "Miscellaneous", "subcategory": "Others",
            "confidence": round(best_score, 1),
            "matched_keyword": None,
            "matching_method": "Fallback",
        }

    @classmethod
    def categorize_with_confidence(cls, description):
        result = cls.categorize_with_explanation(description)
        return (result["category"], result["subcategory"], result["confidence"])

    @classmethod
    def categorize(cls, description):
        cat, subcat, _ = cls.categorize_with_confidence(description)
        return cat, subcat


# ---------------------------------------------------------------------------
# Unknown Transaction Logger
# ---------------------------------------------------------------------------

def log_unknown_transaction(raw_desc: str, norm_desc: str) -> None:
    """Record or increment an UnknownTransaction entry.

    Designed to be called when the categorization engine falls back to
    Miscellaneous — making blind spots visible for future rule improvement.

    Args:
        raw_desc:  Original description as entered/imported.
        norm_desc: TextNormalizer.normalize(raw_desc) result.
    """
    if not norm_desc:
        return
    try:
        obj = UnknownTransaction.objects.get(normalized_description=norm_desc)
        obj.original_description = raw_desc  # keep latest raw form
        obj.frequency += 1
        obj.save(update_fields=["original_description", "frequency", "last_seen"])
    except UnknownTransaction.DoesNotExist:
        UnknownTransaction.objects.create(
            original_description=raw_desc,
            normalized_description=norm_desc,
        )


# ---------------------------------------------------------------------------
# Public API helpers
# ---------------------------------------------------------------------------

def categorize_with_confidence(description):
    """Public helper to get (category, subcategory, confidence_score)."""
    return CategorizationEngine.categorize_with_confidence(description)


def categorize_with_explanation(description):
    """Public helper returning full categorization dict with explainability.

    Returns:
        dict with keys: category, subcategory, confidence,
                        matched_keyword, matching_method
    """
    return CategorizationEngine.categorize_with_explanation(description)


def categorize(description):
    """
    Auto-detect main category and subcategory from the transaction description.

    Returns:
        (main_category, subcategory)

    Example:
        "kfc dinner" -> ("Food", "Eating Out")
    """
    return CategorizationEngine.categorize(description)



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

def get_transactions(user, search=None, month=None, trans_type=None, limit=None):
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

    if limit:
        qs = qs[:limit]

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
        "goal_name":  goal.goal_name or "Savings Goal",
        "deadline":   goal.deadline,
    }


# ---------------------------------------------------------------------------
# Financial Alerts
# ---------------------------------------------------------------------------

def get_financial_alerts(user, balance_data=None):
    """
    Generate smart financial alerts for the user's dashboard.

    Returns a list of alert dicts:
        type  — 'danger' | 'warning' | 'success' | 'info'
        icon  — emoji icon
        title — short heading
        body  — detail message
    """
    alerts = []
    now = timezone.now()

    # --- Overall balance ---
    if balance_data:
        income = balance_data.get("income", Decimal("0"))
        expense = balance_data.get("expense", Decimal("0"))
        balance = balance_data.get("balance", Decimal("0"))
        savings_rate = balance_data.get("savings_rate", Decimal("0"))
        expense_usage = balance_data.get("expense_usage", Decimal("0"))
    else:
        result = Transaction.objects.filter(user=user).aggregate(
            income=Sum(
                Case(When(trans_type="income", then="amount"),
                     default=Value(0), output_field=DecimalField())
            ),
            expense=Sum(
                Case(When(trans_type="expense", then="amount"),
                     default=Value(0), output_field=DecimalField())
            ),
        )
        income  = result["income"]  or Decimal("0")
        expense = abs(result["expense"] or Decimal("0"))
        balance = income - expense
        savings_rate = (balance / income * 100) if income > 0 else Decimal("0")
        expense_usage = (expense / income * 100) if income > 0 else Decimal("0")

    # Overspending alert
    if balance < 0:
        alerts.append({
            "type": "danger",
            "icon": "🚨",
            "title": "Overspending Alert",
            "body": f"Your expenses exceed your income by {abs(balance):.0f}. Review your spending immediately.",
        })
    elif expense_usage >= 80:
        alerts.append({
            "type": "warning",
            "icon": "⚠️",
            "title": "Budget Warning",
            "body": f"You've used {expense_usage:.0f}% of your income on expenses. Consider cutting back.",
        })

    # Low savings warning
    if 0 < savings_rate < 10 and balance >= 0:
        alerts.append({
            "type": "warning",
            "icon": "💰",
            "title": "Low Savings Warning",
            "body": f"Your savings rate is only {savings_rate:.1f}%. Aim for at least 20% to build financial security.",
        })

    # --- This month's data ---
    month_result = Transaction.objects.filter(
        user=user,
        transaction_date__year=now.year,
        transaction_date__month=now.month,
    ).aggregate(
        income=Sum(
            Case(When(trans_type="income", then="amount"),
                 default=Value(0), output_field=DecimalField())
        ),
        expense=Sum(
            Case(When(trans_type="expense", then="amount"),
                 default=Value(0), output_field=DecimalField())
        ),
        largest_expense=Max(
            Case(When(trans_type="expense", then="amount"),
                 default=Value(0), output_field=DecimalField())
        ),
    )
    month_expense = abs(month_result["expense"] or Decimal("0"))
    largest_expense = abs(month_result["largest_expense"] or Decimal("0"))

    # Large expense warning (single transaction > 5000)
    if largest_expense > Decimal("5000"):
        alerts.append({
            "type": "info",
            "icon": "📊",
            "title": "Large Expense Detected",
            "body": f"A single expense of {largest_expense:.0f} was recorded this month. Make sure this was planned.",
        })

    # --- Last month's data for spending increase comparison ---
    if now.month == 1:
        last_month, last_year = 12, now.year - 1
    else:
        last_month, last_year = now.month - 1, now.year

    last_result = Transaction.objects.filter(
        user=user,
        transaction_date__year=last_year,
        transaction_date__month=last_month,
    ).aggregate(
        expense=Sum(
            Case(When(trans_type="expense", then="amount"),
                 default=Value(0), output_field=DecimalField())
        ),
    )
    last_expense = abs(last_result["expense"] or Decimal("0"))

    if last_expense > 0 and month_expense > last_expense:
        increase_pct = ((month_expense - last_expense) / last_expense) * 100
        if increase_pct >= 20:
            alerts.append({
                "type": "warning",
                "icon": "📈",
                "title": "Monthly Spending Increase",
                "body": f"Your spending is up {increase_pct:.0f}% compared to last month. Track your expenses closely.",
            })

    # --- Goal alerts ---
    try:
        current_month_start = now.replace(day=1).date()
        goal = SavingsGoal.objects.get(user=user, month=current_month_start)

        month_income  = month_result["income"]  or Decimal("0")
        month_saved   = month_income - month_expense
        target        = goal.target_amount

        if target > 0:
            pct = int((month_saved / target) * 100)
            pct = max(0, min(pct, 100))

            goal_name = goal.goal_name or "your savings goal"

            if pct >= 100:
                alerts.append({
                    "type": "success",
                    "icon": "🎉",
                    "title": "Goal Achieved!",
                    "body": f"Congratulations! You have reached {goal_name} this month!",
                })
            elif 60 <= pct < 100:
                remaining = target - month_saved
                alerts.append({
                    "type": "info",
                    "icon": "🎯",
                    "title": "Goal Almost There!",
                    "body": f"You're {pct}% towards {goal_name}. Just {remaining:.0f} more to go!",
                })
    except SavingsGoal.DoesNotExist:
        pass

    return alerts