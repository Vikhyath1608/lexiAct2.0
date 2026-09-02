"""
app/core/logging.py
────────────────────
Structured JSON logging via structlog.
Falls back to stdlib logging if structlog is not installed
so the app never crashes on a missing dependency.
"""
from __future__ import annotations
import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

try:
    import structlog

    def add_request_context(logger, method, event_dict):
        event_dict["request_id"] = request_id_var.get()
        event_dict["user_id"] = user_id_var.get()
        return event_dict

    def configure_logging(debug: bool = False) -> None:
        shared_processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            add_request_context,
            structlog.processors.StackInfoRenderer(),
        ]

        renderer = structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer()

        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(logging.DEBUG if debug else logging.INFO)

        for noisy in ["uvicorn.access", "sqlalchemy.engine", "httpx"]:
            logging.getLogger(noisy).setLevel(logging.WARNING)

    def get_logger(name: str = __name__):
        return structlog.get_logger(name)

except ImportError:
    # structlog not installed — fall back to stdlib logging
    # App continues working, just without structured JSON output
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    def configure_logging(debug: bool = False) -> None:
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(stream=sys.stdout, level=level,
                            format="%(asctime)s %(levelname)s %(name)s %(message)s")
        for noisy in ["uvicorn.access", "sqlalchemy.engine", "httpx"]:
            logging.getLogger(noisy).setLevel(logging.WARNING)

    def get_logger(name: str = __name__):
        return logging.getLogger(name)