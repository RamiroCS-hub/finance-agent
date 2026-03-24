# Implementation Progress: Free Audio and Report Quotas

## Estado

- Fecha: 2026-03-23
- Resultado: implementación aplicada

## Cambios realizados

- Extendí [app/services/paywall.py](/Users/rcarnicer/Desktop/anotamelo/app/services/paywall.py) para que `FREE` permita audio con cuota y `PREMIUM` quede ilimitado para audio/reportes.
- Agregué persistencia de consumo en [app/db/models.py](/Users/rcarnicer/Desktop/anotamelo/app/db/models.py), [app/services/plan_usage.py](/Users/rcarnicer/Desktop/anotamelo/app/services/plan_usage.py) y la migración [e4a1f2b7c8d9_add_plan_usage_events.py](/Users/rcarnicer/Desktop/anotamelo/migrations/versions/e4a1f2b7c8d9_add_plan_usage_events.py).
- Sumé helpers de ventanas semanales y mensuales por timezone en [app/services/timezones.py](/Users/rcarnicer/Desktop/anotamelo/app/services/timezones.py).
- Apliqué el precheck y consumo final de cuota de audio en [app/api/webhook.py](/Users/rcarnicer/Desktop/anotamelo/app/api/webhook.py) y [app/api/telegram_webhook.py](/Users/rcarnicer/Desktop/anotamelo/app/api/telegram_webhook.py), reusando [app/services/private_media.py](/Users/rcarnicer/Desktop/anotamelo/app/services/private_media.py).
- Apliqué la cuota mensual de reportes en [app/agent/skills.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/skills.py).
- Actualicé la documentación de contrato de planes en [README.md](/Users/rcarnicer/Desktop/anotamelo/README.md), [docs/setup/local.md](/Users/rcarnicer/Desktop/anotamelo/docs/setup/local.md) y [.env.example](/Users/rcarnicer/Desktop/anotamelo/.env.example).
- Extendí la cobertura en [tests/test_paywall.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_paywall.py), [tests/test_plan_usage.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_plan_usage.py), [tests/test_webhook.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_webhook.py), [tests/test_telegram_webhook.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_telegram_webhook.py), [tests/test_tools.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_tools.py) y [tests/test_db_models.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_db_models.py).

## Notas

- Ejecuté `make migrate` porque esta feature agrega una tabla nueva.
- `FREE` sigue sin acceso libre a imágenes; el cambio solo habilita audio con cuota y reportes con cuota.
- `PREMIUM` no usa esta cuota y sigue ilimitado para audio/reportes.
