"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView  # Auto-redirect ke liye import kiya
from stocks import views as stock_views  # Tumhare stocks app ke views
from django.contrib.auth.decorators import user_passes_test  # Security gate ke liye import kiya

# 🔒 Gatekeeper Rule: Sirf wahi user aage badhega jiska status 'is_staff=True' (Admin) hai.
# Agar koi normal trader access karega, toh use direct login page par redirect kar diya jayega.
admin_only_gate = user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url='/stocks/login/')

urlpatterns = [
    # ➔ Server chalu hote hi direct stocks/login/ open hoga
    path('', RedirectView.as_view(url='stocks/login/', permanent=False)),

    # 1. Default boring admin ka rasta badal kar secret rakh do (Backup ke liye)
    path('db-panel/', admin.site.urls),
    
    # 2. Ab main 'admin/' path par humne gatekeeper laga diya hai!
    # Trader account isko ab बाईपास (bypass) nahi kar payega.
    path('admin/', admin_only_gate(stock_views.admin_dashboard), name='admin_dashboard'),
    
    # Stocks app ke baki normal urls
    path('stocks/', include('stocks.urls')),
]