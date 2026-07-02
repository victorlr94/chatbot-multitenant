from typing import Any

from tests.conftest import FakeLLM

from chatbot_core.agent.agent import Agent
from chatbot_core.agent.tools.base import Tool, ToolRegistry
from chatbot_core.types import ChatMessage, LLMResponse, ToolCall, ToolSpec


def _echo_tool(name: str = "echo") -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        return f"eco: {arguments.get('text', '')}"

    return Tool(
        spec=ToolSpec(name=name, description="Devuelve el texto", parameters={"type": "object"}),
        handler=handler,
    )


def test_direct_answer_without_tools() -> None:
    llm = FakeLLM([LLMResponse(content="Hola, ¿en qué te ayudo?")])
    agent = Agent(llm, ToolRegistry(), system_prompt="Eres un bot.")
    history: list[ChatMessage] = []

    reply = agent.respond(history, "hola")

    assert reply.content == "Hola, ¿en qué te ayudo?"
    assert reply.tool_calls_made == []
    assert history[0].role == "system"
    assert [m.role for m in history] == ["system", "user", "assistant"]


def test_tool_call_roundtrip() -> None:
    llm = FakeLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "hola"})],
            ),
            LLMResponse(content="La herramienta dijo: eco: hola"),
        ]
    )
    agent = Agent(llm, ToolRegistry([_echo_tool()]), system_prompt="Eres un bot.")
    history: list[ChatMessage] = []

    reply = agent.respond(history, "usa la tool")

    assert reply.tool_calls_made == ["echo"]
    assert "eco: hola" in reply.content
    tool_messages = [m for m in llm.calls[1] if m.role == "tool"]
    assert tool_messages and tool_messages[0].content == "eco: hola"
    assert tool_messages[0].tool_call_id == "c1"


def test_unknown_tool_reports_error_and_continues() -> None:
    llm = FakeLLM(
        [
            LLMResponse(content="", tool_calls=[ToolCall(id="c1", name="nope", arguments={})]),
            LLMResponse(content="No pude usar esa herramienta."),
        ]
    )
    agent = Agent(llm, ToolRegistry(), system_prompt="Eres un bot.")

    reply = agent.respond([], "haz algo raro")

    assert reply.content == "No pude usar esa herramienta."


def test_max_tool_rounds_forces_final_answer() -> None:
    looping = LLMResponse(
        content="", tool_calls=[ToolCall(id="c", name="echo", arguments={"text": "x"})]
    )
    llm = FakeLLM([looping, looping, LLMResponse(content="respuesta final")])
    agent = Agent(llm, ToolRegistry([_echo_tool()]), system_prompt="Bot", max_tool_rounds=2)

    reply = agent.respond([], "loop")

    assert reply.content == "respuesta final"
    assert reply.tool_calls_made == ["echo", "echo"]


def test_history_is_reused_across_turns() -> None:
    llm = FakeLLM([LLMResponse(content="uno"), LLMResponse(content="dos")])
    agent = Agent(llm, ToolRegistry(), system_prompt="Bot")
    history: list[ChatMessage] = []

    agent.respond(history, "primer turno")
    agent.respond(history, "segundo turno")

    # system + (user, assistant) x2
    assert len(history) == 5
    # El segundo call del LLM debe incluir el primer intercambio completo.
    assert any(m.content == "primer turno" for m in llm.calls[1])
