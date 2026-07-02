# ADR 0002 — LiteLLM detrás de un Protocol propio como capa de modelo

- Estado: aceptada (2026-07-02)

## Contexto

El MVP corre con Ollama local (llama3.1:8b) pero producción usará un modelo cloud.
El swap no debe tocar código.

## Decisión

El núcleo define `chatbot_core.llm.base.LLM` (Protocol). La implementación por defecto
es `LiteLLMClient`, que normaliza el formato OpenAI (mensajes y tool calling) entre
140+ providers: `ollama/...`, `anthropic/...`, `openai/...`, etc.

## Justificación

- Un solo código de agente para local y cloud; el provider se elige con
  `CHATBOT_LLM_MODEL` en `.env`.
- LiteLLM traduce los `tools` (JSON Schema) al formato de cada provider.
- El Protocol propio evita acoplar el núcleo a LiteLLM: en tests se inyecta `FakeLLM`
  y, si LiteLLM dejara de convenir, se escribe otra implementación del Protocol.

## Consecuencias

- Los embeddings usan la misma vía (`litellm.embedding` → `ollama/bge-m3` en MVP).
- Cuidado con modelos pequeños: el tool calling de un 8B es menos fiable; el diseño de
  tools devuelve errores como texto explicativo para que la conversación se recupere.
