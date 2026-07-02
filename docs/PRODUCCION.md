# Guía de producción — paso a paso

Para una demo o cliente real en menos de un día de trabajo.

## 1. Modelo: cambiar de Ollama a cloud

El único cambio real es el `.env`. El código no se toca.

```bash
# .env (en el servidor de producción)
CHATBOT_LLM_MODEL=anthropic/claude-haiku-4-5-20251001
CHATBOT_LLM_API_BASE=
CHATBOT_EMBEDDING_MODEL=ollama/bge-m3   # embeddings locales siguen siendo opción
                                         # o usar un modelo cloud de embeddings
ANTHROPIC_API_KEY=sk-ant-...
CHATBOT_TENANT=mi_empresa
```

**Opciones de modelo por caso de uso:**

| Modelo | Costo aprox. | Tool calling | Recomendado para |
|---|---|---|---|
| `ollama/qwen3:8b` | $0 (local) | Muy bueno | MVP local, demos |
| `anthropic/claude-haiku-4-5-20251001` | ~$0.001/1K tokens | Excelente | Producción económica |
| `anthropic/claude-sonnet-4-6` | ~$0.01/1K tokens | Excelente | Alta calidad / casos complejos |
| `openai/gpt-4.1-mini` | ~$0.0004/1K tokens | Muy bueno | Alternativa económica cloud |

Valida antes de promover:
```bash
uv run python scripts/evaluate.py
```

## 2. Dockerfile (mínimo funcional)

Crear `Dockerfile` en la raíz:

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# uv para instalar dependencias
RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY src/ src/
COPY tenants/ tenants/
COPY src/chatbot_app/prompts/ src/chatbot_app/prompts/
COPY src/chatbot_app/static/ src/chatbot_app/static/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "chatbot_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  chatbot:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/app/data          # Chroma + DB + logs (persistentes)
      - ./tenants:/app/tenants    # corpus editable sin rebuild
    restart: unless-stopped
```

```bash
docker compose up -d
```

## 3. HTTPS con Caddy (recomendado)

En un VPS con dominio apuntado:

```
# /etc/caddy/Caddyfile
chat.tudominio.com {
    reverse_proxy localhost:8000
}
```

```bash
caddy run   # HTTPS automático vía Let's Encrypt
```

## 4. Ingesta en producción

Después de actualizar documentos del tenant:

```bash
docker compose exec chatbot uv run chatbot ingest
# o en local antes de hacer el build:
uv run chatbot ingest
```

## 5. Monitorear el chatbot en producción

Los logs viven en `data/logs/interactions.jsonl`. Cada línea es un JSON con:
- `ts` — timestamp UTC
- `user_message` / `response` — texto (PII redactada)
- `latency_ms` — latencia de punta a punta
- `tool_calls` — qué herramientas usó
- `refused` / `guard_reason` — si fue bloqueado y por qué
- `model` — qué modelo respondió

Análisis rápido sin herramientas:
```bash
# Latencia promedio (últimas 100 interacciones)
tail -100 data/logs/interactions.jsonl | python -c "
import sys, json, statistics
rows = [json.loads(l) for l in sys.stdin]
lats = [r['latency_ms'] for r in rows]
print(f'p50={statistics.median(lats):.0f}ms  p95={sorted(lats)[int(len(lats)*.95)]:.0f}ms')
"

# Tasa de rechazo
tail -200 data/logs/interactions.jsonl | python -c "
import sys, json
rows = [json.loads(l) for l in sys.stdin]
refused = sum(1 for r in rows if r['refused'])
print(f'Rechazos: {refused}/{len(rows)} ({100*refused/len(rows):.1f}%)')
"
```
