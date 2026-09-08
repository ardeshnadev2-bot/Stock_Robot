import pandas as pd
import yfinance as yf
from src.utils.error_handler import retry_on_failure, NetworkError
from src.utils.logger import log_info, log_error

class DataFetcher:
    """Class to fetch stock market data from yfinance API."""

    @retry_on_failure(max_retries=3, delay=2.0)
    def fetch_data(
        self, symbol: str, start_date: str, end_date: str, interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetches historical stock market data for a given ticker symbol.
        
        Args:
            symbol (str): Ticker symbol (e.g., RELIANCE.NS, ^NSEI).
            start_date (str): Start date in 'YYYY-MM-DD' format.
            end_date (str): End date in 'YYYY-MM-DD' format.
            interval (str): Data interval (e.g., '1d', '1h', '15m').
            
        Returns:
            pd.DataFrame: DataFrame containing historical stock data.
            
        Raises:
            NetworkError: If fetching fails or returning empty dataset.
        """
        log_info("data_fetcher", f"Fetching data for {symbol} ({start_date} to {end_date}, interval={interval})")
        
        try:
            # Download using yfinance Ticker object
            ticker_obj = yf.Ticker(symbol)
            df = ticker_obj.history(
                start=start_date,
                end=end_date,
                interval=interval,
                auto_adjust=False,  # We want both Close and Adjusted Close
                actions=False
            )
            
            # Check if dataframe is empty
            if df.empty:
                # yfinance sometimes returns empty dataframe silently for invalid ticker symbols
                raise NetworkError(f"No data returned for symbol '{symbol}'. The symbol may be invalid or no data exists for this period.")
            
            # Reset index to make Date a column instead of the index
            df = df.reset_index()
            
            return df
            
        except Exception as e:
            if isinstance(e, NetworkError):
                raise e
            raise NetworkError(f"Failed to fetch market data from yfinance API: {str(e)}")
