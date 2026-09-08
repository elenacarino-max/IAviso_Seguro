"""Logging JSON mínimo sin incluir avisos, respuestas ni credenciales."""

import json
import logging
from datetime import UTC, datetime

_STRUCTURED_FIELDS = ("request_id", "attempt", "outcome", "error_type")


class JsonFormatter(logging.Formatter):
    """Serializa únicamente metadatos técnicos permitidos."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    """Configura una única salida estructurada para los eventos de IAviso."""

    logger = logging.getLogger("iaviso")
    if not any(getattr(handler, "_iaviso_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._iaviso_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
