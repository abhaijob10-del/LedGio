"""
country_data.py — Single source of truth for country → currency mapping.

Used by RegistrationForm (choices) and UserProfile (defaults).
Add any country here and it automatically appears in registration.
"""

# List of (country_name, currency_symbol, currency_code) tuples
# Ordered alphabetically for a clean UX in dropdowns.

COUNTRY_CURRENCY_MAP = [
    # country_name            symbol   code
    ("Australia",             "A$",    "AUD"),
    ("Bangladesh",            "৳",     "BDT"),
    ("Brazil",                "R$",    "BRL"),
    ("Canada",                "C$",    "CAD"),
    ("China",                 "¥",     "CNY"),
    ("Denmark",               "kr",    "DKK"),
    ("Egypt",                 "£",     "EGP"),
    ("European Union",        "€",     "EUR"),
    ("France",                "€",     "EUR"),
    ("Germany",               "€",     "EUR"),
    ("Hong Kong",             "HK$",   "HKD"),
    ("India",                 "₹",     "INR"),
    ("Indonesia",             "Rp",    "IDR"),
    ("Israel",                "₪",     "ILS"),
    ("Japan",                 "¥",     "JPY"),
    ("Malaysia",              "RM",    "MYR"),
    ("Mexico",                "MX$",   "MXN"),
    ("Netherlands",           "€",     "EUR"),
    ("New Zealand",           "NZ$",   "NZD"),
    ("Nigeria",               "₦",     "NGN"),
    ("Norway",                "kr",    "NOK"),
    ("Pakistan",              "₨",     "PKR"),
    ("Philippines",           "₱",     "PHP"),
    ("Poland",                "zł",    "PLN"),
    ("Russia",                "₽",     "RUB"),
    ("Saudi Arabia",          "﷼",     "SAR"),
    ("Singapore",             "S$",    "SGD"),
    ("South Africa",          "R",     "ZAR"),
    ("South Korea",           "₩",     "KRW"),
    ("Spain",                 "€",     "EUR"),
    ("Sri Lanka",             "Rs",    "LKR"),
    ("Sweden",                "kr",    "SEK"),
    ("Switzerland",           "CHF",   "CHF"),
    ("Thailand",              "฿",     "THB"),
    ("Turkey",                "₺",     "TRY"),
    ("UAE",                   "د.إ",   "AED"),
    ("United Kingdom",        "£",     "GBP"),
    ("United States",         "$",     "USD"),
    ("Vietnam",               "₫",     "VND"),
]


def get_country_choices():
    """
    Return a list of (country_name, country_name) tuples for use in
    Django form ChoiceField. A blank '-- Select Country --' is prepended.
    """
    blank = [("", "— Select Country —")]
    choices = [(name, name) for name, _sym, _code in COUNTRY_CURRENCY_MAP]
    return blank + choices


def get_currency_for_country(country_name):
    """
    Return (symbol, code) for the given country name.
    Falls back to ("$", "USD") if country not found.
    """
    for name, symbol, code in COUNTRY_CURRENCY_MAP:
        if name == country_name:
            return symbol, code
    return "$", "USD"
