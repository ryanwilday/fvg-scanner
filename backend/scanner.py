from typing import List, Dict, Any


TIMEFRAME_MAP = {
    "1m":  ("1m",  "1d"),
    "5m":  ("5m",  "5d"),
    "15m": ("15m", "5d"),
    "1h":  ("1h",  "30d"),
    "4h":  ("4h",  "60d"),
    "1d":  ("1d",  "180d"),
    "1w":  ("1wk", "730d"),
}


def detect_fvgs(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Expects candles as list of dicts with keys: time, open, high, low, close.
    Returns list of FVG dicts.
    """
    fvgs = []

    for i in range(1, len(candles) - 1):
        prev = candles[i - 1]
        curr = candles[i]
        nxt  = candles[i + 1]

        # Bullish FVG: gap between high of candle[i-1] and low of candle[i+1]
        if nxt["low"] > prev["high"]:
            fvgs.append({
                "direction":   "bullish",
                "gap_top":     nxt["low"],
                "gap_bottom":  prev["high"],
                "candle_time": curr["time"],
            })

        # Bearish FVG: gap between low of candle[i-1] and high of candle[i+1]
        elif nxt["high"] < prev["low"]:
            fvgs.append({
                "direction":   "bearish",
                "gap_top":     prev["low"],
                "gap_bottom":  nxt["high"],
                "candle_time": curr["time"],
            })

    return fvgs


def check_mitigation(fvg: Dict, current_price: float) -> bool:
    """Returns True if price has traded back into the FVG zone."""
    return fvg["gap_bottom"] <= current_price <= fvg["gap_top"]
