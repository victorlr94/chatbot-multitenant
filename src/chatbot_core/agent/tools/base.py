"""Registro de herramientas del agente.

Una Tool une la especificación (JSON Schema que ve el LLM) con el handler que la
ejecuta. Añadir capacidades al chatbot = registrar tools, sin tocar el loop del agente.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chatbot_core.types import ToolSpec

ToolHandler = Callable[[dict[str, Any]], str]


@dataclass
class Tool:
    spec: ToolSpec
    handler: ToolHandler


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.spec.name in self._tools:
            raise ValueError(f"Tool duplicada: {tool.spec.name}")
        self._tools[tool.spec.name] = tool

    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: la herramienta '{name}' no existe."
        try:
            return tool.handler(arguments)
        except Exception as exc:  # noqa: BLE001 — el agente debe seguir conversando
            return f"Error al ejecutar '{name}': {exc}"
