# Meta: WhatsApp Number Rate Limit

## Identificación
- **ID**: 015
- **Slug**: 015-whatsapp-number-rate-limit
- **Tipo**: feature
- **Estado**: done

## Resumen
Agregar rate limiting por número de WhatsApp para frenar bursts de mensajes y proteger el webhook antes de disparar procesamiento caro.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: feature/whatsapp-number-rate-limit
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
- **Completada**: —

## Notas
- El webhook ya valida firma de Meta y siempre retorna 200 para `POST /webhook`.
- Hoy no existe rate limiting antes de `_process_message_background`, por lo que un número puede disparar bursts de texto, audio o imagen.
- `redis>=5.0.1` ya está en dependencias y `docker-compose.yml` ya levanta un servicio Redis, pero la app todavía no lo usa.
- La implementación usa Redis como backend compartido, con fail-open si hay falla operativa y cooldown para no repetir avisos.
