# ADR 0005 — Multi-tenant por configuración (carpeta por empresa)

- Estado: aceptada (2026-07-02)

## Contexto

El requisito central: los temas que responde el bot deben poder intercambiarse según el
sector o la empresa donde se implante, sin reescribir el sistema.

## Decisión

Todo lo específico de una empresa vive en `tenants/<empresa>/`:

- `config.yaml` — identidad, alcance temático, respuesta fuera de alcance, persona,
  servicios, horarios y zona horaria (validado con Pydantic: `TenantConfig`).
- `docs/` — corpus de conocimiento (markdown/txt/PDF) que alimenta el RAG.

Cada instalación activa un tenant vía `CHATBOT_TENANT`. El system prompt se genera
desde una plantilla común (`chatbot_app/prompts/system.md`) + los datos del tenant.

## Justificación

- Onboarding de un cliente nuevo sin tocar código: copiar carpeta, editar YAML,
  reemplazar documentos, `chatbot ingest`.
- El alcance estricto por configuración cumple además la política 2026 de Meta para
  WhatsApp (solo agentes de propósito específico).

## Consecuencias

- El núcleo nunca importa nada de `tenants/`; solo recibe `TenantConfig`.
- Una instalación = un tenant activo (aislamiento simple). Servir varios tenants desde
  un mismo proceso (SaaS) requerirá resolver el tenant por request (fase futura).
