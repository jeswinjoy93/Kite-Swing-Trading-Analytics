"""
Flask API Server for GTT Orders
This server fetches GTT orders from Kite Connect API and serves them via REST API
"""

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from kiteconnect import KiteConnect
import time
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from urllib.parse import urlparse, parse_qs
from config import api_key, api_secret, user_id, password, totp_secret
import yfinance as yf
import pandas as pd
import os
import json
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to store KiteConnect instance
kite = None
access_token = None

# Data directory for caching stock data
DATA_DIR = Path(__file__).parent / 'stock_data'
DATA_DIR.mkdir(exist_ok=True)

def calculate_ema(data, period):
    """Calculate Exponential Moving Average for given period"""
    if len(data) < period:
        return None
    return data['Close'].ewm(span=period, adjust=False).mean().iloc[-1]

def get_stock_data_with_cache(symbol, exchange='NSE'):
    """Fetch stock data from yfinance with daily caching"""
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # NSE symbols need .NS suffix for yfinance
    yf_symbol = f"{symbol}.NS" if exchange == 'NSE' else symbol
    
    # Check for cached file
    cache_file = DATA_DIR / f"{symbol}_{today_date}.json"
    
    if cache_file.exists():
        try:
            print(f"[CACHE] Loading {symbol} from cache")
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            
            # Validate cached data
            if not cached_data or len(cached_data) == 0:
                print(f"[WARN] Empty cache for {symbol}, re-fetching")
                cache_file.unlink()  # Delete invalid cache
            else:
                # Reconstruct DataFrame with proper index
                df = pd.DataFrame(cached_data)
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)
                
                # Validate that we have the required column
                if 'Close' in df.columns and len(df) >= 50:
                    return df
                else:
                    print(f"[WARN] Invalid cache structure for {symbol}, re-fetching")
                    cache_file.unlink()  # Delete invalid cache
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARN] Cache read error for {symbol}: {str(e)}, re-fetching")
            if cache_file.exists():
                cache_file.unlink()  # Delete corrupted cache
    
    # Fetch fresh data from yfinance
    try:
        print(f"[FETCH] Downloading {symbol} data from yfinance")
        # Fetch 1 year to get as much historical data as possible
        stock_data = yf.download(yf_symbol, period='1y', progress=False)
        
        if stock_data.empty:
            print(f"[WARN] No data found for {symbol}")
            return None
        
        # Handle multi-level columns from yfinance (when downloading single stock)
        if isinstance(stock_data.columns, pd.MultiIndex):
            # Flatten multi-level columns
            stock_data.columns = stock_data.columns.get_level_values(0)
        
        # Check if we have the Close column
        if 'Close' not in stock_data.columns:
            print(f"[WARN] No 'Close' column found for {symbol}")
            return None
        
        # Require at least 50 days of data for basic EMA calculations
        if len(stock_data) < 50:
            print(f"[WARN] Insufficient data for {symbol} ({len(stock_data)} days, need at least 50)")
            return None
        
        # Save to cache
        cache_data = stock_data.reset_index().to_dict('records')
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, default=str)
        
        print(f"[OK] Cached {symbol} data ({len(stock_data)} days)")
        return stock_data
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch {symbol}: {str(e)}")
        return None




def initialize_kite_session():
    """Initialize Kite Connect session with authentication"""
    global kite, access_token
    
    try:
        # Step 1: Get the login URL
        kite = KiteConnect(api_key=api_key)
        login_url = kite.login_url()
        
        # Step 2: Setup Selenium for automated login
        # Selenium 4+ automatically manages ChromeDriver
        driver = webdriver.Chrome()
        driver.get(login_url)
        
        # Step 3: Enter Zerodha ID and password
        time.sleep(5)
        driver.find_element(By.ID, "userid").send_keys(user_id)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Step 4: Generate TOTP and submit
        time.sleep(5)
        totp = pyotp.TOTP(totp_secret).now()
        driver.find_element(By.ID, "userid").send_keys(totp)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Step 5: Wait for redirect and extract request_token from URL
        time.sleep(5)
        current_url = driver.current_url
        driver.quit()
        
        # Extract request_token from redirected URL
        parsed_url = urlparse(current_url)
        request_token = parse_qs(parsed_url.query).get("request_token")[0]
        
        # Step 6: Generate access token
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        
        print(f"[OK] Kite Connect session initialized successfully")
        print(f"[OK] Access Token: {access_token[:20]}...")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error initializing Kite session: {str(e)}")
        return False

@app.route('/')
def index():
    """Serve the GTT orders HTML page"""
    return render_template('gtt_orders.html')

@app.route('/api/gtt_orders')
def get_gtt_orders():
    """Fetch and return active GTT orders"""
    global kite, access_token
    
    try:
        # Initialize session if not already done
        if kite is None or access_token is None:
            if not initialize_kite_session():
                return jsonify({
                    'error': 'Failed to initialize Kite Connect session',
                    'orders': []
                }), 500
        
        # Fetch all GTT orders
        gtt_orders = kite.get_gtts()
        
        # Filter only active orders and format them
        active_orders = []
        for order in gtt_orders:
            if order['status'] == 'active':
                formatted_order = {
                    'id': order['id'],
                    'exchange': order['condition']['exchange'],
                    'symbol': order['condition']['tradingsymbol'],
                    'sl_trigger': order['condition']['trigger_values'][0],
                    'tgt_trigger': order['condition']['trigger_values'][1] if len(order['condition']['trigger_values']) > 1 else 0,
                    'type': order['orders'][0]['transaction_type'],
                    'qty': order['orders'][0]['quantity'],
                    'sl_price': order['orders'][0]['price'],
                    'status': order['status']
                }
                active_orders.append(formatted_order)
        
        print(f"[OK] Fetched {len(active_orders)} active GTT orders")
        return jsonify(active_orders)
        
    except Exception as e:
        print(f"[ERROR] Error fetching GTT orders: {str(e)}")
        return jsonify({
            'error': str(e),
            'orders': []
        }), 500

@app.route('/api/holdings')
def get_holdings():
    """Fetch and return holdings data"""
    global kite, access_token
    
    try:
        # Initialize session if not already done
        if kite is None or access_token is None:
            if not initialize_kite_session():
                return jsonify({
                    'error': 'Failed to initialize Kite Connect session',
                    'holdings': []
                }), 500
        
        # Fetch holdings
        holdings = kite.holdings()
        
        # Format holdings data
        formatted_holdings = []
        for h in holdings:
            # Calculate total quantity including MTF
            regular_qty = h['quantity'] + h['t1_quantity']
            mtf_qty = 0
            
            # Extract MTF quantity if exists
            if isinstance(h.get('mtf'), dict):
                mtf_qty = h['mtf'].get('quantity', 0)
            
            total_qty = regular_qty + mtf_qty
            
            if total_qty != 0:
                # Calculate investment including MTF
                regular_investment = regular_qty * h['average_price']
                mtf_investment = 0
                
                if isinstance(h.get('mtf'), dict):
                    mtf_investment = h['mtf'].get('value', 0)
                
                total_investment = regular_investment + mtf_investment
                
                # Calculate P&L percentage
                pnl_percent = (h['pnl'] / total_investment * 100) if total_investment > 0 else 0
                
                formatted_holding = {
                    'symbol': h['tradingsymbol'],
                    'exchange': h['exchange'],
                    'regular_qty': regular_qty,
                    'mtf_qty': mtf_qty,
                    'total_qty': total_qty,
                    'avg_price': round(h['average_price'], 2),
                    'last_price': round(h['last_price'], 2),
                    'investment': round(total_investment, 2),
                    'pnl': round(h['pnl'], 2),
                    'pnl_percent': round(pnl_percent, 2),
                    'day_change': round(h['day_change'], 2),
                    'day_change_percent': round(h['day_change_percentage'], 2)
                }
                formatted_holdings.append(formatted_holding)
        
        print(f"[OK] Fetched {len(formatted_holdings)} holdings")
        return jsonify(formatted_holdings)
        
    except Exception as e:
        print(f"[ERROR] Error fetching holdings: {str(e)}")
        return jsonify({
            'error': str(e),
            'holdings': []
        }), 500

@app.route('/api/risk_analytics')
def get_risk_analytics():
    """Fetch and return risk analytics for stocks with GTT orders"""
    global kite, access_token
    
    try:
        # Initialize session if not already done
        if kite is None or access_token is None:
            if not initialize_kite_session():
                return jsonify({
                    'error': 'Failed to initialize Kite Connect session',
                    'analytics': []
                }), 500
        
        # Fetch holdings and GTT orders
        holdings = kite.holdings()
        gtt_orders = kite.get_gtts()
        
        # Create dictionaries for quick lookup
        holdings_dict = {}
        for h in holdings:
            regular_qty = h['quantity'] + h['t1_quantity']
            mtf_qty = 0
            if isinstance(h.get('mtf'), dict):
                mtf_qty = h['mtf'].get('quantity', 0)
            total_qty = regular_qty + mtf_qty
            
            if total_qty != 0:
                holdings_dict[h['tradingsymbol']] = {
                    'symbol': h['tradingsymbol'],
                    'exchange': h['exchange'],
                    'regular_qty': regular_qty,
                    'mtf_qty': mtf_qty,
                    'total_qty': total_qty,
                    'avg_price': h['average_price'],
                    'last_price': h['last_price'],
                    'pnl': h['pnl']
                }
        
        # Create GTT dictionary
        gtt_dict = {}
        for order in gtt_orders:
            if order['status'] == 'active':
                symbol = order['condition']['tradingsymbol']
                gtt_dict[symbol] = {
                    'sl_trigger': order['condition']['trigger_values'][0],
                    'tgt_trigger': order['condition']['trigger_values'][1] if len(order['condition']['trigger_values']) > 1 else 0,
                    'type': order['orders'][0]['transaction_type'],
                    'qty': order['orders'][0]['quantity']
                }
        
        # Calculate risk analytics for common stocks
        risk_analytics = []
        total_open_risk = 0
        total_capital_risk = 0
        positive_capital_risk = 0  # New: sum of capital risk for profitable positions
        total_profit = 0
        total_investment = 0
        
        for symbol in holdings_dict.keys():
            if symbol in gtt_dict:
                h = holdings_dict[symbol]
                g = gtt_dict[symbol]
                
                # Calculate investment using total quantity (includes MTF)
                investment = h['total_qty'] * h['avg_price']
                
                # Calculate P&L percentage
                pnl_percent = (h['pnl'] / investment * 100) if investment > 0 else 0
                
                # Calculate risk metrics
                sl_percentage = ((h['avg_price'] - g['sl_trigger']) / h['avg_price'] * 100) if h['avg_price'] != 0 else 0
                capital_risk = (h['avg_price'] - g['sl_trigger']) * h['total_qty'] if h['total_qty'] != 0 else 0
                tgt_percentage = ((g['tgt_trigger'] - h['last_price']) / h['last_price'] * 100) if h['last_price'] != 0 else 0
                rr_ratio = ((h['last_price'] - h['avg_price']) / (h['avg_price'] - g['sl_trigger'])) if (h['avg_price'] - g['sl_trigger']) != 0 else 0
                open_pnl_risk = (h['last_price'] - g['sl_trigger']) * h['total_qty'] if h['total_qty'] != 0 else 0
                
                analytics_item = {
                    'symbol': symbol,
                    'exchange': h['exchange'],
                    'total_qty': h['total_qty'],
                    'avg_price': round(h['avg_price'], 2),
                    'last_price': round(h['last_price'], 2),
                    'investment': round(investment, 2),
                    'sl_trigger': round(g['sl_trigger'], 2),
                    'tgt_trigger': round(g['tgt_trigger'], 2),
                    'pnl': round(h['pnl'], 2),
                    'pnl_percent': round(pnl_percent, 2),
                    'sl_percent': round(sl_percentage, 2),
                    'tgt_percent': round(tgt_percentage, 2),
                    'rr_ratio': round(rr_ratio, 2),
                    'open_pnl_risk': round(open_pnl_risk, 2),
                    'capital_risk': round(capital_risk, 2)
                }
                
                risk_analytics.append(analytics_item)
                
                # Update totals
                total_open_risk += open_pnl_risk
                total_capital_risk += capital_risk
                total_profit += h['pnl']
                total_investment += investment
                
                # Add to positive capital risk if capital_risk value is positive
                if capital_risk > 0:
                    positive_capital_risk += capital_risk
        
        # Add summary statistics
        summary = {
            'total_stocks': len(risk_analytics),
            'total_investment': round(total_investment, 2),
            'total_open_risk': round(total_open_risk, 2),
            'total_capital_risk': round(total_capital_risk, 2),
            'positive_capital_risk': round(positive_capital_risk, 2),  # New field
            'total_profit': round(total_profit, 2)
        }
        
        print(f"[OK] Calculated risk analytics for {len(risk_analytics)} stocks")
        return jsonify({
            'analytics': risk_analytics,
            'summary': summary
        })
        
    except Exception as e:
        print(f"[ERROR] Error calculating risk analytics: {str(e)}")
        return jsonify({
            'error': str(e),
            'analytics': [],
            'summary': {}
        }), 500

@app.route('/api/technical_health')
def get_technical_health():
    """Fetch and return technical health data (EMA analysis) for stocks with GTT orders"""
    global kite, access_token
    
    try:
        # Initialize session if not already done
        if kite is None or access_token is None:
            if not initialize_kite_session():
                return jsonify({
                    'error': 'Failed to initialize Kite Connect session',
                    'technical_health': []
                }), 500
        
        # Fetch GTT orders to get list of stocks
        gtt_orders = kite.get_gtts()
        
        # Get unique symbols from active GTT orders
        symbols_data = {}
        for order in gtt_orders:
            if order['status'] == 'active':
                symbol = order['condition']['tradingsymbol']
                exchange = order['condition']['exchange']
                if symbol not in symbols_data:
                    symbols_data[symbol] = exchange
        
        print(f"[OK] Found {len(symbols_data)} unique stocks with active GTT orders")
        
        # Calculate technical health for each stock
        technical_health = []
        for symbol, exchange in symbols_data.items():
            # Fetch stock data with caching
            stock_data = get_stock_data_with_cache(symbol, exchange)
            
            if stock_data is None:
                print(f"[WARN] No data for {symbol}, skipping")
                continue
            
            data_length = len(stock_data)
            print(f"[INFO] {symbol} has {data_length} days of data")
            
            # Get current price (last close)
            current_price = stock_data['Close'].iloc[-1]
            
            # Calculate EMAs only if we have enough data
            ema_10 = calculate_ema(stock_data, 10) if data_length >= 10 else None
            ema_20 = calculate_ema(stock_data, 20) if data_length >= 20 else None
            ema_50 = calculate_ema(stock_data, 50) if data_length >= 50 else None
            ema_200 = calculate_ema(stock_data, 200) if data_length >= 200 else None
            
            # Count how many EMAs are above (only count those that exist)
            bullish_signals = []
            if ema_10 is not None:
                bullish_signals.append(1 if current_price > ema_10 else 0)
            if ema_20 is not None:
                bullish_signals.append(1 if current_price > ema_20 else 0)
            if ema_50 is not None:
                bullish_signals.append(1 if current_price > ema_50 else 0)
            if ema_200 is not None:
                bullish_signals.append(1 if current_price > ema_200 else 0)
            
            total_emas_available = len(bullish_signals)
            bullish_count = sum(bullish_signals)
            
            # Determine if price is above or below each EMA
            health_data = {
                'symbol': symbol,
                'exchange': exchange,
                'current_price': round(current_price, 2),
                'ema_10': round(ema_10, 2) if ema_10 is not None else None,
                'ema_10_status': 'Above' if ema_10 and current_price > ema_10 else ('Below' if ema_10 else 'N/A'),
                'ema_20': round(ema_20, 2) if ema_20 is not None else None,
                'ema_20_status': 'Above' if ema_20 and current_price > ema_20 else ('Below' if ema_20 else 'N/A'),
                'ema_50': round(ema_50, 2) if ema_50 is not None else None,
                'ema_50_status': 'Above' if ema_50 and current_price > ema_50 else ('Below' if ema_50 else 'N/A'),
                'ema_200': round(ema_200, 2) if ema_200 is not None else None,
                'ema_200_status': 'Above' if ema_200 and current_price > ema_200 else ('Below' if ema_200 else 'N/A'),
                'bullish_count': bullish_count,
                'total_emas': total_emas_available
            }
            
            technical_health.append(health_data)
        
        # Sort by symbol alphabetically
        technical_health.sort(key=lambda x: x['symbol'])
        
        # Calculate summary statistics (consider bullish if more than half EMAs are above)
        total_stocks = len(technical_health)
        bullish_stocks = sum(1 for stock in technical_health 
                           if stock['total_emas'] > 0 and 
                           stock['bullish_count'] / stock['total_emas'] >= 0.5)
        
        summary = {
            'total_stocks': total_stocks,
            'bullish_stocks': bullish_stocks,
            'bearish_stocks': total_stocks - bullish_stocks
        }
        
        print(f"[OK] Calculated technical health for {total_stocks} stocks")
        return jsonify({
            'technical_health': technical_health,
            'summary': summary
        })
        
    except Exception as e:
        print(f"[ERROR] Error calculating technical health: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'technical_health': [],
            'summary': {}
        }), 500


@app.route('/api/refresh_session')
def refresh_session():
    """Manually refresh the Kite Connect session"""
    global kite, access_token
    
    kite = None
    access_token = None
    
    if initialize_kite_session():
        return jsonify({'status': 'success', 'message': 'Session refreshed successfully'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to refresh session'}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'session_active': kite is not None and access_token is not None
    })

if __name__ == '__main__':
    print("=" * 60)
    print("GTT Orders API Server")
    print("=" * 60)
    print("\nInitializing Kite Connect session...")
    
    # Initialize session on startup
    initialize_kite_session()
    
    print("\n" + "=" * 60)
    print("Server starting on http://localhost:5000")
    print("=" * 60)
    print("\nAvailable endpoints:")
    print("  • http://localhost:5000/              - GTT Orders Dashboard")
    print("  • http://localhost:5000/api/gtt_orders - Get GTT orders (JSON)")
    print("  • http://localhost:5000/api/health     - Health check")
    print("  • http://localhost:5000/api/refresh_session - Refresh Kite session")
    print("\n" + "=" * 60 + "\n")
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5002)
