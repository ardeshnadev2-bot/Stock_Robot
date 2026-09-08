import pytest
import pandas as pd
import numpy as np
from src.analysis.technical_indicators import TechnicalIndicators
from src.utils.error_handler import IndicatorError

def test_indicators_on_empty_df():
    """Test calculations raise appropriate error on empty DataFrame."""
    with pytest.raises(IndicatorError) as excinfo:
        TechnicalIndicators.calculate_indicators(pd.DataFrame())
    assert "Cannot calculate indicators on empty" in str(excinfo.value)

def test_indicators_insufficient_rows():
    """Test calculations with small datasets (e.g. 5 rows). Should return NaNs instead of crashing."""
    df_small = pd.DataFrame({
        "date": pd.date_range(start="2026-08-01", periods=5),
        "open": [100.0] * 5,
        "high": [105.0] * 5,
        "low": [95.0] * 5,
        "close": [101.0, 102.0, 103.0, 102.0, 101.0],
        "adjusted_close": [101.0, 102.0, 103.0, 102.0, 101.0],
        "volume": [1000] * 5
    })
    
    result = TechnicalIndicators.calculate_indicators(df_small)
    
    # Assert column structures are created but filled with NaN
    assert "sma_20" in result.columns
    assert "sma_50" in result.columns
    assert "rsi_14" in result.columns
    assert "macd" in result.columns
    assert "bb_upper" in result.columns
    assert "hist_vol_20" in result.columns
    
    assert pd.isna(result["sma_20"].iloc[-1])
    assert pd.isna(result["rsi_14"].iloc[-1])
    assert pd.isna(result["macd"].iloc[-1])

def test_indicators_correctness():
    """Test that indicators calculate values correctly when enough data is provided."""
    # Create 60 days of mock price data (increasing linearly)
    prices = [float(100 + i) for i in range(60)]
    df_large = pd.DataFrame({
        "date": pd.date_range(start="2026-07-01", periods=60),
        "open": prices,
        "high": [p + 2 for p in prices],
        "low": [p - 2 for p in prices],
        "close": prices,
        "adjusted_close": prices,
        "volume": [1000] * 60
    })
    
    result = TechnicalIndicators.calculate_indicators(df_large)
    
    # Verify indicator calculations are non-NaN at the end of the range
    assert not pd.isna(result["sma_20"].iloc[-1])
    assert not pd.isna(result["sma_50"].iloc[-1])
    assert not pd.isna(result["ema_20"].iloc[-1])
    assert not pd.isna(result["ema_50"].iloc[-1])
    assert not pd.isna(result["rsi_14"].iloc[-1])
    assert not pd.isna(result["macd"].iloc[-1])
    assert not pd.isna(result["bb_upper"].iloc[-1])
    assert not pd.isna(result["hist_vol_20"].iloc[-1])
    
    # Value assertions:
    # 20 SMA of 60 items (from 40 to 59): avg of range [140 to 159] -> 149.5
    assert result["sma_20"].iloc[-1] == pytest.approx(149.5)
    # 50 SMA of 60 items (from 10 to 59): avg of range [110 to 159] -> 134.5
    assert result["sma_50"].iloc[-1] == pytest.approx(134.5)
    # Bollinger Bands upper > mid > lower
    assert result["bb_upper"].iloc[-1] > result["bb_mid"].iloc[-1]
    assert result["bb_mid"].iloc[-1] > result["bb_lower"].iloc[-1]
