import pandas as pd
from src.data.data_fetcher import DataFetcher
from src.data.data_validator import DataValidator
from src.utils.logger import log_info, log_error

class DataProcessor:
    """Orchestrates data fetching, validation, and preprocessing pipeline."""

    def __init__(self):
        self.fetcher = DataFetcher()
        self.validator = DataValidator()

    def process_market_data(
        self, symbol: str, start_date: str, end_date: str, interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Runs the complete data pipeline: Fetch -> Validate & Clean.
        
        Args:
            symbol (str): Ticker symbol.
            start_date (str): Start date.
            end_date (str): End date.
            interval (str): Interval.
            
        Returns:
            pd.DataFrame: Validated and cleaned DataFrame.
        """
        try:
            # 1. Fetch raw data
            raw_df = self.fetcher.fetch_data(symbol, start_date, end_date, interval)
            
            # 2. Validate and Clean data
            processed_df = self.validator.validate_and_clean(raw_df)
            
            log_info("data_processor", f"Successfully processed {len(processed_df)} rows of data for {symbol}.")
            return processed_df
            
        except Exception as e:
            log_error(
                module_name="data_processor",
                error_type=type(e).__name__,
                message=f"Failed to process market data for {symbol}: {str(e)}",
                action="Propagate Exception",
                exc_info=True
            )
            raise
