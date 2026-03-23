# Meta: Render Managed DB Deploy Readiness

## Identificación
- **ID**: 019
- **Slug**: 019-render-managed-db-readiness
- **Tipo**: chore
- **Estado**: done

## Resumen
Preparar el deploy con PostgreSQL administrado en Render, manteniendo Docker solo para infraestructura local y dejando explícito el contrato operativo de producción.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: chore/render-managed-db-readiness
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
- El repo ya separa la infraestructura local en `docker-compose.yml` con Postgres y Redis, pero no tiene todavía un contrato canónico de despliegue para Render.
- Existe un antecedente cerrado (`002-supabase-deploy-readiness`) enfocado en Supabase; esta feature lo reemplaza para el caso concreto de Render sin reciclar su slug.
- El backend depende de PostgreSQL para persistencia; el rate limiting pasa a planificarse sobre cache local en memoria para no exigir Redis en el deploy inicial de Render.
- El `Dockerfile` actual usa `uvicorn --reload`, lo que es adecuado para desarrollo pero no para un runtime productivo gestionado.
- La implementación aplicada agrega `render.yaml`, guía de deploy en Render y settings explícitos para pool/SSL de base.
