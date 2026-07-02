"""Contrato de la capa LLM. Cualquier provider (Ollama, OpenAI, Anthropic) lo implementa."""

from __future__ import annotations

from typing import Protocol

from chatbot_core.types import ChatMessage, LLMResponse, ToolSpec


class LLM(Protocol):
    """Interfaz mínima que necesita el agente: chat con soporte de tool calling."""

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse: ...
