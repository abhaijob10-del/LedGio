import os
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import redirect
from allauth.exceptions import ImmediateHttpResponse


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for LedGio.
    
    Dynamically initializes or updates the Google SocialApp credentials from
    environment variables (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) and enforces
    registration checks before Google login.
    """

    def get_app(self, request, provider, client_id=None):
        if provider == "google":
            env_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
            env_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
            if env_client_id and env_secret:
                from allauth.socialaccount.models import SocialApp
                from django.contrib.sites.models import Site

                site = Site.objects.get_current(request)
                app = SocialApp.objects.filter(provider="google").first()
                if not app:
                    app = SocialApp.objects.create(
                        provider="google",
                        name="Google",
                        client_id=env_client_id,
                        secret=env_secret,
                    )
                    app.sites.add(site)
                else:
                    updated = False
                    if app.client_id != env_client_id:
                        app.client_id = env_client_id
                        updated = True
                    if app.secret != env_secret:
                        app.secret = env_secret
                        updated = True
                    if updated:
                        app.save()
                    if site not in app.sites.all():
                        app.sites.add(site)
                return app

        return super().get_app(request, provider, client_id=client_id)

    def pre_social_login(self, request, sociallogin):
        # Allow if they are already logged in or this social account is already linked
        if sociallogin.is_existing or request.user.is_authenticated:
            return

        email = sociallogin.account.extra_data.get('email')

        # Allow if a user with this email already exists (auto-connect will handle it)
        if email and User.objects.filter(email__iexact=email).exists():
            return

        # At this point, the user is completely new (not in our DB).
        # We check the 'next' URL to see if they came from the login page.
        # If 'next' contains 'source=login', we reject the login.
        next_url = sociallogin.state.get('next', '')

        if 'source=login' in next_url:
            messages.error(request, "This Google account is not registered. Please create an account first.")
            raise ImmediateHttpResponse(redirect('login'))
