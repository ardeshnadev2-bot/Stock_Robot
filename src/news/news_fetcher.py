import urllib.parse
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from dateutil import parser as date_parser

from src.data.symbol_resolver import SymbolResolver
from src.utils.logger import log_info, log_error

# Comprehensive company name mapping for top Indian and US stocks
KNOWN_COMPANY_NAMES = {
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "Tata Consultancy Services",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "SBIN.NS": "State Bank of India",
    "BHARTIARTL.NS": "Bharti Airtel",
    "ITC.NS": "ITC",
    "LT.NS": "Larsen & Toubro",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "LTIM.NS": "LTIMindtree",
    "AXISBANK.NS": "Axis Bank",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "M&M.NS": "Mahindra & Mahindra",
    "TATAMOTORS.NS": "Tata Motors",
    "ULTRACEMCO.NS": "UltraTech Cement",
    "NTPC.NS": "NTPC",
    "POWERGRID.NS": "Power Grid Corporation",
    "TATASTEEL.NS": "Tata Steel",
    "ADANIENT.NS": "Adani Enterprises",
    "ADANIPORTS.NS": "Adani Ports",
    "SUNPHARMA.NS": "Sun Pharma",
    "JSWSTEEL.NS": "JSW Steel",
    "COALINDIA.NS": "Coal India",
    "ASIANPAINT.NS": "Asian Paints",
    "TITAN.NS": "Titan Company",
    "ONGC.NS": "Oil and Natural Gas Corporation",
    "HCLTECH.NS": "HCL Technologies",
    "MARUTI.NS": "Maruti Suzuki",
    "BAJFINANCE.NS": "Bajaj Finance",
    "BAJAJFINSV.NS": "Bajaj Finserv",
    "NESTLEIND.NS": "Nestle India",
    "GRASIM.NS": "Grasim Industries",
    "TECHM.NS": "Tech Mahindra",
    "INDUSINDBK.NS": "IndusInd Bank",
    "SBILIFE.NS": "SBI Life Insurance",
    "WIPRO.NS": "Wipro",
    "HEROMOTOCO.NS": "Hero MotoCorp",
    "BPCL.NS": "Bharat Petroleum",
    "DRREDDY.NS": "Dr. Reddy's Laboratories",
    "CIPLA.NS": "Cipla",
    "APOLLOHOSP.NS": "Apollo Hospitals",
    "HINDALCO.NS": "Hindalco Industries",
    "BRITANNIA.NS": "Britannia Industries",
    "EICHERMOT.NS": "Eicher Motors",
    "JIOFIN.NS": "Jio Financial Services",
    "SHRIRAMFIN.NS": "Shriram Finance",
    "BEL.NS": "Bharat Electronics",
    "TATACONSUM.NS": "Tata Consumer Products",
    "ADANIPOWER.NS": "Adani Power",
    "^NSEI": "Nifty 50 Index",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "NVDA": "Nvidia",
    "GOOGL": "Alphabet Google",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "JPM": "JPMorgan Chase",
    "V": "Visa",
    "WMT": "Walmart"
}


class NewsFetcher:
    """Fetches real and recent financial and company news using reliable financial news APIs and RSS feeds."""

    def __init__(self, request_timeout: int = 10):
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })

    def get_company_name(self, symbol: str) -> str:
        """
        Resolves the official corporate or trade name for a stock symbol.
        
        Args:
            symbol (str): Stock ticker symbol (e.g. RELIANCE.NS, AAPL).
            
        Returns:
            str: Resolved company name.
        """
        sym_upper = symbol.strip().upper()
        
        # 1. Known dictionary lookup
        if sym_upper in KNOWN_COMPANY_NAMES:
            return KNOWN_COMPANY_NAMES[sym_upper]

        # 2. Reverse lookup in SymbolResolver REGISTRY
        resolver = SymbolResolver()
        for name, ticker in resolver.REGISTRY.items():
            if ticker.upper() == sym_upper:
                return name.title()

        # 3. yfinance metadata lookup (offline-safe with quick timeout)
        try:
            ticker_obj = yf.Ticker(sym_upper)
            info = ticker_obj.info or {}
            long_name = info.get("longName") or info.get("shortName")
            if long_name:
                return long_name.strip()
        except Exception:
            pass

        # 4. Fallback: clean symbol
        clean_name = sym_upper.replace(".NS", "").replace(".BO", "").replace("^", "")
        return clean_name.title()

    def fetch_from_yfinance(self, symbol: str, company_name: str) -> list[dict]:
        """
        Fetches real-time financial news from Yahoo Finance for the specified symbol.
        
        Args:
            symbol (str): Stock symbol.
            company_name (str): Company name.
            
        Returns:
            list[dict]: List of normalized raw article dicts.
        """
        articles = []
        try:
            ticker = yf.Ticker(symbol)
            news_items = ticker.news or []
            log_info("news_fetcher", f"Yahoo Finance returned {len(news_items)} news items for {symbol}.")
            
            for item in news_items:
                try:
                    # Support both new and legacy yfinance news structures
                    content = item.get("content", {}) if isinstance(item, dict) else {}
                    
                    if content:
                        headline = content.get("title") or ""
                        description = content.get("summary") or content.get("description") or ""
                        source = ""
                        provider = content.get("provider")
                        if isinstance(provider, dict):
                            source = provider.get("displayName") or ""
                        elif isinstance(provider, str):
                            source = provider
                            
                        pub_date_raw = content.get("pubDate") or content.get("displayTime") or ""
                        url = ""
                        canonical = content.get("canonicalUrl")
                        click_url = content.get("clickThroughUrl")
                        if isinstance(canonical, dict):
                            url = canonical.get("url") or ""
                        elif isinstance(click_url, dict) and not url:
                            url = click_url.get("url") or ""
                    else:
                        headline = item.get("title", "")
                        description = item.get("summary", "")
                        source = item.get("publisher", "")
                        pub_date_raw = item.get("providerPublishTime", "")
                        url = item.get("link", "")

                    if not headline:
                        continue

                    # Standardize published_date
                    published_date = self._parse_datetime(pub_date_raw)

                    articles.append({
                        "symbol": symbol,
                        "company_name": company_name,
                        "headline": str(headline).strip(),
                        "description": str(description).strip(),
                        "source": str(source).strip() or "Yahoo Finance",
                        "published_date": published_date,
                        "url": str(url).strip()
                    })
                except Exception as parse_err:
                    log_error(
                        module_name="news_fetcher",
                        error_type="YFinanceItemParseError",
                        message=f"Failed to parse yfinance news item for {symbol}: {str(parse_err)}",
                        action="Skip item and continue"
                    )
                    continue

        except Exception as e:
            log_error(
                module_name="news_fetcher",
                error_type="YFinanceNewsFetchError",
                message=f"Error fetching news from Yahoo Finance for {symbol}: {str(e)}",
                action="Continue to next news provider"
            )

        return articles

    def fetch_from_google_news_rss(self, symbol: str, company_name: str) -> list[dict]:
        """
        Fetches real financial news from Google News RSS using targeted financial search queries:
        - Stock Symbol
        - Company Name
        - Company Name + Stock News
        - Company Name + Financial News
        - Company Name + Earnings
        - Company Name + Quarterly Results
        - Company Name + Business News
        
        Args:
            symbol (str): Stock symbol.
            company_name (str): Corporate name.
            
        Returns:
            list[dict]: List of normalized raw article dicts.
        """
        articles = []
        is_indian = symbol.endswith(".NS") or symbol.endswith(".BO") or symbol.startswith("^NSE")
        hl_param = "en-IN" if is_indian else "en-US"
        gl_param = "IN" if is_indian else "US"
        ceid_param = "IN:en" if is_indian else "US:en"

        # Search queries specified in requirements
        queries = [
            f"{company_name} financial news",
            f"{company_name} quarterly results",
            f"{company_name} earnings",
            f"{company_name} stock news",
            f"{company_name} business news",
            f"{company_name}",
            f"{symbol}"
        ]

        seen_urls = set()

        for q in queries:
            try:
                encoded_q = urllib.parse.quote(q)
                url = (
                    f"https://news.google.com/rss/search?q={encoded_q}"
                    f"&hl={hl_param}&gl={gl_param}&ceid={ceid_param}"
                )
                
                resp = self.session.get(url, timeout=self.request_timeout)
                if resp.status_code != 200:
                    log_error(
                        module_name="news_fetcher",
                        error_type="GoogleRSSHttpError",
                        message=f"Google News RSS returned status {resp.status_code} for query '{q}'",
                        action="Continue to next query"
                    )
                    continue

                soup = BeautifulSoup(resp.content, "xml")
                items = soup.find_all("item")

                for it in items[:15]:  # Take top 15 most recent per query to keep response fast and fresh
                    try:
                        title_el = it.find("title")
                        link_el = it.find("link")
                        pub_date_el = it.find("pubDate")
                        desc_el = it.find("description")
                        source_el = it.find("source")

                        headline = title_el.text.strip() if title_el else ""
                        article_url = link_el.text.strip() if link_el else ""
                        pub_date_raw = pub_date_el.text.strip() if pub_date_el else ""
                        
                        source_name = ""
                        if source_el and source_el.text:
                            source_name = source_el.text.strip()
                        elif " - " in headline:
                            # Google RSS titles typically end with ' - Publisher'
                            parts = headline.rsplit(" - ", 1)
                            if len(parts) == 2 and len(parts[1]) < 40:
                                headline = parts[0].strip()
                                source_name = parts[1].strip()

                        if not source_name:
                            source_name = "Financial News"

                        # Extract clean text from description HTML if present
                        description = ""
                        if desc_el and desc_el.text:
                            desc_soup = BeautifulSoup(desc_el.text, "html.parser")
                            description = desc_soup.get_text(separator=" ").strip()

                        if not headline or not article_url:
                            continue

                        if article_url in seen_urls:
                            continue
                        seen_urls.add(article_url)

                        published_date = self._parse_datetime(pub_date_raw)

                        articles.append({
                            "symbol": symbol,
                            "company_name": company_name,
                            "headline": headline,
                            "description": description,
                            "source": source_name,
                            "published_date": published_date,
                            "url": article_url
                        })
                    except Exception as parse_err:
                        continue

            except Exception as query_err:
                log_error(
                    module_name="news_fetcher",
                    error_type="GoogleRSSQueryError",
                    message=f"Error executing Google RSS query '{q}' for {symbol}: {str(query_err)}",
                    action="Continue to next query"
                )
                continue

        log_info("news_fetcher", f"Google News RSS collected {len(articles)} articles for {symbol}.")
        return articles

    def fetch_news(self, symbol: str, company_name: str = None) -> list[dict]:
        """
        Fetches real financial and company news from all configured providers.
        If one provider fails, continues with remaining providers.
        
        Args:
            symbol (str): Stock symbol.
            company_name (str, optional): Corporate name. If omitted, resolved automatically.
            
        Returns:
            list[dict]: List of raw collected news items.
        """
        if not symbol:
            return []

        resolved_name = company_name or self.get_company_name(symbol)
        log_info("news_fetcher", f"Initiating news fetching for {symbol} ({resolved_name})")

        all_articles = []

        # Provider 1: Yahoo Finance
        try:
            yf_articles = self.fetch_from_yfinance(symbol, resolved_name)
            all_articles.extend(yf_articles)
        except Exception as e:
            log_error(
                module_name="news_fetcher",
                error_type="ProviderError",
                message=f"Yahoo Finance provider failed for {symbol}: {str(e)}",
                action="Fallback to Google News RSS"
            )

        # Provider 2: Google News RSS
        try:
            google_articles = self.fetch_from_google_news_rss(symbol, resolved_name)
            all_articles.extend(google_articles)
        except Exception as e:
            log_error(
                module_name="news_fetcher",
                error_type="ProviderError",
                message=f"Google News RSS provider failed for {symbol}: {str(e)}",
                action="Proceed with articles collected so far"
            )

        log_info("news_fetcher", f"Total raw articles collected for {symbol}: {len(all_articles)}")
        return all_articles

    def _parse_datetime(self, raw_val) -> str:
        """Safely parses timestamps or date strings into ISO format (YYYY-MM-DD HH:MM:SS)."""
        if not raw_val:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Integer/Float Unix timestamp
        if isinstance(raw_val, (int, float)):
            try:
                dt = datetime.fromtimestamp(raw_val, tz=timezone.utc)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # String datetime
        try:
            dt = date_parser.parse(str(raw_val))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
