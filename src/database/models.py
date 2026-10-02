# SQL queries for database schema creation and data operations

CREATE_MARKET_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adjusted_close REAL,
    volume REAL,
    interval TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date, interval) ON CONFLICT REPLACE
);
"""

CREATE_ANALYSIS_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    analysis_date TEXT NOT NULL,
    trend TEXT,
    rsi REAL,
    macd REAL,
    volatility TEXT,
    signal TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, analysis_date) ON CONFLICT REPLACE
);
"""

CREATE_STOCK_NEWS_TABLE = """
CREATE TABLE IF NOT EXISTS stock_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    company_name TEXT,
    headline TEXT NOT NULL,
    description TEXT,
    source TEXT,
    url TEXT,
    published_date TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    sentiment_score REAL NOT NULL,
    confidence REAL NOT NULL,
    analysis_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    article_key TEXT NOT NULL UNIQUE
);
"""

# Insert / UPSERT statements
UPSERT_MARKET_DATA = """
INSERT INTO market_data (symbol, date, open, high, low, close, adjusted_close, volume, interval)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

UPSERT_ANALYSIS_RESULT = """
INSERT INTO analysis_results (symbol, analysis_date, trend, rsi, macd, volatility, signal)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

UPSERT_STOCK_NEWS = """
INSERT INTO stock_news (symbol, company_name, headline, description, source, url, published_date, sentiment, sentiment_score, confidence, article_key)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(article_key) DO UPDATE SET
    symbol=excluded.symbol,
    company_name=excluded.company_name,
    headline=excluded.headline,
    description=excluded.description,
    source=excluded.source,
    url=excluded.url,
    published_date=excluded.published_date,
    sentiment=excluded.sentiment,
    sentiment_score=excluded.sentiment_score,
    confidence=excluded.confidence,
    analysis_timestamp=CURRENT_TIMESTAMP;
"""

# Select statements
SELECT_MARKET_DATA = """
SELECT date, open, high, low, close, adjusted_close, volume
FROM market_data
WHERE symbol = ? AND interval = ?
ORDER BY date ASC
"""

SELECT_MARKET_DATA_DATE_RANGE = """
SELECT date, open, high, low, close, adjusted_close, volume
FROM market_data
WHERE symbol = ? AND interval = ? AND date BETWEEN ? AND ?
ORDER BY date ASC
"""

SELECT_LATEST_ANALYSIS = """
SELECT symbol, analysis_date, trend, rsi, macd, volatility, signal, created_at
FROM analysis_results
WHERE symbol = ?
ORDER BY analysis_date DESC
LIMIT 1
"""

SELECT_STOCK_NEWS_BY_SYMBOL = """
SELECT symbol, company_name, headline, description, source, url, published_date, sentiment, sentiment_score, confidence, analysis_timestamp, article_key
FROM stock_news
WHERE symbol = ?
ORDER BY published_date DESC, id DESC
"""

SELECT_STOCK_NEWS_DATE_RANGE = """
SELECT symbol, company_name, headline, description, source, url, published_date, sentiment, sentiment_score, confidence, analysis_timestamp, article_key
FROM stock_news
WHERE symbol = ? AND published_date >= ?
ORDER BY published_date DESC, id DESC
"""

SELECT_CACHED_ARTICLE_SENTIMENT = """
SELECT sentiment, sentiment_score, confidence, analysis_timestamp
FROM stock_news
WHERE article_key = ?
LIMIT 1
"""

