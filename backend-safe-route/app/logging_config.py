"""Central logging configuration for the API process."""

import logging.config
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Adds the active request identifier to each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def configure_logging(log_level: str) -> None:
    """Configure predictable console logs while preserving third-party loggers."""

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "request_id=%(request_id)s %(message)s"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "standard",
                    "filters": ["request_id"],
                },
            },
            "filters": {
                "request_id": {
                    "()": RequestIdFilter,
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["console"],
            },
            "loggers": {
                "httpx": {
                    "level": "WARNING",
                    "propagate": False,
                },
            },
        }
    )
