"""Fixtures compartidas: dobles de LLM/retrieval y tenant de prueba (sin red ni GPU)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from chatbot_core.config import SchedulingConfig, ServiceConfig, TenantConfig
from chatbot_core.scheduling.models import Base
from chatbot_core.types import ChatMessage, LLMResponse, ToolSpec


class FakeLLM:
    """LLM guionizado: devuelve respuestas predefinidas en orden y graba lo que recibe."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None) -> LLMResponse:
        self.calls.append(list(messages))
        if not self._responses:
            return LLMResponse(content="(sin más respuestas guionizadas)")
        return self._responses.pop(0)


class FakeEmbedder:
    """Embeddings deterministas basados en hash de tokens (suficiente para tests)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                vector[hash(token) % 16] += 1.0
            norm = sum(v * v for v in vector) ** 0.5 or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


@pytest.fixture
def tenant() -> TenantConfig:
    return TenantConfig(
        id="test_tenant",
        name="Negocio de Prueba",
        sector="pruebas",
        scope="Solo hablas de los servicios del negocio de prueba.",
        out_of_scope_response="Fuera de alcance.",
        scheduling=SchedulingConfig(
            enabled=True,
            timezone="UTC",
            slot_step_min=30,
            booking_horizon_days=7,
            hours={
                0: ["09:00-12:00"],
                1: ["09:00-12:00"],
                2: ["09:00-12:00"],
                3: ["09:00-12:00"],
                4: ["09:00-12:00"],
            },
            services=[
                ServiceConfig(id="corte", name="Corte de pelo", duration_min=30),
                ServiceConfig(id="tinte", name="Tinte", duration_min=60),
            ],
        ),
    )


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def fixed_now() -> datetime:
    # Lunes 2026-07-06 08:00 — el horario de prueba abre a las 09:00.
    return datetime(2026, 7, 6, 8, 0)
