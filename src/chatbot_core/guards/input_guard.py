"""Guard de entrada: valida el mensaje del usuario antes de llegar al agente.

Heurístico y conservador: bloquea entradas vacías/desmedidas y patrones obvios de
prompt injection. No sustituye al scope enforcement del system prompt; es la
primera capa (principio: preferir rechazar antes que arriesgar).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Patrones típicos de intento de override de instrucciones (es/en).
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignora\s+(todas\s+)?(las\s+)?instrucciones",
        r"olvida\s+(todas\s+)?(tus|las)\s+instrucciones",
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior)\s+instructions",
        r"you\s+are\s+now\s+(a|an)\s",
        r"act\s+as\s+(if|though|a|an)\s",
        r"revela\s+(tu|el)\s+(prompt|instrucciones)",
        r"(reveal|show|print)\s+(your\s+)?(system\s+)?prompt",
        r"\bDAN\s+mode\b",
    )
]

REJECTION_MESSAGE = (
    "Lo siento, no puedo procesar ese mensaje. ¿En qué puedo ayudarte sobre "
    "nuestros servicios o para agendar una cita?"
)


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    response: str = ""


class InputGuard:
    def __init__(self, max_chars: int = 2000) -> None:
        self._max_chars = max_chars

    def check(self, message: str) -> GuardResult:
        stripped = message.strip()
        if not stripped:
            return GuardResult(
                allowed=False,
                reason="empty_input",
                response="No recibí ningún mensaje. ¿En qué puedo ayudarte?",
            )
        if len(stripped) > self._max_chars:
            return GuardResult(
                allowed=False,
                reason="too_long",
                response=(
                    f"Tu mensaje es demasiado largo (máximo {self._max_chars} caracteres). "
                    "¿Puedes resumirlo?"
                ),
            )
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(stripped):
                return GuardResult(
                    allowed=False, reason="prompt_injection", response=REJECTION_MESSAGE
                )
        return GuardResult(allowed=True)
