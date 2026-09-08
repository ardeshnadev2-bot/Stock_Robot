import difflib
import yfinance as yf
from src.utils.logger import log_info, log_error

class SymbolResolver:
    """Resolves and validates search queries to stock tickers."""

    # Registry mapping common company names/keywords (uppercase) to Yahoo Finance symbols
    REGISTRY = {
        "RELIANCE": "RELIANCE.NS",
        "RELIANCE INDUSTRIES": "RELIANCE.NS",
        "TATA CONSULTANCY SERVICES": "TCS.NS",
        "TCS": "TCS.NS",
        "INFOSYS": "INFY.NS",
        "INFY": "INFY.NS",
        "HDFC BANK": "HDFCBANK.NS",
        "ICICI BANK": "ICICIBANK.NS",
        "STATE BANK OF INDIA": "SBIN.NS",
        "SBIN": "SBIN.NS",
        "NIFTY 50": "^NSEI",
        "NIFTY": "^NSEI",
        "APPLE": "AAPL",
        "MICROSOFT": "MSFT",
        "GOOGLE": "GOOGL",
        "AMAZON": "AMZN",
        "TESLA": "TSLA"
    }

    def resolve(self, query: str) -> tuple[str, list[dict]]:
        """
        Resolves a search query to a Yahoo Finance ticker symbol.
        
        Args:
            query (str): The stock ticker or company name.
            
        Returns:
            tuple[str, list[dict]]:
                - Resolved symbol (str), empty string if not resolved.
                - List of suggestions if any: [{'name': Name, 'symbol': Symbol}]
        """
        if not query:
            return "", []

        # 1. Normalize query
        query_norm = query.strip().upper()
        if not query_norm:
            return "", []

        # 2. Direct Match with Registry Values (if user enters 'AAPL' or 'TCS.NS' directly)
        registry_symbols = set(self.REGISTRY.values())
        if query_norm in registry_symbols:
            return query_norm, []

        # 3. Direct Match with Registry Keys (e.g. 'TCS' -> 'TCS.NS')
        if query_norm in self.REGISTRY:
            return self.REGISTRY[query_norm], []

        # 4. Check if appending '.NS' results in a valid registry value
        # (e.g. 'sbin' -> 'SBIN.NS')
        potential_ns = f"{query_norm}.NS"
        if potential_ns in registry_symbols:
            return potential_ns, []

        # 5. Direct Suffix/Prefix Check (Yahoo Finance formatting)
        # If it already contains a dot (like 'TCS.NS' or 'AAPL.MX') or starts with '^' (index)
        if "." in query_norm or query_norm.startswith("^"):
            return query_norm, []

        # 6. Approximate matching using difflib
        # Match against registry keys (company names) and values (symbols)
        possibilities = list(self.REGISTRY.keys())
        close_keys = difflib.get_close_matches(query_norm, possibilities, n=3, cutoff=0.5)
        
        suggestions = []
        for key in close_keys:
            suggestions.append({
                "name": key.title(),
                "symbol": self.REGISTRY[key]
            })

        # Also search keys that contain the query as a substring
        for key, value in self.REGISTRY.items():
            if query_norm in key and not any(s["symbol"] == value for s in suggestions):
                suggestions.append({
                    "name": key.title(),
                    "symbol": value
                })

        # Determine auto-resolved symbol
        # If we have a very close matching registry key (first suggestion), we can return it.
        # Otherwise, fallback to the query_norm itself (which will be validated later).
        # We also try appending .NS for alphabetic strings to support Indian symbols.
        resolved_symbol = ""
        if suggestions:
            # If the user's input is a very close match to a registry key, resolve it
            # e.g., 'Relince' matches 'RELIANCE'
            resolved_symbol = suggestions[0]["symbol"]
        else:
            # Fallback heuristic: if it's purely letters and <= 5 chars, we treat it as
            # a potential Indian symbol and resolve to symbol.NS, otherwise keep original.
            if query_norm.isalpha() and len(query_norm) <= 6:
                resolved_symbol = f"{query_norm}.NS"
            else:
                resolved_symbol = query_norm

        return resolved_symbol, suggestions

    def validate_symbol(self, symbol: str, db_manager=None) -> bool:
        """
        Validates if a symbol is valid by querying local DB first, then yfinance API.
        
        Args:
            symbol (str): Symbol to validate.
            db_manager (DatabaseManager, optional): Database manager for offline fallback check.
            
        Returns:
            bool: True if symbol is valid, False otherwise.
        """
        if not symbol:
            return False

        # 1. Offline check: check if database already has data for this symbol
        if db_manager:
            try:
                db_df = db_manager.get_market_data(symbol, "1d")
                if db_df is not None and not db_df.empty:
                    log_info("symbol_resolver", f"Symbol '{symbol}' successfully validated offline via local database.")
                    return True
            except Exception as e:
                log_error(
                    module_name="symbol_resolver",
                    error_type="DatabaseError",
                    message=f"Error checking cache for symbol '{symbol}': {str(e)}",
                    action="Proceed to API validation"
                )

        # 2. API validation: fetch 1 day history using yfinance
        try:
            ticker = yf.Ticker(symbol)
            # Fetch minimal data to test validity
            df = ticker.history(period="1d")
            if df.empty:
                # yfinance returns empty df for invalid tickers
                log_info("symbol_resolver", f"Validation failed: Ticker '{symbol}' returned empty data on yfinance.")
                return False
            log_info("symbol_resolver", f"Symbol '{symbol}' successfully validated via yfinance API.")
            return True
        except Exception as e:
            log_error(
                module_name="symbol_resolver",
                error_type="ValidationError",
                message=f"Validation failed for symbol '{symbol}': {str(e)}",
                action="Return False"
            )
            return False
