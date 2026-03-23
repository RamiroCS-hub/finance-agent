# Proposal: Supabase Deploy Readiness

## Intent

Determinar qué cambios concretos necesita el producto para operar con Supabase sin romper el flujo actual del bot. El problema principal hoy no es solo la base de datos: también hay dependencias de runtime, secretos, migraciones y storage operativo que no están modeladas para un deploy Supabase-first.

## Scope

### In Scope
- Auditar compatibilidad del backend actual con Supabase Postgres, pooling, SSL y variables de entorno.
- Definir el contrato de despliegue objetivo: qué corre en Supabase y qué corre fuera de Supabase.
- Preparar la configuración, documentación y gaps técnicos mínimos para un primer deploy reproducible.

### Out of Scope
- Reescribir el bot completo como Edge Functions.
- Migrar en esta iteración el storage operativo de Google Sheets a tablas propias si no es estrictamente necesario para el primer deploy.

## Approach

La feature parte de un relevamiento técnico del stack actual para distinguir dependencias compatibles con Supabase de aquellas que siguen requiriendo un servicio Python separado. A partir de eso, se propondrá una ruta incremental: endurecer `DATABASE_URL`, migraciones, secretos y observabilidad, y recién después evaluar una migración más profunda de storage o runtime.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/config.py` | Modified | Soporte explícito para configuración Supabase y SSL/pooling. |
| `app/db/database.py` | Modified | Ajustes de engine y conexión para Supabase Postgres. |
| `migrations/` | Modified | Validación de compatibilidad de Alembic con el target de despliegue. |
| `README.md` | Modified | Nueva guía de despliegue y prerrequisitos. |
| `docs/` | Modified | Checklist operativo y decisiones de arquitectura de deploy. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Asumir que Supabase puede hospedar el webhook FastAPI directamente | High | Documentar explícitamente el split entre plataforma de datos y runtime de app. |
| Dependencias actuales de Google Sheets dificultan un deploy simple | Med | Mantener Sheets en la primera etapa y aislar la integración detrás de servicios. |
| Diferencias de pooling/SSL rompen conexiones async en producción | Med | Probar con settings dedicados y tests de smoke sobre la conexión real. |

## Rollback Plan

Mantener el despliegue actual como baseline y encapsular los cambios detrás de configuración. Si falla el rollout, se revierte el commit y se vuelve al `DATABASE_URL` y documentación previa sin tocar datos productivos.

## Dependencies

- Proyecto Supabase creado con credenciales y cadena de conexión válidas.
- Definición explícita del runtime externo que recibirá el webhook de Meta.

## Success Criteria

- [ ] Existe un diagnóstico claro de qué falta para desplegar con Supabase y qué no corresponde mover allí todavía.
- [ ] La app puede conectarse a Supabase Postgres con configuración documentada y reproducible.
- [ ] Queda definido un camino incremental de despliegue sin ambigüedad operativa.
