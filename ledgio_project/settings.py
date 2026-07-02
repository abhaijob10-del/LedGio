"""
Django settings for ledgio_project project.

Environment variables are loaded from a .env file via python-dotenv.
See .env.example for all available variables.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Load environment variables from .env (must be installed: pip install python-dotenv)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed yet — env vars from OS are still used

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Core Security
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-od#3+z6c_hfpkn&qawhv&rp+1xi*#7dimf0@$7!13mvq)h&q=0",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
).split(",")


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # Django built-ins
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Required by allauth
    'django.contrib.sites',

    # Django AllAuth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # LedGio app
    'expenses',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # AllAuth account middleware (required)
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'ledgio_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Allow allauth templates to be overridden from app templates/
        'DIRS': [BASE_DIR / 'templates'],

        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # LedGio: inject currency_symbol, currency_code into every template
                'expenses.context_processors.currency_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ledgio_project.wsgi.application'


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ---------------------------------------------------------------------------
# Authentication Backends
# ---------------------------------------------------------------------------

AUTHENTICATION_BACKENDS = [
    # Default Django auth (username/password login)
    'django.contrib.auth.backends.ModelBackend',

    # AllAuth for Google OAuth and email auth
    'allauth.account.auth_backends.AuthenticationBackend',
]


# ---------------------------------------------------------------------------
# AllAuth Configuration
# ---------------------------------------------------------------------------

# Use email as primary identifier (alongside username) - allauth 65.x syntax
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]

# MANDATORY = user must verify email before login is allowed
# Change to "optional" or "none" to relax during local development
ACCOUNT_EMAIL_VERIFICATION = os.environ.get("ACCOUNT_EMAIL_VERIFICATION", "mandatory")

ACCOUNT_UNIQUE_EMAIL = True

# Prevent account enumeration attacks on password reset
ACCOUNT_PREVENT_ENUMERATION = True

# Use our custom registration form that includes country
ACCOUNT_FORMS = {}  # We keep our own register_view, allauth forms used only for social

# After social login (Google), redirect to dashboard
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# After email confirmation, go straight to dashboard
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = "/"

# Link social account to existing email account automatically
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Bypass the intermediate "Sign In Via Google" confirmation page
SOCIALACCOUNT_LOGIN_ON_GET = True

# Do not require email verification for social logins (Google has already verified them)
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"

# Custom adapter to prevent unregistered users from logging in via Google
SOCIALACCOUNT_ADAPTER = "expenses.adapters.CustomSocialAccountAdapter"

# Require email from Google (it always provides one, but enforce it)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        # These are set via Django admin → Social Applications
        # (not hardcoded here for security)
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret":    os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "key":       "",
        },
    }
}

# Where allauth looks for its own templates (we override them)
ACCOUNT_TEMPLATE_EXTENSION = "html"


# ---------------------------------------------------------------------------
# Login / Logout URLs
# ---------------------------------------------------------------------------

LOGIN_URL = '/login/'


# ---------------------------------------------------------------------------
# Password Validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ---------------------------------------------------------------------------
# Email Configuration — driven entirely by environment variables
# Switch providers by changing EMAIL_BACKEND + related vars in .env
# ---------------------------------------------------------------------------

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    # Default: print emails to console during development
    "django.core.mail.backends.console.EmailBackend",
)

# For Gmail SMTP — set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST          = os.environ.get("EMAIL_HOST",     "smtp.gmail.com")
EMAIL_PORT          = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS       = os.environ.get("EMAIL_USE_TLS",  "True").lower() in ("true", "1", "yes")
EMAIL_HOST_USER     = os.environ.get("EMAIL_HOST_USER",    "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL  = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"LedGio <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "LedGio <noreply@ledgio.com>",
)

# SendGrid example (set in .env):
#   EMAIL_BACKEND=anymail.backends.sendgrid.EmailBackend
#   SENDGRID_API_KEY=SG.xxxxxxxx
# Mailgun example:
#   EMAIL_BACKEND=anymail.backends.mailgun.EmailBackend
#   MAILGUN_API_KEY=key-xxxx


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static"
]


# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------
# Security settings (only active in production when DEBUG=False)
# ---------------------------------------------------------------------------

if not DEBUG:
    CSRF_COOKIE_HTTPONLY       = True
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SECURE      = True
    CSRF_COOKIE_SECURE         = True
    SECURE_BROWSER_XSS_FILTER  = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS            = "DENY"
    # Uncomment after confirming HTTPS is working:
    # SECURE_HSTS_SECONDS      = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_SSL_REDIRECT      = True


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "expenses": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}
