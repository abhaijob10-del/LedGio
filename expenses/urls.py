from django.urls import path

from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Transactions
    path("transactions/", views.transactions_views, name="transactions"),
    path("add/", views.add_transaction_view, name="add"),
    path("delete/<int:id>/", views.delete, name="delete"),
    path("edit/<int:id>/", views.edit, name="edit"),

    # Balance & Insights
    path("balance/", views.balance_view, name="balance"),
    path("insights/", views.insights, name="insights"),

    # Savings Goal (Feature 5)
    path("savings-goal/", views.savings_goal_view, name="savings_goal"),

    # Auth helpers
    path("logout/", views.logout_view, name="logout"),
    path("check-user/", views.check_user_availability, name="check_user"),

    # Profile
    path("profile/", views.profile_view, name="profile"),

    # Admin Dashboard
    path("ledgio-admin/", views.ledgio_admin_view, name="ledgio_admin"),

    # Admin — User Management
    path("toggle-user/<int:id>/", views.toggle_user_status, name="toggle_user_status"),
    path("users/", views.users_view, name="users"),

    # Admin — Support
    path("support/", views.support_view, name="support"),
    path("resolve-support/<int:id>/", views.resolve_support_request, name="resolve_support"),
    path("activate-from-request/<int:id>/", views.activate_user_from_request, name="activate_from_request"),
    path("support-inbox/", views.support_inbox_view, name="support_inbox"),

    # Admin — Support Detail (Feature 6)
    path("support-detail/<int:id>/", views.support_detail_view, name="support_detail"),
    path("update-support-status/<int:id>/", views.update_support_status, name="update_support_status"),

    # Admin — Staff Management
    path("staff-management/", views.staff_management_view, name="staff_management"),
    path("toggle-staff/<int:id>/", views.toggle_staff_status, name="toggle_staff"),
]