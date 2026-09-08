import logging
import os
import sys
from datetime import datetime
from src.utils.config import LOG_FILE_PATH

class CustomFormatter(logging.Formatter):
    """Custom formatter to format log records in the specified block format."""
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        module_name = record.module
        
        # Get custom fields if they exist, otherwise use defaults
        error_type = getattr(record, 'error_type', 'SystemError' if record.levelno >= logging.ERROR else 'Info')
        action = getattr(record, 'action', 'None' if record.levelno >= logging.ERROR else 'Log message')
        
        message = record.getMessage()
        
        formatted_message = (
            f"[{timestamp}]\n"
            f"MODULE: {module_name}\n"
            f"ERROR TYPE: {error_type}\n"
            f"MESSAGE: {message}\n"
            f"ACTION: {action}\n"
        )
        
        # Add stack trace if there is exception info
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            formatted_message += f"STACK TRACE:\n{exc_text}\n"
            
        formatted_message += "-" * 40
        return formatted_message

def get_logger(name=None):
    """Set up and return the custom logger."""
    logger = logging.getLogger(name or "market_analyzer")
    logger.setLevel(logging.DEBUG)
    
    # Avoid adding duplicate handlers if the logger is already configured
    if not logger.handlers:
        # File Handler
        try:
            file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(CustomFormatter())
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to initialize file logger handler: {e}", file=sys.stderr)
            
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(CustomFormatter())
        logger.addHandler(console_handler)
        
    return logger

# Create global logger
logger = get_logger()

def log_error(module_name: str, error_type: str, message: str, action: str, exc_info=None):
    """Convenience function to log structured errors with custom formatting."""
    extra = {
        'error_type': error_type,
        'action': action
    }
    logger.error(message, extra=extra, exc_info=exc_info)

def log_info(module_name: str, message: str):
    """Convenience function to log structured info messages."""
    extra = {
        'error_type': 'INFO',
        'action': 'Proceed'
    }
    logger.info(message, extra=extra)
