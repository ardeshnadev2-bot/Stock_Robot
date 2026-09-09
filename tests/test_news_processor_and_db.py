import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from src.database.database import DatabaseManager
from src.news.news_processor import NewsProcessor
from src.news.news_fetcher import NewsFetcher
from src.news.news_validator import NewsValidator
from src.news.sentiment_analyzer import SentimentAnalyzer

@pytest.fixture
def memory_db():
    """Provides an isolated in-memory DatabaseManager."""
    return DatabaseManager(db_path=":memory:")

def test_news_sqlite_storage_and_retrieval(memory_db):
    """Test saving news articles with sentiment to SQLite and retrieving them."""
    articles = [
        {
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Reliance expands green energy projects",
            "description": "Investment details announced for solar plants.",
            "source": "Reuters",
            "url": "https://reuters.com/reliance-green-1",
            "published_date": "2026-09-08 10:00:00",
            "sentiment": "Positive",
            "sentiment_score": 0.85,
            "confidence": 92.0,
            "article_key": "rel_key_1"
        },
        {
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Reliance Retail reports quarterly update",
            "description": "Store count increases across tier 2 cities.",
            "source": "Bloomberg",
            "url": "https://bloomberg.com/reliance-retail-1",
            "published_date": "2026-09-07 14:00:00",
            "sentiment": "Neutral",
            "sentiment_score": 0.05,
            "confidence": 75.0,
            "article_key": "rel_key_2"
        }
    ]
    
    saved_count = memory_db.save_news_articles(articles)
    assert saved_count == 2
    
    cached = memory_db.get_cached_news("RELIANCE.NS")
    assert len(cached) == 2
    assert cached[0]["headline"] == "Reliance expands green energy projects"
    assert cached[0]["sentiment"] == "Positive"
    assert cached[0]["sentiment_score"] == 0.85
    assert cached[0]["confidence"] == 92.0

def test_news_duplicate_prevention(memory_db):
    """Test that saving the same article again updates instead of duplicating rows."""
    article1 = {
        "symbol": "TCS.NS",
        "company_name": "Tata Consultancy Services",
        "headline": "TCS signs mega cloud deal",
        "description": "Initial description.",
        "source": "Mint",
        "url": "https://mint.com/tcs-deal",
        "published_date": "2026-09-08 10:00:00",
        "sentiment": "Positive",
        "sentiment_score": 0.70,
        "confidence": 88.0,
        "article_key": "tcs_key_1"
    }
    
    article1_updated = {
        "symbol": "TCS.NS",
        "company_name": "Tata Consultancy Services",
        "headline": "TCS signs mega cloud deal",
        "description": "Updated description with more details.",
        "source": "Mint",
        "url": "https://mint.com/tcs-deal",
        "published_date": "2026-09-08 10:00:00",
        "sentiment": "Positive",
        "sentiment_score": 0.82,
        "confidence": 91.0,
        "article_key": "tcs_key_1"
    }
    
    memory_db.save_news_articles([article1])
    memory_db.save_news_articles([article1_updated])
    
    cached = memory_db.get_cached_news("TCS.NS")
    assert len(cached) == 1
    assert cached[0]["sentiment_score"] == 0.82
    assert cached[0]["confidence"] == 91.0

def test_sentiment_cache_reuse(memory_db):
    """Test that if an article was already analyzed, cached sentiment is reused without running the model."""
    mock_analyzer = MagicMock(spec=SentimentAnalyzer)
    mock_fetcher = MagicMock(spec=NewsFetcher)
    mock_validator = NewsValidator()
    
    processor = NewsProcessor(
        db_manager=memory_db,
        fetcher=mock_fetcher,
        validator=mock_validator,
        analyzer=mock_analyzer
    )
    
    # Pre-populate DB with analyzed article
    pre_analyzed = [{
        "symbol": "INFY.NS",
        "company_name": "Infosys",
        "headline": "Infosys raises revenue guidance",
        "description": "Growth targets upgraded.",
        "source": "Reuters",
        "url": "https://reuters.com/infy-guidance",
        "published_date": "2026-09-08 10:00:00",
        "sentiment": "Positive",
        "sentiment_score": 0.88,
        "confidence": 94.0,
        "article_key": mock_validator.generate_article_key("INFY.NS", "https://reuters.com/infy-guidance", "Infosys raises revenue guidance")
    }]
    memory_db.save_news_articles(pre_analyzed)
    
    # Now simulate fetching the exact same article fresh (force_refresh=True)
    mock_fetcher.get_company_name.return_value = "Infosys"
    mock_fetcher.fetch_news.return_value = [{
        "symbol": "INFY.NS",
        "company_name": "Infosys",
        "headline": "Infosys raises revenue guidance",
        "description": "Growth targets upgraded.",
        "source": "Reuters",
        "url": "https://reuters.com/infy-guidance",
        "published_date": "2026-09-08 10:00:00"
    }]
    
    result = processor.process_news("INFY.NS", force_refresh=True)
    
    # Verify that analyzer.analyze was NOT called because cached sentiment was reused
    mock_analyzer.analyze.assert_not_called()
    assert result["total_news"] == 1
    assert result["articles"][0]["sentiment_score"] == 0.88

def test_recent_news_weighting(memory_db):
    """Test that recent news carries more weight than older news in overall score."""
    processor = NewsProcessor(db_manager=memory_db)
    
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d %H:%M:%S")
    old_str = (now - timedelta(days=25)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Scenario A: Recent is Positive (+0.9), Old is Negative (-0.9)
    # Because recent has higher weight, overall score should be positive!
    articles_recent_positive = [
        {"sentiment": "Positive", "sentiment_score": 0.9, "confidence": 90.0, "published_date": today_str},
        {"sentiment": "Negative", "sentiment_score": -0.9, "confidence": 90.0, "published_date": old_str}
    ]
    res_a = processor.calculate_overall_sentiment(articles_recent_positive)
    assert res_a["overall_score"] > 0.3
    assert res_a["overall_sentiment"] == "Positive"
    
    # Scenario B: Recent is Negative (-0.9), Old is Positive (+0.9)
    # Overall score should be negative!
    articles_recent_negative = [
        {"sentiment": "Negative", "sentiment_score": -0.9, "confidence": 90.0, "published_date": today_str},
        {"sentiment": "Positive", "sentiment_score": 0.9, "confidence": 90.0, "published_date": old_str}
    ]
    res_b = processor.calculate_overall_sentiment(articles_recent_negative)
    assert res_b["overall_score"] < -0.3
    assert res_b["overall_sentiment"] == "Negative"

def test_time_window_filtering(memory_db):
    """Test filtering news articles by 24h, 7d, and 30d time horizons."""
    processor = NewsProcessor(db_manager=memory_db)
    
    now = datetime.now(timezone.utc)
    t_12h = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    t_3d = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    t_15d = (now - timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S")
    t_45d = (now - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
    
    articles = [
        {"headline": "12h ago", "published_date": t_12h},
        {"headline": "3d ago", "published_date": t_3d},
        {"headline": "15d ago", "published_date": t_15d},
        {"headline": "45d ago", "published_date": t_45d},
    ]
    
    f_24h = processor._apply_time_filter(articles, "Last 24 Hours")
    assert len(f_24h) == 1
    assert f_24h[0]["headline"] == "12h ago"
    
    f_7d = processor._apply_time_filter(articles, "Last 7 Days")
    assert len(f_7d) == 2
    
    f_30d = processor._apply_time_filter(articles, "Last 30 Days")
    assert len(f_30d) == 3

def test_no_news_available_empty_result(memory_db):
    """Test empty response handling when no news is available."""
    mock_fetcher = MagicMock(spec=NewsFetcher)
    mock_fetcher.fetch_news.return_value = []
    mock_fetcher.get_company_name.return_value = "Unknown Corp"
    
    processor = NewsProcessor(db_manager=memory_db, fetcher=mock_fetcher)
    result = processor.process_news("UNKNOWN.NS", force_refresh=True)
    
    assert result["total_news"] == 0
    assert result["articles"] == []
    assert result["overall_sentiment"] == "Neutral"
    assert result["overall_score"] == 0.0
