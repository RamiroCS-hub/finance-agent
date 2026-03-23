# Proposal: WhatsApp Number Rate Limit

## Intent

Proteger el webhook y el procesamiento del bot frente a ráfagas de mensajes enviadas por un mismo número de WhatsApp. Hoy cada mensaje válido pasa a background sin un freno previo, lo que expone costos innecesarios en OCR, transcripción y LLM, además de riesgo de abuso o loops.

## Scope

### In Scope
- Aplicar un rate limiter configurable por número de WhatsApp sobre mensajes soportados que llegan al webhook.
- Cortar el flujo antes de `background_tasks.add_task(...)` cuando el número supere el cupo de la ventana configurada.
- Compartir el contador entre instancias usando Redis y mantener respuesta 200 a Meta aun cuando el mensaje quede limitado.

### Out of Scope
- Rate limiting por IP, por tenant o por plan comercial.
- Panel administrativo, métricas avanzadas o políticas complejas por tipo de mensaje.

## Approach

La propuesta agrega un servicio de rate limit respaldado por Redis, consultado desde `POST /webhook` después de validar autenticidad y extraer el `message.from`. Si el número supera el umbral, el webhook no encola el procesamiento pesado y opcionalmente agenda un aviso breve con cooldown para no spamear advertencias.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/config.py` | Modified | Configuración del rate limiter y de Redis. |
| `app/main.py` | Modified | Inicialización del cliente Redis y wiring del servicio. |
| `app/api/webhook.py` | Modified | Enforce del límite por número antes de encolar procesamiento. |
| `app/services/rate_limit.py` | New | Servicio Redis-backed para decisiones allow/block por teléfono. |
| `tests/test_webhook.py` | Modified | Cobertura del webhook bajo y sobre el límite. |
| `tests/test_rate_limit.py` | New | Tests del servicio de rate limiting y cooldown. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Limitar tráfico legítimo demasiado agresivamente | Med | Hacer ventana y cupo configurables, con defaults prudentes. |
| Redis no disponible y bloqueo total del bot | Med | Diseñar fail-open con logging para no degradar disponibilidad. |
| Avisos de límite repetidos al usuario | Med | Guardar cooldown separado para notificar una sola vez por ventana. |

## Rollback Plan

Se puede revertir quitando el wiring del rate limiter en `main.py` y `webhook.py`, y dejando el servicio nuevo sin uso. No requiere migraciones ni altera datos persistentes del producto.

## Dependencies

- Definir variables de entorno para `REDIS_URL` y parámetros del límite.
- Redis disponible en el entorno donde corre el webhook.

## Success Criteria

- [ ] Un mismo número no puede disparar procesamiento ilimitado dentro de una ventana corta.
- [ ] El límite se aplica antes del trabajo pesado y se comparte entre instancias del servicio.
- [ ] Si Redis falla, el webhook sigue operativo y deja evidencia en logs.
