# GTT Orders & Risk Analytics Dashboard

A comprehensive, real-time trading dashboard for Kite Connect with GTT orders management, holdings analysis, advanced risk analytics, and technical health monitoring.

## Features

### 🎯 Five Powerful Tabs

#### 1. GTT Orders Tab
- 📊 Real-time GTT orders display
- 🎨 Color-coded order types (Buy/Sell)
- 📈 Live statistics (Total Orders, Buy/Sell counts, Total Quantity)
- 🔄 Auto-refresh capability

#### 2. Holdings Tab
- 💼 Complete portfolio overview
- 📊 P&L tracking with percentage
- 🎯 **Smart Filters**:
  - Show only holdings with GTT orders
  - Show only holdings without GTT orders
- 🌟 **Visual Highlights**:
  - P&L% > 20% highlighted with green background
  - Color-coded positive/negative P&L

#### 3. Risk Analytics Tab
- 📊 **6 Key Metrics**:
  - Stocks with GTT
  - Total Investment
  - Open PNL Risk
  - Total Capital at Risk
  - Capital at Risk (Positive) - Sum of positive capital risk values
  - Total Profit
- 📈 Detailed risk analysis table with:
  - SL% (Stop Loss percentage)
  - % to Target
  - RR Ratio (Risk-Reward Ratio)
  - Open PNL Risk
  - Capital Risk
- 🎨 **Advanced Visual Formatting**:
  - P&L% > 20% highlighted with green background
  - Positive SL% values shown in bold red (warning)
  - Positive Capital Risk values in bold
  - Color-coded P&L (green for profit, red for loss)

#### 4. Proximity Tab
- 🎯 **Visual Position Tracking**:
  - Card-based layout for each stock
  - Visual proximity indicator showing current price position between SL and Target
  - Color-coded gradient bar (red → yellow → green)
  - Quick assessment of how close positions are to targets or stop losses

#### 5. Technical Health Tab
- 📈 **EMA Analysis Dashboard**:
  - 20-day, 50-day, and 200-day Exponential Moving Averages
  - Color-coded Above/Below/N/A status badges
  - Adaptive calculation (only shows EMAs when sufficient data exists)
  - Trend strength indicators (Strong Bullish ✓✓✓, Moderate ✓✓, Weak ✓, Bearish ✗)
- ⚡ **Smart Daily Caching**:
  - Data fetched from yfinance API only once per day per stock
  - Instant loading on subsequent visits
  - Automatic cache refresh next trading day
- 📊 **Summary Statistics**:
  - Total stocks analyzed
  - Bullish stocks count (price above 50%+ of EMAs)
  - Bearish stocks count

### 🎨 Design Features
- Modern glassmorphism UI with gradient backgrounds
- Fully responsive design (desktop, tablet, mobile)
- Smooth animations and hover effects
- Clean, professional interface
- All 6 stat cards fit in one row on wide screens

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Create/update your `config.py` file with:
```python
api_key = "your_api_key"
api_secret = "your_api_secret"
user_id = "your_user_id"
password = "your_password"
totp_secret = "your_totp_secret"
```

### 3. Setup ChromeDriver

- Download ChromeDriver from: https://chromedriver.chromium.org/
- Update the path in `gtt_api_server.py` (line 34) to point to your ChromeDriver location

### 4. Run the Server

```bash
python gtt_api_server.py
```

The server will:
1. Automatically authenticate with Kite Connect
2. Start on http://localhost:5002
3. Serve the Trading Dashboard

### 5. Access the Dashboard

Open your browser and navigate to:
```
http://localhost:5002
```

## API Endpoints

- `GET /` - Trading Dashboard (HTML)
- `GET /api/gtt_orders` - Fetch GTT orders (JSON)
- `GET /api/holdings` - Fetch holdings data (JSON)
- `GET /api/risk_analytics` - Fetch risk analytics (JSON)
- `GET /api/technical_health` - Fetch technical health data with EMA analysis (JSON)
- `GET /api/health` - Health check
- `GET /api/refresh_session` - Manually refresh Kite session

## Dashboard Usage Guide

### GTT Orders Tab
1. View all active GTT orders
2. See statistics at a glance
3. Click "Refresh Data" to reload

### Holdings Tab
1. View all your holdings with P&L
2. Use filters to:
   - See only stocks with GTT orders (protected positions)
   - See only stocks without GTT orders (unprotected positions)
3. Quickly identify high-performing stocks (P&L% > 20% highlighted in green) to review for potential partial profit taking or exits.

### Risk Analytics Tab
1. **Summary Cards** show:
   - Total stocks with GTT protection
   - Total investment in protected positions
   - Open PNL Risk (potential loss if all positions hit SL)
   - Total Capital at Risk
   - Capital at Risk (Positive) - Risk exposure on profitable positions
   - Total Profit across all positions
2. **Detailed Table** shows per-stock metrics:
   - SL% - How far your stop loss is from entry
   - % to Target - Distance to target price
   - RR Ratio - Risk-Reward ratio
   - Open PNL Risk - Current profit at risk
   - Capital Risk - Initial capital at risk
3. **Visual Indicators**:
   - Green background = P&L% > 20% (high performers)
   - Bold red text = Positive SL% (warning: SL above entry)
   - Bold text = Positive Capital Risk values

### Proximity Tab
1. **Visual Cards** for each stock with GTT:
   - Color-coded proximity bar showing position between SL and Target
   - Current price display
   - SL Trigger, Target values
   - Quick visual assessment of position status

### Technical Health Tab
1. **EMA Analysis**:
   - View 20-day, 50-day, and 200-day EMAs for all stocks
   - Color-coded badges: Green (Above), Red (Below), Gray (N/A)
   - Trend strength based on how many EMAs price is above
2. **Smart Data Management**:
   - First load fetches historical data from yfinance
   - Data cached locally for 24 hours
   - Subsequent loads are instant (no API calls)
   - Cache automatically refreshes next day
3. **Summary Stats**:
   - Total stocks analyzed
   - Bullish stocks (price above majority of EMAs)
   - Bearish stocks

## Troubleshooting

### Server won't start
- Install dependencies: `pip install -r requirements.txt`
- Check `config.py` has all required credentials

### Can't fetch data
- Verify Kite Connect API credentials
- Ensure ChromeDriver path is correct
- Check if you have active GTT orders/holdings

### Dashboard shows error
- Ensure Flask server is running on port 5002
- Check browser console for errors
- Try refreshing session: http://localhost:5002/api/refresh_session

## Security Notes

⚠️ **Important**: 
- Never commit `config.py` to version control
- Keep your API keys secure
- Use environment variables in production
- Access tokens expire daily and need regeneration

## Technologies Used

- **Backend**: Flask, KiteConnect API, Selenium, yfinance
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Data Processing**: Pandas (EMA calculations, data manipulation)
- **Design**: Modern glassmorphism with gradient backgrounds
- **Authentication**: Automated login with TOTP
- **Caching**: File-based daily cache for stock data

## Key Metrics Explained

- **Capital Risk**: Amount you could lose if position hits stop loss
- **Open PNL Risk**: Current profit that could be lost if position hits SL
- **SL%**: Percentage distance between entry price and stop loss
- **RR Ratio**: Risk-Reward ratio (higher is better)
- **Capital at Risk (Positive)**: Sum of capital risk for all positions with positive capital risk values

## License

This project is for personal use only. Comply with Zerodha's API usage terms and conditions.
