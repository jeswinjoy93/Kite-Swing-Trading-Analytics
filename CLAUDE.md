# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A GTT Orders & Risk Analytics Dashboard for Zerodha's Kite Connect API. It's a Flask + Vanilla JS single-page web app running on `localhost:5002` for swing traders managing portfolios with Good-Till-Triggered stop-loss and target orders.

## Commands

```bash
make install      # pip install -r requirements.txt
make run          # python gtt_api_server.py
make clean        # Remove __pycache__
```

Or directly: `python gtt_api_server.py`

## Setup Required

Copy `config_example.py` to `config.py` and fill in Zerodha credentials:
```python
api_key = "..."
api_secret = "..."
user_id = "..."
password = "..."
totp_secret = "..."
```

`config.py` is gitignored — never commit it.

## Architecture

**Single backend file:** `gtt_api_server.py` — Flask app with lazy Kite session initialization. The Kite Connect session is created on the first API call, not at startup. Selenium automates the Zerodha login (Chrome + TOTP) to obtain the access token.

**Single frontend file:** `templates/gtt_orders.html` — ~1500-line single-page app with embedded CSS and vanilla JS. No build step, no framework. Seven tabs; each tab lazy-loads its data on first access.

**Caching:** `stock_data/` directory holds per-day JSON files named `{SYMBOL}_{YYYY-MM-DD}.json` and `INDEX_{SYMBOL}_{YYYY-MM-DD}.json`. The cache logic in `get_stock_data_with_cache()` and `get_index_data_with_cache()` skips yfinance calls if a valid file for today already exists.

## API Endpoints

All served from `localhost:5002`:

| Endpoint | Description |
|---|---|
| `GET /` | Serves `gtt_orders.html` |
| `GET /api/gtt_orders` | Active GTT orders from Kite |
| `GET /api/holdings` | Full portfolio (including MTF/margin holdings) |
| `GET /api/risk_analytics` | Per-stock risk metrics (SL%, RR ratio, capital at risk) |
| `GET /api/technical_health` | EMA analysis (10/20/50/200-day) for GTT-protected stocks |
| `GET /api/market_health` | Same EMA analysis for 18 Nifty indices |
| `GET /api/health` | Session status check |
| `GET /api/refresh_session` | Forces re-authentication |

## Frontend Patterns

- Tab switching via `switchTab(tabName)` — loads data on first visit only
- State held in module-level JS variables: `allHoldings`, `riskAnalyticsData`, `gttSymbols`
- Holdings filtering is client-side (no API re-fetch)
- API base URLs are constants at the top of the `<script>` block: `http://localhost:5002/api/...`
- Console logging convention: `[OK]`, `[ERROR]`, `[WARN]`, `[FETCH]`, `[CACHE]` prefixes

## Key Business Logic

- **Capital Risk** = `(avg_price - sl_trigger) × total_qty`
- **Open PNL Risk** = `(last_price - sl_trigger) × total_qty`
- **RR Ratio** = `(last_price - avg_price) / (avg_price - sl_trigger)`
- **Trend Strength** = count of EMAs the current price is above / total available EMAs
- Bullish = price above ≥50% of available EMAs; Bearish = below ≥50%

## Dependencies

- `kiteconnect==4.2.0` — Zerodha API SDK
- `selenium==4.15.2` + `webdriver-manager` — automated browser login
- `pyotp` — TOTP 2FA generation
- `yfinance` + `pandas` — historical data and EMA calculations
- `flask` + `flask-cors` — web server
