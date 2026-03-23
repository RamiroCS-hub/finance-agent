# Implementation Progress: WhatsApp Number Rate Limit

## Estado

- Fecha: 2026-03-23
- Resultado: implementación aplicada

## Cambios realizados

- Agregué [app/services/rate_limit.py](/Users/rcarnicer/Desktop/anotamelo/app/services/rate_limit.py) con un `RateLimitService` Redis-backed y decisión estructurada `RateLimitDecision`.
- Extendí [app/config.py](/Users/rcarnicer/Desktop/anotamelo/app/config.py) y [.env.example](/Users/rcarnicer/Desktop/anotamelo/.env.example) con configuración de Redis y límites por número.
- Actualicé [app/main.py](/Users/rcarnicer/Desktop/anotamelo/app/main.py) para crear el cliente Redis, inyectar el rate limiter y cerrarlo en shutdown.
- Endurecí [app/api/webhook.py](/Users/rcarnicer/Desktop/anotamelo/app/api/webhook.py) para cortar antes de `background_tasks.add_task(...)` cuando un número supera el cupo y para fallar abierto si Redis no responde.
- Sumé cobertura en [tests/test_rate_limit.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_rate_limit.py) y [tests/test_webhook.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_webhook.py).

## Notas

- El mensaje de limitación se envía al número remitente y no al grupo, para evitar ruido en chats grupales.
- El webhook mantiene `{"status": "ok"}` para eventos válidos aunque el mensaje quede bloqueado por throttling.
