import pandas as pd
import numpy as np
from src.utils.error_handler import IndicatorError
from src.utils.logger import log_info, log_error

class TechnicalIndicators:
    """Calculates technical indicators on stock price DataFrames."""

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates all required technical indicators:
        - SMA 20, SMA 50
        - EMA 20, EMA 50
        - RSI 14
        - MACD, MACD Signal, MACD Histogram
        - Bollinger Bands (20, 2)
        - Rolling Standard Deviation (20)
        - Historical Volatility (20)
        
        Args:
            df (pd.DataFrame): Processed market data with 'close' price column.
            
        Returns:
            pd.DataFrame: DataFrame with indicator columns added.
        """
        if df is None or df.empty:
            raise IndicatorError("Cannot calculate indicators on empty/None DataFrame.")
            
        # Ensure we have required column
        if 'close' not in df.columns:
            raise IndicatorError("Missing 'close' column required for technical indicators calculation.")
            
        df_indicators = df.copy()
        n_rows = len(df_indicators)
        
        # 1. SMA calculations
        if n_rows >= 20:
            df_indicators['sma_20'] = df_indicators['close'].rolling(window=20).mean()
        else:
            df_indicators['sma_20'] = np.nan
            log_info("technical_indicators", "Skipping SMA 20: Dataset is too small (requires >= 20 rows).")
            
        if n_rows >= 50:
            df_indicators['sma_50'] = df_indicators['close'].rolling(window=50).mean()
        else:
            df_indicators['sma_50'] = np.nan
            log_info("technical_indicators", "Skipping SMA 50: Dataset is too small (requires >= 50 rows).")
            
        # 2. EMA calculations
        if n_rows >= 20:
            df_indicators['ema_20'] = df_indicators['close'].ewm(span=20, adjust=False).mean()
        else:
            df_indicators['ema_20'] = np.nan
            log_info("technical_indicators", "Skipping EMA 20: Dataset is too small (requires >= 20 rows).")
            
        if n_rows >= 50:
            df_indicators['ema_50'] = df_indicators['close'].ewm(span=50, adjust=False).mean()
        else:
            df_indicators['ema_50'] = np.nan
            log_info("technical_indicators", "Skipping EMA 50: Dataset is too small (requires >= 50 rows).")
            
        # 3. RSI 14 calculation
        if n_rows >= 15:  # Need at least 15 rows for RSI 14
            delta = df_indicators['close'].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            
            avg_gain = gain.rolling(window=14, min_periods=14).mean()
            avg_loss = loss.rolling(window=14, min_periods=14).mean()
            
            # Wilders smoothing for EMA-like average of gains and losses
            for i in range(14, len(df_indicators)):
                # Note: safe iteration checking for non-nan values
                if not pd.isna(avg_gain.iloc[i-1]):
                    avg_gain.iloc[i] = (avg_gain.iloc[i-1] * 13 + gain.iloc[i]) / 14
                    avg_loss.iloc[i] = (avg_loss.iloc[i-1] * 13 + loss.iloc[i]) / 14
            
            rs = avg_gain / avg_loss
            df_indicators['rsi_14'] = 100 - (100 / (1 + rs))
            # Handle division by zero when average loss is 0
            df_indicators.loc[avg_loss == 0, 'rsi_14'] = 100
        else:
            df_indicators['rsi_14'] = np.nan
            log_info("technical_indicators", "Skipping RSI 14: Dataset is too small (requires >= 15 rows).")
            
        # 4. MACD calculation (Standard 12, 26, 9)
        if n_rows >= 26:
            ema_12 = df_indicators['close'].ewm(span=12, adjust=False).mean()
            ema_26 = df_indicators['close'].ewm(span=26, adjust=False).mean()
            df_indicators['macd'] = ema_12 - ema_26
            df_indicators['macd_signal'] = df_indicators['macd'].ewm(span=9, adjust=False).mean()
            df_indicators['macd_hist'] = df_indicators['macd'] - df_indicators['macd_signal']
        else:
            df_indicators['macd'] = np.nan
            df_indicators['macd_signal'] = np.nan
            df_indicators['macd_hist'] = np.nan
            log_info("technical_indicators", "Skipping MACD: Dataset is too small (requires >= 26 rows).")
            
        # 5. Bollinger Bands (20-day SMA, 2 standard deviations)
        if n_rows >= 20:
            bb_mid = df_indicators['close'].rolling(window=20).mean()
            bb_std = df_indicators['close'].rolling(window=20).std()
            df_indicators['bb_mid'] = bb_mid
            df_indicators['bb_upper'] = bb_mid + (bb_std * 2)
            df_indicators['bb_lower'] = bb_mid - (bb_std * 2)
        else:
            df_indicators['bb_mid'] = np.nan
            df_indicators['bb_upper'] = np.nan
            df_indicators['bb_lower'] = np.nan
            log_info("technical_indicators", "Skipping Bollinger Bands: Dataset is too small (requires >= 20 rows).")
            
        # 6. Rolling Standard Deviation (20 days)
        if n_rows >= 20:
            df_indicators['rolling_std_20'] = df_indicators['close'].rolling(window=20).std()
        else:
            df_indicators['rolling_std_20'] = np.nan
            log_info("technical_indicators", "Skipping Rolling Std Dev: Dataset is too small (requires >= 20 rows).")
            
        # 7. Historical Volatility (Annualized 20 days)
        # Log returns = ln(close_t / close_t-1)
        # Annualized Volatility = std(log_returns) * sqrt(252) * 100
        if n_rows >= 21:  # Need 21 rows to get 20 log return values
            log_returns = np.log(df_indicators['close'] / df_indicators['close'].shift(1))
            df_indicators['hist_vol_20'] = log_returns.rolling(window=20).std() * np.sqrt(252) * 100
        else:
            df_indicators['hist_vol_20'] = np.nan
            log_info("technical_indicators", "Skipping Historical Volatility: Dataset is too small (requires >= 21 rows).")
            
        return df_indicators
