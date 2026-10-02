import hashlib
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from src.utils.logger import log_info, log_error

class NewsValidator:
    """Validates, cleans, deduplicates, and filters financial news articles."""

    def __init__(self):
        # Tracking parameters to strip for canonical URL matching
        self.tracking_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term",
            "utm_content", "fbclid", "gclid", "oc"
        }

    def clean_url(self, raw_url: str) -> str:
        """
        Sanitizes a URL by removing tracking query parameters and trailing slashes.
        """
        if not raw_url or not isinstance(raw_url, str):
            return ""
        try:
            parsed = urllib.parse.urlparse(raw_url.strip())
            if not parsed.scheme or not parsed.netloc:
                return ""
            query_tuples = urllib.parse.parse_qsl(parsed.query)
            clean_tuples = [(k, v) for k, v in query_tuples if k.lower() not in self.tracking_params]
            clean_query = urllib.parse.urlencode(clean_tuples)
            clean_parsed = parsed._replace(query=clean_query, fragment="")
            return urllib.parse.urlunparse(clean_parsed).rstrip("/")
        except Exception:
            return raw_url.strip()

    def normalize_text(self, text: str) -> str:
        """Normalizes text for duplicate comparison (removes punctuation, excess spaces, lowercase)."""
        if not text:
            return ""
        cleaned = re.sub(r"[^\w\s]", "", str(text).lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def generate_article_key(self, symbol: str, url: str, headline: str) -> str:
        """
        Generates a deterministic unique key for an article for caching and duplicate prevention.
        """
        clean_u = self.clean_url(url)
        norm_h = self.normalize_text(headline)
        key_str = f"{symbol.strip().upper()}||{clean_u or norm_h}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def is_valid_url(self, url: str) -> bool:
        """Validates that a URL is well-formed with http/https scheme."""
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urllib.parse.urlparse(url.strip())
            return bool(parsed.scheme in ("http", "https") and parsed.netloc)
        except Exception:
            return False

    def validate_and_normalize_date(self, date_val) -> str | None:
        """
        Validates and parses a publication date.
        Rejects dates in the distant future (> 2 days ahead) or unparseable values.
        Returns formatted ISO datetime string 'YYYY-MM-DD HH:MM:SS' or None if invalid.
        """
        if not date_val:
            return None

        try:
            if isinstance(date_val, (int, float)):
                dt = datetime.fromtimestamp(date_val, tz=timezone.utc)
            elif isinstance(date_val, datetime):
                dt = date_val if date_val.tzinfo else date_val.replace(tzinfo=timezone.utc)
            else:
                dt = date_parser.parse(str(date_val))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

            # Check future threshold (allow max 2 days ahead for timezone variances)
            now = datetime.now(timezone.utc)
            if dt > now + timedelta(days=2):
                return None

            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def is_relevant(self, article: dict, symbol: str, company_name: str) -> bool:
        """
        Determines whether the article is relevant to the target stock or company.
        Checks for mentions of ticker or company keywords in headline and description.
        """
        headline = (article.get("headline") or "").lower()
        description = (article.get("description") or "").lower()
        combined_text = f"{headline} {description}"

        if not combined_text.strip():
            return False

        # 1. Base ticker check (e.g. RELIANCE, TCS, AAPL)
        clean_sym = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").lower()
        if len(clean_sym) >= 3:
            pattern_sym = r"\b" + re.escape(clean_sym) + r"\b"
            if re.search(pattern_sym, combined_text):
                return True

        # 2. Company name check
        if company_name:
            clean_company = company_name.lower()
            # Direct match
            if clean_company in combined_text:
                return True

            # Key word tokens from company name (e.g., "Reliance", "Infosys", "Tata")
            # Exclude generic words like "industries", "limited", "ltd", "corporation", "inc", "co", "bank"
            generic_words = {
                "industries", "limited", "ltd", "corp", "corporation", "inc", "co",
                "company", "services", "technologies", "enterprises", "holdings",
                "group", "india", "the", "and", "financial"
            }
            tokens = [w for w in re.findall(r"\w+", clean_company) if w not in generic_words and len(w) >= 3]
            for token in tokens:
                pattern = r"\b" + re.escape(token) + r"\b"
                if re.search(pattern, combined_text):
                    return True

        return False

    def validate_articles(
        self,
        raw_articles: list[dict],
        symbol: str,
        company_name: str = ""
    ) -> list[dict]:
        """
        Validates, deduplicates, and filters a list of raw news articles.
        Guarantees that a single bad article will not crash the pipeline.
        Returns cleaned articles sorted newest first.
        
        Args:
            raw_articles (list[dict]): Raw news articles from fetchers.
            symbol (str): Stock symbol.
            company_name (str): Company name.
            
        Returns:
            list[dict]: List of valid, deduplicated, relevant articles.
        """
        if not raw_articles:
            return []

        valid_articles = []
        seen_keys = set()
        seen_headlines = set()

        for raw in raw_articles:
            try:
                # 1. Incomplete/invalid record check
                if not isinstance(raw, dict):
                    continue

                headline = str(raw.get("headline") or "").strip()
                # Empty headline check
                if not headline:
                    continue

                raw_url = str(raw.get("url") or "").strip()
                # URL validation check
                if raw_url and not self.is_valid_url(raw_url):
                    continue

                clean_url = self.clean_url(raw_url) if raw_url else ""

                # 2. Missing description handling
                desc = str(raw.get("description") or "").strip()
                if not desc:
                    desc = headline  # Fallback to headline if description missing

                # 3. Date validation
                raw_date = raw.get("published_date")
                if raw_date:
                    pub_date = self.validate_and_normalize_date(raw_date)
                    if not pub_date:
                        # Reject article with invalid/corrupt/future date
                        continue
                else:
                    # Missing date defaults to current UTC timestamp
                    pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                source = str(raw.get("source") or "Financial News").strip()
                comp_name = str(raw.get("company_name") or company_name or symbol).strip()

                candidate = {
                    "symbol": symbol.strip().upper(),
                    "company_name": comp_name,
                    "headline": headline,
                    "description": desc,
                    "source": source,
                    "published_date": pub_date,
                    "url": clean_url
                }

                # 4. Relevance filtering
                if not self.is_relevant(candidate, symbol, company_name):
                    continue

                # 5. Duplicate article removal
                article_key = self.generate_article_key(symbol, clean_url, headline)
                if article_key in seen_keys:
                    continue

                # Also compare normalized headline text to catch same story from different URLs
                norm_h = self.normalize_text(headline)
                if norm_h in seen_headlines:
                    continue

                seen_keys.add(article_key)
                seen_headlines.add(norm_h)

                candidate["article_key"] = article_key
                valid_articles.append(candidate)

            except Exception as item_err:
                log_error(
                    module_name="news_validator",
                    error_type="ArticleValidationError",
                    message=f"Error validating article for {symbol}: {str(item_err)}",
                    action="Skip invalid article safely"
                )
                continue

        # Sort newest relevant news first (descending by published_date)
        valid_articles.sort(key=lambda x: x["published_date"], reverse=True)

        log_info(
            "news_validator",
            f"Validated {len(valid_articles)} / {len(raw_articles)} articles for {symbol} (deduplicated & filtered)."
        )
        return valid_articles
