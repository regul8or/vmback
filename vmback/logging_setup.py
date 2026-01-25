"""
Logging setup for VM Backup
Automatically detects interactive mode and configures appropriate handlers
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional
from datetime import datetime


class VmbackLogger:
    """
    Custom logger wrapper for vmback that provides:
    - Automatic interactive/service mode detection
    - File logging with rotation
    """
    
    def __init__(self, log_path: Optional[str] = None, log_level: str = 'INFO'):
        """
        Initialize logger
        
        Args:
            log_path: Path to log directory (None for current directory)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.log_path = Path(log_path) if log_path else Path.cwd()
        self.log_level = log_level
        self.logger = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging with automatic interactive/service mode detection"""
        # Get root logger
        self.logger = logging.getLogger('vmback')
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Set logger level
        self.logger.setLevel(getattr(logging, self.log_level))
        
        # Create formatter
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(log_format)
        
        # Detect if running interactively (TTY attached)
        is_interactive = sys.stdout.isatty()
        
        if is_interactive:
            # Interactive mode: stdout + optional file logging
            console_handler = logging.StreamHandler(sys.stdout)
            simple_format = '%(asctime)s - %(levelname)s - %(message)s'
            console_handler.setFormatter(logging.Formatter(simple_format))
            console_handler.setLevel(getattr(logging, self.log_level))
            self.logger.addHandler(console_handler)
            
            self.logger.info("Running in interactive mode (TTY detected)")
            
            # Optional: Also log to file in real-time if log path is accessible
            # This helps when monitoring ongoing backups
            try:
                self.log_path.mkdir(parents=True, exist_ok=True)
                
                session_log_file = self._get_session_log_filename()
                file_handler = logging.FileHandler(session_log_file)
                file_handler.setFormatter(logging.Formatter(log_format))
                file_handler.setLevel(getattr(logging, self.log_level))
                self.logger.addHandler(file_handler)
                
                self.logger.info(f"Also logging to file: {session_log_file}")
                
            except (OSError, IOError, PermissionError):
                # Log path not accessible (USB drive not attached, etc.)
                # Continue with console-only logging
                # We'll still try to export session log at the end
                pass
        else:
            # Service mode: journal (WARNING+) + file (configured level)
            
            # 1. Journal handler (stdout for systemd to capture)
            journal_handler = logging.StreamHandler(sys.stdout)
            journal_handler.setFormatter(formatter)
            journal_handler.setLevel(logging.WARNING)
            self.logger.addHandler(journal_handler)
            
            # 2. Session log file (created per run)
            try:
                self.log_path.mkdir(parents=True, exist_ok=True)
                
                session_log_file = self._get_session_log_filename()
                file_handler = logging.FileHandler(session_log_file)
                file_handler.setFormatter(formatter)
                file_handler.setLevel(getattr(logging, self.log_level))
                self.logger.addHandler(file_handler)
                
                self.logger.info("Running in service mode (no TTY detected)")
                self.logger.info(f"Logging to file: {session_log_file}")
                self.logger.info(f"Journal level: WARNING, File level: {self.log_level}")
                
            except (OSError, IOError, PermissionError) as e:
                # Log path not accessible - continue with journal only
                self.logger.warning(f"Could not create log file at {self.log_path}: {e}")
                self.logger.warning("Continuing with journal logging only")
    
    def _get_session_log_filename(self) -> Path:
        """Generate session log filename with timestamp"""
        now = datetime.now()
        filename = f'vmback-{now.strftime("%Y%m%d-%H%M%S")}.log'
        return self.log_path / filename


def setup_logging(config: Dict[str, Any]) -> VmbackLogger:
    """
    Setup logging based on configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        VmbackLogger instance
    """
    log_path = config.get('env', {}).get('log-path')
    log_level = config.get('logging', {}).get('level', 'INFO')
    
    return VmbackLogger(log_path=log_path, log_level=log_level)


def get_logger(name: str = 'vmback') -> logging.Logger:
    """
    Get a logger for a specific component/module
    
    Args:
        name: Component name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
