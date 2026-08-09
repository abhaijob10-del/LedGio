"""
Django settings for ledgio_project project.

Environment variables are loaded from a .env file via python-dotenv.
See .env.example for all available variables.
"""

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# ---------------------------------------------------------------------------
# Load environment variables from .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed yet — env vars from OS environment are still used

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Core Security
# ---------------------------------------------------------------------------

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-od#3+z6c_hfpkn&qawhv&rp+1xi*#7dimf0@$7!13mvq)h&q=0"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY environment variable is required when DEBUG=False."
        )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]


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
    # WhiteNoise: serve static files efficiently in production (no separate static server needed)
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

        # APP_DIRS must be False when using custom loaders
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # LedGio: inject currency_symbol, currency_code into every template
                'expenses.context_processors.currency_context',
            ],
            # Use the cached loader in production to avoid re-parsing templates
            # on every request. Falls back to filesystem + app_directories in DEBUG mode.
            'loaders': [
                (
                    'django.template.loaders.cached.Loader',
                    [
                        'django.template.loaders.filesystem.Loader',
                        'django.template.loaders.app_directories.Loader',
                    ],
                )
            ] if not DEBUG else [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]

WSGI_APPLICATION = 'ledgio_project.wsgi.application'


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        # Keep connections alive for 60 s to avoid per-request reconnect overhead.
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }
}


# ---------------------------------------------------------------------------
# Caching Configuration
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ledgio-local-cache",
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

# Require email from Google & load Client ID / Client Secret dynamically via adapter
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
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
# ---------------------------------------------------------------------------

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

EMAIL_HOST          = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT          = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS       = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
EMAIL_USE_SSL       = os.environ.get("EMAIL_USE_SSL", "False").lower() in ("true", "1", "yes")
EMAIL_HOST_USER     = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL  = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"LedGio <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "LedGio <noreply@ledgio.com>",
)
SERVER_EMAIL        = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)


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

# Directory where collectstatic gathers files for production deployment.
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise: compress and cache static files in production.
# AUTOREFRESH keeps whitenoise compatible with DEBUG=True (no double-serving).
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
    if not DEBUG
    else "django.contrib.staticfiles.storage.StaticFilesStorage"
)


# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------
# Media files (user uploads — profile pictures)
# ---------------------------------------------------------------------------

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ---------------------------------------------------------------------------
# Security settings
# ---------------------------------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True").lower() in ("true", "1", "yes")
    CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True").lower() in ("true", "1", "yes")

    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "yes")

    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True").lower() in ("true", "1", "yes")
    SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "True").lower() in ("true", "1", "yes")


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
        # LedGio application logs
        "expenses": {
            "handlers": ["console"],
            "level": "INFO" if not DEBUG else "DEBUG",
            "propagate": True,
        },
        # Capture SMTP errors from Django's email internals
        "django.core.mail": {
            "handlers": ["console"],
            "level": "INFO" if not DEBUG else "DEBUG",
            "propagate": True,
        },
        # Log security-related events (password reset enumeration, CSRF, etc.)
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": True,
        },
    },
}
