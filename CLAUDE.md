# CLAUDE.md — Kite Swing Trading Analytics

## Project Overview

A real-time trading analytics dashboard for Zerodha Kite users managing swing trading positions with GTT (Good Till Triggered) orders. It provides portfolio risk metrics, technical/market health analysis via EMA indicators, and interactive visualizations — all served through a Flask backend and vanilla JS single-page frontend.

## Tech Stack

- **Backend:** Python 3.11, Flask 3.0.0
- **API Client:** KiteConnect 4.2.0 (Zerodha brokerage API)
- **Browser Automation:** Selenium 4.15.2 + webdriver-manager (automated Kite login with TOTP 2FA)
- **Market Data:** yfinance (Yahoo Finance) with daily file-based caching
- **Data Processing:** pandas
- **Frontend:** Single HTML file — vanilla JavaScript, CSS3 glassmorphism design, no build step

## Repository Structure

```
├── gtt_api_server.py        # Flask backend (all API routes, Kite session, caching logic)
├── templates/
│   └── gtt_orders.html      # Full SPA frontend (HTML + CSS + JS, ~1500 lines)
├── stock_data/              # Daily cached stock/index JSON files (gitignored data)
├── config.py                # Credentials — NEVER committed (see config_example.py)
├── config_example.py        # Template for config.py
├── requirements.txt         # Python dependencies
├── Makefile                 # run, install, clean targets
├── start_server.bat         # Windows startup script
├── README.md                # Full documentation
└── QUICKSTART.md            # Quick start guide
```

## Commands

```bash
# Install dependencies
make install          # or: pip install -r requirements.txt

# Run the server (starts on http://0.0.0.0:5002)
make run              # or: python gtt_api_server.py

# Clean Python cache
make clean
```

There are no tests, linters, or CI/CD pipelines configured in this project.

## Configuration

Copy `config_example.py` to `config.py` and fill in Zerodha credentials:
```python
api_key = "..."
api_secret = "..."
user_id = "..."
password = "..."
totp_secret = "..."
```

**CRITICAL:** `config.py` is in `.gitignore` — never commit credentials.

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Serves the dashboard HTML |
| `GET /api/gtt_orders` | Active GTT orders |
| `GET /api/holdings` | Portfolio holdings with P&L |
| `GET /api/risk_analytics` | Risk metrics for GTT-protected positions |
| `GET /api/technical_health` | EMA analysis (10/20/50/200-day) for held stocks |
| `GET /api/market_health` | EMA analysis for 18 market indices |
| `GET /api/refresh_session` | Manually refresh Kite session |
| `GET /api/health` | Health check |

## Architecture & Key Patterns

### Backend (`gtt_api_server.py`)

- **Lazy session initialization:** Kite session is created on the first API call, not at startup. `initialize_kite_session()` uses Selenium to automate the Zerodha login flow with TOTP.
- **Global state:** `kite` and `access_token` are module-level globals reused across requests.
- **Daily file cache:** Stock and index data from yfinance is cached as JSON in `stock_data/` with filenames like `{SYMBOL}_{YYYY-MM-DD}.json` and `INDEX_{symbol}_{YYYY-MM-DD}.json`. Cache is validated on load and re-fetched if corrupt or missing sufficient data (minimum 50 days).
- **EMA calculation:** Uses pandas `ewm()` for 10/20/50/200-day exponential moving averages, adapting to available data length.
- **Logging:** Console output uses prefixes: `[OK]`, `[ERROR]`, `[WARN]`, `[CACHE]`, `[FETCH]`, `[INFO]`.

### Frontend (`templates/gtt_orders.html`)

- **Single-file SPA** with 7 tabs: GTT Orders, Holdings, Risk Analytics, Proximity, Technical Health, Market Health, Portfolio Heatmap.
- **Vanilla JS** with `async/await` + Fetch API for all backend communication.
- **No framework or build process** — edit the HTML file directly.
- **Glassmorphism UI** with gradient backgrounds (`#667eea` to `#764ba2`), Inter font, responsive CSS grid (`auto-fit` + `minmax`).
- **Color conventions:** Green = profit/bullish/buy, Red = loss/bearish/sell, Yellow = warning/proximity.

## Development Guidelines

### When modifying the backend:
- All routes are in `gtt_api_server.py` — there is no router separation.
- Return JSON from API routes using `jsonify()`. Include error details in the response body.
- Wrap API calls to Kite in try-except — sessions can expire and need refresh.
- Use the existing caching pattern (`get_stock_data_with_cache` / `get_index_data_with_cache`) when adding new data sources.
- The server runs with `debug=True` by default on port 5002.

### When modifying the frontend:
- Everything lives in `templates/gtt_orders.html` — styles in `<style>`, scripts in `<script>`.
- Follow the existing tab pattern: add a tab button, a content div, a `load*` function, and wire it into `switchTab()`.
- Maintain responsive design — use CSS grid with `auto-fit` and test at mobile/tablet/desktop widths.
- Keep the glassmorphism visual style (semi-transparent whites, subtle shadows, gradient accents).

### General conventions:
- No type checking, linting, or formatting tools are configured.
- Commit messages should be descriptive of the feature or fix. The project uses a mix of conventional-commit-style (`feat:`, `fix:`) and plain descriptive messages.
- The `stock_data/` directory contains cached market data and should not be committed (it's auto-generated).
- Never hardcode API keys or credentials anywhere outside `config.py`.

## Market Indices Tracked

The Market Health tab tracks 18 indices: Nifty 50, Nifty Midcap 150, Bank Nifty, and 15 sectoral indices (IT, Auto, Pharma, FMCG, Metal, Realty, Energy, Infrastructure, PSE, PSU Bank, Media, Commodities, Consumption, Services, MNC).
