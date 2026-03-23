# Proposal: Render Managed DB Deploy Readiness

## Intent

Preparar el producto para correr con PostgreSQL administrado en Render sin asumir una base embebida en Docker ni mezclar responsabilidades entre runtime y datos. El problema real no es solo la cadena de conexión: hoy falta dejar explícitos el wiring de servicios, el flujo de migraciones y las dependencias operativas mínimas para un deploy reproducible en Render.

## Scope

### In Scope
- Definir el contrato de despliegue de Render: backend FastAPI aparte, base PostgreSQL administrada aparte y sin dependencia obligatoria de Redis para el rate limiting inicial.
- Preparar la configuración de aplicación y conexión de base para un `DATABASE_URL` inyectado por Render.
- Diseñar los artefactos de deploy/documentación necesarios para que Docker quede limitado al entorno local.

### Out of Scope
- Correr PostgreSQL dentro del contenedor de la app en producción.
- Replantear la arquitectura del bot, migrar storage legacy o rediseñar el dominio financiero.

## Approach

La solución propone un deploy Render-first donde la app mantiene un runtime web propio y se conecta a una base PostgreSQL administrada mediante variables inyectadas por plataforma. El trabajo se concentra en endurecer configuración/bootstrapping, agregar un blueprint o contrato equivalente para Render, y documentar claramente la diferencia entre infraestructura local con Docker y producción con servicios administrados.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `render.yaml` | New | Blueprint canónico para enlazar web service y Postgres administrado en Render. |
| `app/config.py` | Modified | Variables de entorno y defaults compatibles con Postgres administrado y runtime Render. |
| `app/db/database.py` | Modified | Inicialización del engine async con opciones seguras para managed Postgres. |
| `Dockerfile` | Modified | Arranque productivo sin `--reload` y compatible con el puerto del runtime. |
| `.env.example` | Modified | Ejemplos de configuración local vs. Render y dependencias operativas. |
| `README.md` | Modified | Punto de entrada actualizado para deploy en Render. |
| `docs/deploy/render.md` | New | Guía operativa de despliegue y migraciones en Render. |
| `docs/setup/local.md` | Modified | Aclaración de que Docker queda reservado para desarrollo local. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Asumir mal cómo Render inyecta la conexión o maneja servicios enlazados | Med | Basar el blueprint y la documentación en el contrato oficial actual de Render. |
| Simplificar el deploy a cache local y olvidar sus trade-offs por instancia | High | Dejar explícito en la documentación y en la feature 020 que el rate limit no es distribuido. |
| Mantener un `Dockerfile` de desarrollo en producción | High | Separar comando de desarrollo del comando productivo dentro de la feature. |
| Omitir migraciones antes de abrir tráfico | Med | Incluir paso de migración como parte del flujo de readiness y del checklist de release. |

## Rollback Plan

Los cambios son mayormente configuracionales y documentales, por lo que el rollback principal es revertir el commit que introduzca `render.yaml`, ajustes de settings/engine y la guía de deploy. Si un rollout en Render falla, el servicio puede volver al entorno anterior restaurando su `DATABASE_URL` previa y deteniendo el uso del blueprint nuevo sin necesidad de revertir datos productivos ya creados.

## Dependencies

- Un servicio web en Render para ejecutar FastAPI.
- Un servicio PostgreSQL administrado en Render con su `connectionString` disponible para el backend.
- La refactorización del rate limiting a cache local planificada en `020-local-cache-rate-limit` o una decisión equivalente que elimine la dependencia de Redis para el primer deploy.

## Success Criteria

- [ ] Existe una definición clara de que producción en Render usa Postgres administrado separado del contenedor de app.
- [ ] La app queda preparada para arrancar con configuración inyectada por Render y con un flujo de migraciones reproducible.
- [ ] Docker sigue siendo una herramienta de desarrollo local y deja de ser una suposición del deploy productivo.
