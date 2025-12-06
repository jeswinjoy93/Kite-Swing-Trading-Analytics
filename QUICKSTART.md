# Trading Dashboard - Quick Start Guide

## 📁 Project Files

1. **gtt_api_server.py** - Flask backend with Kite Connect integration
2. **templates/gtt_orders.html** - Responsive trading dashboard
3. **config.py** - Your credentials (keep secure!)
4. **requirements.txt** - Python dependencies
5. **start_server.bat** - Easy startup script for Windows

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Credentials
Ensure `config.py` contains your Kite Connect credentials

### Step 3: Start Server
**Option A:** Double-click `start_server.bat` (Windows)  
**Option B:** Run `python gtt_api_server.py`

Then open: **http://localhost:5000**

## 📊 Dashboard Overview

### Three Powerful Tabs

#### 🎯 Tab 1: GTT Orders
- View all active GTT (Good Till Triggered) orders
- Statistics: Total Orders, Buy/Sell counts, Total Quantity
- Color-coded order types (Green=Buy, Red=Sell)

#### 💼 Tab 2: Holdings
- Complete portfolio with P&L tracking
- **Two Smart Filters**:
  - ☑️ Show only holdings WITH GTT orders (protected)
  - ☑️ Show only holdings WITHOUT GTT orders (unprotected)
- **Visual Highlights**:
  - 🟢 Green background for P&L% > 20% (high performers!)
  - Color-coded P&L (green=profit, red=loss)

#### 📈 Tab 3: Risk Analytics
- **6 Key Metrics Cards**:
  1. Stocks with GTT
  2. Total Investment
  3. Open PNL Risk
  4. Total Capital at Risk
  5. **Capital at Risk (Positive)** - Risk on profitable positions
  6. Total Profit

- **Detailed Risk Table** showing:
  - SL% (Stop Loss percentage from entry)
  - % to Target
  - RR Ratio (Risk-Reward)
  - Open PNL Risk
  - Capital Risk

- **Smart Visual Indicators**:
  - 🟢 Green background = P&L% > 20%
  - 🔴 Bold red text = Positive SL% (warning!)
  - **Bold** = Positive Capital Risk values

## 🎨 Key Features

### Visual Highlights
- **P&L% > 20%**: Bright green background highlights your winners
- **Positive SL%**: Bold red warning when stop loss is above entry (risky!)
- **Positive Capital Risk**: Bold text to emphasize risk exposure
- **Color-coded P&L**: Green for profits, red for losses

### Smart Filters (Holdings Tab)
- Filter to see only protected positions (with GTT)
- Filter to see unprotected positions (without GTT)
- Filters are mutually exclusive (only one active at a time)

### Responsive Design
- Works on desktop, tablet, and mobile
- All 6 stat cards fit in one row on wide screens
- Smooth animations and hover effects

## 🔧 What Happens on Startup

1. **Automated Login**:
   - Opens Chrome browser
   - Logs into Zerodha with your credentials
   - Completes 2FA using TOTP
   - Gets access token
   - Closes browser

2. **Server Starts**: Flask runs on http://localhost:5000

3. **Dashboard Ready**: Open in your browser!

## 🌐 API Endpoints

- `http://localhost:5000/` - Dashboard UI
- `http://localhost:5000/api/gtt_orders` - GTT orders (JSON)
- `http://localhost:5000/api/holdings` - Holdings data (JSON)
- `http://localhost:5000/api/risk_analytics` - Risk metrics (JSON)
- `http://localhost:5000/api/health` - Health check
- `http://localhost:5000/api/refresh_session` - Refresh Kite session

## 💡 Pro Tips

### Understanding the Metrics

**Capital Risk**: Money you could lose if position hits stop loss  
**Open PNL Risk**: Current profit at risk if SL triggers  
**SL%**: Distance between entry and stop loss (lower = tighter SL)  
**RR Ratio**: Risk-Reward ratio (>1 is good, >2 is great)  
**Capital at Risk (Positive)**: Total risk exposure on positions with positive capital risk

### Using the Filters

1. **"Show only holdings with GTT"**: See which stocks are protected
2. **"Show only holdings without GTT"**: Find stocks that need stop losses!
3. Uncheck both to see all holdings

### Reading Visual Cues

- 🟢 **Green background on P&L%**: Stock is up >20% - great trade!
- 🔴 **Red bold SL%**: Your stop loss is ABOVE entry price - check this!
- **Bold Capital Risk**: Positive values stand out for quick risk assessment

## ⚠️ Important Notes

1. **ChromeDriver**: Update path in `gtt_api_server.py` line 34 if needed
2. **First Run**: Browser will open automatically for login - this is normal!
3. **Session**: Kite sessions expire daily - restart server next trading day
4. **Security**: NEVER share or commit `config.py`!

## 🐛 Troubleshooting

### "Module not found"
```bash
pip install -r requirements.txt
```

### "ChromeDriver not found"
- Download: https://chromedriver.chromium.org/
- Update path in `gtt_api_server.py` line 34

### Dashboard shows errors
- Ensure server is running (check terminal)
- Try: http://localhost:5000/api/refresh_session
- Check browser console (F12) for errors

### No data showing
- Verify you have active GTT orders/holdings in Kite
- Check server console for error messages
- Ensure credentials in `config.py` are correct

## 📱 Mobile Access

Access from your phone:
1. Find your computer's IP address
2. Open `http://YOUR_IP:5000` on phone
3. Both devices must be on same network

## 🎯 Quick Reference

### Tabs
- **GTT Orders**: View and manage GTT orders
- **Holdings**: Portfolio with smart filters
- **Risk Analytics**: Advanced risk metrics

### Filters (Holdings Tab)
- With GTT: Protected positions
- Without GTT: Unprotected positions

### Visual Highlights
- Green background: P&L% > 20%
- Red bold: Positive SL% (warning)
- Bold: Positive Capital Risk

### Refresh
Click "Refresh Data" button in any tab to reload latest data

---

**Ready?** Double-click `start_server.bat` and open http://localhost:5000 in your browser!

**Need More Help?** Check the detailed README.md file.
