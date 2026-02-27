"""
Flask API Server for GTT Orders
This server fetches GTT orders from Kite Connect API and serves them via REST API
"""

from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from kiteconnect import KiteConnect
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

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to store KiteConnect instance
kite = None
access_token = None

# Short-TTL cache for GTT orders (60 seconds)
_gtt_cache = {'data': None, 'fetched_at': 0}

# In-memory EMA cache keyed by (cache_key, date_str)
_ema_cache = {}

# Data directory for caching stock data
DATA_DIR = Path(__file__).parent / 'stock_data'
DATA_DIR.mkdir(exist_ok=True)

def get_ema_data(stock_data, cache_key):
    """Return EMA values for a DataFrame, using in-memory cache to avoid recomputation."""
    today_date = datetime.now().strftime('%Y-%m-%d')
    key = (cache_key, today_date)
    if key in _ema_cache:
        return _ema_cache[key]

    data_length = len(stock_data)
    current_price = float(stock_data['Close'].iloc[-1])
    ema_10  = calculate_ema(stock_data, 10)  if data_length >= 10  else None
    ema_20  = calculate_ema(stock_data, 20)  if data_length >= 20  else None
    ema_50  = calculate_ema(stock_data, 50)  if data_length >= 50  else None
    ema_200 = calculate_ema(stock_data, 200) if data_length >= 200 else None

    result = {
        'current_price': round(current_price, 2),
        'ema_10':  round(float(ema_10),  2) if ema_10  is not None else None,
        'ema_20':  round(float(ema_20),  2) if ema_20  is not None else None,
        'ema_50':  round(float(ema_50),  2) if ema_50  is not None else None,
        'ema_200': round(float(ema_200), 2) if ema_200 is not None else None,
    }
    _ema_cache[key] = result
    return result


def cleanup_old_cache(days_to_keep=3):
    """Remove cached JSON files older than days_to_keep days."""
    today = datetime.now().date()
    removed = 0
    for f in DATA_DIR.glob("*.json"):
        try:
            date_str = f.stem.split('_')[-1]
            file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if (today - file_date).days > days_to_keep:
                f.unlink()
                removed += 1
        except (ValueError, IndexError):
            pass
    if removed:
        print(f"[OK] Cleaned up {removed} old cache file(s)")


def get_cached_gtts():
    """Return GTT orders, re-fetching at most once every 60 seconds"""
    import time
    if _gtt_cache['data'] is not None and time.time() - _gtt_cache['fetched_at'] < 60:
        return _gtt_cache['data']
    _gtt_cache['data'] = kite.get_gtts()
    _gtt_cache['fetched_at'] = time.time()
    return _gtt_cache['data']

def calculate_ema(data, period):
    """Calculate Exponential Moving Average for given period"""
    if len(data) < period:
        return None
    return data['Close'].ewm(span=period, adjust=False).mean().iloc[-1]

def _fetch_with_cache(yf_symbol, cache_key, label):
    """Fetch OHLCV data from yfinance with daily file caching.

    yf_symbol  — ticker passed to yf.download (e.g. 'RELIANCE.NS', '^NSEI')
    cache_key  — filename stem used for the JSON file (e.g. 'RELIANCE', 'INDEX_NSEI')
    label      — human-readable name used in log messages
    """
    today_date = datetime.now().strftime('%Y-%m-%d')
    cache_file = DATA_DIR / f"{cache_key}_{today_date}.json"

    if cache_file.exists():
        try:
            print(f"[CACHE] Loading {label} from cache")
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            if not cached_data:
                print(f"[WARN] Empty cache for {label}, re-fetching")
                cache_file.unlink()
            else:
                df = pd.DataFrame(cached_data)
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)
                if 'Close' in df.columns and len(df) >= 50:
                    return df
                print(f"[WARN] Invalid cache structure for {label}, re-fetching")
                cache_file.unlink()
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARN] Cache read error for {label}: {e}, re-fetching")
            if cache_file.exists():
                cache_file.unlink()

    try:
        print(f"[FETCH] Downloading {label} data from yfinance")
        data = yf.download(yf_symbol, period='1y', progress=False)
        if data.empty:
            print(f"[WARN] No data found for {label}")
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if 'Close' not in data.columns:
            print(f"[WARN] No 'Close' column found for {label}")
            return None
        if len(data) < 50:
            print(f"[WARN] Insufficient data for {label} ({len(data)} days, need at least 50)")
            return None
        cache_data = data.reset_index().to_dict('records')
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, default=str)
        print(f"[OK] Cached {label} data ({len(data)} days)")
        return data
    except Exception as e:
        print(f"[ERROR] Failed to fetch {label}: {e}")
        return None


def get_stock_data_with_cache(symbol, exchange='NSE'):
    """Fetch stock data from yfinance with daily caching"""
    yf_symbol = f"{symbol}.NS" if exchange == 'NSE' else symbol
    return _fetch_with_cache(yf_symbol, symbol, symbol)




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
        wait.until(EC.presence_of_element_located((By.ID, "userid")))
        driver.find_element(By.ID, "userid").send_keys(user_id)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Step 4: Generate TOTP and submit
        # Zerodha's login is a single-page flow: after password submit the same page
        # re-renders with a type="number" TOTP input (also id='userid', maxlength=6).
        # We wait for the input to become a number type as the signal the TOTP step loaded.
        wait.until(lambda d: d.find_element(By.ID, "userid").get_attribute("type") == "number")
        totp_field = wait.until(EC.element_to_be_clickable((By.ID, "userid")))
        totp = pyotp.TOTP(totp_secret).now()

        # type="number" blocks send_keys. Switch to text, set value via native setter,
        # fire React's onChange, then click submit via JS to bypass disabled state.
        driver.execute_script("""
            var el = arguments[0];
            var val = arguments[1];
            el.type = 'text';
            el.focus();
            var nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(el, val);
            el.dispatchEvent(new Event('input',  {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.type = 'number';
        """, totp_field, totp)

        driver.execute_script(
            "document.querySelector('button[type=\"submit\"]').click();"
        )

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
        
        # Fetch all GTT orders
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
        
        # Fetch holdings and GTT orders in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_holdings = executor.submit(kite.holdings)
            f_gtts = executor.submit(get_cached_gtts)
        holdings = f_holdings.result()
        gtt_orders = f_gtts.result()
        
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

        # Pre-warm cache: fetch all uncached symbols in parallel
        today_date = datetime.now().strftime('%Y-%m-%d')
        uncached = [(sym, exc) for sym, exc in symbols_data.items()
                    if not (DATA_DIR / f"{sym}_{today_date}.json").exists()]
        if uncached:
            print(f"[FETCH] Downloading {len(uncached)} uncached stocks in parallel")
            with ThreadPoolExecutor(max_workers=min(len(uncached), 8)) as executor:
                list(executor.map(lambda t: get_stock_data_with_cache(*t), uncached))

        # Calculate technical health for each stock
        technical_health = []
        for symbol, exchange in symbols_data.items():
            stock_data = get_stock_data_with_cache(symbol, exchange)
            
            if stock_data is None:
                print(f"[WARN] No data for {symbol}, skipping")
                continue
            
            print(f"[INFO] {symbol} has {len(stock_data)} days of data")
            ema = get_ema_data(stock_data, symbol)
            current_price = ema['current_price']

            bullish_signals = [
                1 if (current_price > ema[k]) else 0
                for k in ('ema_10', 'ema_20', 'ema_50', 'ema_200')
                if ema[k] is not None
            ]
            bullish_count = sum(bullish_signals)
            total_emas_available = len(bullish_signals)

            def _status(v):
                return 'Above' if v and current_price > v else ('Below' if v else 'N/A')

            health_data = {
                'symbol': symbol,
                'exchange': exchange,
                'current_price': current_price,
                'ema_10': ema['ema_10'], 'ema_10_status': _status(ema['ema_10']),
                'ema_20': ema['ema_20'], 'ema_20_status': _status(ema['ema_20']),
                'ema_50': ema['ema_50'], 'ema_50_status': _status(ema['ema_50']),
                'ema_200': ema['ema_200'], 'ema_200_status': _status(ema['ema_200']),
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


def get_index_data_with_cache(symbol, name):
    """Fetch index data from yfinance with daily caching"""
    safe_symbol = symbol.replace('^', '').replace('.', '_')
    return _fetch_with_cache(symbol, f"INDEX_{safe_symbol}", name)


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

        # Pre-warm cache: fetch all uncached indices in parallel
        today_date = datetime.now().strftime('%Y-%m-%d')
        uncached_indices = [
            (sym, nm) for sym, nm in market_indices.items()
            if not (DATA_DIR / f"INDEX_{sym.replace('^','').replace('.','_')}_{today_date}.json").exists()
        ]
        if uncached_indices:
            print(f"[FETCH] Downloading {len(uncached_indices)} uncached indices in parallel")
            with ThreadPoolExecutor(max_workers=min(len(uncached_indices), 8)) as executor:
                list(executor.map(lambda t: get_index_data_with_cache(*t), uncached_indices))

        # Calculate market health for each index
        market_health = []
        for symbol, name in market_indices.items():
            index_data = get_index_data_with_cache(symbol, name)
            
            if index_data is None:
                print(f"[WARN] No data for {name} ({symbol}), skipping")
                continue
            
            print(f"[INFO] {name} has {len(index_data)} days of data")
            safe_symbol = symbol.replace('^', '').replace('.', '_')
            ema = get_ema_data(index_data, f"INDEX_{safe_symbol}")
            current_price = ema['current_price']

            bullish_signals = [
                1 if (current_price > ema[k]) else 0
                for k in ('ema_10', 'ema_20', 'ema_50', 'ema_200')
                if ema[k] is not None
            ]
            bullish_count = sum(bullish_signals)
            total_emas_available = len(bullish_signals)

            def _status(v):
                return 'Above' if v and current_price > v else ('Below' if v else 'N/A')

            health_data = {
                'symbol': symbol,
                'name': name,
                'current_price': current_price,
                'ema_10': ema['ema_10'], 'ema_10_status': _status(ema['ema_10']),
                'ema_20': ema['ema_20'], 'ema_20_status': _status(ema['ema_20']),
                'ema_50': ema['ema_50'], 'ema_50_status': _status(ema['ema_50']),
                'ema_200': ema['ema_200'], 'ema_200_status': _status(ema['ema_200']),
                'bullish_count': bullish_count,
                'total_emas': total_emas_available
            }
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
    
    # Clean up stale cache files before starting
    cleanup_old_cache(days_to_keep=3)

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5002)
