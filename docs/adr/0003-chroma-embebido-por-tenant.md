# ADR 0003 — ChromaDB embebido con una colección por tenant

- Estado: aceptada (2026-07-02)

## Contexto

El RAG necesita un vector store local para el MVP, con corpus pequeños-medianos por
empresa (decenas a cientos de documentos).

## Decisión

ChromaDB en modo embebido/persistente (`data/chroma/`), una colección por tenant,
detrás del Protocol `chatbot_core.retrieval.base.VectorStore`. Distancia coseno.

## Justificación

- Cero infraestructura para el MVP (sin servidor, sin Docker).
- La colección por tenant aísla los corpus: imposible mezclar información entre
  empresas en el retrieval.
- El Protocol permite migrar a Qdrant/pgvector en producción tocando solo el wiring
  de `chatbot_app.bootstrap`.

## Consecuencias

- La ingesta es destructiva por diseño (`clear()` + re-add): el corpus del tenant es la
  fuente de verdad y reindexar es barato a esta escala.
- Al escalar a muchos tenants o corpus grandes, evaluar un store servidor (ADR futuro).
