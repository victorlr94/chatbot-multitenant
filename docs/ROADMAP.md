# Roadmap

Orden sugerido para llevar el MVP a producción real. Cada bloque es independiente
salvo donde se indica dependencia.

---

## Bloque 1 — Despliegue web (prioridad máxima para mostrar el MVP)

### 1.1 Dockerfile + docker-compose
```dockerfile
# imagen mínima: python 3.12-slim + uv + la app
# volúmenes: data/ (Chroma + DB + logs), tenants/
# env_file: .env (no va en la imagen)
```
Permite correr el chatbot en cualquier VPS/cloud sin instalar nada a mano.

### 1.2 Reverse proxy (Caddy o Nginx)
- Caddy: HTTPS automático con Let's Encrypt, configuración mínima.
- Expone el widget en `https://chat.tudominio.com`.

### 1.3 Modelo cloud para producción
Cambiar solo `.env`:
```bash
CHATBOT_LLM_MODEL=anthropic/claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
```
Validar primero con `uv run python scripts/evaluate.py`. El modelo local Ollama
sigue siendo la referencia de evaluación sin costo.

**Tiempo estimado: 1-2 días**

---

## Bloque 2 — Embeber el widget en la web del cliente

El widget (`src/chatbot_app/static/index.html`) es autocontenido. Para embeberlo
en cualquier sitio web del cliente:

```html
<!-- En el <head> del sitio del cliente -->
<script>
  (function() {
    var iframe = document.createElement('iframe');
    iframe.src = 'https://chat.tudominio.com/?tenant=mi_empresa';
    iframe.style.cssText = 'position:fixed;bottom:20px;right:20px;width:380px;height:560px;border:none;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.2);z-index:9999';
    document.body.appendChild(iframe);
  })();
</script>
```

O bien copiar/adaptar el HTML del widget directamente al sitio del cliente.

**Tiempo estimado: 2-4 horas**

---

## Bloque 3 — Primer cliente real (paralelo a Bloque 1)

1. Crear `tenants/<cliente>/config.yaml` con los datos del negocio real.
2. Añadir documentos reales en `tenants/<cliente>/docs/` (servicios, precios,
   horarios, políticas en markdown o PDF).
3. Correr `uv run chatbot ingest`.
4. Probar con `uv run chatbot chat` antes de subir a producción.
5. Pasar el conjunto de preguntas reales del cliente a `evaluations/<cliente>.yaml`
   y correr `scripts/evaluate.py` para medir calidad.

**Tiempo estimado: 4-8 horas (depende de qué tan listos estén los documentos)**

---

## Bloque 4 — Mejoras de calidad del agente

### 4.1 Clasificador de intención como segunda capa de scope
El system prompt solo (modelo 8B) a veces responde preguntas fuera de alcance.
Solución: un paso de clasificación previo al agente que decide si la pregunta
está dentro o fuera de scope antes de pasar al LLM caro.

```python
# En ChatPipeline.handle(), antes de llamar al agente:
if not self._scope_classifier.is_in_scope(message):
    return out_of_scope_response
```

Opciones: prompt simple con el LLM pequeño, o un clasificador de texto liviano
(ej. `fasttext`, `sentence-transformers` con ejemplos positivos/negativos).

### 4.2 Recordatorios de citas
- Job programado (APScheduler) que lee citas confirmadas próximas.
- Envía recordatorio por email (SMTP) o WhatsApp (fase 5).
- Configuración por tenant: `scheduling.reminder_hours_before: [24, 1]`.

### 4.3 Sesiones persistentes
Reemplazar `SessionStore` (en memoria) por una tabla SQLite/Postgres que serialice
el historial de conversación. Permite retomar conversaciones tras reinicio.

**Tiempo estimado bloque 4: 3-5 días**

---

## Bloque 5 — Canal WhatsApp

Requisitos previos:
- Cuenta Meta Business verificada.
- BSP (Business Solution Provider): Meta Cloud API directa, Twilio, o 360dialog.
- Plantillas de mensaje aprobadas por Meta para recordatorios (mensajes fuera
  de la ventana de 24h).

Implementación:
1. Crear `chatbot_core/channels/whatsapp.py` implementando el Protocol `Channel`.
2. Webhook FastAPI en `/webhook/whatsapp` que valida la firma de Meta y pasa el
   mensaje al pipeline.
3. Responder vía la API del BSP elegido.
4. Cumplir política Meta 2026: el bot debe tener propósito específico declarado
   (soporte + citas → califica), flujos estructurados y criterios de finalización.

**Tiempo estimado: 3-5 días + tiempo de aprobación de Meta (1-2 semanas)**

---

## Bloque 6 — Panel de administración (opcional para V1)

- Subir/actualizar documentos del corpus sin tocar el servidor.
- Ver citas agendadas y su estado.
- Ver métricas del log de interacciones: latencia, tasa de rechazo, topics más
  frecuentes, preguntas sin respuesta.
- Leer el JSONL de `data/logs/interactions.jsonl` ya es suficiente para análisis
  manual en el MVP.

**Tiempo estimado: 1-2 semanas**

---

## Bloque 7 — Escalado multi-tenant SaaS (largo plazo)

Actualmente cada instalación sirve un tenant. Para servir múltiples clientes
desde un solo proceso:
- Resolver el tenant por dominio/subdominio o header en cada request.
- Separar la ingesta por tenant en Chroma (ya está: una colección por tenant).
- Auth mínima para el panel de admin.
- Mover de SQLite a Postgres (cambio solo en `CHATBOT_DB_URL`).
- Redis para sesiones y jobs de recordatorios.

---

## Checklist para mostrar el MVP en una demo real

- [ ] `qwen3:8b` descargado y configurado en `.env`
- [ ] `uv run chatbot ingest` corrido con corpus real (o demo_clinica)
- [ ] `uv run python scripts/evaluate.py` con score ≥ 80%
- [ ] `uv run uvicorn chatbot_app.main:app` corriendo localmente
- [ ] Widget accesible en `http://localhost:8000` desde el navegador
- [ ] Demo path probado: pregunta del corpus → respuesta con fuente, pregunta
      fuera de alcance → rechazo, flujo de cita completo (listar → slot → reservar)
- [ ] (Opcional) Despliegue en VPS con HTTPS para demo remota
