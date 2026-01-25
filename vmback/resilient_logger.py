"""
Resilient logging wrapper that handles log file errors gracefully
"""

import logging
import sys
from typing import Optional


class ResilientLogger:
    """
    Wrapper around logging.Logger that handles file write errors gracefully
    
    When log file becomes unavailable (disk sleep, network disconnect, etc.),
    this logger can continue logging to console without crashing.
    """
    
    def __init__(self, logger: logging.Logger, on_error: str = 'continue'):
        """
        Initialize resilient logger
        
        Args:
            logger: Underlying logger instance
            on_error: What to do on log file error ('continue', 'warn', 'fail')
        """
        self.logger = logger
        self.on_error = on_error
        self._file_handler_failed = False
        self._last_error_reported = None
    
    def _handle_log_error(self, exc: Exception, message: str):
        """Handle logging error based on policy"""
        # Avoid infinite error loops
        if str(exc) == self._last_error_reported:
            return
        
        self._last_error_reported = str(exc)
        
        if self.on_error == 'fail':
            # Re-raise the error, causing program to exit
            raise exc
        
        elif self.on_error == 'warn':
            # Print warning to stderr (bypasses logging system)
            if not self._file_handler_failed:
                print(
                    f"WARNING: Log file error: {exc}. Continuing with console logging only.",
                    file=sys.stderr
                )
                self._file_handler_failed = True
        
        # 'continue' does nothing - silently continue
    
    def _safe_log(self, level: int, msg: str, *args, **kwargs):
        """Safely log message, handling file errors"""
        try:
            self.logger.log(level, msg, *args, **kwargs)
        except (OSError, IOError) as e:
            self._handle_log_error(e, msg)
            
            # Try to log to console only
            try:
                # Remove file handlers temporarily
                original_handlers = self.logger.handlers[:]
                self.logger.handlers = [
                    h for h in original_handlers 
                    if not isinstance(h, logging.FileHandler)
                ]
                
                # Log to console
                self.logger.log(level, msg, *args, **kwargs)
                
                # Restore handlers (will fail again, but keeps structure)
                self.logger.handlers = original_handlers
            except:
                pass  # If console logging also fails, nothing we can do
    
    def debug(self, msg, *args, **kwargs):
        """Log debug message"""
        self._safe_log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        """Log info message"""
        self._safe_log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        """Log warning message"""
        self._safe_log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        """Log error message"""
        self._safe_log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        """Log critical message"""
        self._safe_log(logging.CRITICAL, msg, *args, **kwargs)
    
    # Aliases
    warn = warning
    
    def __getattr__(self, name):
        """Delegate other methods to underlying logger"""
        return getattr(self.logger, name)


def make_resilient(logger: logging.Logger, on_error: str = 'continue') -> ResilientLogger:
    """
    Convert a regular logger to a resilient logger
    
    Args:
        logger: Logger to wrap
        on_error: Error handling policy ('continue', 'warn', 'fail')
        
    Returns:
        ResilientLogger instance
    """
    if isinstance(logger, ResilientLogger):
        return logger  # Already resilient
    
    return ResilientLogger(logger, on_error)
