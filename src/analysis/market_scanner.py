import pandas as pd
import numpy as np
from datetime import datetime, timezone
from src.analysis.technical_indicators import TechnicalIndicators
from src.analysis.market_analyzer import MarketAnalyzer
from src.utils.logger import log_info, log_error

class MarketScanner:
    """Scans a stock universe, coordinates caching, calculations, and error-handling."""

    def __init__(self):
        self.analyzer = MarketAnalyzer()
        self.failed_stocks = []  # List of dicts: {"symbol": symbol, "stage": stage, "reason": reason}
        self.skipped_count = 0

    def scan_universe(
        self,
        universe: list[str],
        db_manager,
        data_processor,
        force_refresh: bool = False,
        progress_callback=None
    ) -> list[dict]:
        """
        Scans a list of stocks. Automatically falls back to API if cached data is stale, 
        missing, or contains insufficient rows. Does not crash on individual stock failures.
        
        Args:
            universe (list[str]): List of stock symbols to scan.
            db_manager (DatabaseManager): Local SQLite database manager.
            data_processor (DataProcessor): Data fetcher, validator, and cleaner.
            force_refresh (bool): Force fresh API calls, ignoring cache freshness.
            progress_callback (callable, optional): UI callback tracking (current, total).
            
        Returns:
            list[dict]: Successfully analyzed stock summaries.
        """
        results = []
        self.failed_stocks = []
        self.skipped_count = 0
        total = len(universe)
        
        # Log universe summary
        log_info("market_scanner", f"Total symbols loaded: {total}")
        
        for idx, symbol in enumerate(universe):
            # Log exact scanning progress as required
            log_info("market_scanner", f"Scanning {idx + 1}/{total}: {symbol}")
            
            if progress_callback:
                progress_callback(idx + 1, total)
                
            stage = "Data Retrieval"
            try:
                # 1. Check Cached Data (Does Valid Data Exist?)
                stage = "Check Cached Data"
                df_market = db_manager.get_market_data(symbol, "1d")
                has_valid_cache = df_market is not None and len(df_market) >= 50
                
                cache_is_fresh = False
                if has_valid_cache and not force_refresh:
                    latest_analysis = db_manager.get_latest_analysis(symbol)
                    if latest_analysis:
                        created_at_str = latest_analysis.get("created_at")
                        if created_at_str:
                            try:
                                # SQLite CURRENT_TIMESTAMP is in format "YYYY-MM-DD HH:MM:SS"
                                created_date = datetime.strptime(created_at_str.split()[0], "%Y-%m-%d").date()
                                if created_date == datetime.now(timezone.utc).date():
                                    cache_is_fresh = True
                            except Exception:
                                cache_is_fresh = False
                
                if has_valid_cache and cache_is_fresh:
                    log_info("market_scanner", f"Using cached market data for {symbol} (cache is fresh and sufficient).")
                
                # 2. Fetch Fresh Data if Cache is Stale/Missing/Insufficient
                if not has_valid_cache or not cache_is_fresh:
                    stage = "Data Fetch"
                    start_str = (datetime.today() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
                    end_str = datetime.today().strftime("%Y-%m-%d")
                    
                    try:
                        df_fresh = data_processor.process_market_data(symbol, start_str, end_str, "1d")
                        if df_fresh is None or df_fresh.empty:
                            raise ValueError("No market data returned from provider API.")
                        
                        # Save fresh data to local cache
                        stage = "Save to SQLite"
                        db_manager.save_market_data(df_fresh, symbol, "1d")
                        df_market = df_fresh
                    except Exception as fetch_err:
                        # Fallback to stale cache if it exists and has enough rows
                        if has_valid_cache:
                            log_info("market_scanner", f"Fetching failed for {symbol}: {str(fetch_err)}. Falling back to cached market data.")
                        else:
                            raise fetch_err

                # 3. Check Minimum Data Requirements before Indicator Calculations
                stage = "Validate Minimum Data"
                row_count = len(df_market)
                if row_count < 50:
                    raise ValueError(f"Insufficient historical data: {row_count} rows (minimum 50 required for indicator calculations).")

                # 4. Calculate Technical Indicators
                stage = "Indicator Calculation"
                df_with_indicators = TechnicalIndicators.calculate_indicators(df_market)

                # 5. Run Trend Analysis using Existing Analyzer
                stage = "Market Analysis"
                analysis_res = self.analyzer.analyze(df_with_indicators, symbol)
                
                # Expose the score and latest volume
                analysis_res["score"] = analysis_res.get("score", 50)
                try:
                    analysis_res["volume"] = float(df_with_indicators.iloc[-1]["volume"])
                except Exception:
                    analysis_res["volume"] = 0.0
                
                # Get company name from symbol resolver mapping
                from src.data.symbol_resolver import SymbolResolver
                resolver = SymbolResolver()
                company_name = symbol
                for name, ticker in resolver.REGISTRY.items():
                    if ticker == symbol:
                        company_name = name.title()
                        break
                if company_name == symbol:
                    company_name = symbol.replace(".NS", "").replace("^", "").title()
                analysis_res["company_name"] = company_name
                
                # 6. Save latest analysis result to cache
                stage = "Cache Analysis Summary"
                db_manager.save_analysis_result(
                    symbol=analysis_res["symbol"],
                    analysis_date=analysis_res["analysis_date"],
                    trend=analysis_res["trend"],
                    rsi=analysis_res["rsi_value"],
                    macd=analysis_res["macd_value"],
                    volatility=analysis_res["volatility"],
                    signal=analysis_res["signal"]
                )
                
                results.append(analysis_res)
                log_info("market_scanner", f"Successfully analyzed and stored scanner result for {symbol}.")
                
            except Exception as e:
                # Capture failed stock diagnostics without crashing the entire scan run
                error_msg = str(e)
                self.failed_stocks.append({
                    "symbol": symbol,
                    "stage": stage,
                    "reason": error_msg
                })
                
                if "Insufficient historical data" in error_msg:
                    self.skipped_count += 1
                
                log_error(
                    module_name="market_scanner",
                    error_type=type(e).__name__,
                    message=f"Scanner pipeline failed for {symbol} at stage '{stage}': {error_msg}",
                    action="Skip stock and continue scanning remaining universe"
                )
                
        return results

    def rank_results(self, results: list[dict]) -> dict:
        """
        Groups results into Bullish, Bearish, and Neutral lists, and ranks them.
        
        Args:
            results (list[dict]): Successfully analyzed stocks.
            
        Returns:
            dict: {"Bullish": [...], "Bearish": [...], "Neutral": [...]}
        """
        ranked = {"Bullish": [], "Bearish": [], "Neutral": []}
        
        for res in results:
            trend = res.get("trend", "Neutral")
            if trend in ranked:
                ranked[trend].append(res)
            else:
                ranked["Neutral"].append(res)
                
        # Sorting categories:
        # Bullish: Sort by score descending (highest score/bullishness first)
        ranked["Bullish"] = sorted(ranked["Bullish"], key=lambda x: x.get("score", 0), reverse=True)
        # Bearish: Sort by score ascending (lowest score/strongest bearish first)
        ranked["Bearish"] = sorted(ranked["Bearish"], key=lambda x: x.get("score", 0))
        # Neutral: Sort by score proximity to 50 (closest to 50 first)
        ranked["Neutral"] = sorted(ranked["Neutral"], key=lambda x: abs(x.get("score", 50) - 50))
        
        # Assign rank indices
        for category in ["Bullish", "Bearish", "Neutral"]:
            for rank_idx, item in enumerate(ranked[category]):
                item["rank"] = rank_idx + 1
                
        return ranked
