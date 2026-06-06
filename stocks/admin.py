from django.contrib import admin
from .models import UserWallet, Stock, UserPortfolio, Transaction

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
   
    list_display = ('name', 'ticker', 'initial_price', 'current_price', 'admin_stock_pnl')
  
    list_editable = ('current_price',) 

admin.site.register(UserWallet)
admin.site.register(UserPortfolio)
admin.site.register(Transaction)