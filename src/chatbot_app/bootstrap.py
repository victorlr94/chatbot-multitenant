"""Composición de la aplicación: construye el pipeline completo desde Settings.

Único lugar donde se eligen implementaciones concretas (LiteLLM, Chroma, SQLite).
Cambiar de provider/store es cambiar este wiring o las variables de entorno.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chatbot_core.agent.agent import Agent
from chatbot_core.agent.tools.base import ToolRegistry
from chatbot_core.agent.tools.knowledge import build_search_kb_tool
from chatbot_core.agent.tools.scheduling import build_scheduling_tools
from chatbot_core.config import Settings, TenantConfig, load_tenant_config, tenant_docs_dir
from chatbot_core.guards.input_guard import InputGuard
from chatbot_core.guards.output_guard import OutputGuard
from chatbot_core.ingestion.chunking import chunk_document
from chatbot_core.ingestion.loaders import load_documents
from chatbot_core.llm.base import LLM
from chatbot_core.llm.litellm_client import LiteLLMClient
from chatbot_core.observability.interactions import InteractionLogger
from chatbot_core.pipeline import ChatPipeline, SessionStore
from chatbot_core.retrieval.chroma_store import ChromaVectorStore
from chatbot_core.retrieval.embedder import LiteLLMEmbedder
from chatbot_core.retrieval.retriever import Retriever
from chatbot_core.scheduling.models import Base
from chatbot_core.scheduling.service import SchedulingService

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


@dataclass
class AppContext:
    settings: Settings
    tenant: TenantConfig
    pipeline: ChatPipeline
    sessions: SessionStore


def build_system_prompt(tenant: TenantConfig) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    tz = ZoneInfo(tenant.scheduling.timezone)
    now = datetime.now(tz)
    weekdays = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    today = f"{weekdays[now.weekday()]} {now.date().isoformat()}"
    return template.format(
        tenant_name=tenant.name,
        sector=tenant.sector,
        today=today,
        scope=tenant.scope.strip(),
        persona=tenant.persona.strip(),
        out_of_scope_response=tenant.out_of_scope_response.strip(),
        language=tenant.language,
    )


def _build_session_factory(settings: Settings) -> sessionmaker[Session]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _build_retriever(settings: Settings, tenant_id: str) -> Retriever:
    store = ChromaVectorStore(settings.chroma_path, collection_name=tenant_id)
    embedder = LiteLLMEmbedder(settings.embedding_model, api_base=settings.llm_api_base)
    return Retriever(
        store, embedder, k=settings.retrieval_k, min_score=settings.retrieval_min_score
    )


def build_context(settings: Settings | None = None, llm: LLM | None = None) -> AppContext:
    """Construye el pipeline listo para usar. `llm` inyectable para tests."""
    settings = settings or Settings()
    tenant = load_tenant_config(settings.tenants_dir, settings.tenant)

    retriever = _build_retriever(settings, tenant.id)
    registry = ToolRegistry([build_search_kb_tool(retriever)])

    if tenant.scheduling.enabled and tenant.scheduling.services:
        scheduling = SchedulingService(_build_session_factory(settings), tenant)
        for tool in build_scheduling_tools(scheduling):
            registry.register(tool)

    system_prompt = build_system_prompt(tenant)
    agent = Agent(
        llm=llm
        or LiteLLMClient(
            model=settings.llm_model,
            api_base=settings.llm_api_base,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout,
            think=settings.llm_think,
        ),
        tools=registry,
        system_prompt=system_prompt,
        max_tool_rounds=settings.llm_max_tool_rounds,
    )

    sessions = SessionStore()
    pipeline = ChatPipeline(
        agent=agent,
        input_guard=InputGuard(max_chars=settings.max_input_chars),
        output_guard=OutputGuard(system_prompt=system_prompt),
        logger=InteractionLogger(settings.interactions_log_path),
        sessions=sessions,
        tenant_id=tenant.id,
        model_name=settings.llm_model,
    )
    return AppContext(settings=settings, tenant=tenant, pipeline=pipeline, sessions=sessions)


def ingest_tenant(settings: Settings | None = None) -> int:
    """(Re)indexa el corpus del tenant activo. Devuelve el número de chunks indexados."""
    settings = settings or Settings()
    tenant = load_tenant_config(settings.tenants_dir, settings.tenant)

    documents = load_documents(tenant_docs_dir(settings.tenants_dir, tenant.id))
    chunks = [c for doc in documents for c in chunk_document(doc)]

    store = ChromaVectorStore(settings.chroma_path, collection_name=tenant.id)
    embedder = LiteLLMEmbedder(settings.embedding_model, api_base=settings.llm_api_base)
    store.clear()
    if chunks:
        embeddings = embedder.embed([c.text for c in chunks])
        store.add(chunks, embeddings)
    return len(chunks)
