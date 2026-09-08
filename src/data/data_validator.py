import pandas as pd
import numpy as np
from src.utils.error_handler import ValidationError
from src.utils.logger import log_info, log_error

class DataValidator:
    """Class to validate and clean raw stock market data."""

    def validate_and_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validates and cleans stock market data.
        
        Args:
            df (pd.DataFrame): Raw DataFrame containing market data.
            
        Returns:
            pd.DataFrame: Cleaned and validated DataFrame.
            
        Raises:
            ValidationError: If validation fails critically (e.g. empty dataframe, missing required columns).
        """
        if df is None:
            raise ValidationError("DataFrame is None")
            
        if df.empty:
            raise ValidationError("DataFrame is empty")
            
        # Create a copy to prevent modifying original
        df_cleaned = df.copy()
        
        # 1. Standardize and validate Date column
        date_col = None
        for col in ['Date', 'Datetime', 'date', 'datetime']:
            if col in df_cleaned.columns:
                date_col = col
                break
                
        if not date_col:
            raise ValidationError("Required column 'Date' or 'Datetime' is missing from market data.")
            
        # Rename date column to standard 'date'
        df_cleaned = df_cleaned.rename(columns={date_col: 'date'})
        
        # Parse dates to datetime objects and handle incorrect format
        try:
            df_cleaned['date'] = pd.to_datetime(df_cleaned['date'], utc=True)
            # Remove timezone info for easier handling/comparison in sqlite
            df_cleaned['date'] = df_cleaned['date'].dt.tz_localize(None)
        except Exception as e:
            raise ValidationError(f"Invalid date format: {str(e)}")
            
        # 2. Sort by date and remove duplicates
        df_cleaned = df_cleaned.sort_values(by='date')
        duplicate_count = df_cleaned.duplicated(subset=['date']).sum()
        if duplicate_count > 0:
            log_info("data_validator", f"Removing {duplicate_count} duplicate date rows.")
            df_cleaned = df_cleaned.drop_duplicates(subset=['date'])
            
        # 3. Verify required OHLCV columns exist
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in df_cleaned.columns]
        if missing_cols:
            raise ValidationError(f"Missing required market data columns: {missing_cols}")
            
        # Handle 'Adj Close' (Adjusted Close)
        if 'Adj Close' in df_cleaned.columns:
            df_cleaned = df_cleaned.rename(columns={'Adj Close': 'adjusted_close'})
        elif 'adjusted_close' not in df_cleaned.columns:
            # Fallback if yfinance didn't include it
            df_cleaned['adjusted_close'] = df_cleaned['Close']
            
        # Standardize other column names to lowercase
        df_cleaned = df_cleaned.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # Ensure correct datatypes
        numeric_cols = ['open', 'high', 'low', 'close', 'adjusted_close', 'volume']
        for col in numeric_cols:
            df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')
            
        # 4. Handle missing values
        nan_counts = df_cleaned[numeric_cols].isna().sum()
        if nan_counts.sum() > 0:
            log_info("data_validator", f"Found missing (NaN) values: {nan_counts.to_dict()}. Attempting recovery.")
            # Interpolate or fill missing pricing data, drop rows if too many missing values
            # Forward-fill price columns
            price_cols = ['open', 'high', 'low', 'close', 'adjusted_close']
            df_cleaned[price_cols] = df_cleaned[price_cols].ffill().bfill()
            
            # Fill missing volumes with 0
            df_cleaned['volume'] = df_cleaned['volume'].fillna(0)
            
            # If there are still NaN values, drop those rows
            df_cleaned = df_cleaned.dropna(subset=price_cols)
            if df_cleaned.empty:
                raise ValidationError("DataFrame contains only invalid/NaN pricing data.")
                
        # 5. Handle zero/missing volume
        df_cleaned['volume'] = df_cleaned['volume'].replace({np.nan: 0})
        # Note: volumes can be 0 (e.g. market index ^NSEI volumes are sometimes 0 on yfinance)
        
        # 6. Validate OHLC relations
        # High must be greater than or equal to Open, Close, and Low
        # Low must be less than or equal to Open, Close, and High
        invalid_high = (
            (df_cleaned['high'] < df_cleaned['open']) |
            (df_cleaned['high'] < df_cleaned['close']) |
            (df_cleaned['high'] < df_cleaned['low'])
        )
        invalid_low = (
            (df_cleaned['low'] > df_cleaned['open']) |
            (df_cleaned['low'] > df_cleaned['close']) |
            (df_cleaned['low'] > df_cleaned['high'])
        )
        
        invalid_rows_mask = invalid_high | invalid_low
        invalid_count = invalid_rows_mask.sum()
        
        if invalid_count > 0:
            log_info("data_validator", f"Detected {invalid_count} rows with invalid OHLC relationships. Correcting/Cleaning.")
            # Calculate correct high and low values using a copy of the slice before modifying either column
            ohlc_slice = df_cleaned.loc[invalid_rows_mask, ['open', 'close', 'high', 'low']]
            corrected_high = ohlc_slice.max(axis=1)
            corrected_low = ohlc_slice.min(axis=1)
            
            df_cleaned.loc[invalid_rows_mask, 'high'] = corrected_high
            df_cleaned.loc[invalid_rows_mask, 'low'] = corrected_low
            
        # Re-check to ensure no invalid relations remain
        final_invalid_high = (
            (df_cleaned['high'] < df_cleaned['open']) |
            (df_cleaned['high'] < df_cleaned['close']) |
            (df_cleaned['high'] < df_cleaned['low'])
        )
        final_invalid_low = (
            (df_cleaned['low'] > df_cleaned['open']) |
            (df_cleaned['low'] > df_cleaned['close']) |
            (df_cleaned['low'] > df_cleaned['high'])
        )
        if final_invalid_high.sum() > 0 or final_invalid_low.sum() > 0:
            raise ValidationError("Data validation failed: Persistent invalid OHLC values detected.")
            
        return df_cleaned
