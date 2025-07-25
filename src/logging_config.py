"""Structured logging configuration using structlog."""

import sys
import logging
from typing import Any, Dict

import structlog
from structlog.types import EventDict, Processor

from .config import settings


def add_severity(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add severity field for cloud logging compatibility."""
    if method_name == "debug":
        event_dict["severity"] = "DEBUG"
    elif method_name == "info":
        event_dict["severity"] = "INFO"
    elif method_name == "warning":
        event_dict["severity"] = "WARNING"
    elif method_name == "error":
        event_dict["severity"] = "ERROR"
    elif method_name == "critical":
        event_dict["severity"] = "CRITICAL"
    return event_dict


def drop_color_message_key(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Remove color_message key from event dict."""
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application."""
    # Configure Python's logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )
    
    # Common processors for all environments
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_severity,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        drop_color_message_key,
    ]
    
    # Development-specific configuration
    if settings.is_development:
        processors.extend([
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ])
        
        # Use ConsoleRenderer for pretty printing in development
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
        )
    else:
        # Production configuration with JSON output
        processors.append(
            structlog.processors.JSONRenderer()
        )
        formatter = None
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set up formatter for stdlib logging if in development
    if formatter and settings.is_development:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.handlers = [handler]
        root_logger.setLevel(getattr(logging, settings.log_level))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Initialize logging on module import
setup_logging()