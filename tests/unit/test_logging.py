"""Pruebas del formato de observabilidad permitido."""

import json
import logging

from backend.app.core.logging import JsonFormatter


def test_json_formatter_emits_structured_allowlisted_fields():
    record = logging.LogRecord(
        name="iaviso.triage",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="triage_attempt",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.attempt = 2
    record.outcome = "accepted"
    record.notice_text = "contenido que no debe registrarse"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "triage_attempt"
    assert payload["request_id"] == "req-123"
    assert payload["attempt"] == 2
    assert payload["outcome"] == "accepted"
    assert "notice_text" not in payload
