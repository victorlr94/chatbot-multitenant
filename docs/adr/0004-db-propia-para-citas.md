# ADR 0004 — DB propia como fuente de verdad de citas; calendario externo opcional

- Estado: aceptada (2026-07-02)

## Contexto

El agendamiento necesita disponibilidad por reglas de negocio (horarios, duración,
horizonte) y protección contra doble reserva. Alternativas: Google Calendar API directo,
Cal.com, o DB propia.

## Decisión

Las citas viven en la DB propia (SQLite en MVP, Postgres en producción vía
`CHATBOT_DB_URL`). Los servicios y horarios vienen del `config.yaml` del tenant. La
sincronización con calendarios externos es opcional y best-effort, detrás del Protocol
`CalendarSync` (implementación actual: `NoopCalendarSync`).

## Justificación

- Control total de las reglas por sector sin depender de la semántica de un proveedor.
- Anti doble-reserva verificable: chequeo transaccional + índice único parcial
  `(tenant_id, starts_at) WHERE status='confirmed'` como backstop.
- Google Calendar directo hace difícil modelar slots/reglas y arriesga doble booking.

## Consecuencias

- MVP asume un recurso/agenda por tenant (documentado en README). Multi-profesional
  requerirá añadir una dimensión `resource` al modelo y al índice único.
- La integración real con Google Calendar es una fase futura que no toca el motor.
