# Proposal: Local Cache Rate Limit

## Intent

Reemplazar el rate limiter respaldado por Redis por un cache local en memoria para reducir complejidad operativa y evitar desplegar infraestructura extra solo para esta protección. El objetivo es mantener el freno previo al OCR, transcripción y LLM, pero con una estrategia suficiente para una primera etapa de despliegue simple.

## Scope

### In Scope
- Sustituir el backend Redis del `RateLimitService` por un almacenamiento local en memoria con expiración por ventana y cooldown.
- Eliminar el wiring obligatorio de Redis en startup para el path de rate limiting.
- Mantener el contrato observable del webhook: `200 {"status":"ok"}`, bloqueo previo al trabajo pesado y aviso opcional con cooldown.

### Out of Scope
- Compartir estado de rate limit entre múltiples instancias o regiones.
- Introducir una solución distribuida alternativa como Postgres, Valkey o colas externas.

## Approach

La propuesta conserva la ubicación del control en `POST /webhook`, pero cambia el backend del `RateLimitService` a una estructura en memoria del proceso con TTL por ventana y un cooldown separado para notificaciones. El deploy queda más simple porque ya no depende de `REDIS_URL`, a cambio de aceptar que el límite es best-effort por instancia y se resetea ante reinicios.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/rate_limit.py` | Modified | Reemplazo de backend Redis por cache local con limpieza/expiración. |
| `app/main.py` | Modified | Eliminación del cliente Redis para el rate limiter y simplificación del wiring. |
| `app/config.py` | Modified | Remoción o reducción de configuración específica de Redis para este flujo. |
| `tests/test_rate_limit.py` | Modified | Ajuste de tests al nuevo backend en memoria. |
| `tests/test_webhook.py` | Modified | Regresión del webhook con el nuevo wiring sin Redis. |
| `docs/setup/local.md` | Modified | Aclaración de que el rate limit ya no requiere Redis. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| El límite no se comparte entre múltiples réplicas | High | Documentar explícitamente que el comportamiento es por proceso y adecuado para una primera etapa simple. |
| Reinicios del proceso borran el estado del cupo y cooldown | High | Aceptar el trade-off y dejarlo explicitado en docs y diseño. |
| Crecimiento de memoria por keys expiradas | Med | Incorporar limpieza por expiración y tests sobre vencimiento de entradas. |

## Rollback Plan

Si el cache local no resulta suficiente, se puede revertir este cambio y volver al wiring Redis previo de la feature 015. No hay migraciones ni cambios de datos persistentes involucrados.

## Dependencies

- Ninguna dependencia externa adicional.
- Decisión explícita de aceptar rate limiting local por instancia.

## Success Criteria

- [ ] El webhook sigue limitando mensajes antes del trabajo pesado sin depender de Redis.
- [ ] La app puede arrancar y operar sin `REDIS_URL` cuando solo se necesita rate limiting local.
- [ ] Quedan documentados los trade-offs de consistencia y persistencia del enfoque en memoria.
