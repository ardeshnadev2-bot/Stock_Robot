import pytest
from unittest.mock import patch
from src.news.sentiment_analyzer import SentimentAnalyzer

def test_positive_sentiment():
    """Test positive financial news classification and score range."""
    analyzer = SentimentAnalyzer()
    
    # Exact example from requirement prompt
    headline = "Company reports strong quarterly profit growth"
    res = analyzer.analyze(headline)
    
    assert res["sentiment"] == "Positive"
    assert 0.5 <= res["sentiment_score"] <= 1.0
    assert 70.0 <= res["confidence"] <= 100.0

def test_negative_sentiment():
    """Test negative financial news classification and score range."""
    analyzer = SentimentAnalyzer()
    
    headline = "Company reports quarterly loss, shares slump after missing revenue estimates"
    res = analyzer.analyze(headline)
    
    assert res["sentiment"] == "Negative"
    assert -1.0 <= res["sentiment_score"] <= -0.4
    assert 70.0 <= res["confidence"] <= 100.0

def test_neutral_sentiment():
    """Test neutral news classification."""
    analyzer = SentimentAnalyzer()
    
    headline = "Company publishes schedule for annual investor presentation conference"
    description = "The investor relations division announced the event details."
    res = analyzer.analyze(headline, description)
    
    assert res["sentiment"] == "Neutral"
    assert -0.25 <= res["sentiment_score"] <= 0.25
    assert 0.0 <= res["confidence"] <= 100.0

def test_score_and_confidence_ranges():
    """Test that all output scores adhere strictly to defined bounds."""
    analyzer = SentimentAnalyzer()
    
    test_cases = [
        "Massive earnings surge and special dividend announced",
        "Severe fraud investigation launched by financial regulator",
        "Board of directors meeting adjourned without resolutions",
        "",  # empty
        "   "  # whitespace
    ]
    
    for text in test_cases:
        res = analyzer.analyze(text)
        assert -1.0 <= res["sentiment_score"] <= 1.0
        assert 0.0 <= res["confidence"] <= 100.0
        assert res["sentiment"] in ["Positive", "Negative", "Neutral"]

def test_financial_context_nuance():
    """Test that the model understands financial domain context beyond simple keywords."""
    analyzer = SentimentAnalyzer()
    
    # "growth" negated or with negative financial context
    neg_headline = "Company fails to meet growth targets as margins contract sharply"
    neg_res = analyzer.analyze(neg_headline)
    assert neg_res["sentiment"] == "Negative"
    assert neg_res["sentiment_score"] < 0.0
    
    # "dividend hike and robust turnaround"
    pos_headline = "Board approves dividend hike following multi-fold turnaround"
    pos_res = analyzer.analyze(pos_headline)
    assert pos_res["sentiment"] == "Positive"
    assert pos_res["sentiment_score"] > 0.0

def test_sentiment_model_failure_handling():
    """Test that model exceptions are safely caught and return safe neutral response."""
    analyzer = SentimentAnalyzer()
    
    with patch.object(analyzer, "_analyze_with_finbert", side_effect=RuntimeError("FinBERT error")), \
         patch.object(analyzer, "_analyze_with_financial_lexicon", side_effect=RuntimeError("Lexicon error")):
        res = analyzer.analyze("Some news headline")
        assert res["sentiment"] == "Neutral"
        assert res["sentiment_score"] == 0.0
        assert res["confidence"] == 50.0

