# Meta: Free Audio and Report Quotas

## Identificación
- **ID**: 020
- **Slug**: 020-free-audio-report-quotas
- **Tipo**: feature
- **Estado**: verified

## Resumen
Cambiar los planes para que `FREE` tenga hasta 5 audios por semana y 3 reportes PDF por mes, mientras `PREMIUM` queda ilimitado, con enforcement persistente por usuario y períodos calendario basados en su timezone.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Base de datos**: PostgreSQL + SQLAlchemy async + Alembic

## Git
- **Branch**: feature/free-audio-report-quotas
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
- El paywall actual solo modela límites estáticos de tipos de media y no tiene cuotas periódicas persistentes.
- La generación de reportes PDF ocurre hoy en `ReportSkill` y no está metereada por plan.
- La corrección del usuario mueve las cuotas al plan `FREE`; `PREMIUM` debe seguir ilimitado para audio y reportes.
- La semántica propuesta mantiene el pedido original de períodos: 5 audios por semana y 3 reportes por mes.
- La semana y el mes se calculan según `default_timezone` del usuario; si falta, se usa la timezone inferida/default ya existente.
- Esta feature requiere cambios de modelo y migración de Alembic; al implementar hay que ejecutar `make migrate` como paso obligatorio del repo.
