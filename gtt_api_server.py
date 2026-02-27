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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, parse_qs
from config import api_key, api_secret, user_id, password, totp_secret
import yfinance as yf
import pandas as pd
import os
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to store KiteConnect instance
kite = None
access_token = None

# Data directory for caching stock data
DATA_DIR = Path(__file__).parent / 'stock_data'
DATA_DIR.mkdir(exist_ok=True)

# --- In-memory cache for Kite API responses ---
_kite_cache = {}
KITE_CACHE_TTL = 60  # seconds

def get_cached_holdings():
    """Return holdings from cache if fresh, otherwise fetch from Kite API."""
    if 'holdings' in _kite_cache:
        data, ts = _kite_cache['holdings']
        if time.time() - ts < KITE_CACHE_TTL:
            print("[CACHE] Using cached holdings")
            return data
    data = kite.holdings()
    _kite_cache['holdings'] = (data, time.time())
    return data

def get_cached_gtts():
    """Return GTT orders from cache if fresh, otherwise fetch from Kite API."""
    if 'gtts' in _kite_cache:
        data, ts = _kite_cache['gtts']
        if time.time() - ts < KITE_CACHE_TTL:
            print("[CACHE] Using cached GTT orders")
            return data
    data = kite.get_gtts()
    _kite_cache['gtts'] = (data, time.time())
    return data

def invalidate_kite_cache():
    """Clear the in-memory Kite API cache."""
    _kite_cache.clear()

# --- Shared helpers ---

def parse_holding(h):
    """Parse a raw Kite holding into a normalized dict with MTF-aware quantities."""
    regular_qty = h['quantity'] + h['t1_quantity']
    mtf_qty = h['mtf'].get('quantity', 0) if isinstance(h.get('mtf'), dict) else 0
    total_qty = regular_qty + mtf_qty
    regular_investment = regular_qty * h['average_price']
    mtf_investment = h['mtf'].get('value', 0) if isinstance(h.get('mtf'), dict) else 0
    investment = regular_investment + mtf_investment
    return {
        'symbol': h['tradingsymbol'],
        'exchange': h['exchange'],
        'regular_qty': regular_qty,
        'mtf_qty': mtf_qty,
        'total_qty': total_qty,
        'avg_price': h['average_price'],
        'last_price': h['last_price'],
        'investment': investment,
        'pnl': h['pnl'],
        'day_change': h['day_change'],
        'day_change_percentage': h['day_change_percentage'],
    }

def build_health_data(stock_data, identifier_fields):
    """Build EMA health dict for a stock or index given its DataFrame."""
    data_length = len(stock_data)
    current_price = stock_data['Close'].iloc[-1]
    emas = {p: calculate_ema(stock_data, p) if data_length >= p else None for p in [10, 20, 50, 200]}

    bullish_count = sum(1 for v in emas.values() if v is not None and current_price > v)
    total_emas = sum(1 for v in emas.values() if v is not None)

    health = {
        **identifier_fields,
        'current_price': round(current_price, 2),
        'bullish_count': bullish_count,
        'total_emas': total_emas,
    }
    for period, val in emas.items():
        health[f'ema_{period}'] = round(val, 2) if val is not None else None
        health[f'ema_{period}_status'] = ('Above' if current_price > val else 'Below') if val is not None else 'N/A'
    return health

def calculate_ema(data, period):
    """Calculate Exponential Moving Average for given period"""
    if len(data) < period:
        return None
    return data['Close'].ewm(span=period, adjust=False).mean().iloc[-1]

def _get_data_with_cache(yf_symbol, display_name, cache_prefix=""):
    """Unified yfinance data fetcher with daily file caching.

    Args:
        yf_symbol: The Yahoo Finance ticker (e.g. "RELIANCE.NS" or "^NSEI").
        display_name: Human-readable name for log messages.
        cache_prefix: Optional prefix for cache filenames (e.g. "INDEX_").
    """
    today_date = datetime.now().strftime('%Y-%m-%d')
    safe_name = display_name.replace('^', '').replace('.', '_')
    cache_file = DATA_DIR / f"{cache_prefix}{safe_name}_{today_date}.json"

    if cache_file.exists():
        try:
            print(f"[CACHE] Loading {display_name} from cache")
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)

            if not cached_data or len(cached_data) == 0:
                print(f"[WARN] Empty cache for {display_name}, re-fetching")
                cache_file.unlink()
            else:
                df = pd.DataFrame(cached_data)
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)

                if 'Close' in df.columns and len(df) >= 50:
                    return df
                else:
                    print(f"[WARN] Invalid cache structure for {display_name}, re-fetching")
                    cache_file.unlink()
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARN] Cache read error for {display_name}: {str(e)}, re-fetching")
            if cache_file.exists():
                cache_file.unlink()

    try:
        print(f"[FETCH] Downloading {display_name} data from yfinance")
        stock_data = yf.download(yf_symbol, period='1y', progress=False)

        if stock_data.empty:
            print(f"[WARN] No data found for {display_name}")
            return None

        if isinstance(stock_data.columns, pd.MultiIndex):
            stock_data.columns = stock_data.columns.get_level_values(0)

        if 'Close' not in stock_data.columns:
            print(f"[WARN] No 'Close' column found for {display_name}")
            return None

        if len(stock_data) < 50:
            print(f"[WARN] Insufficient data for {display_name} ({len(stock_data)} days, need at least 50)")
            return None

        cache_data = stock_data.reset_index().to_dict('records')
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, default=str)

        print(f"[OK] Cached {display_name} data ({len(stock_data)} days)")
        return stock_data

    except Exception as e:
        print(f"[ERROR] Failed to fetch {display_name}: {str(e)}")
        return None

def get_stock_data_with_cache(symbol, exchange='NSE'):
    """Fetch stock data from yfinance with daily caching."""
    yf_symbol = f"{symbol}.NS" if exchange == 'NSE' else symbol
    return _get_data_with_cache(yf_symbol, symbol)

def get_index_data_with_cache(symbol, name):
    """Fetch index data from yfinance with daily caching."""
    return _get_data_with_cache(symbol, name, cache_prefix="INDEX_")




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
        wait = WebDriverWait(driver, 15)
        driver.get(login_url)

        # Step 3: Enter Zerodha ID and password
        userid_field = wait.until(EC.presence_of_element_located((By.ID, "userid")))
        userid_field.send_keys(user_id)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Step 4: Generate TOTP and submit
        totp_field = wait.until(EC.presence_of_element_located((By.ID, "userid")))
        totp = pyotp.TOTP(totp_secret).now()
        totp_field.send_keys(totp)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Step 5: Wait for redirect and extract request_token from URL
        wait.until(EC.url_contains("request_token"))
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
        
        # Fetch all GTT orders (with in-memory caching)
        gtt_orders = get_cached_gtts()

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
        
        # Fetch holdings (with in-memory caching)
        holdings = get_cached_holdings()

        # Format holdings data using shared parser
        formatted_holdings = []
        for h in holdings:
            parsed = parse_holding(h)
            if parsed['total_qty'] != 0:
                pnl_percent = (parsed['pnl'] / parsed['investment'] * 100) if parsed['investment'] > 0 else 0
                formatted_holdings.append({
                    'symbol': parsed['symbol'],
                    'exchange': parsed['exchange'],
                    'regular_qty': parsed['regular_qty'],
                    'mtf_qty': parsed['mtf_qty'],
                    'total_qty': parsed['total_qty'],
                    'avg_price': round(parsed['avg_price'], 2),
                    'last_price': round(parsed['last_price'], 2),
                    'investment': round(parsed['investment'], 2),
                    'pnl': round(parsed['pnl'], 2),
                    'pnl_percent': round(pnl_percent, 2),
                    'day_change': round(parsed['day_change'], 2),
                    'day_change_percent': round(parsed['day_change_percentage'], 2)
                })
        
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
        
        # Fetch holdings and GTT orders (with in-memory caching)
        holdings = get_cached_holdings()
        gtt_orders = get_cached_gtts()

        # Create dictionaries for quick lookup using shared parser
        holdings_dict = {}
        for h in holdings:
            parsed = parse_holding(h)
            if parsed['total_qty'] != 0:
                holdings_dict[parsed['symbol']] = parsed
        
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
        
        # Fetch GTT orders to get list of stocks (with in-memory caching)
        gtt_orders = get_cached_gtts()

        # Get unique symbols from active GTT orders
        symbols_data = {}
        for order in gtt_orders:
            if order['status'] == 'active':
                symbol = order['condition']['tradingsymbol']
                exchange = order['condition']['exchange']
                if symbol not in symbols_data:
                    symbols_data[symbol] = exchange

        print(f"[OK] Found {len(symbols_data)} unique stocks with active GTT orders")

        # Fetch all stock data in parallel
        stock_data_map = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(get_stock_data_with_cache, sym, exc): sym
                for sym, exc in symbols_data.items()
            }
            for future in as_completed(futures):
                sym = futures[future]
                stock_data_map[sym] = future.result()

        # Calculate technical health for each stock using shared builder
        technical_health = []
        for symbol, exchange in symbols_data.items():
            stock_data = stock_data_map.get(symbol)
            if stock_data is None:
                print(f"[WARN] No data for {symbol}, skipping")
                continue

            print(f"[INFO] {symbol} has {len(stock_data)} days of data")
            health_data = build_health_data(stock_data, {'symbol': symbol, 'exchange': exchange})
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


@app.route('/api/market_health')
def get_market_health():
    """Fetch and return market health data (EMA analysis) for Indian market indices"""

    try:
        # Define market indices to track
        # Using Yahoo Finance symbols for Indian indices
        market_indices = {
            # Broad Market Indices
            '^NSEI': 'Nifty 50',
            '^NSEMDCP50': 'Nifty Midcap 150',

            # Sectoral Indices
            '^NSEBANK': 'Bank Nifty',
            '^CNXIT': 'Nifty IT',
            '^CNXAUTO': 'Nifty Auto',
            '^CNXPHARMA': 'Nifty Pharma',
            '^CNXFMCG': 'Nifty FMCG',
            '^CNXMETAL': 'Nifty Metal',
            '^CNXREALTY': 'Nifty Realty',
            '^CNXENERGY': 'Nifty Energy',
            '^CNXINFRA': 'Nifty Infrastructure',
            '^CNXPSE': 'Nifty PSE',
            '^CNXPSUBANK': 'Nifty PSU Bank',
            '^CNXMEDIA': 'Nifty Media',
            '^CNXCMDT': 'Nifty Commodities',
            '^CNXCONSUM': 'Nifty Consumption',
            '^CNXSERVICE': 'Nifty Services',
            '^CNXMNC': 'Nifty MNC'
        }

        print(f"[OK] Fetching data for {len(market_indices)} market indices")

        # Fetch all index data in parallel
        index_data_map = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(get_index_data_with_cache, sym, name): (sym, name)
                for sym, name in market_indices.items()
            }
            for future in as_completed(futures):
                sym, name = futures[future]
                index_data_map[sym] = future.result()

        # Calculate market health for each index using shared builder
        market_health = []
        for symbol, name in market_indices.items():
            index_data = index_data_map.get(symbol)
            if index_data is None:
                print(f"[WARN] No data for {name} ({symbol}), skipping")
                continue

            print(f"[INFO] {name} has {len(index_data)} days of data")
            health_data = build_health_data(index_data, {'symbol': symbol, 'name': name})
            market_health.append(health_data)

        # Calculate summary statistics (consider bullish if more than half EMAs are above)
        total_indices = len(market_health)
        bullish_indices = sum(1 for index in market_health
                           if index['total_emas'] > 0 and
                           index['bullish_count'] / index['total_emas'] >= 0.5)

        summary = {
            'total_indices': total_indices,
            'bullish_indices': bullish_indices,
            'bearish_indices': total_indices - bullish_indices
        }

        print(f"[OK] Calculated market health for {total_indices} indices")
        return jsonify({
            'market_health': market_health,
            'summary': summary
        })

    except Exception as e:
        print(f"[ERROR] Error calculating market health: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'market_health': [],
            'summary': {}
        }), 500




@app.route('/api/refresh_session')
def refresh_session():
    """Manually refresh the Kite Connect session"""
    global kite, access_token
    
    kite = None
    access_token = None
    invalidate_kite_cache()

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
    print("\n" + "=" * 60)
    print("Server starting on http://localhost:5002")
    print("=" * 60)
    print("\nAvailable endpoints:")
    print("  • http://localhost:5002/              - Swing Trading Dashboard")
    print("  • http://localhost:5002/api/health     - Health check")
    print("  • http://localhost:5002/api/refresh_session - Refresh Kite session")
    print("\n" + "=" * 60 + "\n")
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5002)
