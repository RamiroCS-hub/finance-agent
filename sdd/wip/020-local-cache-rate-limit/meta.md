# Meta: Local Cache Rate Limit

## Identificación
- **ID**: 020
- **Slug**: 020-local-cache-rate-limit
- **Tipo**: chore
- **Estado**: done

## Resumen
Reemplazar el backend Redis del rate limit por un cache local en memoria para simplificar el deploy sin perder el freno operativo previo al procesamiento pesado.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: chore/local-cache-rate-limit
- **Base branch**: main

## Artefactos
- [x] 1-functional/spec.md
- [x] 2-technical/spec.md
- [x] 3-tasks/tasks.json
- [x] 4-implementation/progress.md
- [x] 5-verify/report.md

## Fechas
- **Creada**: 2026-03-23
- **Última actualización**: 2026-03-23
- **Completada**: 2026-03-23

## Notas
- La feature `015-whatsapp-number-rate-limit` quedó implementada sobre Redis y ya está cerrada.
- El nuevo objetivo es simplificar la operación, especialmente para Render, eliminando la dependencia de Redis del path de rate limiting.
- La solución propuesta acepta el trade-off de estado local por proceso: el límite no se comparte entre réplicas y se reinicia cuando el proceso reinicia.
- La implementación aplicada mantiene el fail-open del webhook si un rate limiter inyectado falla, pero el servicio default ya no depende de infraestructura externa.
