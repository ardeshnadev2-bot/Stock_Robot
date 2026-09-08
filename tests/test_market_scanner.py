import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from src.analysis.market_scanner import MarketScanner

def test_scanner_rank_results():
    """Test that scanner ranks and groups results into categories properly sorted by score."""
    scanner = MarketScanner()
    
    mock_results = [
        {"symbol": "BULL_1", "trend": "Bullish", "score": 80},
        {"symbol": "BULL_2", "trend": "Bullish", "score": 95},
        {"symbol": "BEAR_1", "trend": "Bearish", "score": 20},
        {"symbol": "BEAR_2", "trend": "Bearish", "score": 10},
        {"symbol": "NEUT_1", "trend": "Neutral", "score": 45},
        {"symbol": "NEUT_2", "trend": "Neutral", "score": 52},
    ]
    
    ranked = scanner.rank_results(mock_results)
    
    # Assert categorized
    assert len(ranked["Bullish"]) == 2
    assert len(ranked["Bearish"]) == 2
    assert len(ranked["Neutral"]) == 2
    
    # Assert Bullish sorted by score descending (highest score first)
    assert ranked["Bullish"][0]["symbol"] == "BULL_2"  # 95 score
    assert ranked["Bullish"][0]["rank"] == 1
    assert ranked["Bullish"][1]["symbol"] == "BULL_1"  # 80 score
    assert ranked["Bullish"][1]["rank"] == 2
    
    # Assert Bearish sorted by score ascending (lowest score first, i.e. most bearish)
    assert ranked["Bearish"][0]["symbol"] == "BEAR_2"  # 10 score
    assert ranked["Bearish"][0]["rank"] == 1
    assert ranked["Bearish"][1]["symbol"] == "BEAR_1"  # 20 score
    assert ranked["Bearish"][1]["rank"] == 2
    
    # Assert Neutral sorted by proximity to 50
    # NEUT_2 (52) is 2 away from 50, NEUT_1 (45) is 5 away from 50
    assert ranked["Neutral"][0]["symbol"] == "NEUT_2"
    assert ranked["Neutral"][0]["rank"] == 1
    assert ranked["Neutral"][1]["symbol"] == "NEUT_1"
    assert ranked["Neutral"][1]["rank"] == 2

def test_scanner_skips_failed_stocks_and_continues():
    """Test scanner logs and skips a failed stock without crashing the entire scan."""
    scanner = MarketScanner()
    
    mock_db = MagicMock()
    # Cache returns None to trigger fetching
    mock_db.get_latest_analysis.return_value = None
    mock_db.get_market_data.return_value = pd.DataFrame()
    
    mock_processor = MagicMock()
    # Mock stock 1 to fail, stock 2 to succeed
    mock_processor.process_market_data.side_effect = [
        Exception("API connection failure"),  # stock 1 fails
        pd.DataFrame({
            "date": pd.date_range(start="2026-08-01", periods=60),
            "open": [100.0] * 60,
            "high": [105.0] * 60,
            "low": [95.0] * 60,
            "close": [101.0] * 60,
            "adjusted_close": [101.0] * 60,
            "volume": [1000] * 60
        })  # stock 2 succeeds
    ]
    
    universe = ["FAILING_STOCK", "TCS.NS"]
    
    # Execute scan
    results = scanner.scan_universe(
        universe=universe,
        db_manager=mock_db,
        data_processor=mock_processor,
        force_refresh=True
    )
    
    # Verify that scanning succeeded for TCS.NS and skipped FAILING_STOCK
    assert len(results) == 1
    assert results[0]["symbol"] == "TCS.NS"
    assert mock_processor.process_market_data.call_count == 2

def test_scanner_uses_fresh_cache():
    """Test that scanner retrieves today's analysis and bypasses fetching."""
    scanner = MarketScanner()
    
    mock_db = MagicMock()
    # Mock cached analysis created today (matching UTC date format)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    mock_db.get_latest_analysis.return_value = {
        "symbol": "RELIANCE.NS",
        "analysis_date": "2026-08-30",
        "trend": "Bullish",
        "rsi": 60.0,
        "macd": 1.0,
        "volatility": "Low",
        "signal": "Test signal",
        "created_at": today_str
    }
    
    # Mock cached market data in SQLite
    mock_db.get_market_data.return_value = pd.DataFrame({
        "date": pd.date_range(start="2026-08-01", periods=60),
        "open": [100.0] * 60,
        "high": [105.0] * 60,
        "low": [95.0] * 60,
        "close": [101.0] * 60,
        "adjusted_close": [101.0] * 60,
        "volume": [1000] * 60
    })
    
    mock_processor = MagicMock()
    
    # Execute scan without force refresh
    results = scanner.scan_universe(
        universe=["RELIANCE.NS"],
        db_manager=mock_db,
        data_processor=mock_processor,
        force_refresh=False
    )
    
    # Verify yfinance API fetch was NOT called because cache is fresh
    assert len(results) == 1
    assert results[0]["symbol"] == "RELIANCE.NS"
    mock_processor.process_market_data.assert_not_called()

def test_scanner_handles_stale_cache_and_successful_fetch():
    """Test that scanner retrieves stale cache, tries to fetch fresh, succeeds, and updates cache."""
    scanner = MarketScanner()
    
    mock_db = MagicMock()
    # Stale cache analysis (not today)
    mock_db.get_latest_analysis.return_value = {
        "symbol": "RELIANCE.NS",
        "analysis_date": "2026-08-20",
        "trend": "Bullish",
        "rsi": 60.0,
        "macd": 1.0,
        "volatility": "Low",
        "signal": "Test signal",
        "created_at": "2026-08-20 12:00:00"
    }
    
    # Stale cached market data in SQLite
    mock_db.get_market_data.return_value = pd.DataFrame({
        "date": pd.date_range(start="2026-08-01", periods=60),
        "open": [100.0] * 60,
        "high": [105.0] * 60,
        "low": [95.0] * 60,
        "close": [101.0] * 60,
        "adjusted_close": [101.0] * 60,
        "volume": [1000] * 60
    })
    
    mock_processor = MagicMock()
    mock_processor.process_market_data.return_value = pd.DataFrame({
        "date": pd.date_range(start="2026-08-05", periods=60),
        "open": [102.0] * 60,
        "high": [107.0] * 60,
        "low": [97.0] * 60,
        "close": [103.0] * 60,
        "adjusted_close": [103.0] * 60,
        "volume": [1100] * 60
    })
    
    results = scanner.scan_universe(
        universe=["RELIANCE.NS"],
        db_manager=mock_db,
        data_processor=mock_processor,
        force_refresh=False
    )
    
    assert len(results) == 1
    assert results[0]["symbol"] == "RELIANCE.NS"
    # yfinance API fetch WAS called because cache is stale
    mock_processor.process_market_data.assert_called_once()
    # verify it saved fresh data to SQLite
    mock_db.save_market_data.assert_called_once()

def test_scanner_handles_fetch_failure_with_stale_cache_fallback():
    """Test that if fetching fresh data fails, scanner falls back to stale cache if valid."""
    scanner = MarketScanner()
    
    mock_db = MagicMock()
    mock_db.get_latest_analysis.return_value = None  # no analysis summary
    
    # Valid stale market data (60 rows) in SQLite
    mock_db.get_market_data.return_value = pd.DataFrame({
        "date": pd.date_range(start="2026-08-01", periods=60),
        "open": [100.0] * 60,
        "high": [105.0] * 60,
        "low": [95.0] * 60,
        "close": [101.0] * 60,
        "adjusted_close": [101.0] * 60,
        "volume": [1000] * 60
    })
    
    mock_processor = MagicMock()
    # API fetch fails
    mock_processor.process_market_data.side_effect = Exception("yfinance rate limit/network error")
    
    results = scanner.scan_universe(
        universe=["RELIANCE.NS"],
        db_manager=mock_db,
        data_processor=mock_processor,
        force_refresh=False
    )
    
    # Verify scanner falls back to using SQLite cached data
    assert len(results) == 1
    assert results[0]["symbol"] == "RELIANCE.NS"
    mock_processor.process_market_data.assert_called_once()
    assert len(scanner.failed_stocks) == 0

def test_scanner_handles_fetch_failure_no_cache():
    """Test that if fetch fails and there is no cache, the stock is marked as failed."""
    scanner = MarketScanner()
    
    mock_db = MagicMock()
    mock_db.get_latest_analysis.return_value = None
    mock_db.get_market_data.return_value = None  # no cache
    
    mock_processor = MagicMock()
    mock_processor.process_market_data.side_effect = Exception("Connection timed out")
    
    results = scanner.scan_universe(
        universe=["RELIANCE.NS"],
        db_manager=mock_db,
        data_processor=mock_processor,
        force_refresh=False
    )
    
    assert len(results) == 0
    assert len(scanner.failed_stocks) == 1
    assert scanner.failed_stocks[0]["symbol"] == "RELIANCE.NS"
    assert scanner.failed_stocks[0]["stage"] == "Data Fetch"
    assert "Connection timed out" in scanner.failed_stocks[0]["reason"]

def test_scanner_skips_insufficient_data():
    """Test that if data has < 50 rows, the stock is skipped and recorded correctly."""
    scanner = MarketScanner()
    
    mock_db = MagicMock()
    mock_db.get_latest_analysis.return_value = None
    # Database cache has only 10 rows (insufficient)
    mock_db.get_market_data.return_value = pd.DataFrame({
        "date": pd.date_range(start="2026-08-01", periods=10),
        "open": [100.0] * 10,
        "high": [105.0] * 10,
        "low": [95.0] * 10,
        "close": [101.0] * 10,
        "adjusted_close": [101.0] * 10,
        "volume": [1000] * 10
    })
    
    mock_processor = MagicMock()
    # API fetch also returns insufficient data (15 rows)
    mock_processor.process_market_data.return_value = pd.DataFrame({
        "date": pd.date_range(start="2026-08-01", periods=15),
        "open": [100.0] * 15,
        "high": [105.0] * 15,
        "low": [95.0] * 15,
        "close": [101.0] * 15,
        "adjusted_close": [101.0] * 15,
        "volume": [1000] * 15
    })
    
    results = scanner.scan_universe(
        universe=["RELIANCE.NS"],
        db_manager=mock_db,
        data_processor=mock_processor,
        force_refresh=False
    )
    
    assert len(results) == 0
    assert scanner.skipped_count == 1
    assert len(scanner.failed_stocks) == 1
    assert scanner.failed_stocks[0]["symbol"] == "RELIANCE.NS"
    assert scanner.failed_stocks[0]["stage"] == "Validate Minimum Data"
    assert "Insufficient historical data" in scanner.failed_stocks[0]["reason"]

def test_scanner_extracts_volume_and_resolves_company_names():
    """Test that scanner extracts volume and resolves company names beautifully."""
    scanner = MarketScanner()
    
    mock_db = MagicMock()
    mock_db.get_latest_analysis.return_value = None
    mock_db.get_market_data.return_value = pd.DataFrame({
        "date": pd.date_range(start="2026-08-01", periods=60),
        "open": [100.0] * 60,
        "high": [105.0] * 60,
        "low": [95.0] * 60,
        "close": [101.0] * 60,
        "adjusted_close": [101.0] * 60,
        "volume": [9999.0] * 60
    })
    
    mock_processor = MagicMock()
    
    # RELIANCE.NS matches registry -> Reliance Industries (or Reliance)
    # UNRESOLVED.NS falls back -> Unresolved
    results = scanner.scan_universe(
        universe=["RELIANCE.NS", "UNRESOLVED.NS"],
        db_manager=mock_db,
        data_processor=mock_processor,
        force_refresh=False
    )
    
    assert len(results) == 2
    
    # Check volume extraction
    assert results[0]["volume"] == 9999.0
    assert results[1]["volume"] == 9999.0
    
    # Check name resolution
    assert "Reliance" in results[0]["company_name"]
    assert results[1]["company_name"] == "Unresolved"
