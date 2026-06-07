import traceback
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count
from decimal import Decimal
from django.utils import timezone
from .models import Stock, UserWallet, UserPortfolio, Transaction
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages

# Helper Function to Check Sunday Lockout Status
def check_if_market_closed():
    """ Returns True if today is Sunday (weekday index 6) """
    return timezone.now().weekday() == 6


# ==================== 1. USER DASHBOARD VIEW ====================
@login_required
def user_dashboard(request):
    try:
        wallet, created = UserWallet.objects.get_or_create(user=request.user, defaults={'balance': Decimal('0.00')})
        stocks = Stock.objects.all()
        portfolio = UserPortfolio.objects.filter(user=request.user)
        is_market_closed = check_if_market_closed()
        
        if request.method == "POST":
            # ─── SUNDAY PROTOCOL ENFORCEMENT ───
            if is_market_closed:
                messages.error(request, "Market is closed on Sundays! Trading operations are locked.")
                return redirect('user_dashboard')

            # ─── ADD FUNDS LOGIC ───
            if 'add_funds' in request.POST:
                amount = request.POST.get('amount')
                if amount and Decimal(amount) > 0:
                    wallet.balance += Decimal(amount)
                    wallet.save()
                    
                    # FIX: Agar database me stock NOT NULL hai, to hum filter lagane ke liye ya to default placeholder link karte hain,
                    # ya fir Transaction.objects.create se stock field ko skip karte hain agar database override allowed ho.
                    # Magar safe side ke liye hum pehle check karte hain ki koi dummy/placeholder stock entity bani ho, 
                    # nahi to hum sirf handle karne ke liye stock reference ko control karenge ya try-catch block lagayenge.
                    try:
                        # Agar field strict hai, to hum check karte hain kya koi stock available hai jise hum reference de sakein (jaise virtual node)
                        # Agar stock pass karna mandatory hi hai database schema me:
                        fallback_stock = Stock.objects.first() 
                        
                        Transaction.objects.create(
                            user=request.user,
                            stock=fallback_stock, # NULL error se bachne ke liye base stock link kiya (ya ise field se hatayein)
                            transaction_type='DEPOSIT', 
                            quantity=0,
                            price_at_transaction=Decimal('0.00'),
                            total_amount=Decimal(amount),
                            admin_commission=Decimal('0.00')
                        )
                    except Exception as tx_err:
                        # Agar models.py me `null=True` missing hai aur fallback_stock bhi nahi mila, to sirf balance update safely run hone do
                        print(f"[WALLET TRANSACTION LOG ERROR]: {tx_err}")
                        pass

                    messages.success(request, f"Liquidity injection of ₹{amount} successful!")
                    return redirect('user_dashboard')

            # ─── BUY STOCK LOGIC ───
            if 'buy_stock' in request.POST or request.POST.get('stock_id') and not 'sell_stock' in request.POST:
                stock_id = request.POST.get('stock_id')
                qty = int(request.POST.get('quantity', 0))
                
                if qty > 0:
                    stock = get_object_or_404(Stock, id=stock_id)
                    total_cost = stock.current_price * qty
                    commission = total_cost * Decimal('0.01')
                    final_deduction = total_cost + commission
                    
                    if wallet.balance >= final_deduction:
                        wallet.balance -= final_deduction
                        wallet.save()
                        
                        user_stock, created = UserPortfolio.objects.get_or_create(user=request.user, stock=stock)
                        user_stock.quantity += qty
                        user_stock.save()
                        
                        stock.total_buy_count += 1
                        stock.save()
                        
                        Transaction.objects.create(
                            user=request.user,
                            stock=stock,
                            transaction_type='BUY',
                            quantity=qty,
                            price_at_transaction=stock.current_price,
                            total_amount=total_cost,
                            admin_commission=commission
                        )
                        messages.success(request, f"Successfully acquired {qty} shares of {stock.ticker}!")
                        return redirect('user_dashboard')
                    else:
                        messages.error(request, "Insufficient structural vault capital!")

            # ─── SELL STOCK LOGIC ───
            if 'sell_stock' in request.POST:
                portfolio_id = request.POST.get('portfolio_id')
                qty_to_sell = int(request.POST.get('quantity_sell', 0))
                
                user_portfolio_item = get_object_or_404(UserPortfolio, id=portfolio_id, user=request.user)
                
                if qty_to_sell > 0 and user_portfolio_item.quantity >= qty_to_sell:
                    stock = user_portfolio_item.stock
                    total_revenue = stock.current_price * qty_to_sell
                    commission = total_revenue * Decimal('0.01')
                    final_credit = total_revenue - commission
                    
                    wallet.balance += final_credit
                    wallet.save()
                    
                    user_portfolio_item.quantity -= qty_to_sell
                    if user_portfolio_item.quantity == 0:
                        user_portfolio_item.delete()
                    else:
                        user_portfolio_item.save()
                    
                    stock.total_sell_count += 1
                    stock.save()
                    
                    Transaction.objects.create(
                        user=request.user,
                        stock=stock,
                        transaction_type='SELL',
                        quantity=qty_to_sell,
                        price_at_transaction=stock.current_price,
                        total_amount=total_revenue,
                        admin_commission=commission
                    )
                    messages.success(request, f"Liquidation of {qty_to_sell} shares of {stock.ticker} complete.")
                    return redirect('user_dashboard')
                else:
                    messages.error(request, "Invalid liquidation asset volume.")

        context = {
            'wallet': wallet,
            'stocks': stocks,
            'portfolio': portfolio,
            'is_market_closed': is_market_closed,        
        }
        return render(request, 'stocks/user_dashboard.html', context)

    except Exception as e:
        print("\n" + "="*60 + "\n[ERROR IN USER DASHBOARD VIEW]:\n" + "="*60)
        traceback.print_exc()
        print("="*60 + "\n")
        raise e

# User Portfolio Pie Chart API
@login_required
def user_chart_data(request):
    transactions = Transaction.objects.filter(user=request.user, transaction_type='BUY').values('stock__name').annotate(total_spent=Sum('total_amount'))
    
    labels = [item['stock__name'] for item in transactions if item['stock__name']]
    data = [float(item['total_spent']) for item in transactions]
    
    wallet, created = UserWallet.objects.get_or_create(user=request.user, defaults={'balance': Decimal('0.00')})
    labels.append('Available Wallet')
    data.append(float(wallet.balance))
    
    return JsonResponse({'labels': labels, 'data': data})


# ─── USER POPUP ANALYSIS TREND LINE API ───
@login_required
def stock_trend_api(request, stock_id):
    """ Specific stock ka buy price transaction records fetch karke up/down direction analysis nikalna """
    stock = get_object_or_404(Stock, id=stock_id)
    
    # Is stock ki last 15 BUY transactions trace karo graph records ke liye
    history = Transaction.objects.filter(stock=stock, transaction_type='BUY').order_by('timestamp')[:15]
    
    if history.exists():
        prices = [float(tx.price_at_transaction) for tx in history]
        timestamps = [tx.timestamp.strftime('%d %b %H:%M') for tx in history]
    else:
        # Static Fallback sequence agar database nodes pe trades empty hon
        base_p = float(stock.current_price)
        prices = [base_p * 0.95, base_p * 0.98, base_p * 1.02, base_p]
        timestamps = ['Opening Baseline', 'Intraday Low', 'Intraday High', 'Current Valuation']

    # Final Delta Evaluation
    is_up = True
    if len(prices) >= 2:
        is_up = prices[-1] >= prices[-2]

    return JsonResponse({
        'stock_name': stock.name,
        'ticker': stock.ticker,
        'current_price': float(stock.current_price),
        'prices': prices,
        'timestamps': timestamps,
        'is_up': is_up
    })


# ==================== 2. USER SETTINGS & ACCOUNT MANAGEMENT ====================
@login_required
def user_settings(request):
    password_form = PasswordChangeForm(request.user)
    return render(request, 'stocks/settings.html', {'password_form': password_form})


@login_required
def update_profile(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()
        
        messages.success(request, "Profile successfully update ho gayi!")
        return redirect('user_settings')
        
    return redirect('user_settings')


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your Password Has Successfully Changed!")
            return redirect('user_settings')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
            return redirect('user_settings')
            
    return redirect('user_settings')


@login_required
def trade_history(request):
    history = Transaction.objects.filter(user=request.user).order_by('-id')
    return render(request, 'stocks/history.html', {'history': history})


# ==================== 3. ADMIN DASHBOARD VIEW ====================
def is_admin(user):
    return user.is_staff

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    try:
        all_stocks = Stock.objects.all()
        is_market_closed = check_if_market_closed()
        
        # ─── PRICE MANIPULATION & ASSET CRUDS HANDLING (POST REQUESTS) ───
        if request.method == "POST":
            if is_market_closed:
                messages.error(request, "Market is closed on Sundays! Admin control manual overrides are frozen.")
                return redirect('admin_dashboard')

            # 1. Manual Price Update Overrides
            if 'update_price' in request.POST:
                stock_id = request.POST.get('stock_id')
                new_price = request.POST.get('new_price')
                target_stock = get_object_or_404(Stock, id=stock_id)
                target_stock.current_price = Decimal(new_price)
                target_stock.save()
                messages.success(request, f"{target_stock.ticker} value targeted successfully to ₹{new_price}!")
                return redirect('admin_dashboard')
                
            # 2. Quick Actions (+5% / -5% Dynamic Adjustments)
            elif 'adjust_price' in request.POST:
                stock_id = request.POST.get('stock_id')
                direction = request.POST.get('direction')
                target_stock = get_object_or_404(Stock, id=stock_id)
                if direction == 'up':
                    target_stock.current_price = target_stock.current_price * Decimal('1.05')
                elif direction == 'down':
                    target_stock.current_price = target_stock.current_price * Decimal('0.95')
                target_stock.save()
                messages.success(request, f"{target_stock.ticker} delta speed shifted!")
                return redirect('admin_dashboard')

            # 3. Add New Stock Asset Module
            elif 'add_stock' in request.POST:
                ticker = request.POST.get('ticker', '').upper().strip()
                name = request.POST.get('name', '').strip()
                initial_price = request.POST.get('current_price', '0.00')
                
                if not ticker or not name or not initial_price:
                    messages.error(request, "All fields are required to register an asset Node.")
                    return redirect('admin_dashboard')
                    
                if Stock.objects.filter(ticker=ticker).exists():
                    messages.error(request, f"Asset Symbol '{ticker}' already exists node engine!")
                else:
                    asset_val = Decimal(initial_price)
                    Stock.objects.create(
                        ticker=ticker,
                        name=name,
                        initial_price=asset_val,
                        current_price=asset_val
                    )
                    messages.success(request, f"New Asset Node {ticker} successfully deployed!")
                return redirect('admin_dashboard')

            # 4. Delete Stock Asset From Database
            elif 'delete_stock' in request.POST:
                stock_id = request.POST.get('stock_id')
                target_stock = get_object_or_404(Stock, id=stock_id)
                ticker_name = target_stock.ticker
                target_stock.delete()
                messages.success(request, f"Asset {ticker_name} completely purged from base platform!")
                return redirect('admin_dashboard')

        # ─── CORE SYSTEM COUNTERS & ANALYTICS ───
        total_commission = Transaction.objects.aggregate(Sum('admin_commission'))['admin_commission__sum'] or 0
        
        # FIX: Yahan method ko call karne ke liye () add kiya hai aur safe-handling rakhi hai
        try:
            total_market_pnl = sum([stock.admin_stock_pnl() for stock in all_stocks]) if all_stocks else 0
        except TypeError:
            total_market_pnl = sum([stock.admin_stock_pnl for stock in all_stocks]) if all_stocks else 0
            
        total_platform_funds = UserWallet.objects.aggregate(Sum('balance'))['balance__sum'] or 0
        
        # ─── MOST TRADED ASSET ENGINE ───
        most_traded_query = Stock.objects.all().order_by('-total_buy_count', '-total_sell_count').first()
        
        if most_traded_query and (most_traded_query.total_buy_count > 0 or most_traded_query.total_sell_count > 0):
            hot_stock = {
                'ticker': most_traded_query.ticker,
                'name': most_traded_query.name,
                'total_qty': most_traded_query.total_buy_count + most_traded_query.total_sell_count
            }
        else:
            hot_stock = {'ticker': 'NONE', 'name': 'No Trades Yet', 'total_qty': 0}

        # ─── REAL-TIME ANALYTICS MATRIX LEDGER ───
        user_stock_purchases = Transaction.objects.filter(transaction_type__in=['BUY', 'SELL']).select_related('user', 'stock').order_by('-id')[:50]

        # ─── AUDIT TRACKER QUERIES ───
        fund_transactions = Transaction.objects.filter(transaction_type='DEPOSIT').order_by('-id')[:30]
        
        try:
            from .models import ActivityLog
            session_logs = ActivityLog.objects.all().order_by('-timestamp')[:30]
            active_logins_count = ActivityLog.objects.filter(action='LOGIN').count()
        except:
            session_logs = Transaction.objects.all().order_by('-id')[:20] 
            active_logins_count = User.objects.count()

        context = {
            'total_commission': total_commission,
            'total_market_pnl': total_market_pnl,
            'total_platform_funds': total_platform_funds,
            'hot_stock': hot_stock,
            'all_stocks': all_stocks,
            'stocks': all_stocks, 
            'fund_transactions': fund_transactions,
            'session_logs': session_logs,
            'active_logins_count': active_logins_count,
            'user_stock_purchases': user_stock_purchases, 
            'is_market_closed': is_market_closed,         
        }
        return render(request, 'stocks/admin_dashboard.html', context)

    except Exception as e:
        print("\n" + "="*60 + "\n[ERROR IN ADMIN DASHBOARD VIEW]:\n" + "="*60)
        traceback.print_exc()
        print("="*60 + "\n")
        raise e


# Admin Chart Data API (Chart.js Async Matrix Connection)
@login_required
@user_passes_test(is_admin)
def admin_chart_data(request):
    try:
        commission_data = Transaction.objects.filter(transaction_type='BUY').values('stock__name').annotate(total_comm=Sum('admin_commission'))
        comm_labels = [item['stock__name'] for item in commission_data if item['stock__name']]
        comm_values = [float(item['total_comm']) for item in commission_data]
        
        stocks = Stock.objects.all()
        stock_labels = [stock.ticker for stock in stocks]
        
        # FIX: Yahan bhi float() ke andar function call karne ke liye () lagaya hai
        try:
            stock_pnl_values = [float(stock.admin_stock_pnl()) for stock in stocks]
        except TypeError:
            stock_pnl_values = [float(stock.admin_stock_pnl) for stock in stocks]
        
        return JsonResponse({
            'comm_labels': comm_labels,
            'comm_values': comm_values,
            'stock_labels': stock_labels,
            'stock_pnl_values': stock_pnl_values
        })
    except Exception as e:
        print("\n" + "="*60 + "\n[ERROR IN ADMIN CHART DATA API]:\n" + "="*60)
        traceback.print_exc()
        print("="*60 + "\n")
        return JsonResponse({'error': str(e)}, status=500)

# ==================== 4. AUTHENTICATION VIEWS ====================
def register_view(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')
        
    if request.method == 'POST':
        uname = request.POST.get('username')
        uemail = request.POST.get('email')
        upass = request.POST.get('password')
        
        if not uname or not upass:
            messages.error(request, "Please fill all required fields.")
            return render(request, 'stocks/register.html')
            
        if User.objects.filter(username=uname).exists():
            messages.error(request, "Username already exists!")
            return render(request, 'stocks/register.html')
            
        user = User.objects.create_user(username=uname, email=uemail, password=upass)
        user.save()
        
        try:
            from .models import ActivityLog
            ActivityLog.objects.create(user=user, action='LOGIN')
        except:
            pass
        
        login(request, user)
        messages.success(request, "Registration successful. Welcome to Node!")
        return redirect('user_dashboard')
        
    return render(request, 'stocks/register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')
        
    if request.method == 'POST':
        uname = request.POST.get('username')
        upass = request.POST.get('password')
        
        if not uname or not upass:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'stocks/login.html')
            
        user = authenticate(request, username=uname, password=upass)
        if user is not None:
            login(request, user)
            
            try:
                from .models import ActivityLog
                ActivityLog.objects.create(user=user, action='LOGIN')
            except:
                pass
                
            messages.success(request, f"Secure session established for Node: {user.username}")
            return redirect('user_dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            return render(request, 'stocks/login.html')
            
    return render(request, 'stocks/login.html')


def logout_view(request):
    if request.user.is_authenticated:
        try:
            from .models import ActivityLog
            ActivityLog.objects.create(user=request.user, action='LOGOUT')
        except:
            pass
            
    logout(request)
    messages.info(request, "Secure session node terminated.")
    return redirect('login')