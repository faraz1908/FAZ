import datetime
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import UserWallet, Stock, UserPortfolio, Transaction

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    # Display analytics fields directly to find high performing or most traded assets
    list_display = ('name', 'ticker', 'initial_price', 'current_price', 'admin_stock_pnl', 'total_buy_count', 'total_sell_count')
    list_editable = ('current_price',)
    
    # Ordering criteria sets the trend filters: Jiska volume zyada hoga wo list me top pe dikhega
    ordering = ('-total_buy_count', '-total_sell_count')
    search_fields = ('name', 'ticker')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # Feature: Kis user ne kaunsa stock kab transaction kiya, poora clear deep layout tracking
    list_display = ('user', 'transaction_type', 'stock', 'quantity', 'price_at_transaction', 'total_amount', 'admin_commission', 'timestamp')
    list_filter = ('transaction_type', 'timestamp', 'stock')
    search_fields = ('user__username', 'stock__ticker', 'transaction_type')
    readonly_fields = ('timestamp',)

    # Validation: Django Backend level security block structure for Sunday logs modification
    def save_model(self, request, obj, form, change):
        current_day = datetime.datetime.now().weekday() # 6 stands for Sunday in Python datetime
        if current_day == 6:
            raise ValidationError("Market Warning: Backend logs aur order operations Sundays ko processed nahi kiye ja sakte kyuki standard market operations officially closed hain!")
        super().save_model(request, obj, form, change)


@admin.register(UserPortfolio)
class UserPortfolioAdmin(admin.ModelAdmin):
    list_display = ('user', 'stock', 'quantity', 'current_investment_value')
    list_filter = ('stock', 'user')
    search_fields = ('user__username', 'stock__ticker')


@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance')
    search_fields = ('user__username',)