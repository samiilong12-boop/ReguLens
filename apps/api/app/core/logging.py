"""Structured logging setup with secret and sensitive field redaction."""
import logging
import structlog
from typing import Any, Dict

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "authorization",
    "jwt_secret_key",
    "api_key",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
}


def redact_sensitive_data(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Redacts passwords, tokens, and authorization headers from logs."""
    for key, value in list(event_dict.items()):
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
        elif isinstance(value, dict):
            event_dict[key] = redact_dict(value)
    return event_dict


def redact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    redacted = {}
    for k, v in d.items():
        if any(sensitive in str(k).lower() for sensitive in SENSITIVE_KEYS):
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = redact_dict(v)
        else:
            redacted[k] = v
    return redacted


def setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_sensitive_data,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
