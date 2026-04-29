"""
Flask API Server for GTT Orders
This server fetches GTT orders from Kite Connect API and serves them via REST API
"""

from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, render_template, request
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
import json
from datetime import datetime
from pathlib import Path
import threading

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


# Force JSON responses for /api/* errors so the frontend never has to parse HTML.
@app.errorhandler(404)
def _api_404(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': f'Not found: {request.method} {request.path}'}), 404
    return e

@app.errorhandler(405)
def _api_405(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': f'Method not allowed: {request.method} {request.path}'}), 405
    return e

@app.errorhandler(500)
def _api_500(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': f'Server error: {e}'}), 500
    return e

# Global variable to store KiteConnect instance
kite = None
access_token = None
_kite_lock = threading.Lock()  # Prevents concurrent Selenium login race conditions

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
        # Initialize session if not already done (double-checked lock prevents concurrent logins)
        if kite is None or access_token is None:
            with _kite_lock:
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
                if not order.get('orders') or not order.get('condition', {}).get('trigger_values'):
                    print(f"[WARN] Skipping malformed GTT order id={order.get('id')}: missing orders or trigger_values")
                    continue
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

def _format_holding_base(h):
    """Extract qty and MTF info from a raw Kite holding dict."""
    regular_qty = h['quantity'] + h['t1_quantity']
    mtf_qty = 0
    mtf_investment = 0
    if isinstance(h.get('mtf'), dict):
        mtf_qty = h['mtf'].get('quantity', 0)
        mtf_investment = h['mtf'].get('value', 0)
    total_qty = regular_qty + mtf_qty
    return regular_qty, mtf_qty, total_qty, mtf_investment


@app.route('/api/holdings')
def get_holdings():
    """Fetch and return holdings data"""
    global kite, access_token
    
    try:
        # Initialize session if not already done (double-checked lock prevents concurrent logins)
        if kite is None or access_token is None:
            with _kite_lock:
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
            regular_qty, mtf_qty, total_qty, mtf_investment = _format_holding_base(h)

            if total_qty != 0:
                # Calculate investment including MTF
                regular_investment = regular_qty * h['average_price']
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
        # Initialize session if not already done (double-checked lock prevents concurrent logins)
        if kite is None or access_token is None:
            with _kite_lock:
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
            regular_qty, mtf_qty, total_qty, _ = _format_holding_base(h)
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
        
        # Group active GTTs by symbol — a symbol can have multiple GTT orders,
        # each protecting a different slice of the position.
        gtts_by_symbol = {}
        for order in gtt_orders:
            if order['status'] != 'active':
                continue
            if not order.get('orders') or not order.get('condition', {}).get('trigger_values'):
                continue
            symbol = order['condition']['tradingsymbol']
            gtts_by_symbol.setdefault(symbol, []).append({
                'gtt_id': order['id'],
                'sl_trigger': order['condition']['trigger_values'][0],
                'tgt_trigger': order['condition']['trigger_values'][1] if len(order['condition']['trigger_values']) > 1 else 0,
                'type': order['orders'][0]['transaction_type'],
                'qty': order['orders'][0]['quantity']
            })

        # Emit one row per GTT order so multi-GTT symbols show as separate trades.
        # Per-row qty/capital_risk/open_pnl_risk reflect that GTT's protected slice;
        # avg_price/last_price/sl_percent/tgt_percent/rr_ratio are position-level and
        # therefore identical across rows for the same symbol. P&L is allocated
        # proportionally to each GTT's qty so per-row totals sum back to the holding P&L.
        risk_analytics = []
        total_open_risk = 0
        total_capital_risk = 0
        positive_capital_risk = 0
        total_profit = 0
        total_investment = 0

        for symbol, gtt_list in gtts_by_symbol.items():
            if symbol not in holdings_dict:
                continue
            h = holdings_dict[symbol]
            holding_qty = h['total_qty']
            holding_investment = holding_qty * h['avg_price']
            holding_pnl_percent = (h['pnl'] / holding_investment * 100) if holding_investment > 0 else 0

            for g in gtt_list:
                gtt_qty = g['qty']
                investment = gtt_qty * h['avg_price']
                pnl_share = (h['pnl'] * gtt_qty / holding_qty) if holding_qty else 0

                sl_percentage = ((h['avg_price'] - g['sl_trigger']) / h['avg_price'] * 100) if h['avg_price'] != 0 else 0
                capital_risk = (h['avg_price'] - g['sl_trigger']) * gtt_qty
                tgt_percentage = ((g['tgt_trigger'] - h['last_price']) / h['last_price'] * 100) if h['last_price'] != 0 else 0
                rr_ratio = ((h['last_price'] - h['avg_price']) / (h['avg_price'] - g['sl_trigger'])) if (h['avg_price'] - g['sl_trigger']) != 0 else 0
                open_pnl_risk = (h['last_price'] - g['sl_trigger']) * gtt_qty

                analytics_item = {
                    'symbol': symbol,
                    'gtt_id': g['gtt_id'],
                    'exchange': h['exchange'],
                    'total_qty': gtt_qty,
                    'holding_qty': holding_qty,
                    'avg_price': round(h['avg_price'], 2),
                    'last_price': round(h['last_price'], 2),
                    'investment': round(investment, 2),
                    'sl_trigger': round(g['sl_trigger'], 2),
                    'tgt_trigger': round(g['tgt_trigger'], 2),
                    'pnl': round(pnl_share, 2),
                    'pnl_percent': round(holding_pnl_percent, 2),
                    'sl_percent': round(sl_percentage, 2),
                    'tgt_percent': round(tgt_percentage, 2),
                    'rr_ratio': round(rr_ratio, 2),
                    'open_pnl_risk': round(open_pnl_risk, 2),
                    'capital_risk': round(capital_risk, 2)
                }

                risk_analytics.append(analytics_item)

                total_open_risk += open_pnl_risk
                total_capital_risk += capital_risk
                total_profit += pnl_share
                total_investment += investment
                if capital_risk > 0:
                    positive_capital_risk += capital_risk

        # Group rows for the same symbol together; secondary sort by SL trigger desc
        # so the tightest stop appears first.
        risk_analytics.sort(key=lambda r: (r['symbol'], -r['sl_trigger']))
        
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
        # Initialize session if not already done (double-checked lock prevents concurrent logins)
        if kite is None or access_token is None:
            with _kite_lock:
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




def _ensure_kite_session():
    """Initialize Kite if needed. Returns (ok, error_response_tuple_or_None)."""
    global kite, access_token
    if kite is None or access_token is None:
        with _kite_lock:
            if kite is None or access_token is None:
                if not initialize_kite_session():
                    return False, (jsonify({'error': 'Failed to initialize Kite Connect session'}), 500)
    return True, None


def _invalidate_gtt_cache():
    _gtt_cache['data'] = None
    _gtt_cache['fetched_at'] = 0


# Terminal Kite order statuses — once an order reaches one of these, it won't change.
_ORDER_TERMINAL_STATES = {'COMPLETE', 'REJECTED', 'CANCELLED'}


def _wait_for_order_fill(order_id, timeout_seconds=10, poll_interval=0.5):
    """Poll kite.order_history until the order reaches a terminal state or timeout.

    Returns a dict: {status, filled_qty, average_price, message}.
    On timeout returns the latest known status with filled_qty so far.
    """
    import time as _time
    deadline = _time.time() + timeout_seconds
    last = {'status': 'UNKNOWN', 'filled_qty': 0, 'average_price': 0, 'message': ''}
    while _time.time() < deadline:
        try:
            history = kite.order_history(order_id=order_id)
        except Exception as e:
            last['message'] = f'order_history error: {e}'
            _time.sleep(poll_interval)
            continue
        if history:
            latest = history[-1]
            last = {
                'status': latest.get('status', 'UNKNOWN'),
                'filled_qty': int(latest.get('filled_quantity', 0) or 0),
                'average_price': float(latest.get('average_price', 0) or 0),
                'message': latest.get('status_message') or '',
            }
            if last['status'] in _ORDER_TERMINAL_STATES:
                return last
        _time.sleep(poll_interval)
    last['message'] = last['message'] or f'No terminal status within {timeout_seconds}s'
    return last


def _shrink_or_delete_gtt(gtt_id, fill_qty):
    """After a partial/full exit, shrink the linked GTT by fill_qty (or delete if it would hit zero).

    Re-fetches the GTT to use the latest qty/triggers (in case it was edited externally).
    Returns a dict describing what happened — never raises; serializes errors into the result.
    """
    try:
        gtt = kite.get_gtt(trigger_id=int(gtt_id))
    except Exception as e:
        return {'gtt_action': 'none', 'error': f'failed to fetch GTT {gtt_id}: {e}'}

    if not gtt or gtt.get('status') != 'active':
        return {'gtt_action': 'none', 'reason': f'GTT {gtt_id} is not active (status={gtt.get("status") if gtt else "missing"})'}

    legs = gtt.get('orders') or []
    cond = gtt.get('condition') or {}
    symbol = cond.get('tradingsymbol')
    exchange = cond.get('exchange')
    triggers = cond.get('trigger_values') or []
    if not legs or not symbol or not exchange or len(triggers) < 1:
        return {'gtt_action': 'none', 'error': f'GTT {gtt_id} has unexpected shape'}

    current_qty = int(legs[0].get('quantity', 0))
    new_qty = current_qty - int(fill_qty)

    if new_qty <= 0:
        try:
            kite.delete_gtt(trigger_id=int(gtt_id))
            print(f"[OK] Deleted GTT {gtt_id} ({symbol}) — exit fill ({fill_qty}) covered remaining qty ({current_qty})")
            _invalidate_gtt_cache()
            return {'gtt_action': 'deleted', 'previous_qty': current_qty}
        except Exception as e:
            return {'gtt_action': 'none', 'error': f'delete_gtt failed: {e}'}

    # Shrink — preserve trigger_type and trigger_values, just change leg qty.
    trigger_type = gtt.get('type') or kite.GTT_TYPE_OCO
    last_price = float(cond.get('last_price') or legs[0].get('price') or triggers[0])
    new_orders = []
    for leg in legs:
        new_orders.append({
            'exchange': exchange,
            'tradingsymbol': symbol,
            'transaction_type': leg.get('transaction_type', kite.TRANSACTION_TYPE_SELL),
            'quantity': new_qty,
            'order_type': leg.get('order_type', kite.ORDER_TYPE_LIMIT),
            'product': leg.get('product', kite.PRODUCT_CNC),
            'price': float(leg.get('price', 0)),
        })
    try:
        kite.modify_gtt(
            trigger_id=int(gtt_id),
            trigger_type=trigger_type,
            tradingsymbol=symbol,
            exchange=exchange,
            trigger_values=[float(t) for t in triggers],
            last_price=last_price,
            orders=new_orders,
        )
        print(f"[OK] Shrunk GTT {gtt_id} ({symbol}) qty {current_qty} -> {new_qty}")
        _invalidate_gtt_cache()
        return {'gtt_action': 'shrunk', 'previous_qty': current_qty, 'new_qty': new_qty}
    except Exception as e:
        return {'gtt_action': 'none', 'error': f'modify_gtt failed: {e}'}


@app.route('/api/exit_position', methods=['POST'])
def exit_position():
    """Place a SELL order, wait for it to fill, then shrink (or delete) the linked GTT.

    Body: {symbol, exchange, qty, order_type: 'MARKET'|'LIMIT', price?, gtt_id?}
    Product (CNC/MTF) is auto-detected from holdings.

    Synchronous: holds the request open up to ~10s waiting for fill.
    Response: {status, order_id, fill: {status, filled_qty, average_price, message}, gtt: {gtt_action, ...}}
    """
    ok, err = _ensure_kite_session()
    if not ok:
        return err

    try:
        body = request.get_json(force=True) or {}
        symbol = body.get('symbol')
        exchange = body.get('exchange')
        qty = int(body.get('qty', 0))
        order_type = (body.get('order_type') or 'MARKET').upper()
        price = body.get('price')
        gtt_id = body.get('gtt_id')

        if not symbol or not exchange or qty <= 0:
            return jsonify({'error': 'symbol, exchange, and positive qty are required'}), 400
        if order_type not in ('MARKET', 'LIMIT'):
            return jsonify({'error': 'order_type must be MARKET or LIMIT'}), 400
        if order_type == 'LIMIT' and (price is None or float(price) <= 0):
            return jsonify({'error': 'price is required for LIMIT orders'}), 400

        holdings = kite.holdings()
        match = next((h for h in holdings if h['tradingsymbol'] == symbol and h['exchange'] == exchange), None)
        if match is None:
            return jsonify({'error': f'No holding found for {symbol} on {exchange}'}), 400

        regular_qty, mtf_qty, total_qty, _ = _format_holding_base(match)
        if qty > total_qty:
            return jsonify({'error': f'Requested qty {qty} exceeds holding qty {total_qty}'}), 400

        # Prefer regular (CNC) inventory first; fall back to MTF if regular is exhausted.
        # The kiteconnect SDK doesn't expose a PRODUCT_MTF constant — Kite's API uses the literal "MTF".
        if regular_qty >= qty:
            product = kite.PRODUCT_CNC
        elif mtf_qty >= qty:
            product = "MTF"
        else:
            return jsonify({
                'error': f'Cannot place a single order for qty {qty}: split across CNC ({regular_qty}) and MTF ({mtf_qty}). Place separate exits.'
            }), 400

        # Zerodha disabled raw MARKET orders via API — they require "market protection".
        # Emulate it: send a LIMIT priced 1% below current LTP for a SELL, which fills like
        # a market order under normal conditions but caps slippage if the book is thin.
        # tick_size on NSE/BSE equity is 0.05, so round down to a valid tick.
        MARKET_PROTECTION_PCT = 0.01
        TICK_SIZE = 0.05
        order_kwargs = {
            'variety': kite.VARIETY_REGULAR,
            'exchange': exchange,
            'tradingsymbol': symbol,
            'transaction_type': kite.TRANSACTION_TYPE_SELL,
            'quantity': qty,
            'product': product,
            'order_type': kite.ORDER_TYPE_LIMIT,
        }
        if order_type == 'MARKET':
            ltp = float(match['last_price'])
            protected_price = ltp * (1 - MARKET_PROTECTION_PCT)
            # Round down to nearest tick so the exchange accepts the price.
            protected_price = round(int(protected_price / TICK_SIZE) * TICK_SIZE, 2)
            order_kwargs['price'] = protected_price
            print(f"[INFO] Market-emulated as LIMIT @ ₹{protected_price} (LTP ₹{ltp}, {MARKET_PROTECTION_PCT*100:.0f}% protection)")
        else:
            order_kwargs['price'] = float(price)

        order_id = kite.place_order(**order_kwargs)
        print(f"[OK] Placed SELL {order_type} order_id={order_id} {symbol} qty={qty} product={product} price={order_kwargs['price']}")

        fill = _wait_for_order_fill(order_id, timeout_seconds=10)
        print(f"[INFO] Order {order_id} fill status: {fill}")

        gtt_result = {'gtt_action': 'none'}
        if fill['status'] == 'REJECTED' or fill['status'] == 'CANCELLED':
            gtt_result['reason'] = f"order {fill['status'].lower()} — leaving GTT untouched"
        elif fill['filled_qty'] <= 0:
            gtt_result['reason'] = 'no fill yet — leaving GTT untouched (use Edit to shrink manually if it fills later)'
        elif gtt_id:
            gtt_result = _shrink_or_delete_gtt(gtt_id, fill['filled_qty'])
        else:
            gtt_result['reason'] = 'no gtt_id supplied'

        # Always invalidate so subsequent reads see current GTT state regardless of branch above.
        _invalidate_gtt_cache()

        return jsonify({
            'status': 'success',
            'order_id': order_id,
            'fill': fill,
            'gtt': gtt_result,
        })

    except Exception as e:
        print(f"[ERROR] exit_position failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/modify_gtt', methods=['POST'])
def modify_gtt():
    """Modify an existing GTT order's SL trigger, target trigger, and qty.

    Body: {gtt_id, symbol, exchange, sl_trigger, tgt_trigger, qty, last_price?}
    last_price is optional — if omitted we read it from holdings (Kite uses it as the reference price).
    """
    ok, err = _ensure_kite_session()
    if not ok:
        return err

    try:
        body = request.get_json(force=True) or {}
        gtt_id = body.get('gtt_id')
        symbol = body.get('symbol')
        exchange = body.get('exchange')
        sl_trigger = float(body.get('sl_trigger', 0))
        tgt_trigger = float(body.get('tgt_trigger', 0))
        qty = int(body.get('qty', 0))
        last_price = body.get('last_price')

        if not gtt_id or not symbol or not exchange:
            return jsonify({'error': 'gtt_id, symbol, and exchange are required'}), 400
        if sl_trigger <= 0 or tgt_trigger <= 0 or qty <= 0:
            return jsonify({'error': 'sl_trigger, tgt_trigger, and qty must be positive'}), 400
        if sl_trigger >= tgt_trigger:
            return jsonify({'error': 'sl_trigger must be below tgt_trigger'}), 400

        if last_price is None:
            holdings = kite.holdings()
            match = next((h for h in holdings if h['tradingsymbol'] == symbol and h['exchange'] == exchange), None)
            if match is None:
                return jsonify({'error': f'No holding found for {symbol} to determine last_price'}), 400
            last_price = float(match['last_price'])
        else:
            last_price = float(last_price)

        orders = [
            {'exchange': exchange, 'tradingsymbol': symbol, 'transaction_type': kite.TRANSACTION_TYPE_SELL,
             'quantity': qty, 'order_type': kite.ORDER_TYPE_LIMIT, 'product': kite.PRODUCT_CNC, 'price': sl_trigger},
            {'exchange': exchange, 'tradingsymbol': symbol, 'transaction_type': kite.TRANSACTION_TYPE_SELL,
             'quantity': qty, 'order_type': kite.ORDER_TYPE_LIMIT, 'product': kite.PRODUCT_CNC, 'price': tgt_trigger},
        ]

        trigger_id = kite.modify_gtt(
            trigger_id=int(gtt_id),
            trigger_type=kite.GTT_TYPE_OCO,
            tradingsymbol=symbol,
            exchange=exchange,
            trigger_values=[sl_trigger, tgt_trigger],
            last_price=last_price,
            orders=orders,
        )
        print(f"[OK] Modified GTT trigger_id={trigger_id} {symbol} SL={sl_trigger} TGT={tgt_trigger} qty={qty}")
        _invalidate_gtt_cache()
        return jsonify({'status': 'success', 'trigger_id': trigger_id})

    except Exception as e:
        print(f"[ERROR] modify_gtt failed: {e}")
        return jsonify({'error': str(e)}), 500


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

    # Initialize Kite session once at startup, then start the server.
    # use_reloader=False prevents Werkzeug from spawning a second worker process,
    # which would otherwise re-run __main__ and trigger a duplicate browser login.
    initialize_kite_session()

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5002, use_reloader=False)
