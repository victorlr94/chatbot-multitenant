"""Loop del agente: conversa, decide tools, las ejecuta y compone la respuesta.

Agente único con tool use (decisión de arquitectura: ver docs/adr/0001).
El loop es agnóstico a qué tools existen; la especialización por empresa
entra vía system prompt + tools registradas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chatbot_core.agent.tools.base import ToolRegistry
from chatbot_core.llm.base import LLM
from chatbot_core.types import ChatMessage

FALLBACK_RESPONSE = (
    "Lo siento, no pude generar una respuesta en este momento. ¿Puedes reformular tu pregunta?"
)


@dataclass
class AgentReply:
    content: str
    tool_calls_made: list[str] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        system_prompt: str,
        max_tool_rounds: int = 4,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_tool_rounds = max_tool_rounds

    def respond(self, history: list[ChatMessage], user_message: str) -> AgentReply:
        """Genera la respuesta y ANEXA a `history` los mensajes de este turno."""
        if not history or history[0].role != "system":
            history.insert(0, ChatMessage(role="system", content=self._system_prompt))
        history.append(ChatMessage(role="user", content=user_message))

        tools_made: list[str] = []
        specs = self._tools.specs()

        for _ in range(self._max_tool_rounds):
            response = self._llm.chat(history, tools=specs or None)
            if not response.wants_tools:
                if not tools_made:
                    # Sin tools usadas: respuesta directa (fuera de scope, etc.)
                    content = response.content.strip() or FALLBACK_RESPONSE
                    history.append(ChatMessage(role="assistant", content=content))
                    return AgentReply(content=content, tool_calls_made=tools_made)
                # Se usaron tools pero el modelo paró voluntariamente: forzar síntesis
                # sin tools para que genere lenguaje natural en lugar de JSON/crudo.
                break

            history.append(
                ChatMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )
            for call in response.tool_calls:
                tools_made.append(call.name)
                result = self._tools.execute(call.name, call.arguments)
                history.append(ChatMessage(role="tool", content=result, tool_call_id=call.id))

        # Síntesis final sin herramientas (agotadas las rondas o parada voluntaria post-tools).
        response = self._llm.chat(history, tools=None)
        content = response.content.strip() or FALLBACK_RESPONSE
        history.append(ChatMessage(role="assistant", content=content))
        return AgentReply(content=content, tool_calls_made=tools_made)
