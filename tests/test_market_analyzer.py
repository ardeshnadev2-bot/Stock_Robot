import pytest
import pandas as pd
import numpy as np
from src.analysis.market_analyzer import MarketAnalyzer

def test_market_analyzer_empty_df():
    """Test analyzer handles empty dataframe gracefully by returning safe dict."""
    analyzer = MarketAnalyzer()
    res = analyzer.analyze(pd.DataFrame(), "RELIANCE.NS")
    
    assert res["symbol"] == "RELIANCE.NS"
    assert res["trend"] == "Neutral"
    assert res["latest_price"] == 0.0
    assert "DISCLAIMER:" in res["disclaimer"]

def test_market_analyzer_bullish_classification():
    """Test bullish classification when price and indicators align upward."""
    analyzer = MarketAnalyzer()
    
    # Create indicator df representing bullish setup (upward trend)
    # Price = 150 (above SMA 50 = 120 and SMA 20 = 135)
    # SMA 20 > SMA 50 (Golden cross alignment)
    # RSI = 65 (Bullish momentum)
    # MACD = 2.5 > MACD Signal = 1.8 (Bullish crossover)
    df = pd.DataFrame({
        "date": [pd.Timestamp("2026-08-30")],
        "open": [148.0],
        "high": [152.0],
        "low": [147.0],
        "close": [150.0],
        "volume": [1000.0],
        "sma_20": [135.0],
        "sma_50": [120.0],
        "ema_20": [136.0],
        "ema_50": [121.0],
        "rsi_14": [65.0],
        "macd": [2.5],
        "macd_signal": [1.8],
        "macd_hist": [0.7],
        "bb_mid": [135.0],
        "bb_upper": [148.0],  # Close (150) above upper band
        "bb_lower": [122.0],
        "hist_vol_20": [22.0]
    })
    
    # We append a row to simulate double length for pct change
    df_with_prev = pd.concat([
        pd.DataFrame({
            "date": [pd.Timestamp("2026-08-29")], "open": [144.0], "high": [146.0], "low": [143.0], "close": [145.0], "volume": [800.0],
            "sma_20": [134.0], "sma_50": [119.0], "ema_20": [135.0], "ema_50": [120.0], "rsi_14": [63.0], "macd": [2.3],
            "macd_signal": [1.7], "macd_hist": [0.6], "bb_mid": [134.0], "bb_upper": [146.0], "bb_lower": [122.0], "hist_vol_20": [21.0]
        }),
        df
    ], ignore_index=True)
    
    res = analyzer.analyze(df_with_prev, "RELIANCE.NS")
    
    assert res["trend"] == "Bullish"
    assert res["latest_price"] == 150.0
    assert res["price_change_pct"] == pytest.approx(3.4482758)
    assert "Bullish" in res["sma_ema_status"]
    assert "Bullish" in res["macd_status"]
    assert "Overbought" in res["bollinger_band_position"]  # 150 >= 148

def test_market_analyzer_bearish_classification():
    """Test bearish classification when price and indicators align downward."""
    analyzer = MarketAnalyzer()
    
    # Create indicator df representing bearish setup (downward trend)
    # Price = 90 (below SMA 50 = 120 and SMA 20 = 105)
    # SMA 20 < SMA 50 (Death cross alignment)
    # RSI = 28 (Oversold/Bearish momentum)
    # MACD = -3.5 < MACD Signal = -2.8 (Bearish crossover)
    df = pd.DataFrame({
        "date": [pd.Timestamp("2026-08-30")],
        "open": [92.0],
        "high": [93.0],
        "low": [89.0],
        "close": [90.0],
        "volume": [1000.0],
        "sma_20": [105.0],
        "sma_50": [120.0],
        "ema_20": [104.0],
        "ema_50": [119.0],
        "rsi_14": [28.0],
        "macd": [-3.5],
        "macd_signal": [-2.8],
        "macd_hist": [-0.7],
        "bb_mid": [105.0],
        "bb_upper": [118.0],
        "bb_lower": [92.0],  # Close (90) below lower band
        "hist_vol_20": [40.0]  # High volatility (>35)
    })
    
    df_with_prev = pd.concat([
        pd.DataFrame({
            "date": [pd.Timestamp("2026-08-29")], "open": [94.0], "high": [95.0], "low": [92.0], "close": [93.0], "volume": [800.0],
            "sma_20": [106.0], "sma_50": [121.0], "ema_20": [105.0], "ema_50": [120.0], "rsi_14": [30.0], "macd": [-3.2],
            "macd_signal": [-2.7], "macd_hist": [-0.5], "bb_mid": [106.0], "bb_upper": [119.0], "bb_lower": [93.0], "hist_vol_20": [38.0]
        }),
        df
    ], ignore_index=True)
    
    res = analyzer.analyze(df_with_prev, "TCS.NS")
    
    assert res["trend"] == "Bearish"
    assert res["latest_price"] == 90.0
    assert res["volatility"] == "High"
    assert "Bearish" in res["sma_ema_status"]
    assert "Oversold" in res["bollinger_band_position"]  # 90 <= 92
