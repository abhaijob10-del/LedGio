from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from expenses.views import register_view, LedGioPasswordResetView, test_email_view

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # LedGio app routes
    path("", include("expenses.urls")),

    # ---------- Authentication ----------

    # Standard login / logout
    path("login/",  auth_views.LoginView.as_view(template_name="login.html"),  name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/login/"),        name="logout"),

    # Registration
    path("register/", register_view, name="register"),

    # ---------- Password Reset ----------
    path(
        "password-reset/",
        LedGioPasswordResetView.as_view(
            template_name="password_reset.html",
            email_template_name="emails/password_reset_email.txt",
            html_email_template_name="emails/password_reset_email.html",
            subject_template_name="emails/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    # ---------- Google OAuth / AllAuth (Feature 2 + 3) ----------
    # Provides: /accounts/google/login/, /accounts/confirm-email/, etc.
    path("accounts/", include("allauth.urls")),
]

# Serve user-uploaded media files in development
# Also expose staff-only email diagnostic route in DEBUG mode only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Staff-only SMTP diagnostic — NEVER exposed in production
    urlpatterns += [
        path("test-email/", test_email_view, name="test_email"),
    ]