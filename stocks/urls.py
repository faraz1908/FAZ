from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'), # Default me login page khulega
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('api/user-chart/', views.user_chart_data, name='user_chart_data'),
    
    path('admin-analytics/', views.admin_dashboard, name='admin_dashboard'),
    path('api/admin-chart/', views.admin_chart_data, name='admin_chart_data'),
    path('admin-hq/', views.admin_dashboard, name='admin_dashboard'),
    # Settings Main Page
    path('settings/', views.user_settings, name='user_settings'),
    
    # Settings Actions
    path('settings/update-profile/', views.update_profile, name='update_profile'),
    path('settings/change-password/', views.change_password, name='change_password'),
    path('settings/history/', views.trade_history, name='trade_history'),
]