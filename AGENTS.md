# AGENTS.md — contexto para agentes de IA

Guía de trabajo para cualquier agente (o desarrollador) que retome este repo.
Sintetiza qué es el proyecto, cómo está construido y las decisiones que no se
deben re-litigar sin motivo.

## Qué es

Chatbot **multi-tenant reutilizable por sector**: responde preguntas sobre una
base de conocimiento intercambiable (RAG) y gestiona citas (agendar, consultar,
cancelar). Montar la solución para una empresa nueva = crear
`tenants/<empresa>/` (config + corpus) y reindexar; **el código no se toca**.

- MVP corre 100% local con Ollama (LLM + embeddings).
- Producción usa modelo cloud (Anthropic Claude Haiku por defecto) vía LiteLLM.
- El swap local ⇄ cloud es cambio de `.env`, no de código.

## Stack

Python 3.12 · `uv` · FastAPI · LiteLLM · ChromaDB · SQLAlchemy · Pydantic ·
Typer (CLI) · pytest/ruff/mypy.

## Arquitectura y decisiones firmes (no re-litigar sin motivo)

1. **Agente único con tool calling, NO multiagente.** Justificado en
   [docs/adr/0001](docs/adr/0001-agente-unico-con-tools.md): para un chatbot
   conversacional el multiagente multiplica tokens (4-220x) sin mejorar calidad.
   La especialización por empresa vive en **datos y config**, no en más agentes.
2. **Todo lo intercambiable detrás de `typing.Protocol`** (LLM, VectorStore,
   Embedder, Channel, CalendarSync). Cambiar de provider/store toca una impl, no
   veinte call-sites.
3. **Frontera núcleo/dominio estricta**: `chatbot_core/` no importa nada de
   `chatbot_app/` ni de `tenants/`.
4. **Config centralizada** en `Settings` (Pydantic) — fuente única de verdad,
   inyectada hacia abajo. Nada lee `os.environ` ni rutas por su cuenta.

## Layout

```text
src/
  chatbot_core/            # NÚCLEO reutilizable (mypy strict)
    config.py              # Settings (.env) + TenantConfig (YAML). load_dotenv() aquí.
    llm/                   # Protocol LLM + LiteLLMClient
    ingestion/             # loaders + chunking
    retrieval/             # Protocol VectorStore + Chroma + embedder + retriever
    agent/                 # loop del agente
      tools/               # knowledge (search_kb) + scheduling
    scheduling/            # motor de citas (models, service, exceptions)
    guards/                # input_guard, output_guard
    observability/         # InteractionLogger (JSONL, PII redactada)
    pipeline.py            # orquesta guards + agente + sesiones + log
  chatbot_app/             # APLICACIÓN (wiring concreto)
    bootstrap.py           # build_context(): único lugar que elige impls concretas
    main.py                # FastAPI: /api/chat, /health, widget
    cli.py                 # comandos Typer: ingest, chat
    prompts/system.md      # system prompt con placeholders {tenant_name}, etc.
    static/index.html      # widget web autocontenido
tenants/demo_clinica/      # tenant de ejemplo: config.yaml + docs/
tests/                     # unit con FakeLLM (sin red); marker `slow` = Ollama real
docs/adr/                  # decisiones de arquitectura
scripts/                   # evaluate.py (gate antes de cambiar modelo)
```

## Cómo correr

```bash
uv sync
uv run chatbot ingest                              # indexa corpus del tenant activo
uv run chatbot chat                                # chat en terminal
uv run uvicorn chatbot_app.main:app --reload       # canal web en :8000
uv run pytest                                      # tests rápidos (sin red)
uv run pytest -m slow                              # integración con Ollama real
uv run ruff check src tests && uv run mypy src
```

## Flujo de la clave de API (importante)

`config.py` llama `load_dotenv(override=False)` **al importarse**, lo que vuelca
`.env` a `os.environ`. LiteLLM detecta el provider por el prefijo del modelo
(`anthropic/…`, `openai/…`, `ollama/…`) y busca la clave estándar
(`ANTHROPIC_API_KEY`, etc.) en el entorno. Por eso el swap es solo `.env` y no
hay claves en el código. `override=False` deja que un secreto inyectado por el
SO/CI (producción) tenga precedencia sobre el `.env`.

## Gotchas aprendidos (no repetir errores)

- **Modelos pequeños (qwen3/llama3.1 8B) devuelven JSON crudo tras una tool
  call** en vez de redactar prosa. Mitigación en el código: el agente hace una
  **síntesis final sin tools** con un recordatorio de formato temporal
  (`_SYNTHESIS_FORMAT_REMINDER` en `agent/agent.py`) que NO se persiste en el
  historial. Con Haiku el problema desaparece, pero el mecanismo sigue siendo
  buena defensa.
- **Ollama en CPU/GPU lenta puede exceder el timeout de 120s** en la síntesis
  (segunda llamada). Con modelo cloud no ocurre. Si se vuelve a Ollama, subir
  `CHATBOT_LLM_TIMEOUT` o usar `qwen3:8b` con `CHATBOT_LLM_THINK=false`.
- **`search_kb` (RAG informativo) vs tools de citas** son mundos separados por
  diseño (reglas 3 y 4 del system prompt). No mezclar: preguntas informativas →
  `search_kb`; agendar → flujo de citas paso a paso con confirmación explícita.
- **`book_appointment` una sola vez por reserva** y solo tras confirmación del
  usuario (pasos 5-7 del prompt). Hay lock transaccional anti doble-reserva.

## Convenciones

- Commits convencionales en español (`feat:`, `fix:`, `docs:`).
- `chatbot_core/*` bajo mypy `strict`; mantener tipado completo.
- Tests nuevos con `FakeLLM` (ver `tests/conftest.py`), sin red ni GPU.
- Antes de promover un cambio de modelo/prompt: `uv run python scripts/evaluate.py`.

## Estado y pendientes

Ver la tabla de estado en el [README](README.md) y el [ROADMAP](docs/ROADMAP.md).
Grandes bloques pendientes: Dockerfile/deploy, sesiones persistentes, sync real
de Google Calendar, canal WhatsApp (Meta API/BSP + política 2026).
