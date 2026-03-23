# Implementation Progress: 020-local-cache-rate-limit

## Estado

- Fecha: 2026-03-23
- Resultado: implementado

## Cambios aplicados

- `app/services/rate_limit.py`
  - Reemplazo del backend Redis por estructuras locales en memoria con cleanup oportunista.
- `app/main.py`
  - Eliminación del wiring de Redis para el rate limiting.
- `app/config.py`
  - Settings dinámicos por instancia para facilitar tests y configuración de entorno.
- `tests/test_rate_limit.py`
  - Ajuste de cobertura al rate limiter local y agregado de test de cleanup.

## Notas

- El rate limit quedó local por proceso y mantiene cooldown de notificación.
- El webhook conserva fail-open si un rate limiter inyectado levanta una excepción.
