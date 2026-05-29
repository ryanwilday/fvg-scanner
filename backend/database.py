from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./fvg_scanner.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)
    asset_type = Column(String, nullable=False)  # "stock" or "crypto"
    timeframe = Column(String, nullable=False)    # "1h", "4h", "1d", etc.
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FVGAlert(Base):
    __tablename__ = "fvg_alerts"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    asset_type = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    direction = Column(String, nullable=False)   # "bullish" or "bearish"
    gap_top = Column(Float, nullable=False)
    gap_bottom = Column(Float, nullable=False)
    candle_time = Column(DateTime, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)
    mitigated = Column(Boolean, default=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
