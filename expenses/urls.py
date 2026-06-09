from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("transactions/", views.transactions_views, name="transactions"),
    path("add/", views.add_transaction_view, name="add"),
    path("insights/", views.insights, name="insights"),
    path("delete/<int:id>/", views.delete, name="delete"),
    path("edit/<int:id>/", views.edit, name="edit"),
    path("balance/", views.balance_view, name="balance"),
    path("logout/", views.logout_view, name="logout"),
    path("check-user/", views.check_user_availability, name="check_user"),
    path("profile/", views.profile_view, name="profile"),
    path("ledgio-admin/", views.ledgio_admin_view, name="ledgio_admin"),
    path("toggle-user/<int:id>/", views.toggle_user_status, name="toggle_user_status"),
    path("support/", views.support_view, name="support"),
    path("resolve-support/<int:id>/", views.resolve_support_request, name="resolve_support"),
    path("activate-from-request/<int:id>/", views.activate_user_from_request, name="activate_from_request"),
    path("users/", views.users_view, name="users"),
    path("support-inbox/", views.support_inbox_view, name="support_inbox"),
    path("staff-management/", views.staff_management_view, name="staff_management"),
    path("toggle-staff/<int:id>/", views.toggle_staff_status, name="toggle_staff"),
]