from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import redirect
from allauth.exceptions import ImmediateHttpResponse

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
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
