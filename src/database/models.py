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

# Insert / UPSERT statements
UPSERT_MARKET_DATA = """
INSERT INTO market_data (symbol, date, open, high, low, close, adjusted_close, volume, interval)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

UPSERT_ANALYSIS_RESULT = """
INSERT INTO analysis_results (symbol, analysis_date, trend, rsi, macd, volatility, signal)
VALUES (?, ?, ?, ?, ?, ?, ?)
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
