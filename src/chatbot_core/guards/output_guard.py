"""Guard de salida: última línea de defensa sobre la respuesta del agente.

Impide fugas obvias (el system prompt en la salida) y acota la longitud. La
redacción de PII para los LOGS vive en observability; aquí no se tocan los datos
que el propio usuario está gestionando (su nombre/teléfono en una reserva).
"""

from __future__ import annotations

from dataclasses import dataclass

SYSTEM_LEAK_RESPONSE = (
    "Lo siento, no puedo compartir esa información. ¿En qué puedo ayudarte sobre "
    "nuestros servicios o para agendar una cita?"
)


@dataclass
class OutputCheck:
    content: str
    flagged: bool = False
    reason: str = ""


class OutputGuard:
    def __init__(self, system_prompt: str, max_chars: int = 4000) -> None:
        # Fragmento largo y distintivo del prompt: si aparece en la salida, es fuga.
        self._fingerprint = " ".join(system_prompt.split())[:200].lower()
        self._max_chars = max_chars

    def check(self, content: str) -> OutputCheck:
        normalized = " ".join(content.split()).lower()
        if len(self._fingerprint) >= 80 and self._fingerprint in normalized:
            return OutputCheck(
                content=SYSTEM_LEAK_RESPONSE, flagged=True, reason="system_prompt_leak"
            )
        if len(content) > self._max_chars:
            return OutputCheck(
                content=content[: self._max_chars] + " […]", flagged=True, reason="too_long"
            )
        return OutputCheck(content=content)
