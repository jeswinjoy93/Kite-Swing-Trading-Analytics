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

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to store KiteConnect instance
kite = None
access_token = None

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
