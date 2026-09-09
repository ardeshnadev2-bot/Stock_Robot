import pytest
from src.news.news_validator import NewsValidator

def test_duplicate_removal():
    """Test that duplicate articles by URL or normalized headline are removed."""
    validator = NewsValidator()
    
    raw_articles = [
        {
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Reliance to invest in green hydrogen plant",
            "description": "Reliance announced new green investments.",
            "source": "LiveMint",
            "published_date": "2026-09-08 10:00:00",
            "url": "https://livemint.com/industry/reliance-hydrogen?utm_source=twitter"
        },
        {
            # Exact duplicate with different tracking param
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Reliance to invest in green hydrogen plant",
            "description": "Reliance announced new green investments.",
            "source": "LiveMint",
            "published_date": "2026-09-08 10:00:00",
            "url": "https://livemint.com/industry/reliance-hydrogen?utm_source=facebook"
        },
        {
            # Duplicate normalized headline from different URL
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Reliance to Invest in Green Hydrogen Plant!",
            "description": "Summary of hydrogen plan.",
            "source": "Moneycontrol",
            "published_date": "2026-09-08 10:05:00",
            "url": "https://moneycontrol.com/reliance-hydrogen"
        },
        {
            # Unique article
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Reliance Retail expands store network across India",
            "description": "Reliance retail opening 50 new locations.",
            "source": "Economic Times",
            "published_date": "2026-09-08 11:00:00",
            "url": "https://economictimes.com/reliance-retail-stores"
        }
    ]
    
    validated = validator.validate_articles(raw_articles, "RELIANCE.NS", "Reliance Industries")
    assert len(validated) == 2
    headlines = [a["headline"] for a in validated]
    assert "Reliance to invest in green hydrogen plant" in headlines
    assert "Reliance Retail expands store network across India" in headlines

def test_missing_headline_rejection():
    """Test that articles with empty or missing headlines are rejected."""
    validator = NewsValidator()
    
    raw_articles = [
        {"symbol": "INFY.NS", "headline": "", "description": "Infosys results", "url": "https://a.com/1"},
        {"symbol": "INFY.NS", "headline": "   ", "description": "Infosys results", "url": "https://a.com/2"},
        {"symbol": "INFY.NS", "headline": None, "description": "Infosys results", "url": "https://a.com/3"},
        {"symbol": "INFY.NS", "headline": "Infosys wins European contract", "description": "Infosys secures deal.", "url": "https://a.com/4"},
    ]
    
    validated = validator.validate_articles(raw_articles, "INFY.NS", "Infosys")
    assert len(validated) == 1
    assert validated[0]["headline"] == "Infosys wins European contract"

def test_missing_description_handling():
    """Test that missing or empty description falls back to headline gracefully."""
    validator = NewsValidator()
    
    raw_articles = [
        {
            "symbol": "TCS.NS",
            "company_name": "Tata Consultancy Services",
            "headline": "TCS announces quarterly dividend payout",
            "description": "",
            "source": "Reuters",
            "published_date": "2026-09-08 09:00:00",
            "url": "https://reuters.com/tcs-dividend"
        }
    ]
    
    validated = validator.validate_articles(raw_articles, "TCS.NS", "Tata Consultancy Services")
    assert len(validated) == 1
    assert validated[0]["description"] == "TCS announces quarterly dividend payout"

def test_invalid_url_and_future_date_handling():
    """Test handling of invalid URLs and distant future dates."""
    validator = NewsValidator()
    
    raw_articles = [
        {
            # Invalid URL scheme
            "symbol": "AAPL",
            "headline": "Apple launches new iPhone series",
            "description": "Apple event today.",
            "url": "ftp://bad-scheme.com/article",
            "published_date": "2026-09-08 10:00:00"
        },
        {
            # Distant future date (> 2 days in the future)
            "symbol": "AAPL",
            "headline": "Apple announces futuristic product line",
            "description": "Apple future announcement.",
            "url": "https://appleinsider.com/future",
            "published_date": "2030-01-01 00:00:00"
        },
        {
            # Valid article
            "symbol": "AAPL",
            "headline": "Apple reports record services revenue growth",
            "description": "Apple services segment climbs 14%.",
            "url": "https://cnbc.com/apple-revenue",
            "published_date": "2026-09-08 10:00:00"
        }
    ]
    
    validated = validator.validate_articles(raw_articles, "AAPL", "Apple")
    assert len(validated) == 1
    assert validated[0]["headline"] == "Apple reports record services revenue growth"

def test_relevant_and_irrelevant_news_filtering():
    """Test filtering of relevant vs irrelevant news articles."""
    validator = NewsValidator()
    
    raw_articles = [
        {
            # Relevant to Reliance
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Reliance Jio expands 5G enterprise solutions",
            "description": "Reliance telecommunications arm introduces new packages.",
            "url": "https://telecom.com/reliance-jio"
        },
        {
            # Completely irrelevant to Reliance (e.g. general sports news)
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Champions League highlights and quarterfinal draw results",
            "description": "Football recap from across European leagues with top scores.",
            "url": "https://sports.com/champions-league"
        },
        {
            # Irrelevant stock news (about Maruti Suzuki when target is Reliance)
            "symbol": "RELIANCE.NS",
            "company_name": "Reliance Industries",
            "headline": "Maruti Suzuki reports passenger car sales figures",
            "description": "Auto maker shipped 180,000 units in August across India.",
            "url": "https://auto.com/maruti-sales"
        }
    ]
    
    validated = validator.validate_articles(raw_articles, "RELIANCE.NS", "Reliance Industries")
    assert len(validated) == 1
    assert "Reliance Jio" in validated[0]["headline"]

def test_malformed_article_does_not_crash():
    """Test that malformed records (wrong types, missing keys) do not crash validation."""
    validator = NewsValidator()
    
    raw_articles = [
        None,
        12345,
        "string instead of dict",
        {"symbol": "TCS.NS"},  # Missing headline and other required fields
        {
            "symbol": "TCS.NS",
            "company_name": "Tata Consultancy Services",
            "headline": "TCS signs strategic cloud alliance with enterprise client",
            "description": "Tata Consultancy Services expands cloud unit.",
            "url": "https://tcs.com/cloud",
            "published_date": "2026-09-08 10:00:00"
        }
    ]
    
    validated = validator.validate_articles(raw_articles, "TCS.NS", "Tata Consultancy Services")
    assert len(validated) == 1
    assert validated[0]["headline"] == "TCS signs strategic cloud alliance with enterprise client"
