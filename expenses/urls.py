from django.urls import path
from . import views

urlpatterns = [

    path('', views.dashboard, name='dashboard'),
    path('transactions/', views.transactions_views, name='transactions'),
    path('add/', views.add_transaction_view, name='add'),
    path('insights/', views.insights, name='insights'),
    path('delete/<int:id>/',views.delete, name='delete'),
    path('edit/<int:id>/', views.edit, name='edit'),
    path('balance/', views.balance_view, name='balance'),
    path('logout/', views.logout_view, name='logout'),
    path('check-user/', views.check_user_availability, name='check_user'),
    path('profile/', views.profile_view, name='profile'),
    path('ledgio-admin/', views.ledgio_admin_view, name='ledgio_admin'),
    path('toggle-user/<int:id>/', views.toggle_user_status, name='toggle_user_status'),
]