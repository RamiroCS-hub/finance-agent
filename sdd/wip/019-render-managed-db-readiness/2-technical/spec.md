# Technical Spec: Render Managed DB Deploy Readiness

**Feature**: `019-render-managed-db-readiness`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La solución adapta el despliegue actual para que Render sea la plataforma de referencia en producción: un web service ejecuta FastAPI y se conecta a un PostgreSQL administrado por variable de entorno, mientras la infraestructura con Docker queda limitada al desarrollo local. La app conserva el mismo dominio y los mismos endpoints; el cambio vive en configuración, bootstrap de base de datos, runtime de arranque y artefactos operativos de deploy. El rate limiting deja de requerir Redis en el contrato base porque se asume su refactorización a cache local por proceso.

```text
Production
WhatsApp / Telegram -> Render Web Service (FastAPI)
                                 -> Render Postgres (DATABASE_URL)

Local
Developer -> docker-compose -> Postgres + Redis
         -> uvicorn app.main:app
```

## Architecture Decision Records

### ADR-001: Render Postgres es el target productivo de datos

- **Status**: Accepted
- **Context**: El usuario necesita que la base viva en Render como servicio separado y no dentro de Docker.
- **Decision**: Preparar el backend para consumir un PostgreSQL administrado por Render mediante `DATABASE_URL`, sin empaquetar la base dentro de la app.
- **Consequences**: Producción gana una topología clara y alineada con la plataforma. A cambio, los contratos de configuración y migración deben quedar explícitos.
- **Alternatives considered**: Mantener solo la topología local con Docker. Se descarta porque no satisface el objetivo productivo.

### ADR-002: El deploy queda modelado por artefactos declarativos y documentación canónica

- **Status**: Accepted
- **Context**: Hoy el repo no tiene un blueprint de Render ni una guía específica de ese provider.
- **Decision**: Introducir `render.yaml` y `docs/deploy/render.md` como fuentes de verdad del deploy productivo.
- **Consequences**: El deploy se vuelve repetible y auditable en git. A cambio, hay que mantener esos artefactos sincronizados con los settings reales.
- **Alternatives considered**: Configurar Render solo manualmente desde UI. Se descarta por poca trazabilidad.

### ADR-003: La compatibilidad se resuelve por configuración y bootstrap, no por bifurcar código

- **Status**: Accepted
- **Context**: El dominio del producto no cambia; cambian el entorno y las dependencias.
- **Decision**: Extender `app/config.py`, endurecer `app/db/database.py` y ajustar el arranque del contenedor para que local y producción difieran solo por variables/command.
- **Consequences**: El cambio es incremental y de bajo riesgo brownfield. A cambio, la calidad del deploy depende de tests de configuración y de una buena guía operativa.
- **Alternatives considered**: Introducir un entrypoint distinto para Render. Se descarta por complejidad innecesaria.

### ADR-004: El rate limiting productivo inicial usa cache local por proceso

- **Status**: Accepted
- **Context**: El usuario pidió evitar desplegar Redis aparte y simplificar el primer contrato operativo en Render.
- **Decision**: La guía y el blueprint base se apoyan en la refactorización del rate limiting a cache local, dejando Redis fuera del mínimo necesario para el deploy inicial.
- **Consequences**: Producción requiere menos infraestructura. A cambio, el rate limiting deja de ser compartido entre réplicas.
- **Alternatives considered**: Mantener Redis/Key Value administrado. Se descarta en esta iteración.

## Component Design

### Render blueprint

**Responsabilidad**: declarar servicios, bases y env vars de producción en Render.

**Interfaz pública**:
```yaml
services:
  - type: web
    env: docker
    name: anotamelo-api
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: anotamelo-db
          property: connectionString
```

**Dependencias**: `Dockerfile`, Render Blueprint contract, variables del backend.

### Config layer

**Responsabilidad**: exponer settings de conexión y runtime compatibles con managed Postgres.

**Interfaz pública**:
```python
class Settings:
    DATABASE_URL: str
    DATABASE_SSL_MODE: str
    DATABASE_POOL_SIZE: int
    DATABASE_MAX_OVERFLOW: int
    DATABASE_POOL_RECYCLE_SECONDS: int
```

**Dependencias**: entorno, `.env`, normalización de URLs.

### Database bootstrap

**Responsabilidad**: construir el engine async con opciones seguras para producción sin romper local.

**Interfaz pública**:
```python
def build_engine(database_url: str | None = None):
    return create_async_engine(...)
```

**Dependencias**: SQLAlchemy, asyncpg, settings.

### Runtime bootstrap

**Responsabilidad**: arrancar la app con un comando productivo compatible con el puerto del host.

**Interfaz pública**:
```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**Dependencias**: `Dockerfile`, runtime de Render, `PORT`.

### Deploy documentation

**Responsabilidad**: documentar provisionado, migración, checklist y smoke checks.

**Interfaz pública**:
```text
README.md
docs/deploy/render.md
docs/setup/local.md
.env.example
```

**Dependencias**: decisiones de arquitectura y comandos soportados (`make migrate`, `make up`).

## Data Model

Sin cambios en modelo de datos.

## API Contract

Sin cambios en API pública.

## Error Handling

- Errores de conexión a Postgres administrado deben fallar con mensajes accionables de configuración.
- El deploy guide debe diferenciar claramente fallas de DB, trade-offs del rate limiting local y fallas del runtime web.
- La documentación debe aclarar que el rate limiting ya no depende de `REDIS_URL` en el deploy inicial, pero sí tiene alcance por instancia.

## Testing Strategy

- **Unit tests**: `Settings` y parseo de variables nuevas para Render; construcción del engine con opciones de SSL/pool.
- **Integration tests**: smoke test de inicialización de sesión contra configuración compatible con managed Postgres; validación de arranque sin Redis gracias al rate limiting local.
- **E2E tests**: no requeridos para esta feature.

Referencia a scenarios de `1-functional/spec.md`: REQ-01 y REQ-03 se validan sobre artefactos/documentación; REQ-02 por tests/config/migraciones; REQ-04 por checklist y smoke de runtime sin Redis.

## Non-Functional Requirements

- **Performance**: sin cambios funcionales esperados; la configuración de pool debe evitar degradación por defaults inadecuados.
- **Security**: las cadenas de conexión y secretos de provider no deben quedar hardcodeados en el repo ni en el blueprint con valores literales.
- **Observability**: logs de startup y guía operativa deben permitir distinguir fallas de configuración de fallas de aplicación.

## Brownfield Annotations

<!-- extends: sdd/wip/002-supabase-deploy-readiness/2-technical/spec.md -->

Esta feature mantiene el patrón de usar un runtime Python externo y una base administrada, pero reemplaza el target operacional por Render y agrega el blueprint declarativo necesario para ese provider.
