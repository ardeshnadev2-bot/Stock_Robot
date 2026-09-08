import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from src.data.data_fetcher import DataFetcher
from src.utils.error_handler import NetworkError

def test_fetch_data_success():
    """Test successful market data fetch."""
    fetcher = DataFetcher()
    
    # Create dummy dataframe matching yfinance columns
    mock_df = pd.DataFrame({
        "Open": [100.0, 101.0],
        "High": [105.0, 106.0],
        "Low": [99.0, 100.0],
        "Close": [102.0, 103.0],
        "Volume": [1000, 1500]
    }, index=pd.date_range(start="2026-08-01", periods=2, freq="D", name="Date"))
    
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance
        
        result = fetcher.fetch_data("RELIANCE.NS", "2026-08-01", "2026-08-02")
        
        assert not result.empty
        assert len(result) == 2
        assert "Date" in result.columns
        assert list(result["Close"]) == [102.0, 103.0]

def test_fetch_data_invalid_symbol_or_empty():
    """Test behavior when yfinance returns empty dataframe (which represents invalid symbol or no data)."""
    fetcher = DataFetcher()
    
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()  # Empty response
        mock_ticker.return_value = mock_instance
        
        with pytest.raises(NetworkError) as excinfo:
            fetcher.fetch_data("INVALID", "2026-08-01", "2026-08-02")
            
        assert "No data returned for symbol" in str(excinfo.value)

def test_fetch_data_api_failure():
    """Test API network exceptions handling."""
    fetcher = DataFetcher()
    
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        # Raise generic exception to trigger retry and eventual NetworkError
        mock_instance.history.side_effect = Exception("API connection timed out")
        mock_ticker.return_value = mock_instance
        
        # We patch time.sleep to avoid waiting 2 seconds between retries during test
        with patch("time.sleep", return_value=None):
            with pytest.raises(NetworkError) as excinfo:
                fetcher.fetch_data("RELIANCE.NS", "2026-08-01", "2026-08-02")
                
            assert "Failed to fetch market data" in str(excinfo.value)
