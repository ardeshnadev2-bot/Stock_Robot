import time
import functools
from typing import Callable, Any
from src.utils.logger import log_error, log_info
from src.utils.config import MAX_RETRIES, RETRY_DELAY_SECONDS

# Custom Exceptions
class MarketAnalyzerError(Exception):
    """Base exception for the Market Data Analyzer application."""
    pass

class NetworkError(MarketAnalyzerError):
    """Exception raised for network or API fetching failures."""
    pass

class ValidationError(MarketAnalyzerError):
    """Exception raised when data validation fails."""
    pass

class DatabaseError(MarketAnalyzerError):
    """Exception raised when database operations fail."""
    pass

class IndicatorError(MarketAnalyzerError):
    """Exception raised during technical indicator calculations."""
    pass


def retry_on_failure(max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY_SECONDS):
    """
    Decorator that retries a function call on failure (exception raised).
    Mainly useful for API fetches / network calls.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    module_name = func.__module__.split('.')[-1]
                    error_type = type(e).__name__
                    
                    if retries >= max_retries:
                        log_error(
                            module_name=module_name,
                            error_type=error_type,
                            message=f"Function {func.__name__} failed after {max_retries} attempts. Error: {str(e)}",
                            action="Raise Exception",
                            exc_info=True
                        )
                        raise
                    else:
                        log_error(
                            module_name=module_name,
                            error_type=error_type,
                            message=f"Attempt {retries}/{max_retries} for function {func.__name__} failed. Retrying in {delay}s...",
                            action=f"Retry {retries + 1}",
                            exc_info=False
                        )
                        time.sleep(delay)
            return None
        return wrapper
    return decorator


def handle_api_errors(default_return: Any = None):
    """Decorator to handle API exceptions gracefully, returning a default value instead of crashing."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                module_name = func.__module__.split('.')[-1]
                log_error(
                    module_name=module_name,
                    error_type=type(e).__name__,
                    message=f"API operation error in {func.__name__}: {str(e)}",
                    action=f"Return default: {default_return}",
                    exc_info=True
                )
                return default_return
        return wrapper
    return decorator


def handle_db_errors(default_return: Any = None):
    """Decorator to handle database errors gracefully and log them without crashing the application."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                module_name = func.__module__.split('.')[-1]
                log_error(
                    module_name=module_name,
                    error_type="DatabaseError",
                    message=f"Database error in {func.__name__}: {str(e)}",
                    action="Rollback transaction and return safe response",
                    exc_info=True
                )
                return default_return
        return wrapper
    return decorator
