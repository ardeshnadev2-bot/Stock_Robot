import sqlite3
import pandas as pd
from datetime import datetime
from src.utils.config import DB_PATH
from src.utils.error_handler import handle_db_errors, DatabaseError
from src.utils.logger import log_info, log_error
from src.database.models import (
    CREATE_MARKET_DATA_TABLE,
    CREATE_ANALYSIS_RESULTS_TABLE,
    CREATE_STOCK_NEWS_TABLE,
    UPSERT_MARKET_DATA,
    UPSERT_ANALYSIS_RESULT,
    UPSERT_STOCK_NEWS,
    SELECT_MARKET_DATA,
    SELECT_MARKET_DATA_DATE_RANGE,
    SELECT_LATEST_ANALYSIS,
    SELECT_STOCK_NEWS_BY_SYMBOL,
    SELECT_STOCK_NEWS_DATE_RANGE,
    SELECT_CACHED_ARTICLE_SENTIMENT
)

class DatabaseManager:
    """Manages SQLite database connections and CRUD operations."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn = None
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a connection to the SQLite database."""
        if self.db_path == ":memory:":
            return self._conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def __del__(self):
        if hasattr(self, '_conn') and self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

    @handle_db_errors(default_return=False)
    def init_db(self) -> bool:
        """Initializes the database schema if tables do not exist."""
        log_info("database", f"Initializing database at: {self.db_path}")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_MARKET_DATA_TABLE)
            cursor.execute(CREATE_ANALYSIS_RESULTS_TABLE)
            cursor.execute(CREATE_STOCK_NEWS_TABLE)
            conn.commit()
        return True

    @handle_db_errors(default_return=0)
    def save_market_data(self, df: pd.DataFrame, symbol: str, interval: str) -> int:
        """
        Saves a DataFrame of processed market data to the database using SQLite UPSERT logic.
        
        Args:
            df (pd.DataFrame): Cleaned and validated market data.
            symbol (str): Ticker symbol.
            interval (str): Time interval.
            
        Returns:
            int: Number of rows saved/updated.
        """
        if df is None or df.empty:
            return 0

        rows_inserted = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Prepare rows for insertion
            # SQLite insertion expects string dates
            data_to_insert = []
            for _, row in df.iterrows():
                # Convert Timestamp/Datetime to string formatted date
                if isinstance(row['date'], pd.Timestamp) or isinstance(row['date'], datetime):
                    date_str = row['date'].strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date_str = str(row['date'])
                
                data_to_insert.append((
                    symbol,
                    date_str,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['adjusted_close']),
                    float(row['volume']),
                    interval
                ))
            
            # Batch execute UPSERT
            cursor.executemany(UPSERT_MARKET_DATA, data_to_insert)
            conn.commit()
            rows_inserted = len(data_to_insert)
            
        log_info("database", f"Saved {rows_inserted} market records for {symbol} ({interval}) to SQLite.")
        return rows_inserted

    @handle_db_errors(default_return=None)
    def get_market_data(
        self, symbol: str, interval: str, start_date: str = None, end_date: str = None
    ) -> pd.DataFrame:
        """
        Fetches historical market data from the SQLite database.
        
        Args:
            symbol (str): Ticker symbol.
            interval (str): Time interval.
            start_date (str, optional): Start date string.
            end_date (str, optional): End date string.
            
        Returns:
            pd.DataFrame: Cleaned market data from database, or empty DataFrame.
        """
        with self.get_connection() as conn:
            if start_date and end_date:
                df = pd.read_sql_query(
                    SELECT_MARKET_DATA_DATE_RANGE,
                    conn,
                    params=(symbol, interval, start_date, end_date)
                )
            else:
                df = pd.read_sql_query(
                    SELECT_MARKET_DATA,
                    conn,
                    params=(symbol, interval)
                )
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            log_info("database", f"Fetched {len(df)} market records from SQLite database for {symbol}.")
        else:
            log_info("database", f"No database records found for {symbol} ({interval}).")
            
        return df

    @handle_db_errors(default_return=False)
    def save_analysis_result(
        self, symbol: str, analysis_date: str, trend: str, rsi: float, macd: float, volatility: str, signal: str
    ) -> bool:
        """
        Saves a summary of the technical analysis.
        
        Args:
            symbol (str): Stock symbol.
            analysis_date (str): Date of the analysis ('YYYY-MM-DD').
            trend (str): Classified trend (Bullish/Bearish/Neutral).
            rsi (float): Current RSI value.
            macd (float): Current MACD value.
            volatility (str): Volatility classification (Low/Medium/High).
            signal (str): Technical signal summary.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                UPSERT_ANALYSIS_RESULT,
                (symbol, analysis_date, trend, rsi, macd, volatility, signal)
            )
            conn.commit()
        log_info("database", f"Saved analysis summary for {symbol} as of {analysis_date}.")
        return True

    @handle_db_errors(default_return=None)
    def get_latest_analysis(self, symbol: str) -> dict:
        """
        Retrieves the latest analysis summary for a stock.
        
        Args:
            symbol (str): Stock symbol.
            
        Returns:
            dict: Latest analysis summary or None.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_LATEST_ANALYSIS, (symbol,))
            row = cursor.fetchone()
            
        if row:
            return dict(row)
        return None

    @handle_db_errors(default_return=0)
    def save_news_articles(self, articles: list[dict]) -> int:
        """
        Saves a list of analyzed news articles to SQLite with duplicate prevention.
        
        Args:
            articles (list[dict]): List of news article dicts with sentiment fields.
            
        Returns:
            int: Number of articles inserted or updated.
        """
        if not articles:
            return 0
            
        rows_saved = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            data_to_insert = []
            import hashlib
            for art in articles:
                article_key = art.get("article_key")
                if not article_key:
                    raw_id = art.get("url") or f"{art.get('symbol', '')}_{art.get('headline', '')}"
                    article_key = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
                    
                data_to_insert.append((
                    art.get("symbol", ""),
                    art.get("company_name", ""),
                    art.get("headline", ""),
                    art.get("description", ""),
                    art.get("source", ""),
                    art.get("url", ""),
                    str(art.get("published_date", "")),
                    art.get("sentiment", "Neutral"),
                    float(art.get("sentiment_score", 0.0)),
                    float(art.get("confidence", 0.0)),
                    article_key
                ))
            cursor.executemany(UPSERT_STOCK_NEWS, data_to_insert)
            conn.commit()
            rows_saved = len(data_to_insert)
            
        log_info("database", f"Saved/Updated {rows_saved} news articles in SQLite.")
        return rows_saved

    @handle_db_errors(default_return=[])
    def get_cached_news(self, symbol: str, start_date: str = None) -> list[dict]:
        """
        Retrieves cached news articles for a stock symbol from SQLite.
        
        Args:
            symbol (str): Stock symbol.
            start_date (str, optional): Cutoff date filter.
            
        Returns:
            list[dict]: List of news article dictionaries.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if start_date:
                cursor.execute(SELECT_STOCK_NEWS_DATE_RANGE, (symbol, start_date))
            else:
                cursor.execute(SELECT_STOCK_NEWS_BY_SYMBOL, (symbol,))
            rows = cursor.fetchall()
            
        return [dict(row) for row in rows]

    @handle_db_errors(default_return=None)
    def get_cached_article_sentiment(self, article_key: str) -> dict | None:
        """
        Retrieves cached sentiment for an article if already analyzed.
        
        Args:
            article_key (str): Unique hash or key for the article.
            
        Returns:
            dict | None: Cached sentiment dict or None if not cached.
        """
        if not article_key:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_CACHED_ARTICLE_SENTIMENT, (article_key,))
            row = cursor.fetchone()
        if row:
            return dict(row)
        return None

