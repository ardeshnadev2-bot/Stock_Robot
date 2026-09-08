import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from src.data.symbol_resolver import SymbolResolver

def test_symbol_resolver_exact_matches():
    """Test resolution of exact names and short tickers in registry."""
    resolver = SymbolResolver()
    
    # Registry keys matching
    symbol, suggestions = resolver.resolve("TCS")
    assert symbol == "TCS.NS"
    assert len(suggestions) == 0

    symbol, suggestions = resolver.resolve("Infosys")
    assert symbol == "INFY.NS"

    symbol, suggestions = resolver.resolve("Nifty")
    assert symbol == "^NSEI"

def test_symbol_resolver_direct_tickers():
    """Test resolution of inputs that are already valid tickers."""
    resolver = SymbolResolver()
    
    # Direct Yahoo Finance tickers
    symbol, suggestions = resolver.resolve("AAPL")
    assert symbol == "AAPL"
    
    symbol, suggestions = resolver.resolve("RELIANCE.NS")
    assert symbol == "RELIANCE.NS"

    symbol, suggestions = resolver.resolve("^NSEI")
    assert symbol == "^NSEI"

def test_symbol_resolver_normalization_and_case():
    """Test that resolver normalizes whitespace and capitalization correctly."""
    resolver = SymbolResolver()
    
    symbol, suggestions = resolver.resolve("   tcs   ")
    assert symbol == "TCS.NS"
    
    symbol, suggestions = resolver.resolve("InFy")
    assert symbol == "INFY.NS"
    
    symbol, suggestions = resolver.resolve("reliance industries")
    assert symbol == "RELIANCE.NS"

def test_symbol_resolver_suffix_handling():
    """Test that suffix .NS is handled and preserved correctly."""
    resolver = SymbolResolver()
    
    # Suffix already included
    symbol, suggestions = resolver.resolve("INFY.NS")
    assert symbol == "INFY.NS"
    
    # Ticker suffix heuristic: letters-only short words without dot get .NS appended
    symbol, suggestions = resolver.resolve("SBIN")
    assert symbol == "SBIN.NS"

def test_symbol_resolver_approximate_matches():
    """Test that misspelt inputs produce appropriate suggestions using difflib."""
    resolver = SymbolResolver()
    
    symbol, suggestions = resolver.resolve("Relince")
    assert len(suggestions) > 0
    # First suggestion should be Reliance Industries or Reliance
    assert suggestions[0]["symbol"] == "RELIANCE.NS"
    assert "Reliance" in suggestions[0]["name"]

def test_symbol_resolver_validation_offline():
    """Test offline symbol validation using the local database manager."""
    resolver = SymbolResolver()
    mock_db = MagicMock()
    
    # Case: cached data exists in database
    mock_db.get_market_data.return_value = pd.DataFrame({"close": [100.0]})
    assert resolver.validate_symbol("TCS.NS", mock_db) is True
    mock_db.get_market_data.assert_called_with("TCS.NS", "1d")

    # Case: no cached data, falls back to API
    mock_db.get_market_data.return_value = pd.DataFrame()  # Empty
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame({"Close": [100.0]})
        mock_ticker.return_value = mock_instance
        
        assert resolver.validate_symbol("TCS.NS", mock_db) is True

def test_symbol_resolver_validation_api_success():
    """Test yfinance validation with valid API ticker."""
    resolver = SymbolResolver()
    
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame({"Close": [100.0]})
        mock_ticker.return_value = mock_instance
        
        assert resolver.validate_symbol("AAPL") is True

def test_symbol_resolver_validation_api_invalid():
    """Test yfinance validation fails with invalid API ticker."""
    resolver = SymbolResolver()
    
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()  # Empty on invalid ticker
        mock_ticker.return_value = mock_instance
        
        assert resolver.validate_symbol("INVALID") is False
