import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import List, Optional
import os

from database import init_db, get_db, WatchlistItem, FVGAlert
from scanner import detect_fvgs, check_mitigation
from data_fetcher import fetch_candles, fetch_current_price, fetch_stock_candles_batch
import scheduler as sched

app = FastAPI(title="FVG Scanner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WatchlistCreate(BaseModel):
    symbol: str
    asset_type: str   # "stock" or "crypto"
    timeframe: str    # "1h", "4h", "1d", etc.


class WatchlistOut(BaseModel):
    id: int
    symbol: str
    asset_type: str
    timeframe: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FVGOut(BaseModel):
    id: int
    symbol: str
    asset_type: str
    timeframe: str
    direction: str
    gap_top: float
    gap_bottom: float
    candle_time: datetime
    detected_at: datetime
    mitigated: bool

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Core scan logic
# ---------------------------------------------------------------------------

def run_scan_for_timeframe(timeframe: str):
    from database import SessionLocal
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter(
            WatchlistItem.active == True,
            WatchlistItem.timeframe == timeframe,
        ).all()

        # Batch fetch all stocks in one API call to avoid rate limiting
        stock_items = [i for i in items if i.asset_type == "stock"]
        crypto_items = [i for i in items if i.asset_type == "crypto"]

        candle_map = {}
        if stock_items:
            batch = fetch_stock_candles_batch([i.symbol for i in stock_items], timeframe)
            candle_map.update(batch)
        for item in crypto_items:
            candle_map[item.symbol] = fetch_candles(item.symbol, item.asset_type, item.timeframe)

        for item in items:
            candles = candle_map.get(item.symbol, [])
            if len(candles) < 3:
                continue

            fvgs = detect_fvgs(candles)

            for fvg in fvgs:
                exists = db.query(FVGAlert).filter(
                    FVGAlert.symbol == item.symbol,
                    FVGAlert.timeframe == item.timeframe,
                    FVGAlert.direction == fvg["direction"],
                    FVGAlert.candle_time == fvg["candle_time"],
                ).first()

                if not exists:
                    alert = FVGAlert(
                        symbol=item.symbol,
                        asset_type=item.asset_type,
                        timeframe=item.timeframe,
                        direction=fvg["direction"],
                        gap_top=fvg["gap_top"],
                        gap_bottom=fvg["gap_bottom"],
                        candle_time=fvg["candle_time"],
                    )
                    db.add(alert)

        # Update mitigation status — fetch each symbol's price once, not once per alert
        active_alerts = db.query(FVGAlert).filter(
            FVGAlert.mitigated == False,
            FVGAlert.timeframe == timeframe,
        ).all()

        price_cache: dict = {}
        for alert in active_alerts:
            if alert.symbol not in price_cache:
                price_cache[alert.symbol] = fetch_current_price(alert.symbol, alert.asset_type)
            price = price_cache[alert.symbol]
            if price and check_mitigation({"gap_top": alert.gap_top, "gap_bottom": alert.gap_bottom}, price):
                alert.mitigated = True

        db.commit()
        print(f"[scan] Completed scan for timeframe={timeframe} at {datetime.now(timezone.utc)}")
    except Exception as e:
        print(f"[scan] Error during scan: {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    init_db()
    sched.start()

    from database import SessionLocal
    db = SessionLocal()
    try:
        timeframes = {item.timeframe for item in db.query(WatchlistItem).filter(WatchlistItem.active == True).all()}
        for tf in timeframes:
            sched.register_timeframe(tf, run_scan_for_timeframe)
    finally:
        db.close()


@app.on_event("shutdown")
def on_shutdown():
    sched.shutdown()


# ---------------------------------------------------------------------------
# Watchlist endpoints
# ---------------------------------------------------------------------------

VALID_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "6h", "1d", "1w"}
VALID_ASSET_TYPES = {"stock", "crypto"}


@app.get("/api/watchlist", response_model=List[WatchlistOut])
def get_watchlist(db: Session = Depends(get_db)):
    return db.query(WatchlistItem).filter(WatchlistItem.active == True).all()


@app.post("/api/watchlist", response_model=WatchlistOut)
def add_to_watchlist(item: WatchlistCreate, db: Session = Depends(get_db)):
    if item.asset_type not in VALID_ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"asset_type must be one of {VALID_ASSET_TYPES}")
    if item.timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"timeframe must be one of {VALID_TIMEFRAMES}")

    symbol = item.symbol.upper().strip()
    existing = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).first()
    if existing:
        if not existing.active:
            existing.active = True
            existing.timeframe = item.timeframe
            db.commit()
            db.refresh(existing)
            sched.register_timeframe(item.timeframe, run_scan_for_timeframe)
            return existing
        raise HTTPException(status_code=409, detail="Symbol already in watchlist")

    db_item = WatchlistItem(symbol=symbol, asset_type=item.asset_type, timeframe=item.timeframe)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    sched.register_timeframe(item.timeframe, run_scan_for_timeframe)
    return db_item


@app.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(symbol: str, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol.upper()).first()
    if not item:
        raise HTTPException(status_code=404, detail="Symbol not found")
    item.active = False
    db.commit()
    return {"message": f"{symbol.upper()} removed from watchlist"}


# ---------------------------------------------------------------------------
# FVG alert endpoints
# ---------------------------------------------------------------------------

@app.get("/api/alerts", response_model=List[FVGOut])
def get_alerts(
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    mitigated: Optional[bool] = None,
    days_back: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(FVGAlert)
    if symbol:
        query = query.filter(FVGAlert.symbol == symbol.upper())
    if direction:
        query = query.filter(FVGAlert.direction == direction)
    if mitigated is not None:
        query = query.filter(FVGAlert.mitigated == mitigated)
    if days_back is not None:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        query = query.filter(FVGAlert.candle_time >= cutoff)
    return query.order_by(FVGAlert.detected_at.desc()).limit(limit).all()


@app.post("/api/scan")
def manual_scan(db: Session = Depends(get_db)):
    """Trigger an immediate scan for all active watchlist items."""
    timeframes = {item.timeframe for item in db.query(WatchlistItem).filter(WatchlistItem.active == True).all()}
    if not timeframes:
        return {"message": "No active watchlist items to scan"}
    for tf in timeframes:
        run_scan_for_timeframe(tf)
    return {"message": f"Scan triggered for timeframes: {', '.join(timeframes)}"}


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))
