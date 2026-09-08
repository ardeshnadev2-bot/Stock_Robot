import pandas as pd
import numpy as np
from datetime import datetime
from src.analysis.technical_indicators import TechnicalIndicators
from src.utils.logger import log_info, log_error

class MarketAnalyzer:
    """Analyzes market indicators and classifies stock trends and volatility."""

    def analyze(self, df_with_indicators: pd.DataFrame, symbol: str) -> dict:
        """
        Performs trend, volatility, and momentum analysis on a DataFrame with computed indicators.
        
        Args:
            df_with_indicators (pd.DataFrame): DataFrame containing indicators (sma, rsi, macd, etc.)
            symbol (str): Stock symbol.
            
        Returns:
            dict: Structured dictionary containing analysis results, metrics, and summary.
        """
        if df_with_indicators is None or df_with_indicators.empty:
            return self._empty_analysis(symbol)
            
        # Get the latest row of data for metrics
        latest_row = df_with_indicators.iloc[-1]
        
        # Latest Close and Change %
        latest_close = float(latest_row['close'])
        prev_close = float(df_with_indicators.iloc[-2]['close']) if len(df_with_indicators) > 1 else latest_close
        pct_change = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0
        
        # Initialize indicator scoring
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0
        
        # 1. Moving Averages Trend Status
        sma_ema_status = "Neutral"
        if not pd.isna(latest_row.get('sma_50')) and not pd.isna(latest_row.get('sma_20')):
            price_vs_sma50 = latest_close > latest_row['sma_50']
            sma20_vs_sma50 = latest_row['sma_20'] > latest_row['sma_50']
            
            if price_vs_sma50 and sma20_vs_sma50:
                sma_ema_status = "Bullish (Price above SMA 50, Golden Cross alignment)"
                bullish_signals += 1
            elif not price_vs_sma50 and not sma20_vs_sma50:
                sma_ema_status = "Bearish (Price below SMA 50, Death Cross alignment)"
                bearish_signals += 1
            else:
                sma_ema_status = "Neutral (Mixed signals or consolidation)"
            total_signals += 1
        elif not pd.isna(latest_row.get('sma_20')):
            # fallback if sma_50 is not available
            if latest_close > latest_row['sma_20']:
                sma_ema_status = "Bullish (Price above SMA 20)"
                bullish_signals += 0.5
            else:
                sma_ema_status = "Bearish (Price below SMA 20)"
                bearish_signals += 0.5
            total_signals += 0.5

        # 2. RSI Momentum Status
        rsi_value = latest_row.get('rsi_14')
        rsi_status = "Neutral"
        momentum_summary = "Neutral"
        if not pd.isna(rsi_value):
            if rsi_value > 70:
                rsi_status = "Overbought"
                momentum_summary = "Strong Positive"
                bullish_signals += 0.5  # RSI overbought shows strong momentum (though exhaustion risk exists)
            elif rsi_value > 60:
                rsi_status = "Bullish Momentum"
                momentum_summary = "Positive"
                bullish_signals += 1
            elif rsi_value < 30:
                rsi_status = "Oversold"
                momentum_summary = "Strong Negative"
                bearish_signals += 0.5
            elif rsi_value < 40:
                rsi_status = "Bearish Momentum"
                momentum_summary = "Negative"
                bearish_signals += 1
            else:
                rsi_status = "Neutral"
                momentum_summary = "Neutral"
            total_signals += 1

        # 3. MACD Status
        macd_val = latest_row.get('macd')
        macd_signal_val = latest_row.get('macd_signal')
        macd_hist_val = latest_row.get('macd_hist')
        macd_status = "Neutral"
        if not pd.isna(macd_val) and not pd.isna(macd_signal_val):
            if macd_val > macd_signal_val:
                macd_status = "Bullish (MACD Line is above Signal Line)"
                bullish_signals += 1
            else:
                macd_status = "Bearish (MACD Line is below Signal Line)"
                bearish_signals += 1
            total_signals += 1

        # 4. Volatility Level & Bollinger Bands Position
        hist_vol = latest_row.get('hist_vol_20')
        volatility_level = "Medium"
        if not pd.isna(hist_vol):
            if hist_vol > 35:
                volatility_level = "High"
            elif hist_vol < 15:
                volatility_level = "Low"
            else:
                volatility_level = "Medium"
        else:
            hist_vol = 0.0

        bb_position = "Within Bands"
        bb_upper = latest_row.get('bb_upper')
        bb_lower = latest_row.get('bb_lower')
        bb_mid = latest_row.get('bb_mid')
        if not pd.isna(bb_upper) and not pd.isna(bb_lower):
            if latest_close >= bb_upper:
                bb_position = "Overbought (Price >= Upper Bollinger Band)"
            elif latest_close <= bb_lower:
                bb_position = "Oversold (Price <= Lower Bollinger Band)"
            else:
                # Calculate percentage distance inside bands
                band_width = bb_upper - bb_lower
                dist_pct = ((latest_close - bb_lower) / band_width) * 100 if band_width != 0 else 50
                bb_position = f"Middle (At {dist_pct:.1f}% range from Lower to Upper)"

        # 5. Volume Analysis (Volume vs. 20-day Volume Average)
        latest_vol = float(latest_row['volume'])
        vol_status = "Average"
        if len(df_with_indicators) >= 20:
            avg_vol = df_with_indicators['volume'].rolling(window=20).mean().iloc[-1]
            if avg_vol > 0:
                vol_ratio = latest_vol / avg_vol
                if vol_ratio > 1.5:
                    vol_status = f"High Volume ({vol_ratio:.1f}x of 20-day Avg)"
                elif vol_ratio < 0.5:
                    vol_status = f"Low Volume ({vol_ratio:.1f}x of 20-day Avg)"
                else:
                    vol_status = f"Normal Volume ({vol_ratio:.1f}x of 20-day Avg)"
        else:
            vol_status = "Insufficient rows for volume average"

        # Determine Final Trend Classification
        trend_classification = "Neutral"
        score = 50
        if total_signals > 0:
            bullish_ratio = bullish_signals / total_signals
            score = int(bullish_ratio * 100)
            if bullish_ratio >= 0.6:
                trend_classification = "Bullish"
            elif bullish_ratio <= 0.35:
                trend_classification = "Bearish"
            else:
                trend_classification = "Neutral"

        # Create human-readable signals
        signals_summary = f"Indicators support a {trend_classification.lower()} view. "
        if trend_classification == "Bullish":
            signals_summary += "Strong upward momentum or support has been established."
        elif trend_classification == "Bearish":
            signals_summary += "Downward pressure is dominant. Monitor support levels."
        else:
            signals_summary += "The stock is consolidating or showing conflicting trends."

        analysis_date = latest_row['date']
        if isinstance(analysis_date, pd.Timestamp) or isinstance(analysis_date, datetime):
            analysis_date_str = analysis_date.strftime("%Y-%m-%d")
        else:
            analysis_date_str = str(analysis_date)[:10]

        result = {
            "symbol": symbol,
            "analysis_date": analysis_date_str,
            "latest_price": latest_close,
            "price_change_pct": pct_change,
            "trend": trend_classification,
            "score": score,
            "rsi_value": float(rsi_value) if not pd.isna(rsi_value) else None,
            "rsi_status": rsi_status,
            "momentum": momentum_summary,
            "macd_value": float(macd_val) if not pd.isna(macd_val) else None,
            "macd_status": macd_status,
            "sma_ema_status": sma_ema_status,
            "bollinger_band_position": bb_position,
            "volatility": volatility_level,
            "volatility_value": float(hist_vol),
            "volume_analysis": vol_status,
            "signal": signals_summary,
            "disclaimer": "DISCLAIMER: This analysis is for educational and informational purposes only. It is generated by technical indicators and does not constitute financial advice or guaranteed trading outcomes."
        }
        
        log_info("market_analyzer", f"Analysis complete for {symbol}. Classification: {trend_classification}")
        return result

    def _empty_analysis(self, symbol: str) -> dict:
        """Returns default empty result on failure or empty input."""
        return {
            "symbol": symbol,
            "analysis_date": datetime.today().strftime("%Y-%m-%d"),
            "latest_price": 0.0,
            "price_change_pct": 0.0,
            "trend": "Neutral",
            "score": 50,
            "rsi_value": None,
            "rsi_status": "Insufficient Data",
            "momentum": "Neutral",
            "macd_value": None,
            "macd_status": "Insufficient Data",
            "sma_ema_status": "Insufficient Data",
            "bollinger_band_position": "Insufficient Data",
            "volatility": "Low",
            "volatility_value": 0.0,
            "volume_analysis": "Insufficient Data",
            "signal": "No analysis available due to lack of historical price data.",
            "disclaimer": "DISCLAIMER: This analysis is for educational and informational purposes only. It is generated by technical indicators and does not constitute financial advice or guaranteed trading outcomes."
        }
