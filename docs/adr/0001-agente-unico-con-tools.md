# ADR 0001 — Agente único con herramientas, no sistema multiagente

- Estado: aceptada (2026-07-02)

## Contexto

El producto debe responder preguntas por sector (RAG) y gestionar citas. Se evaluó
multiagente (orquestador + especialistas) vs agente único con tool calling.

## Decisión

Agente único con tools (`search_kb`, `get_available_slots`, `book_appointment`, …).
La especialización por empresa vive en configuración y datos (tenant), no en agentes.

## Justificación

- Investigación 2026: los sistemas multiagente consumen 4-220x más tokens que un agente
  único equivalente y solo rinden mejor en tareas descomponibles en sub-tareas
  independientes y paralelizables (investigación breadth-first). Una conversación de
  atención al cliente es secuencial: no cumple esa condición.
  Referencias: arXiv 2604.02460, arXiv 2605.09104.
- Con un modelo local de 8B (MVP), la latencia de orquestar varios agentes es inviable.
- Menos superficie de fallo: un solo loop, un solo prompt de sistema, tools testeables
  de forma determinista.

## Consecuencias

- Añadir capacidades = registrar tools en `ToolRegistry` (no tocar el loop del agente).
- Si a futuro una tarea justifica delegación, una tool puede encapsular internamente un
  sub-agente sin cambiar el contrato hacia el agente principal.
