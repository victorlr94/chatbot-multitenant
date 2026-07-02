"""Log estructurado de interacciones (JSONL, append-only) con redacción de PII.

Un registro por turno de conversación: qué se preguntó, qué respondió el sistema,
qué tools se usaron, latencia y si hubo rechazo. Los textos se redactan (emails,
teléfonos) porque el log es para análisis operativo, no para reidentificar clientes.
El sink es intercambiable a futuro (SQLite/tracing) sin tocar a los llamadores.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# 7+ dígitos seguidos admitiendo separadores comunes: cubre teléfonos locales e
# internacionales. El lookahead evita confundir fechas ISO (2026-07-06) con teléfonos.
_PHONE_RE = re.compile(r"(?<!\d)(?!\d{4}-\d{2}-\d{2}(?!\d))(?:\+?\d[\s.-]?){7,15}(?!\d)")


def redact_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[email]", text)
    return _PHONE_RE.sub("[phone]", text)


class InteractionLogger:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        tenant: str,
        session_id: str,
        channel: str,
        user_message: str,
        response: str,
        latency_ms: int,
        model: str,
        tool_calls: list[str],
        refused: bool = False,
        guard_reason: str = "",
    ) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "tenant": tenant,
            "session_id": session_id,
            "channel": channel,
            "user_message": redact_pii(user_message),
            "response": redact_pii(response),
            "latency_ms": latency_ms,
            "model": model,
            "tool_calls": tool_calls,
            "refused": refused,
            "guard_reason": guard_reason,
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
