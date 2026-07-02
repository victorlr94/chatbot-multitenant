"""Implementación de LLM sobre LiteLLM.

LiteLLM normaliza el formato OpenAI entre providers: con `model="ollama/llama3.1:8b"`
habla con Ollama local; con `model="anthropic/..."` u `"openai/..."` habla con la nube.
El swap es configuración, no código.
"""

from __future__ import annotations

import json
from typing import Any

import litellm

from chatbot_core.types import ChatMessage, LLMResponse, ToolCall, ToolSpec


def _to_openai_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        item: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            item["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id is not None:
            item["tool_call_id"] = msg.tool_call_id
        out.append(item)
    return out


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class LiteLLMClient:
    def __init__(
        self,
        model: str,
        api_base: str | None = None,
        temperature: float = 0.2,
        timeout: float = 120.0,
        think: bool | None = None,
    ) -> None:
        self._model = model
        self._api_base = api_base
        self._temperature = temperature
        self._timeout = timeout
        # think=False desactiva el thinking mode de qwen3 vía Ollama (mucho más rápido)
        self._think = think

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": _to_openai_messages(messages),
            "temperature": self._temperature,
            "timeout": self._timeout,
        }
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._think is not None and self._model.startswith("ollama/"):
            kwargs["extra_body"] = {"think": self._think}
        if tools:
            kwargs["tools"] = [t.to_openai() for t in tools]

        response = litellm.completion(**kwargs)
        message = response.choices[0].message

        tool_calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            tool_calls.append(
                ToolCall(
                    id=tc.id or f"call_{len(tool_calls)}",
                    name=tc.function.name or "",
                    arguments=_parse_arguments(tc.function.arguments),
                )
            )

        content = message.content or ""
        # Algunos modelos Ollama (ej. llama3.1:8b) devuelven el tool call como JSON
        # en el campo content en lugar de en message.tool_calls. LiteLLM no siempre
        # normaliza este comportamiento, así que lo parseamos manualmente como fallback.
        if not tool_calls and content.strip().startswith("{"):
            tool_calls = _try_parse_content_tool_call(content.strip())
            if tool_calls:
                content = ""

        return LLMResponse(content=content, tool_calls=tool_calls)


def _try_parse_content_tool_call(content: str) -> list[ToolCall]:
    """Intenta parsear un tool call JSON embebido en el campo content."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    if data.get("type") != "function" or "function" not in data:
        return []
    fn = data["function"]
    name = fn.get("name", "")
    args = fn.get("arguments", {})
    if not name:
        return []
    if isinstance(args, str):
        args = _parse_arguments(args)
    if not isinstance(args, dict):
        args = {}
    return [ToolCall(id=data.get("id", "call_0"), name=name, arguments=args)]
