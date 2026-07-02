"""Tool `search_kb`: búsqueda en la base de conocimiento del tenant (RAG)."""

from __future__ import annotations

from typing import Any

from chatbot_core.agent.tools.base import Tool
from chatbot_core.retrieval.retriever import Retriever
from chatbot_core.types import ToolSpec

NO_RESULTS_MESSAGE = (
    "No se encontró información relevante en la base de conocimiento. "
    "Indica al usuario que no dispones de esa información; NO inventes una respuesta."
)


def build_search_kb_tool(retriever: Retriever) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return "Error: falta el parámetro 'query'."
        results = retriever.retrieve(query)
        if not results:
            return NO_RESULTS_MESSAGE
        blocks = [
            f"[fuente: {r.chunk.metadata.get('source', r.chunk.id)} | score: {r.score:.2f}]\n"
            f"{r.chunk.text}"
            for r in results
        ]
        return "\n\n---\n\n".join(blocks)

    spec = ToolSpec(
        name="search_kb",
        description=(
            "Busca en la base de conocimiento de la empresa. Úsala SIEMPRE antes de "
            "responder preguntas sobre servicios, precios, horarios, políticas o "
            "cualquier dato de la empresa."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pregunta o términos de búsqueda en el idioma del usuario",
                }
            },
            "required": ["query"],
        },
    )
    return Tool(spec=spec, handler=handler)
