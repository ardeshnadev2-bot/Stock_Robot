import math
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser

from src.database.database import DatabaseManager
from src.news.news_fetcher import NewsFetcher
from src.news.news_validator import NewsValidator
from src.news.sentiment_analyzer import SentimentAnalyzer
from src.utils.logger import log_info, log_error

TIME_FILTER_DELTAS = {
    "Last 24 Hours": timedelta(days=1),
    "Last 7 Days": timedelta(days=7),
    "Last 30 Days": timedelta(days=30),
}

class NewsProcessor:
    """Controls and coordinates the complete News & Sentiment Analysis pipeline."""

    def __init__(
        self,
        db_manager: DatabaseManager = None,
        fetcher: NewsFetcher = None,
        validator: NewsValidator = None,
        analyzer: SentimentAnalyzer = None
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.fetcher = fetcher or NewsFetcher()
        self.validator = validator or NewsValidator()
        self.analyzer = analyzer or SentimentAnalyzer()

    def process_news(
        self,
        symbol: str,
        company_name: str = None,
        time_filter: str = "Last 7 Days",
        force_refresh: bool = False
    ) -> dict:
        """
        Orchestrates news fetching, validation, deduplication, sentiment analysis,
        caching, time filtering, and overall stock sentiment calculation.
        
        Args:
            symbol (str): Stock ticker symbol.
            company_name (str, optional): Official company name.
            time_filter (str): 'Last 24 Hours', 'Last 7 Days', or 'Last 30 Days'.
            force_refresh (bool): Whether to bypass recent DB cache and fetch fresh.
            
        Returns:
            dict: Processed news and overall sentiment summary.
        """
        if not symbol:
            return self._empty_result("", "", time_filter)

        symbol_upper = symbol.strip().upper()
        comp_name = company_name or self.fetcher.get_company_name(symbol_upper)
        log_info("news_processor", f"Processing news for {symbol_upper} ({comp_name}), filter={time_filter}")

        # 1. Fetch cached articles from SQLite
        cached_articles = []
        if not force_refresh:
            try:
                cached_articles = self.db_manager.get_cached_news(symbol_upper)
            except Exception as e:
                log_error(
                    module_name="news_processor",
                    error_type="DatabaseReadError",
                    message=f"Failed to read cached news for {symbol_upper}: {str(e)}",
                    action="Fetch from API"
                )
                cached_articles = []

        # If cache is empty or user requested force refresh, fetch fresh news
        if force_refresh or not cached_articles:
            log_info("news_processor", f"Fetching fresh news for {symbol_upper}...")
            try:
                raw_articles = self.fetcher.fetch_news(symbol_upper, comp_name)
            except Exception as e:
                log_error(
                    module_name="news_processor",
                    error_type="NewsFetchError",
                    message=f"Error fetching news for {symbol_upper}: {str(e)}",
                    action="Use cached articles if available"
                )
                raw_articles = []

            # 2. Validate and deduplicate
            valid_articles = self.validator.validate_articles(raw_articles, symbol_upper, comp_name)

            # 3. Sentiment Analysis with SQLite Cache Reuse
            analyzed_articles = []
            for art in valid_articles:
                art_key = art.get("article_key")
                cached_sentiment = None
                if art_key:
                    cached_sentiment = self.db_manager.get_cached_article_sentiment(art_key)

                if cached_sentiment:
                    # Reuse cached sentiment without re-running model
                    art["sentiment"] = cached_sentiment["sentiment"]
                    art["sentiment_score"] = float(cached_sentiment["sentiment_score"])
                    art["confidence"] = float(cached_sentiment["confidence"])
                    art["analysis_timestamp"] = cached_sentiment.get("analysis_timestamp")
                else:
                    # Run sentiment analysis
                    sent_res = self.analyzer.analyze(art["headline"], art.get("description", ""))
                    art["sentiment"] = sent_res["sentiment"]
                    art["sentiment_score"] = float(sent_res["sentiment_score"])
                    art["confidence"] = float(sent_res["confidence"])

                analyzed_articles.append(art)

            # 4. Save newly fetched & analyzed articles to SQLite
            if analyzed_articles:
                try:
                    self.db_manager.save_news_articles(analyzed_articles)
                except Exception as e:
                    log_error(
                        module_name="news_processor",
                        error_type="DatabaseSaveError",
                        message=f"Failed to persist news articles for {symbol_upper}: {str(e)}",
                        action="Continue with in-memory articles"
                    )

            articles_to_process = analyzed_articles
        else:
            log_info("news_processor", f"Using {len(cached_articles)} cached news articles for {symbol_upper}.")
            articles_to_process = cached_articles

        # 5. Apply Time Filter
        filtered_articles = self._apply_time_filter(articles_to_process, time_filter)

        # 6. Deduplicate articles for overall sentiment (in case multiple DB rows match)
        unique_articles = self._deduplicate_article_list(filtered_articles)

        # 7. Sort newest first
        unique_articles.sort(key=lambda x: str(x.get("published_date", "")), reverse=True)

        if not unique_articles:
            log_info("news_processor", f"No recent relevant news found for {symbol_upper} in time window: {time_filter}.")
            return self._empty_result(symbol_upper, comp_name, time_filter)

        # 8. Calculate Overall Stock Sentiment with Time-Decay Weighting
        overall_metrics = self.calculate_overall_sentiment(unique_articles)

        return {
            "symbol": symbol_upper,
            "company_name": comp_name,
            "time_filter": time_filter,
            "total_news": overall_metrics["total_news"],
            "positive_count": overall_metrics["positive_count"],
            "negative_count": overall_metrics["negative_count"],
            "neutral_count": overall_metrics["neutral_count"],
            "overall_sentiment": overall_metrics["overall_sentiment"],
            "overall_score": overall_metrics["overall_score"],
            "overall_confidence": overall_metrics["overall_confidence"],
            "articles": unique_articles
        }

    def _apply_time_filter(self, articles: list[dict], time_filter: str) -> list[dict]:
        """Filters articles by publication date according to the selected time filter."""
        delta = TIME_FILTER_DELTAS.get(time_filter, timedelta(days=7))
        cutoff_dt = datetime.now(timezone.utc) - delta

        filtered = []
        for art in articles:
            pub_date_str = art.get("published_date")
            if not pub_date_str:
                continue

            try:
                dt = date_parser.parse(str(pub_date_str))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff_dt:
                    filtered.append(art)
            except Exception:
                # If date cannot be parsed, include conservatively if within last 7 days
                filtered.append(art)

        return filtered

    def _deduplicate_article_list(self, articles: list[dict]) -> list[dict]:
        """Ensures duplicate articles do not affect overall sentiment multiple times."""
        unique = []
        seen_keys = set()
        seen_headlines = set()

        for art in articles:
            key = art.get("article_key") or art.get("url") or art.get("headline")
            headline_clean = self.validator.normalize_text(art.get("headline", ""))
            
            if key and key in seen_keys:
                continue
            if headline_clean and headline_clean in seen_headlines:
                continue

            if key:
                seen_keys.add(key)
            if headline_clean:
                seen_headlines.add(headline_clean)
            unique.append(art)

        return unique

    def calculate_overall_sentiment(self, articles: list[dict]) -> dict:
        """
        Calculates the overall stock sentiment with recent-news weighting.
        Recent news has higher importance than older news using exponential decay.
        """
        if not articles:
            return {
                "total_news": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "overall_sentiment": "Neutral",
                "overall_score": 0.0,
                "overall_confidence": 50.0
            }

        total_news = len(articles)
        pos_count = 0
        neg_count = 0
        neu_count = 0

        now = datetime.now(timezone.utc)
        weighted_score_sum = 0.0
        weighted_conf_sum = 0.0
        total_weight = 0.0

        for art in articles:
            sentiment = art.get("sentiment", "Neutral")
            score = float(art.get("sentiment_score", 0.0))
            conf = float(art.get("confidence", 50.0))

            if sentiment == "Positive":
                pos_count += 1
            elif sentiment == "Negative":
                neg_count += 1
            else:
                neu_count += 1

            # Calculate article age in days
            pub_date_str = art.get("published_date")
            age_days = 0.0
            if pub_date_str:
                try:
                    dt = date_parser.parse(str(pub_date_str))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_seconds = (now - dt).total_seconds()
                    age_days = max(0.0, age_seconds / 86400.0)
                except Exception:
                    age_days = 1.0

            # Exponential decay weight: weight = exp(-0.15 * age_days)
            # 0 days (today) = 1.0, 2 days = 0.74, 7 days = 0.35, 14 days = 0.12
            weight = math.exp(-0.15 * age_days)
            total_weight += weight
            weighted_score_sum += (score * weight)
            weighted_conf_sum += (conf * weight)

        # Weighted score and confidence
        if total_weight > 0:
            overall_score = round(weighted_score_sum / total_weight, 2)
            avg_conf = weighted_conf_sum / total_weight
        else:
            overall_score = 0.0
            avg_conf = 50.0

        overall_score = max(-1.0, min(1.0, overall_score))

        # Overall sentiment classification
        if overall_score >= 0.15:
            overall_sentiment = "Positive"
        elif overall_score <= -0.15:
            overall_sentiment = "Negative"
        else:
            overall_sentiment = "Neutral"

        # Overall confidence sample adjustment (increases slightly with corroborating sample size)
        sample_factor = min(1.1, 0.9 + (total_news * 0.02))
        overall_confidence = round(min(98.0, max(50.0, avg_conf * sample_factor)), 1)

        return {
            "total_news": total_news,
            "positive_count": pos_count,
            "negative_count": neg_count,
            "neutral_count": neu_count,
            "overall_sentiment": overall_sentiment,
            "overall_score": overall_score,
            "overall_confidence": overall_confidence
        }

    def _empty_result(self, symbol: str, company_name: str, time_filter: str) -> dict:
        """Returns standard empty payload when no news is available."""
        return {
            "symbol": symbol,
            "company_name": company_name,
            "time_filter": time_filter,
            "total_news": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "overall_sentiment": "Neutral",
            "overall_score": 0.0,
            "overall_confidence": 50.0,
            "articles": []
        }
