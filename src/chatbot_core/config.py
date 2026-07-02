"""Configuración centralizada: Settings globales (.env) y configuración por tenant (YAML).

Fuente única de verdad. El resto del núcleo recibe estos objetos inyectados;
nada lee variables de entorno ni rutas por su cuenta.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la instalación (independiente del tenant)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CHATBOT_", extra="ignore")

    # LLM — cambiar de Ollama a cloud es cambiar estas dos variables.
    llm_model: str = "ollama/llama3.1:8b"
    llm_api_base: str | None = "http://localhost:11434"
    llm_temperature: float = 0.2
    llm_max_tool_rounds: int = 4

    # Embeddings (multilingüe; servido también por Ollama en el MVP)
    embedding_model: str = "ollama/bge-m3"

    # Retrieval
    retrieval_k: int = 4
    retrieval_min_score: float = 0.35

    # Rutas y almacenamiento
    tenants_dir: Path = Path("tenants")
    data_dir: Path = Path("data")
    db_url: str = "sqlite:///data/chatbot.db"

    # Tenant activo en esta instalación
    tenant: str = "demo_clinica"

    # Guards
    max_input_chars: int = 2000

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def interactions_log_path(self) -> Path:
        return self.data_dir / "logs" / "interactions.jsonl"


class ServiceConfig(BaseModel):
    """Un servicio agendable del negocio (ej. 'consulta general')."""

    id: str
    name: str
    duration_min: int = 30
    description: str = ""


class SchedulingConfig(BaseModel):
    """Reglas de agendamiento del tenant."""

    enabled: bool = True
    timezone: str = "America/Havana"
    slot_step_min: int = 30
    booking_horizon_days: int = 14
    # Horario por día de semana (0=lunes .. 6=domingo): lista de rangos "HH:MM-HH:MM"
    hours: dict[int, list[str]] = Field(default_factory=dict)
    services: list[ServiceConfig] = Field(default_factory=list)


class TenantConfig(BaseModel):
    """Todo lo específico de una empresa/sector vive aquí, no en el código."""

    id: str
    name: str
    sector: str
    language: str = "es"
    # Descripción del alcance temático: qué SÍ responde este bot.
    scope: str
    # Respuesta fija cuando la pregunta queda fuera del alcance.
    out_of_scope_response: str
    # Tono/persona opcional para el system prompt.
    persona: str = ""
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)


def load_tenant_config(tenants_dir: Path, tenant_id: str) -> TenantConfig:
    """Carga y valida `tenants/<tenant_id>/config.yaml`."""
    config_path = tenants_dir / tenant_id / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No existe la configuración del tenant: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Configuración de tenant inválida (se esperaba un mapa): {config_path}")
    raw.setdefault("id", tenant_id)
    return TenantConfig.model_validate(raw)


def tenant_docs_dir(tenants_dir: Path, tenant_id: str) -> Path:
    """Directorio del corpus documental del tenant."""
    return tenants_dir / tenant_id / "docs"
