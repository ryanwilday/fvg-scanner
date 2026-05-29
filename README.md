# FVG Scanner

Detects Fair Value Gaps (FVGs) across stocks and crypto on user-defined timeframes. Alerts surface in a web portal.

## Data sources
- **Stocks** — Yahoo Finance (~15 min delayed, free, no API key)
- **Crypto** — Coinbase Advanced Trade public API (real-time, free, no key)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

## Usage

1. Add a symbol, select stock or crypto, pick a timeframe, click **Add**
2. Click **Scan Now** to immediately scan all watchlist items
3. Scans also run automatically on each candle close for the configured timeframe
4. Bullish FVGs (green) and bearish FVGs (red) appear as cards
5. A "mitigated" badge appears when price trades back through the gap zone

## Supported timeframes

`1m`, `5m`, `15m`, `1h`, `4h`, `6h`, `1d`, `1w`

## Supported symbols

- **Stocks**: any ticker valid on Yahoo Finance (e.g. `AAPL`, `TSLA`, `SPY`)
- **Crypto**: any pair on Coinbase (e.g. `BTC`, `ETH`, `SOL` — auto-appends `-USD`)
