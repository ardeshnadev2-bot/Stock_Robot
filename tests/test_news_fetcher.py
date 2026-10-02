import pytest
from unittest.mock import patch, MagicMock
from src.news.news_fetcher import NewsFetcher

def test_get_company_name():
    """Test resolving company names from symbols."""
    fetcher = NewsFetcher()
    assert fetcher.get_company_name("RELIANCE.NS") == "Reliance Industries"
    assert fetcher.get_company_name("TCS.NS") == "Tata Consultancy Services"
    assert fetcher.get_company_name("AAPL") == "Apple"
    assert fetcher.get_company_name("^NSEI") == "Nifty 50 Index"

def test_fetch_from_yfinance_success():
    """Test successful news fetching from yfinance."""
    fetcher = NewsFetcher()
    
    mock_news = [
        {
            "content": {
                "title": "Reliance announces major renewable energy expansion",
                "summary": "Reliance Industries green energy arm has completed a new solar initiative.",
                "provider": {"displayName": "Reuters"},
                "pubDate": "2026-09-08T10:00:00Z",
                "canonicalUrl": {"url": "https://finance.yahoo.com/news/reliance-green-energy-1000.html"}
            }
        },
        {
            # Legacy format support
            "title": "Reliance Q2 profit beats expectations",
            "summary": "Quarterly net profit rose 15% year-on-year.",
            "publisher": "Bloomberg",
            "providerPublishTime": 1788775200,
            "link": "https://finance.yahoo.com/news/reliance-profit-beats.html"
        }
    ]
    
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.news = mock_news
        mock_ticker.return_value = mock_instance
        
        articles = fetcher.fetch_from_yfinance("RELIANCE.NS", "Reliance Industries")
        
        assert len(articles) == 2
        assert articles[0]["headline"] == "Reliance announces major renewable energy expansion"
        assert articles[0]["source"] == "Reuters"
        assert "2026-09-08" in articles[0]["published_date"]
        assert articles[1]["headline"] == "Reliance Q2 profit beats expectations"
        assert articles[1]["source"] == "Bloomberg"

def test_fetch_empty_api_response():
    """Test handling of empty API response."""
    fetcher = NewsFetcher()
    
    with patch("yfinance.Ticker") as mock_ticker, patch.object(fetcher.session, "get") as mock_get:
        mock_instance = MagicMock()
        mock_instance.news = []
        mock_ticker.return_value = mock_instance
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<rss><channel></channel></rss>"
        mock_get.return_value = mock_resp
        
        articles = fetcher.fetch_news("RELIANCE.NS", "Reliance Industries")
        assert articles == []

def test_fetch_invalid_api_response():
    """Test handling of malformed or invalid API response."""
    fetcher = NewsFetcher()
    
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        # Invalid / corrupt news objects
        mock_instance.news = [{"invalid_key": 123}, None, "malformed string"]
        mock_ticker.return_value = mock_instance
        
        # Must not crash and return valid list
        articles = fetcher.fetch_from_yfinance("RELIANCE.NS", "Reliance Industries")
        assert isinstance(articles, list)
        assert len(articles) == 0

def test_api_failure_handling_and_provider_fallback():
    """Test that if one provider fails (e.g. yfinance), fetcher continues with the other provider (Google RSS)."""
    fetcher = NewsFetcher()
    
    with patch("yfinance.Ticker", side_effect=Exception("YFinance API down")), \
         patch.object(fetcher, "fetch_from_google_news_rss") as mock_google:
        
        mock_google.return_value = [{
            "symbol": "TCS.NS",
            "company_name": "Tata Consultancy Services",
            "headline": r"TCS signs $1B digital transformation contract",
            "description": "Tata Consultancy Services secures key enterprise deal.",
            "source": "Economic Times",
            "published_date": "2026-09-08 12:00:00",
            "url": "https://economictimes.com/tcs-contract"
        }]
        
        articles = fetcher.fetch_news("TCS.NS", "Tata Consultancy Services")
        assert len(articles) == 1
        assert articles[0]["headline"] == r"TCS signs $1B digital transformation contract"
