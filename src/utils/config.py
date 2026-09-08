import os

# Project Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")

# Create directories if they don't exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Database
DB_PATH = os.path.join(DATA_DIR, "market_analyzer.db")

# Log File
LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")

# Stock Tickers (Indian Market focus)
DEFAULT_TICKERS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "^NSEI",  # Nifty 50 Index
]

# Configure Stock Universes (At least top 50 actively traded stocks per selected market)
STOCK_UNIVERSES = {
    "NIFTY 50 (India)": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "HINDUNILVR.NS",
        "LTIM.NS", "AXISBANK.NS", "KOTAKBANK.NS", "M&M.NS", "TATAMOTORS.NS",
        "ULTRACEMCO.NS", "NTPC.NS", "POWERGRID.NS", "TATASTEEL.NS", "ADANIENT.NS",
        "ADANIPORTS.NS", "SUNPHARMA.NS", "JSWSTEEL.NS", "COALINDIA.NS", "ASIANPAINT.NS",
        "TITAN.NS", "ONGC.NS", "HCLTECH.NS", "MARUTI.NS", "BAJFINANCE.NS",
        "BAJAJFINSV.NS", "NESTLEIND.NS", "GRASIM.NS", "TECHM.NS", "INDUSINDBK.NS",
        "SBILIFE.NS", "WIPRO.NS", "HEROMOTOCO.NS", "BPCL.NS", "DRREDDY.NS",
        "CIPLA.NS", "APOLLOHOSP.NS", "HINDALCO.NS", "BRITANNIA.NS", "EICHERMOT.NS",
        "JIOFIN.NS", "SHRIRAMFIN.NS", "BEL.NS", "TATACONSUM.NS", "ADANIPOWER.NS"
    ],
    "S&P 500 (US - Top 50)": [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "LLY", "AVGO",
        "V", "JPM", "UNH", "MA", "WMT", "PG", "XOM", "HD", "JNJ", "ORCL",
        "COST", "ABBV", "MRK", "BAC", "AMD", "CVX", "PEP", "CRM", "KO", "TMO",
        "ADBE", "WFC", "QCOM", "ACN", "GE", "CSCO", "MCD", "DIS", "INTU", "DHR",
        "CAT", "ABT", "AMGN", "VZ", "IBM", "TXN", "PM", "AXP", "SPGI", "MS"
    ],
    "NASDAQ 100 (US - Top 50)": [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST", "CSCO",
        "ADBE", "NFLX", "PEP", "AMD", "QCOM", "TMUS", "INTU", "TXN", "AMGN", "AMAT",
        "ISRG", "HON", "CMCSA", "BKNG", "VRTX", "ADI", "ADP", "PANW", "MDLZ", "MU",
        "REGN", "KLAC", "LRCX", "INTC", "SNPS", "CDNS", "MELI", "ASML", "MAR", "ORLY",
        "CTAS", "NXPI", "WDAY", "PCAR", "ROP", "MNST", "PAYX", "ADSK", "AEP", "KDP"
    ]
}

# Time intervals supported
SUPPORTED_INTERVALS = {
    "1d": "Daily",
    "1h": "1 Hour",
    "15m": "15 Minutes",
    "5m": "5 Minutes",
}

# Technical Indicator Configurations
RSI_PERIOD = 14
SMA_SHORT = 20
SMA_LONG = 50
EMA_SHORT = 20
EMA_LONG = 50
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
VOLATILITY_PERIOD = 20

# Error Handler Configurations
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
