import requests
import yfinance as yf
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from scanner import TIMEFRAME_MAP


# ---------------------------------------------------------------------------
# Stocks via yfinance (~15 min delayed, free)
# ---------------------------------------------------------------------------

def fetch_stock_candles(symbol: str, timeframe: str) -> List[Dict[str, Any]]:
    yf_interval, yf_period = TIMEFRAME_MAP.get(timeframe, ("1h", "30d"))
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=yf_period, interval=yf_interval, auto_adjust=True)
    if df.empty:
        return []
    df = df.reset_index()
    candles = []
    for _, row in df.iterrows():
        ts = row["Datetime"] if "Datetime" in row else row["Date"]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        candles.append({
            "time":  ts,
            "open":  float(row["Open"]),
            "high":  float(row["High"]),
            "low":   float(row["Low"]),
            "close": float(row["Close"]),
        })
    return candles


# ---------------------------------------------------------------------------
# Crypto via Coinbase Advanced Trade API (free, no auth needed for public data)
# ---------------------------------------------------------------------------

COINBASE_BASE = "https://api.coinbase.com/api/v3/brokerage/market/products"

COINBASE_GRANULARITY = {
    "1m":  "ONE_MINUTE",
    "5m":  "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "1h":  "ONE_HOUR",
    "4h":  "FOUR_HOUR" ,
    "6h":  "SIX_HOUR",
    "1d":  "ONE_DAY",
}

CANDLES_PER_FETCH = 300


def _coinbase_symbol(symbol: str) -> str:
    """Convert BTC, ETH, BTC/USD, BTCUSD -> BTC-USD format."""
    symbol = symbol.upper().replace("/", "-").replace("_", "-")
    if "-" not in symbol:
        symbol = symbol + "-USD"
    return symbol


def fetch_crypto_candles(symbol: str, timeframe: str) -> List[Dict[str, Any]]:
    cb_symbol = _coinbase_symbol(symbol)
    granularity = COINBASE_GRANULARITY.get(timeframe, "ONE_HOUR")

    url = f"{COINBASE_BASE}/{cb_symbol}/candles"
    params = {"granularity": granularity, "limit": CANDLES_PER_FETCH}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Coinbase] Error fetching {cb_symbol}: {e}")
        return []

    candles = []
    for c in data.get("candles", []):
        candles.append({
            "time":  datetime.fromtimestamp(int(c["start"]), tz=timezone.utc),
            "open":  float(c["open"]),
            "high":  float(c["high"]),
            "low":   float(c["low"]),
            "close": float(c["close"]),
        })

    # Coinbase returns newest first — reverse so oldest is first
    candles.sort(key=lambda x: x["time"])
    return candles


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def fetch_candles(symbol: str, asset_type: str, timeframe: str) -> List[Dict[str, Any]]:
    if asset_type == "crypto":
        return fetch_crypto_candles(symbol, timeframe)
    return fetch_stock_candles(symbol, timeframe)


def fetch_current_price(symbol: str, asset_type: str) -> Optional[float]:
    try:
        if asset_type == "crypto":
            cb_symbol = _coinbase_symbol(symbol)
            url = f"{COINBASE_BASE}/{cb_symbol}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return float(resp.json()["price"])
        else:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            return float(info.last_price)
    except Exception as e:
        print(f"[price] Error fetching price for {symbol}: {e}")
        return None
