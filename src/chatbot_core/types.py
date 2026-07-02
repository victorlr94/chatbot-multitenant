"""Tipos compartidos del núcleo: mensajes de chat, tool calls y documentos."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCall:
    """Invocación de una herramienta solicitada por el LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """Mensaje del historial de conversación, en formato neutral al provider."""

    role: Role
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class LLMResponse:
    """Respuesta del LLM: texto final o solicitud de tool calls."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class ToolSpec:
    """Especificación de una herramienta en formato JSON Schema (estándar OpenAI)."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class Document:
    """Documento fuente cargado desde el corpus de un tenant."""

    id: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Chunk:
    """Fragmento de documento listo para indexar."""

    id: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ScoredChunk:
    """Fragmento recuperado con su score de similitud (1.0 = idéntico)."""

    chunk: Chunk
    score: float
