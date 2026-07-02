"""Pipeline de un turno de chat: input guard → agente → output guard → log.

Es el único punto de entrada que deben usar los canales (CLI, web, WhatsApp):
así todos pasan por las mismas defensas y observabilidad.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from chatbot_core.agent.agent import Agent
from chatbot_core.guards.input_guard import InputGuard
from chatbot_core.guards.output_guard import OutputGuard
from chatbot_core.observability.interactions import InteractionLogger
from chatbot_core.types import ChatMessage


@dataclass
class ChatResult:
    reply: str
    refused: bool = False
    tool_calls: list[str] = field(default_factory=list)


class SessionStore:
    """Historiales de conversación en memoria, por session_id (MVP single-process)."""

    def __init__(self, max_sessions: int = 1000) -> None:
        self._sessions: dict[str, list[ChatMessage]] = {}
        self._max_sessions = max_sessions

    def get(self, session_id: str) -> list[ChatMessage]:
        if session_id not in self._sessions:
            if len(self._sessions) >= self._max_sessions:
                # Descarta la sesión más antigua (orden de inserción de dict).
                oldest = next(iter(self._sessions))
                del self._sessions[oldest]
            self._sessions[session_id] = []
        return self._sessions[session_id]

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class ChatPipeline:
    def __init__(
        self,
        agent: Agent,
        input_guard: InputGuard,
        output_guard: OutputGuard,
        logger: InteractionLogger,
        sessions: SessionStore,
        tenant_id: str,
        model_name: str,
    ) -> None:
        self._agent = agent
        self._input_guard = input_guard
        self._output_guard = output_guard
        self._logger = logger
        self._sessions = sessions
        self._tenant_id = tenant_id
        self._model_name = model_name

    def handle(self, session_id: str, message: str, channel: str = "cli") -> ChatResult:
        started = time.perf_counter()

        guard = self._input_guard.check(message)
        if not guard.allowed:
            self._log(session_id, channel, message, guard.response, started, [], True, guard.reason)
            return ChatResult(reply=guard.response, refused=True)

        history = self._sessions.get(session_id)
        agent_reply = self._agent.respond(history, message)

        output = self._output_guard.check(agent_reply.content)
        if output.flagged and output.content != agent_reply.content:
            # Sustituye también el último mensaje del historial para no arrastrar la fuga.
            history[-1] = ChatMessage(role="assistant", content=output.content)

        self._log(
            session_id,
            channel,
            message,
            output.content,
            started,
            agent_reply.tool_calls_made,
            output.flagged,
            output.reason,
        )
        return ChatResult(
            reply=output.content,
            refused=output.flagged,
            tool_calls=agent_reply.tool_calls_made,
        )

    def _log(
        self,
        session_id: str,
        channel: str,
        message: str,
        response: str,
        started: float,
        tool_calls: list[str],
        refused: bool,
        reason: str,
    ) -> None:
        self._logger.log(
            tenant=self._tenant_id,
            session_id=session_id,
            channel=channel,
            user_message=message,
            response=response,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=self._model_name,
            tool_calls=tool_calls,
            refused=refused,
            guard_reason=reason,
        )
