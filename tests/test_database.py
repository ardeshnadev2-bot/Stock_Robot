import pytest
import pandas as pd
from src.database.database import DatabaseManager

def test_database_init():
    """Test database setup and table initialization."""
    # Use in-memory database to isolate testing
    db = DatabaseManager(db_path=":memory:")
    
    # Check tables were created
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
    assert "market_data" in tables
    assert "analysis_results" in tables

def test_database_save_and_retrieve_market_data():
    """Test saving processed market data and fetching it back."""
    db = DatabaseManager(db_path=":memory:")
    
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-01", "2026-08-02"]),
        "open": [100.0, 101.0],
        "high": [105.0, 106.0],
        "low": [95.0, 96.0],
        "close": [102.0, 103.0],
        "adjusted_close": [102.0, 103.0],
        "volume": [1000, 1100]
    })
    
    # Save to database
    rows_saved = db.save_market_data(df, "RELIANCE.NS", "1d")
    assert rows_saved == 2
    
    # Retrieve from database
    retrieved = db.get_market_data("RELIANCE.NS", "1d")
    assert not retrieved.empty
    assert len(retrieved) == 2
    assert "date" in retrieved.columns
    assert list(retrieved["close"]) == [102.0, 103.0]
    
    # Test retrieve with date range
    retrieved_range = db.get_market_data("RELIANCE.NS", "1d", "2026-08-01 00:00:00", "2026-08-01 23:59:59")
    assert len(retrieved_range) == 1
    assert retrieved_range.iloc[0]["close"] == 102.0

def test_database_duplicate_prevention():
    """Test database avoids saving duplicate rows using UNIQUE constraint UPSERT."""
    db = DatabaseManager(db_path=":memory:")
    
    df1 = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-01"]),
        "open": [100.0],
        "high": [105.0],
        "low": [95.0],
        "close": [102.0],
        "adjusted_close": [102.0],
        "volume": [1000]
    })
    
    df2 = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-01"]),
        "open": [100.0],
        "high": [105.0],
        "low": [95.0],
        "close": [105.0],  # Updated close price
        "adjusted_close": [105.0],
        "volume": [1200]
    })
    
    # Save both dataframes (same date, same ticker, same interval)
    db.save_market_data(df1, "TCS.NS", "1d")
    db.save_market_data(df2, "TCS.NS", "1d")
    
    # Retrieve and verify only 1 row exists (with updated values)
    retrieved = db.get_market_data("TCS.NS", "1d")
    assert len(retrieved) == 1
    assert retrieved.iloc[0]["close"] == 105.0
    assert retrieved.iloc[0]["volume"] == 1200.0

def test_database_save_and_retrieve_analysis():
    """Test saving and retrieving technical analysis summaries."""
    db = DatabaseManager(db_path=":memory:")
    
    # Save analysis results
    success = db.save_analysis_result(
        symbol="INFY.NS",
        analysis_date="2026-08-30",
        trend="Bullish",
        rsi=62.5,
        macd=1.2,
        volatility="Medium",
        signal="RSI and MACD indicate upward trend."
    )
    
    assert success is True
    
    # Retrieve analysis results
    latest = db.get_latest_analysis("INFY.NS")
    assert latest is not None
    assert latest["symbol"] == "INFY.NS"
    assert latest["trend"] == "Bullish"
    assert latest["rsi"] == 62.5
    assert latest["macd"] == 1.2
    assert latest["volatility"] == "Medium"
    assert latest["signal"] == "RSI and MACD indicate upward trend."
