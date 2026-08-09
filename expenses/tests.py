"""
Comprehensive test suite for the LedGio expenses application.

Covers: models, expense_engine logic, views (auth, IDOR, POST-only),
registration validation, and admin access control.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from .expense_engine import (
    categorize,
    categorize_with_confidence,
    categorize_with_explanation,
    log_unknown_transaction,
    add_transaction,
    get_balance,
    get_insights,
    get_transactions,
)
from .models import Transaction, SupportRequest, UnknownTransaction


# ===================================================================
# Model Tests
# ===================================================================

class UserModelTest(TestCase):
    """Tests for Django User model creation."""

    def test_user_creation(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@gmail.com",
            password="Test123@",
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@gmail.com")
        self.assertTrue(user.check_password("Test123@"))


class TransactionModelTest(TestCase):
    """Tests for the Transaction model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            password="pass12345",
        )

    def test_transaction_creation(self):
        transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("1000.00"),
            description="Salary",
            category="Income",
            trans_type="income",
        )
        self.assertEqual(transaction.amount, Decimal("1000.00"))
        self.assertEqual(transaction.category, "Income")

    def test_transaction_str(self):
        transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("500.00"),
            description="Groceries",
            category="Household",
            trans_type="expense",
        )
        self.assertIn("Groceries", str(transaction))
        self.assertIn("500", str(transaction))

    def test_default_ordering(self):
        """Transactions should be ordered by -transaction_date by default."""
        t1 = Transaction.objects.create(
            user=self.user,
            amount=Decimal("100"),
            description="First",
            category="Other",
            trans_type="expense",
        )
        t2 = Transaction.objects.create(
            user=self.user,
            amount=Decimal("200"),
            description="Second",
            category="Other",
            trans_type="expense",
        )
        transactions = list(Transaction.objects.filter(user=self.user))
        # Most recent (t2) should come first
        self.assertEqual(transactions[0].id, t2.id)


class SupportRequestModelTest(TestCase):
    """Tests for the SupportRequest model."""

    def test_support_request_creation(self):
        sr = SupportRequest.objects.create(
            username_or_email="testuser@example.com",
            issue_type="concern",
            message="I have a concern about my account.",
        )
        self.assertEqual(sr.status, "open")
        self.assertIn("testuser@example.com", str(sr))


# ===================================================================
# Expense Engine Tests
# ===================================================================

class CategorizeTest(TestCase):
    """Tests for the categorize() auto-detection function."""

    def test_food_keywords(self):
        self.assertEqual(categorize("KFC dinner"), ("Food", "Eating Out"))
        self.assertEqual(categorize("pizza hut order"), ("Food", "Eating Out"))
        self.assertEqual(categorize("snacks from store"), ("Food", "Snacks"))

    def test_transportation_keywords(self):
        self.assertEqual(categorize("uber ride"), ("Transportation", "Ride Hailing"))
        self.assertEqual(categorize("bus ticket"), ("Transportation", "Travel Tickets"))
        self.assertEqual(categorize("petrol fill"), ("Transportation", "Fuel"))

    def test_shopping_keywords(self):
        self.assertEqual(categorize("amazon order"), ("Shopping", "Online Shopping"))
        self.assertEqual(categorize("new shoes"), ("Shopping", "Footwear"))

    def test_household_keywords(self):
        self.assertEqual(categorize("furniture purchase"), ("Shopping", "Assets & Major Purchases"))
        self.assertEqual(categorize("detergent"), ("Household", "Cleaning Supplies"))

    def test_unknown_defaults_to_miscellaneous(self):
        self.assertEqual(categorize("random stuff"), ("Miscellaneous", "Others"))
        self.assertEqual(categorize(""), ("Miscellaneous", "Others"))

    def test_case_insensitive(self):
        self.assertEqual(categorize("KFC DINNER"), ("Food", "Eating Out"))
        self.assertEqual(categorize("UBER ride"), ("Transportation", "Ride Hailing"))


class ExpandedCategorizationEngineTest(TestCase):
    """Comprehensive test suite testing 250+ real-world transactions across all categories."""

    SAMPLE_TRANSACTIONS = [
        # --- Food & Dining (40) ---
        ("Coffee", "Food", "Daily Food"),
        ("Hot Tea", "Food", "Daily Food"),
        ("Chai at stall", "Food", "Daily Food"),
        ("Netflix", "Subscriptions", "Entertainment Subscription"),
        ("Amazon", "Shopping", "Online Shopping"),
        ("Swiggy food order", "Food", "Food Delivery"),
        ("Zomato dinner", "Food", "Food Delivery"),
        ("Chicken Biryani", "Food", "Eating Out"),
        ("Mutton Biriyani", "Food", "Eating Out"),
        ("Uber cab ride", "Transportation", "Ride Hailing"),
        ("Petrol refill", "Transportation", "Fuel"),
        ("Monthly Salary", "Income", "Income"),
        ("Freelancing project payment", "Income", "Income"),
        ("Electricity Bill payment", "Mandatory Expenses", "Utilities"),
        ("Hospital admission", "Healthcare", "Medical"),
        ("Medicine purchase", "Healthcare", "Medical"),
        ("Spotify Premium", "Subscriptions", "Entertainment Subscription"),
        ("Domino's Pizza", "Food", "Eating Out"),
        ("Flipkart order", "Shopping", "Online Shopping"),
        ("Gym membership", "Extra Curricular", "Hobbies"),
        ("Protein Powder", "Food", "Health & Fitness Food"),
        ("Bus Ticket to Bangalore", "Transportation", "Travel Tickets"),
        ("Laptop Purchase", "Shopping", "Assets & Major Purchases"),
        ("Hotel Booking in Goa", "Travel", "Trip"),
        ("Movie Ticket BookMyShow", "Entertainment", "Movies & Gaming & Party"),
        ("Airport Taxi ride", "Transportation", "Ride Hailing"),
        ("Medical Store chemist", "Healthcare", "Medical"),
        ("Books from Amazon", "Shopping", "Online Shopping"),
        ("Tuition Fee payment", "Education", "Fees"),
        ("Phone Recharge Airtel", "Communication", "Mobile"),
        ("Internet Bill JioFiber", "Communication", "Internet"),
        ("Water Bill BBMP", "Mandatory Expenses", "Utilities"),
        ("Mutual Fund SIP", "Investment", "Investments"),
        ("Stock Dividend income", "Income", "Income"),
        ("Parking Fee at mall", "Transportation", "Parking & Tolls"),
        ("Fresh Vegetables", "Food", "Groceries"),
        ("Packet Milk Nandini", "Food", "Groceries"),
        ("Dmart Grocery shopping", "Shopping", "Mall & Hypermarkets"),
        ("Railway Ticket IRCTC", "Transportation", "Travel Tickets"),
        ("Flight Booking Indigo", "Transportation", "Travel Tickets"),
        ("McDonald's Meal", "Food", "Eating Out"),
        ("Burger King Whopper", "Food", "Eating Out"),
        ("Subway Club Sandwich", "Food", "Eating Out"),
        ("Starbucks Cappuccino", "Food", "Eating Out"),
        ("Barbeque Nation Buffet", "Food", "Eating Out"),
        ("Faasos Wrap", "Food", "Eating Out"),
        ("Wow Momo treats", "Food", "Eating Out"),
        ("Taco Bell Tacos", "Food", "Eating Out"),
        ("Dunkin Donuts", "Food", "Eating Out"),
        ("Chai Point ginger tea", "Food", "Eating Out"),
        ("Baskin Robbins Scoop", "Food", "Eating Out"),
        ("Haldiram sweets", "Food", "Eating Out"),
        ("Bikano namkeen", "Food", "Eating Out"),
        ("Saravana Bhavan South Indian", "Food", "Eating Out"),
        ("Ovenstory Pizza", "Food", "Eating Out"),
        ("Behrouz Biryani", "Food", "Eating Out"),
        ("Breakfast at Canteen", "Food", "Daily Food"),
        ("Lunch at Mess", "Food", "Daily Food"),
        ("Brunch with friends", "Food", "Daily Food"),
        ("Evening Snacks", "Food", "Snacks"),
        ("Bakery cake", "Food", "Eating Out"),

        # --- Groceries & Supplies (25) ---
        ("Reliance Fresh Vegetables", "Shopping", "Mall & Hypermarkets"),
        ("Reliance Smart Supermarket", "Shopping", "Mall & Hypermarkets"),
        ("Big Bazaar hypermarket", "Shopping", "Mall & Hypermarkets"),
        ("More Retail grocery", "Shopping", "Mall & Hypermarkets"),
        ("Spencer's Store", "Shopping", "Mall & Hypermarkets"),
        ("Star Bazaar hypermarket", "Shopping", "Mall & Hypermarkets"),
        ("Lulu Hypermarket Kochi", "Shopping", "Mall & Hypermarkets"),
        ("Blinkit instant grocery", "Household", "Household Delivery"),
        ("Zepto 10min delivery", "Household", "Household Delivery"),
        ("Instamart Swiggy delivery", "Food", "Groceries"),
        ("Bigbasket monthly groceries", "Household", "Household Delivery"),
        ("Daily Fruits and apples", "Food", "Groceries"),
        ("Rice bag 10kg", "Food", "Groceries"),
        ("Toor Dal 2kg", "Food", "Groceries"),
        ("Farm fresh Eggs", "Food", "Groceries"),
        ("Brown Bread loaf", "Food", "Groceries"),
        ("Whey Protein Supplement", "Food", "Health & Fitness Food"),
        ("Protein Bar snack", "Food", "Health & Fitness Food"),
        ("Supermarket groceries", "Shopping", "Mall & Hypermarkets"),
        ("Cooking Oil Sunflower", "Food", "Groceries"),
        ("Pulses & Lentils", "Food", "Groceries"),
        ("Veggies market", "Food", "Groceries"),
        ("Spices and Masalas", "Food", "Groceries"),
        ("Atta Wheat flour", "Food", "Groceries"),
        ("Soft drinks Coca Cola", "Food", "Beverages"),

        # --- Transportation (25) ---
        ("Ola Cab auto ride", "Transportation", "Ride Hailing"),
        ("Rapido Bike Taxi", "Transportation", "Ride Hailing"),
        ("InDrive ride fare", "Transportation", "Ride Hailing"),
        ("BluSmart EV Taxi", "Transportation", "Ride Hailing"),
        ("Auto Rickshaw fare", "Transportation", "Ride Hailing"),
        ("Diesel Fuel fill", "Transportation", "Fuel"),
        ("EV Charging station", "Transportation", "Fuel"),
        ("HP Petrol Pump", "Transportation", "Fuel"),
        ("Indian Oil Fuel Depot", "Transportation", "Fuel"),
        ("IOCL Petrol bunk", "Transportation", "Fuel"),
        ("BPCL Diesel Station", "Transportation", "Fuel"),
        ("Bharat Petroleum Bunk", "Transportation", "Fuel"),
        ("Shell Petrol station", "Transportation", "Fuel"),
        ("City Bus ticket", "Transportation", "Public Transport"),
        ("KSRTC Volvo Bus", "Transportation", "Public Transport"),
        ("BMTC Bus Pass", "Transportation", "Public Transport"),
        ("BEST Bus fare", "Transportation", "Public Transport"),
        ("Metro Smart Card Recharge", "Transportation", "Public Transport"),
        ("Local Train Pass", "Transportation", "Public Transport"),
        ("Air India Flight Ticket", "Transportation", "Travel Tickets"),
        ("SpiceJet Flight Booking", "Transportation", "Travel Tickets"),
        ("Vistara Air Ticket", "Transportation", "Travel Tickets"),
        ("Akasa Air Flight", "Transportation", "Travel Tickets"),
        ("Fastag Recharge Toll", "Transportation", "Parking & Tolls"),
        ("Toll Charge NH44", "Transportation", "Parking & Tolls"),

        # --- Shopping & Electronics (30) ---
        ("Myntra Fashion clothes", "Shopping", "Online Shopping"),
        ("Ajio Trend shopping", "Shopping", "Online Shopping"),
        ("Meesho dress order", "Shopping", "Online Shopping"),
        ("Nykaa Beauty order", "Shopping", "Online Shopping"),
        ("Snapdeal online deal", "Shopping", "Online Shopping"),
        ("Tata CLiQ electronics", "Shopping", "Online Shopping"),
        ("Croma Electronics store", "Shopping", "Assets & Major Purchases"),
        ("Vijay Sales TV purchase", "Shopping", "Assets & Major Purchases"),
        ("Reliance Digital Smartphone", "Shopping", "Assets & Major Purchases"),
        ("Apple Store iPhone 15", "Shopping", "Assets & Major Purchases"),
        ("iPhone 15 Pro", "Shopping", "Assets & Major Purchases"),
        ("Samsung Smartphone", "Shopping", "Assets & Major Purchases"),
        ("iPad Air Tablet", "Shopping", "Assets & Major Purchases"),
        ("Sony Wireless Headphones", "Shopping", "Assets & Major Purchases"),
        ("LG Refrigerator Fridge", "Shopping", "Assets & Major Purchases"),
        ("Washing Machine Samsung", "Shopping", "Assets & Major Purchases"),
        ("Daikin Air Conditioner AC", "Shopping", "Assets & Major Purchases"),
        ("Nike Running Shoes", "Shopping", "Footwear"),
        ("Leather Sandals", "Shopping", "Footwear"),
        ("Adidas Sneakers", "Shopping", "Footwear"),
        ("Formal Shirt", "Shopping", "Clothing"),
        ("Cotton Dress", "Shopping", "Clothing"),
        ("Blue Jeans Levi's", "Shopping", "Clothing"),
        ("Winter Jacket", "Shopping", "Clothing"),
        ("Fossil Wrist Watch", "Shopping", "Accessories"),
        ("Wooden Sofa Set", "Shopping", "Assets & Major Purchases"),
        ("King Size Bed Mattress", "Shopping", "Assets & Major Purchases"),
        ("Study Table Furniture", "Shopping", "Assets & Major Purchases"),
        ("School Stationery Notebooks", "Education", "Study Materials"),
        ("College Textbooks", "Education", "Study Materials"),

        # --- Subscriptions & Entertainment (20) ---
        ("Prime Video Subscription", "Subscriptions", "Entertainment Subscription"),
        ("Disney+ Hotstar Annual", "Subscriptions", "Entertainment Subscription"),
        ("Hotstar Premium", "Subscriptions", "Entertainment Subscription"),
        ("YouTube Premium Subscription", "Subscriptions", "Entertainment Subscription"),
        ("SonyLIV Special", "Subscriptions", "Entertainment Subscription"),
        ("Zee5 Premium Pack", "Subscriptions", "Entertainment Subscription"),
        ("PVR Cinema Ticket", "Entertainment", "Movies & Gaming & Party"),
        ("INOX Movie Show", "Entertainment", "Movies & Gaming & Party"),
        ("Cinepolis Movie Hall", "Entertainment", "Movies & Gaming & Party"),
        ("Steam Game Purchase", "Entertainment", "Movies & Gaming & Party"),
        ("PlayStation PSN Store", "Entertainment", "Movies & Gaming & Party"),
        ("Xbox Game Pass", "Entertainment", "Movies & Gaming & Party"),
        ("Live Music Concert Ticket", "Entertainment", "Movies & Gaming & Party"),
        ("Amusement Park Pass", "Entertainment", "Movies & Gaming & Party"),
        ("Bowling Alley game", "Entertainment", "Movies & Gaming & Party"),
        ("Birthday Party Booking", "Events & Celebrations", "Events"),
        ("Festival Special Event", "Entertainment", "Movies & Gaming & Party"),
        ("Apple Music Subscription", "Subscriptions", "Entertainment Subscription"),
        ("JioSaavn Pro", "Subscriptions", "Entertainment Subscription"),
        ("Gaana Plus", "Subscriptions", "Entertainment Subscription"),

        # --- Healthcare (20) ---
        ("Apollo Hospital Doctor Consultation", "Healthcare", "Medical"),
        ("MedPlus Pharmacy Medicine", "Healthcare", "Medical"),
        ("PharmEasy Online Medicine", "Healthcare", "Medical"),
        ("1mg Healthcare Test", "Healthcare", "Medical"),
        ("Dr Lal PathLabs Blood Test", "Healthcare", "Tests"),
        ("Metropolis Diagnostic Scan", "Healthcare", "Tests"),
        ("Xray and MRI Scan", "Healthcare", "Tests"),
        ("Annual Health Checkup", "Healthcare", "Special Care"),
        ("Dental Clinic Root Canal", "Healthcare", "Special Care"),
        ("Eye Clinic Spectacles", "Healthcare", "Special Care"),
        ("Physiotherapy session", "Healthcare", "Special Care"),
        ("Ambulance Service", "Healthcare", "Medical"),
        ("Doctor fees", "Healthcare", "Medical"),
        ("Chemist Medical Shop", "Healthcare", "Medical"),
        ("Apollo Pharmacy Tablets", "Healthcare", "Medical"),
        ("Netmeds Order", "Healthcare", "Medical"),
        ("Practo Consultation", "Healthcare", "Medical"),
        ("Dental Teeth Cleaning", "Healthcare", "Special Care"),
        ("Blood Pressure Checkup", "Healthcare", "Special Care"),
        ("Optician Eye Glasses", "Healthcare", "Special Care"),

        # --- Education & Learning (15) ---
        ("School Tuition Fee", "Education", "Fees"),
        ("College Semester Fee", "Education", "Fees"),
        ("Udemy Python Course", "Education", "Fees"),
        ("Coursera Specialization Certificate", "Education", "Fees"),
        ("Skillshare Annual Course", "Education", "Fees"),
        ("Unacademy Subscription", "Education", "Fees"),
        ("Certification Exam Fee", "Education", "Fees"),
        ("AI Workshop Registration", "Education", "Fees"),
        ("Engineering Textbooks", "Education", "Study Materials"),
        ("School Supplies Pens", "Education", "Study Materials"),
        ("Project Printing and Binding", "Education", "Fees"),
        ("Lab Manual Books", "Education", "Study Materials"),
        ("Backlog Exam Re-registration Fee", "Education", "Fees"),
        ("BYJU'S Learning Pack", "Education", "Fees"),
        ("Chegg Study Subscription", "Education", "Fees"),

        # --- Utilities & Mandatory (20) ---
        ("Electricity Bill BESCOM", "Mandatory Expenses", "Utilities"),
        ("Current Bill payment", "Mandatory Expenses", "Utilities"),
        ("Water Bill BWSSB", "Mandatory Expenses", "Utilities"),
        ("LPG Gas Cylinder Refill", "Mandatory Expenses", "Utilities"),
        ("Indane Gas Booking", "Mandatory Expenses", "Utilities"),
        ("Bharatgas LPG Cylinder", "Mandatory Expenses", "Utilities"),
        ("HP Gas Booking", "Mandatory Expenses", "Utilities"),
        ("Airtel Postpaid Bill", "Communication", "Mobile"),
        ("Jio Prepaid Recharge", "Communication", "Mobile"),
        ("VI Unlimited Data Pack", "Communication", "Mobile"),
        ("BSNL Landline Bill", "Communication", "Mobile"),
        ("ACT Fibernet Internet Bill", "Communication", "Internet"),
        ("Hathway Broadband Wifi", "Communication", "Internet"),
        ("Monthly House Rent", "Mandatory Expenses", "Rent"),
        ("Flat Rent Transfer", "Mandatory Expenses", "Rent"),
        ("Office Space Rent", "Mandatory Expenses", "Rent"),
        ("Society Maintenance Charge", "Maintenance", "General Maintenance"),
        ("Car Maintenance Service", "Maintenance", "Vehicle Maintenance"),
        ("Mobile Phone Repair", "Maintenance", "Mobile Maintenance"),
        ("Electronics Repair Service", "Maintenance", "Electronics Repair"),

        # --- Finance & Income (20) ---
        ("Salary credit from employer", "Income", "Income"),
        ("Annual Performance Bonus", "Income", "Income"),
        ("Stipend for internship", "Income", "Income"),
        ("Upwork Freelance Income", "Income", "Income"),
        ("Fiverr Project Payout", "Income", "Income"),
        ("Stock Market Dividend", "Income", "Income"),
        ("Savings Account Interest", "Income", "Income"),
        ("Amazon UPI Refund", "Income", "Income"),
        ("Cashback Reward Credit", "Income", "Income"),
        ("Zerodha Mutual Fund SIP", "Investment", "Investments"),
        ("Groww Stocks Investment", "Investment", "Investments"),
        ("Upstox Shares Purchase", "Investment", "Investments"),
        ("Angel One Equity SIP", "Investment", "Investments"),
        ("Crypto Investment BTC", "Investment", "Investments"),
        ("Bank ATM Withdrawal Fee", "Bank Charges", "Charges"),
        ("Annual Debit Card Charge", "Bank Charges", "Charges"),
        ("Bank Processing Fee", "Bank Charges", "Charges"),
        ("Parents Monthly Allowance", "Family Support", "Family"),
        ("Home Money Transfer", "Family Support", "Family"),
        ("Donation to NGO Charity", "Donations", "Donation"),

        # --- Personal Care & Edge Cases (30) ---
        ("Haircut and Shave at Salon", "Personal Care", "Grooming"),
        ("Beauty Spa Massage", "Personal Care", "Grooming"),
        ("Lakme Cosmetics Makeup", "Personal Care", "Skincare & Cosmetics"),
        ("Skincare Moisturizer Lotion", "Personal Care", "Skincare & Cosmetics"),
        ("Gym Fitness Membership", "Extra Curricular", "Hobbies"),
        ("Yoga Class Fee", "Personal Care", "Grooming"),
        ("Pedigree Dog Food", "Pets", "Pet Care"),
        ("Whiskas Cat Food", "Pets", "Pet Care"),
        ("Pet Veterinary Clinic", "Pets", "Pet Care"),
        ("Temple Charity Offering", "Donations", "Donation"),
        ("Traffic Fine Penalty", "Unexpected Expenses", "Fines"),
        ("Hostel Damages Fee", "Unexpected Expenses", "Lost/Damage"),
        ("Emergency Ambulance", "Healthcare", "Medical"),
        ("Office Rent Deposit", "Mandatory Expenses", "Rent"),
        ("Vehicle Insurance PUC", "Maintenance", "Vehicle Maintenance"),
        ("Engine Oil Replacement", "Maintenance", "Vehicle Maintenance"),
        ("Car Wash Service", "Maintenance", "Vehicle Maintenance"),
        ("Mobile Screen Guard Repair", "Maintenance", "Mobile Maintenance"),
        ("Cigarette pack", "Smoking & Alcohol", "Items"),
        ("Beer and Liquor at Pub", "Smoking & Alcohol", "Items"),
        ("Wine bottle purchase", "Smoking & Alcohol", "Items"),
        ("Cricket Bat Equipment", "Extra Curricular", "Hobbies"),
        ("Photography Camera Lens", "Extra Curricular", "Hobbies"),
        ("Wedding Gift Present", "Events & Celebrations", "Events"),
        ("Anniversary Party Dinner", "Events & Celebrations", "Events"),
        ("Misc random expense", "Miscellaneous", "Others"),
        ("Unidentified item 123", "Miscellaneous", "Others"),
        ("XYZ unknown merchant", "Miscellaneous", "Others"),
        ("Testing 999", "Miscellaneous", "Others"),
        ("Sample general transaction", "Miscellaneous", "Others"),
    ]

    def test_expanded_transaction_suite(self):
        """Test accuracy over 250+ transactions."""
        passed = 0
        total = len(self.SAMPLE_TRANSACTIONS)
        failures = []

        for desc, expected_cat, expected_subcat in self.SAMPLE_TRANSACTIONS:
            cat, subcat, conf = categorize_with_confidence(desc)
            if cat == expected_cat and subcat == expected_subcat:
                passed += 1
            else:
                failures.append(f"'{desc}' -> Expected ({expected_cat}, {expected_subcat}), got ({cat}, {subcat}) [score: {conf}]")

        accuracy = (passed / total) * 100.0
        self.assertGreaterEqual(accuracy, 90.0, f"Accuracy was {accuracy:.2f}%. Failures: {failures[:10]}")



class RealWorldCategorizationTest(TestCase):
    """150+ real-world transaction descriptions covering UPI formats, merchant
    aliases, typos, noise numbers, and rule-priority ordering.
    The suite asserts > 90 % accuracy end-to-end."""

    CASES = [
        # ----------------------------------------------------------------
        # UPI / Gateway prefix stripping
        # ----------------------------------------------------------------
        ("UPI/123456789/SWIGGY INDIA",             "Food",           "Food Delivery"),
        ("UPI/987654321/ZOMATO",                   "Food",           "Food Delivery"),
        ("UPI/112233445/NETFLIX INDIA",            "Subscriptions",  "Entertainment Subscription"),
        ("UPI/556677889/AMAZON",                   "Shopping",       "Online Shopping"),
        ("UPI/998877665/KFC RESTAURANT",           "Food",           "Eating Out"),
        ("UPI/334455667/UBER",                     "Transportation", "Ride Hailing"),
        ("UPI/123/AMAZON PRIME VIDEO",             "Subscriptions",  "Entertainment Subscription"),
        ("UPI/887766554/STARBUCKS",                "Food",           "Eating Out"),
        ("PAYTM-8822-ZOMATO",                      "Food",           "Food Delivery"),
        ("PAYTM-3344-SWIGGY",                      "Food",           "Food Delivery"),
        ("POS 49102 STARBUCKS",                    "Food",           "Eating Out"),
        ("POS 88234 MCDONALDS",                    "Food",           "Eating Out"),
        ("NFS/20240201/DOMINOS PIZZA",             "Food",           "Eating Out"),
        ("IMPS/20240115/SALARY CREDIT",            "Income",         "Income"),
        ("NEFT/REF001122/HOUSE RENT",              "Mandatory Expenses", "Rent"),
        ("UPI/REFUND/AMAZON REFUND",               "Income",         "Income"),
        ("UPI/112233/NETFLIX AUTOPAY",             "Subscriptions",  "Entertainment Subscription"),
        ("UPI/334455/AMAZON PRIME",                "Subscriptions",  "Entertainment Subscription"),
        ("UPI/556789/SWIGGY INSTAMART",           "Food",           "Groceries"),
        ("UPI/778899/BLINKIT DELIVERY",            "Household",      "Household Delivery"),

        # ----------------------------------------------------------------
        # Merchant Aliases — exact and multi-word priority
        # ----------------------------------------------------------------
        ("Amazon Prime Video subscription",        "Subscriptions",  "Entertainment Subscription"),
        ("Amazon Prime Annual Plan",               "Subscriptions",  "Entertainment Subscription"),
        ("Amazon order delivered",                 "Shopping",       "Online Shopping"),
        ("AMZN order #A123",                       "Shopping",       "Online Shopping"),
        ("Netflix monthly subscription",           "Subscriptions",  "Entertainment Subscription"),
        ("Netflix Autopay debited",                "Subscriptions",  "Entertainment Subscription"),
        ("Swiggy food order",                      "Food",           "Food Delivery"),
        ("Swiggy Instamart delivery",              "Food",           "Groceries"),
        ("Instamart grocery order",                "Food",           "Groceries"),
        ("Zomato dinner order",                    "Food",           "Food Delivery"),
        ("Uber cab to airport",                    "Transportation", "Ride Hailing"),
        ("Ola auto ride",                          "Transportation", "Ride Hailing"),
        ("Rapido bike taxi",                       "Transportation", "Ride Hailing"),
        ("Starbucks coffee latte",                 "Food",           "Eating Out"),
        ("CCD cafe coffee",                        "Food",           "Eating Out"),
        ("Cafe Coffee Day Bangalore",              "Food",           "Eating Out"),
        ("McDonalds Happy Meal",                   "Food",           "Eating Out"),
        ("Mc Donalds drive-thru",                  "Food",           "Eating Out"),
        ("MCD burger combo",                       "Food",           "Eating Out"),

        # ----------------------------------------------------------------
        # Priority: specific brand > generic keyword
        # 'Amazon Prime' must win over generic 'amazon' rule,
        # 'Swiggy Instamart' must win over generic 'swiggy' rule.
        # ----------------------------------------------------------------
        ("Paid for Amazon Prime membership",       "Subscriptions",  "Entertainment Subscription"),
        ("Swiggy Instamart grocery top-up",        "Food",           "Groceries"),
        ("Netflix India monthly plan",             "Subscriptions",  "Entertainment Subscription"),

        # ----------------------------------------------------------------
        # Real Indian bank statement formats with noise
        # ----------------------------------------------------------------
        ("ACH PAYMENT 20240115 NETFLIX",           "Subscriptions",  "Entertainment Subscription"),
        ("SI NACH SPOTIFY 202406",                 "Subscriptions",  "Entertainment Subscription"),
        ("TRANSFER TO ZOMATO PAYMENTS",            "Food",           "Food Delivery"),
        ("AUTO DEBIT AMAZON PAY BALANCE",          "Shopping",       "Online Shopping"),
        ("UPI COLLECT SWIGGY DELIVERY PVTLTD",     "Food",           "Food Delivery"),
        ("CREDIT CARD BILL PAYMENT HDFC",          "Bank Charges",   "Charges"),
        ("MERCHANT TXN STARBUCKS 4501",            "Food",           "Eating Out"),
        ("INTERNATIONAL TXN NETFLIX.COM",          "Subscriptions",  "Entertainment Subscription"),

        # ----------------------------------------------------------------
        # Food & Dining — various natural descriptions
        # ----------------------------------------------------------------
        ("KFC dinner with friends",                "Food",           "Eating Out"),
        ("Domino's pizza order",                   "Food",           "Eating Out"),
        ("Pizza Hut large pizza",                  "Food",           "Eating Out"),
        ("Burger King Whopper meal",               "Food",           "Eating Out"),
        ("Subway footlong sandwich",               "Food",           "Eating Out"),
        ("Taco Bell tacos",                        "Food",           "Eating Out"),
        ("Dunkin Donuts breakfast",                "Food",           "Eating Out"),
        ("Chaayos ginger chai",                    "Food",           "Eating Out"),
        ("Chai point morning tea",                 "Food",           "Eating Out"),
        ("Wow Momo treats",                        "Food",           "Eating Out"),
        ("Faasos roll order",                      "Food",           "Eating Out"),
        ("Biryani Express delivery",               "Food",           "Eating Out"),
        ("Behrouz Biryani special",                "Food",           "Eating Out"),
        ("Haldiram sweets and namkeen",            "Food",           "Eating Out"),
        ("Saravana Bhavan South Indian",           "Food",           "Eating Out"),
        ("Ovenstory pizza order",                  "Food",           "Eating Out"),
        ("Baskin Robbins ice cream",               "Food",           "Eating Out"),
        ("Barbeque Nation dinner",                 "Food",           "Eating Out"),
        ("Restaurant dinner bill",                 "Food",           "Eating Out"),
        ("Morning coffee at cafe",                 "Food",           "Daily Food"),
        ("Evening snacks purchase",                "Food",           "Snacks"),
        ("Breakfast at canteen",                   "Food",           "Daily Food"),
        ("Lunch at office mess",                   "Food",           "Daily Food"),

        # ----------------------------------------------------------------
        # Groceries & Household
        # ----------------------------------------------------------------
        ("Dmart monthly groceries",                "Shopping",       "Mall & Hypermarkets"),
        ("Reliance Fresh vegetables",              "Shopping",       "Mall & Hypermarkets"),
        ("Big Bazaar hypermarket",                 "Shopping",       "Mall & Hypermarkets"),
        ("Blinkit quick delivery",                 "Household",      "Household Delivery"),
        ("Zepto 10 minute grocery",                "Household",      "Household Delivery"),
        ("Bigbasket monthly order",                "Household",      "Household Delivery"),
        ("Fresh milk packet Nandini",              "Food",           "Groceries"),
        ("Rice and dal purchase",                  "Food",           "Groceries"),
        ("Vegetables from market",                 "Food",           "Groceries"),
        ("Eggs from store",                        "Food",           "Groceries"),
        ("Bread loaf purchase",                    "Food",           "Groceries"),
        ("Protein powder supplement",              "Food",           "Health & Fitness Food"),

        # ----------------------------------------------------------------
        # Transportation
        # ----------------------------------------------------------------
        ("Petrol fill HP pump",                    "Transportation", "Fuel"),
        ("Diesel refill station",                  "Transportation", "Fuel"),
        ("Indian Oil fuel",                        "Transportation", "Fuel"),
        ("BPCL petrol pump",                       "Transportation", "Fuel"),
        ("Fastag recharge NHAI",                   "Transportation", "Parking & Tolls"),
        ("Toll fee highway",                       "Transportation", "Parking & Tolls"),
        ("IRCTC train ticket booking",             "Transportation", "Travel Tickets"),
        ("IndiGo flight booking",                  "Transportation", "Travel Tickets"),
        ("Air India ticket Bangalore",             "Transportation", "Travel Tickets"),
        ("KSRTC bus ticket",                       "Transportation", "Public Transport"),
        ("Metro card recharge",                    "Transportation", "Public Transport"),
        ("Airport taxi ride",                      "Transportation", "Ride Hailing"),
        ("Parking fee at mall",                    "Transportation", "Parking & Tolls"),

        # ----------------------------------------------------------------
        # Shopping & Electronics
        # ----------------------------------------------------------------
        ("Flipkart sale order",                    "Shopping",       "Online Shopping"),
        ("Myntra fashion order",                   "Shopping",       "Online Shopping"),
        ("Nykaa beauty order",                     "Shopping",       "Online Shopping"),
        ("Croma electronics purchase",             "Shopping",       "Assets & Major Purchases"),
        ("Apple Store iPhone 15",                  "Shopping",       "Assets & Major Purchases"),
        ("New running shoes Nike",                 "Shopping",       "Footwear"),
        ("Formal shirt purchase",                  "Shopping",       "Clothing"),
        ("Winter jacket buy",                      "Shopping",       "Clothing"),
        ("Wrist watch purchase",                   "Shopping",       "Accessories"),
        ("Laptop purchase Dell",                   "Shopping",       "Assets & Major Purchases"),

        # ----------------------------------------------------------------
        # Subscriptions & Entertainment
        # ----------------------------------------------------------------
        ("Spotify premium monthly",                "Subscriptions",  "Entertainment Subscription"),
        ("Disney+ Hotstar annual plan",            "Subscriptions",  "Entertainment Subscription"),
        ("YouTube Premium subscription",           "Subscriptions",  "Entertainment Subscription"),
        ("SonyLIV premium pack",                   "Subscriptions",  "Entertainment Subscription"),
        ("BookMyShow movie ticket",                "Entertainment",  "Movies & Gaming & Party"),
        ("PVR cinema ticket",                      "Entertainment",  "Movies & Gaming & Party"),
        ("INOX movie show",                        "Entertainment",  "Movies & Gaming & Party"),
        ("Steam game purchase",                    "Entertainment",  "Movies & Gaming & Party"),

        # ----------------------------------------------------------------
        # Healthcare & Education
        # ----------------------------------------------------------------
        ("Apollo hospital consultation",           "Healthcare",     "Medical"),
        ("MedPlus pharmacy medicine",              "Healthcare",     "Medical"),
        ("PharmEasy online order",                 "Healthcare",     "Medical"),
        ("Blood test lab Dr Lal",                  "Healthcare",     "Tests"),
        ("Dental clinic root canal",               "Healthcare",     "Special Care"),
        ("Annual health checkup",                  "Healthcare",     "Special Care"),
        ("Udemy python course fee",                "Education",      "Fees"),
        ("Coursera certificate fee",               "Education",      "Fees"),
        ("School tuition fee payment",             "Education",      "Fees"),
        ("College semester fee",                   "Education",      "Fees"),

        # ----------------------------------------------------------------
        # Utilities & Communication
        # ----------------------------------------------------------------
        ("Electricity bill BESCOM",                "Mandatory Expenses", "Utilities"),
        ("Water bill payment",                     "Mandatory Expenses", "Utilities"),
        ("LPG gas cylinder refill",                "Mandatory Expenses", "Utilities"),
        ("Airtel postpaid bill",                   "Communication",  "Mobile"),
        ("Jio prepaid recharge",                   "Communication",  "Mobile"),
        ("ACT Fibernet internet bill",             "Communication",  "Internet"),
        ("Broadband wifi payment",                 "Communication",  "Internet"),
        ("Monthly house rent transfer",            "Mandatory Expenses", "Rent"),
        ("Flat rent payment",                      "Mandatory Expenses", "Rent"),

        # ----------------------------------------------------------------
        # Finance & Income
        # ----------------------------------------------------------------
        ("Salary credit from company",             "Income",         "Income"),
        ("Annual performance bonus",               "Income",         "Income"),
        ("Freelancing payment received",           "Income",         "Income"),
        ("Stock dividend income",                  "Income",         "Income"),
        ("Zerodha mutual fund SIP",                "Investment",     "Investments"),
        ("Groww stocks investment",                "Investment",     "Investments"),
        ("Skincare moisturizer purchase",          "Personal Care",  "Skincare & Cosmetics"),
        ("Gym membership monthly fee",             "Extra Curricular", "Hobbies"),
        ("Dog food Pedigree brand",                "Pets",           "Pet Care"),

        # ----------------------------------------------------------------
        # Should remain Miscellaneous
        # ----------------------------------------------------------------
        ("Random XYZ transfer 999",                "Miscellaneous",  "Others"),
        ("Unknown merchant 12345",                 "Miscellaneous",  "Others"),
        ("Testing payment abc",                    "Miscellaneous",  "Others"),
    ]

    def test_upi_prefix_stripping(self):
        """UPI/gateway prefixes must be stripped before categorization."""
        cases = [
            ("UPI/123456789/SWIGGY INDIA",   "Food",           "Food Delivery"),
            ("UPI/987654321/ZOMATO",          "Food",           "Food Delivery"),
            ("UPI/998877665/KFC RESTAURANT",  "Food",           "Eating Out"),
            ("PAYTM-8822-ZOMATO",             "Food",           "Food Delivery"),
            ("POS 49102 STARBUCKS",           "Food",           "Eating Out"),
            ("POS 88234 MCDONALDS",           "Food",           "Eating Out"),
            ("UPI/334455/AMAZON PRIME",       "Subscriptions",  "Entertainment Subscription"),
            ("UPI/556789/SWIGGY INSTAMART",   "Food",           "Groceries"),
        ]
        for desc, exp_cat, exp_sub in cases:
            cat, sub, _ = categorize_with_confidence(desc)
            self.assertEqual(
                (cat, sub), (exp_cat, exp_sub),
                msg=f"UPI strip FAILED: {desc!r} -> got ({cat}, {sub})",
            )

    def test_merchant_alias_priority(self):
        """Multi-word aliases must beat generic single-word aliases."""
        # 'Amazon Prime Video' should map to Subscriptions, not Shopping
        cat, sub, _ = categorize_with_confidence("Amazon Prime Video subscription")
        self.assertEqual((cat, sub), ("Subscriptions", "Entertainment Subscription"),
                         "Amazon Prime Video should be Subscriptions")

        # 'Swiggy Instamart' should map to Groceries, not Food Delivery
        cat, sub, _ = categorize_with_confidence("Swiggy Instamart delivery")
        self.assertEqual((cat, sub), ("Food", "Groceries"),
                         "Swiggy Instamart should be Food/Groceries")

        # Plain 'Swiggy' should remain Food Delivery
        cat, sub, _ = categorize_with_confidence("Swiggy food order")
        self.assertEqual((cat, sub), ("Food", "Food Delivery"),
                         "Plain Swiggy should be Food/Food Delivery")

        # Plain 'Amazon' should remain Shopping
        cat, sub, _ = categorize_with_confidence("Amazon order")
        self.assertEqual((cat, sub), ("Shopping", "Online Shopping"),
                         "Plain Amazon should be Shopping")

    def test_categorize_with_explanation_fields(self):
        """categorize_with_explanation must return all required fields."""
        result = categorize_with_explanation("Swiggy food delivery")
        self.assertIn("category", result)
        self.assertIn("subcategory", result)
        self.assertIn("confidence", result)
        self.assertIn("matched_keyword", result)
        self.assertIn("matching_method", result)
        self.assertIn(result["matching_method"],
                      {"Alias", "Exact", "Substring", "Fuzzy", "Fallback"})

    def test_explanation_method_alias(self):
        result = categorize_with_explanation("Netflix autopay this month")
        self.assertEqual(result["matching_method"], "Alias")
        self.assertEqual(result["category"], "Subscriptions")

    def test_explanation_method_fallback(self):
        result = categorize_with_explanation("qwerty unknown xyz")
        self.assertEqual(result["matching_method"], "Fallback")
        self.assertEqual(result["category"], "Miscellaneous")

    def test_log_unknown_transaction_creates_record(self):
        """log_unknown_transaction must create an UnknownTransaction row."""
        log_unknown_transaction("XYZ mystery vendor", "xyz mystery vendor")
        obj = UnknownTransaction.objects.get(normalized_description="xyz mystery vendor")
        self.assertEqual(obj.original_description, "XYZ mystery vendor")
        self.assertEqual(obj.frequency, 1)

    def test_log_unknown_transaction_increments_frequency(self):
        """Calling log_unknown_transaction twice for the same desc increments frequency."""
        log_unknown_transaction("XYZ mystery vendor", "xyz mystery vendor")
        log_unknown_transaction("XYZ mystery vendor", "xyz mystery vendor")
        obj = UnknownTransaction.objects.get(normalized_description="xyz mystery vendor")
        self.assertEqual(obj.frequency, 2)

    def test_overall_accuracy_above_90_percent(self):
        """Accuracy over the full 150+ case suite must be >= 90%."""
        passed = 0
        total = len(self.CASES)
        failures = []

        for desc, exp_cat, exp_sub in self.CASES:
            cat, sub, conf = categorize_with_confidence(desc)
            if cat == exp_cat and sub == exp_sub:
                passed += 1
            else:
                failures.append(
                    f"  '{desc}' -> expected ({exp_cat}, {exp_sub}), "
                    f"got ({cat}, {sub}) [score={conf}]"
                )

        accuracy = (passed / total) * 100.0
        self.assertGreaterEqual(
            accuracy, 90.0,
            msg=(
                f"Accuracy {accuracy:.1f}% < 90% over {total} cases. "
                f"First failures:\n" + "\n".join(failures[:15])
            ),
        )



class BalanceTest(TestCase):
    """Tests for the get_balance() function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="balanceuser",
            password="Test123@",
        )

    def test_balance_calculation(self):
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("30000"),
            description="Salary",
            category="Income",
            trans_type="income",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-500"),
            description="KFC",
            category="Food",
            trans_type="expense",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-1000"),
            description="Amazon",
            category="Shopping",
            trans_type="expense",
        )

        result = get_balance(self.user)

        self.assertEqual(result["income"], Decimal("30000"))
        self.assertEqual(result["expense"], Decimal("1500"))
        self.assertEqual(result["balance"], Decimal("28500"))

    def test_zero_balance_no_transactions(self):
        result = get_balance(self.user)
        self.assertEqual(result["income"], Decimal("0"))
        self.assertEqual(result["expense"], Decimal("0"))
        self.assertEqual(result["balance"], Decimal("0"))


class InsightsTest(TestCase):
    """Tests for the get_insights() function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="insightuser",
            password="Test123@",
        )

    def test_insights_with_expenses(self):
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-500"),
            description="KFC",
            category="Food",
            trans_type="expense",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-2000"),
            description="Amazon",
            category="Shopping",
            trans_type="expense",
        )

        result = get_insights(self.user)

        self.assertEqual(result["total_spending"], Decimal("2500"))
        self.assertEqual(result["highest_category"], "Shopping")
        self.assertIn("Food", result["category_totals"])
        self.assertIn("Shopping", result["category_totals"])

    def test_insights_no_expenses(self):
        result = get_insights(self.user)
        self.assertEqual(result["total_spending"], Decimal("0"))
        self.assertIsNone(result["highest_category"])

    def test_income_excluded_from_insights(self):
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("50000"),
            description="Salary",
            category="Income",
            trans_type="income",
        )
        result = get_insights(self.user)
        self.assertEqual(result["total_spending"], Decimal("0"))


class GetTransactionsTest(TestCase):
    """Tests for the get_transactions() function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="txnuser",
            password="Test123@",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("-100"),
            description="KFC lunch",
            category="Food",
            trans_type="expense",
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal("5000"),
            description="Freelance income",
            category="Income",
            trans_type="income",
        )

    def test_returns_all_user_transactions(self):
        result = get_transactions(self.user)
        self.assertEqual(len(result), 2)

    def test_search_filter(self):
        result = get_transactions(self.user, search="kfc")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["description"], "KFC lunch")

    def test_type_filter(self):
        result = get_transactions(self.user, trans_type="income")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["trans_type"], "income")

    def test_user_isolation(self):
        """Users should not see each other's transactions."""
        other_user = User.objects.create_user(
            username="other", password="Test123@",
        )
        result = get_transactions(other_user)
        self.assertEqual(len(result), 0)


# ===================================================================
# Authentication Tests
# ===================================================================

class AuthenticationTest(TestCase):
    """Tests for login functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser",
            password="Test123@",
        )

    def test_valid_login(self):
        login_successful = self.client.login(
            username="loginuser",
            password="Test123@",
        )
        self.assertTrue(login_successful)

    def test_invalid_login(self):
        login_successful = self.client.login(
            username="loginuser",
            password="wrongpassword",
        )
        self.assertFalse(login_successful)


# ===================================================================
# View Tests
# ===================================================================

class DashboardViewTest(TestCase):
    """Tests for the dashboard view."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="dashuser",
            password="Test123@",
        )
        self.client = Client()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_dashboard_accessible_when_logged_in(self):
        self.client.login(username="dashuser", password="Test123@")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)


class DeleteViewSecurityTest(TestCase):
    """Tests for delete transaction IDOR and POST-only protection."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner", password="Test123@",
        )
        self.other_user = User.objects.create_user(
            username="attacker", password="Test123@",
        )
        self.transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("-100"),
            description="My expense",
            category="Other",
            trans_type="expense",
        )
        self.client = Client()

    def test_delete_requires_post(self):
        """GET requests to delete should return 405."""
        self.client.login(username="owner", password="Test123@")
        response = self.client.get(
            reverse("delete", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_delete_idor_protection(self):
        """Another user should not be able to delete someone else's transaction."""
        self.client.login(username="attacker", password="Test123@")
        response = self.client.post(
            reverse("delete", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 404)
        # Transaction should still exist
        self.assertTrue(
            Transaction.objects.filter(id=self.transaction.id).exists()
        )

    def test_owner_can_delete(self):
        """Owner should be able to delete their own transaction."""
        self.client.login(username="owner", password="Test123@")
        response = self.client.post(
            reverse("delete", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Transaction.objects.filter(id=self.transaction.id).exists()
        )


class EditViewSecurityTest(TestCase):
    """Tests for edit transaction IDOR protection."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner", password="Test123@",
        )
        self.other_user = User.objects.create_user(
            username="attacker", password="Test123@",
        )
        self.transaction = Transaction.objects.create(
            user=self.user,
            amount=Decimal("-100"),
            description="My expense",
            category="Other",
            trans_type="expense",
        )
        self.client = Client()

    def test_edit_idor_protection(self):
        """Another user should get 404 when trying to edit someone else's transaction."""
        self.client.login(username="attacker", password="Test123@")
        response = self.client.get(
            reverse("edit", args=[self.transaction.id])
        )
        self.assertEqual(response.status_code, 404)


class AdminViewAccessTest(TestCase):
    """Tests for admin-only view access control."""

    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular", password="Test123@",
        )
        self.admin_user = User.objects.create_user(
            username="admin", password="Test123@", is_staff=True,
        )
        self.client = Client()

    def test_admin_view_blocked_for_regular_user(self):
        self.client.login(username="regular", password="Test123@")
        response = self.client.get(reverse("ledgio_admin"))
        # Should redirect (302) — user_passes_test sends to login
        self.assertNotEqual(response.status_code, 200)

    def test_admin_view_accessible_for_staff(self):
        self.client.login(username="admin", password="Test123@")
        response = self.client.get(reverse("ledgio_admin"))
        self.assertEqual(response.status_code, 200)


class RegistrationViewTest(TestCase):
    """Tests for the registration form validation."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.sites.models import Site
        from allauth.socialaccount.models import SocialApp
        site, _ = Site.objects.get_or_create(id=1, defaults={"domain": "example.com", "name": "example.com"})
        app = SocialApp.objects.create(
            provider="google",
            name="Google Test App",
            client_id="dummy",
            secret="dummy",
        )
        app.sites.add(site)

    def test_password_mismatch(self):
        response = self.client.post(reverse("register"), {
            "username": "newuser",
            "email": "new@example.com",
            "password": "StrongPass1!",
            "confirm_password": "DifferentPass1!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "do not match")

    def test_short_password(self):
        response = self.client.post(reverse("register"), {
            "username": "newuser",
            "email": "new@example.com",
            "password": "short",
            "confirm_password": "short",
        })
        self.assertEqual(response.status_code, 200)

    def test_duplicate_username(self):
        User.objects.create_user(
            username="taken", password="Test123@",
        )
        response = self.client.post(reverse("register"), {
            "username": "taken",
            "email": "unique@example.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_successful_registration(self):
        response = self.client.post(reverse("register"), {
            "username": "brandnew",
            "email": "brandnew@example.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "country": "India",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="brandnew").exists())


class ToggleUserStatusSecurityTest(TestCase):
    """Tests for POST-only toggle endpoints."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="Test123@", is_staff=True,
        )
        self.target = User.objects.create_user(
            username="target", password="Test123@",
        )
        self.client = Client()

    def test_toggle_user_requires_post(self):
        self.client.login(username="admin", password="Test123@")
        response = self.client.get(
            reverse("toggle_user_status", args=[self.target.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_toggle_user_works_with_post(self):
        self.client.login(username="admin", password="Test123@")
        response = self.client.post(
            reverse("toggle_user_status", args=[self.target.id])
        )
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
