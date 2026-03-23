# Technical Spec: Supabase Deploy Readiness

**Feature**: `002-supabase-deploy-readiness`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La solucion mantiene la arquitectura actual del producto y la hace compatible con Supabase como backend de PostgreSQL administrado. El webhook FastAPI y el procesamiento del agente siguen viviendo en un servicio Python externo; Supabase concentra la base de datos, secretos asociados al entorno de datos y tooling operativo alrededor de Postgres.

```text
Meta WhatsApp -> FastAPI service -> SQLAlchemy async -> Supabase Postgres
                                  -> Google Sheets
                                  -> LLM / media providers
```

La feature introduce configuracion explicita de conexion, documentacion de despliegue y smoke checks. No cambia el dominio del producto.

## Architecture Decision Records

### ADR-001: Supabase se usa como plataforma de datos, no como runtime principal

- **Status**: Accepted
- **Context**: El backend actual es una aplicacion FastAPI stateful con integraciones externas y procesamiento asincrono.
- **Decision**: Usar Supabase para PostgreSQL administrado y capacidades de soporte, manteniendo el webhook y el agente en un servicio Python desplegado aparte.
- **Consequences**: La migracion es incremental y de bajo riesgo. A cambio, el deploy sigue siendo de dos piezas y no "todo dentro de Supabase".
- **Alternatives considered**: Reescribir el producto como edge functions. Se descarta en esta etapa por costo de cambio y riesgo.

### ADR-002: La compatibilidad se resuelve por configuracion y checklist operativa

- **Status**: Accepted
- **Context**: El problema principal es de entorno, no de dominio.
- **Decision**: Resolver la readiness con cambios pequenos en `config`, engine de DB y documentacion operativa.
- **Consequences**: Se reduce el alcance y se puede verificar rapido. A cambio, no se elimina todavia la dependencia de otros servicios.
- **Alternatives considered**: Hacer una migracion profunda de arquitectura en una sola iteracion.

### ADR-003: Google Sheets permanece como dependencia externa en la primera ola

- **Status**: Accepted
- **Context**: El storage operativo de gastos hoy vive en Sheets.
- **Decision**: Mantener Sheets sin migrarlo durante la readiness de Supabase.
- **Consequences**: El deploy inicial es mas alcanzable. A cambio, la arquitectura sigue siendo hibrida.
- **Alternatives considered**: Migrar todos los gastos a Postgres en la misma feature.

## Component Design

### Config layer

**Responsabilidad**: modelar variables de entorno y defaults de conexion compatibles con Supabase.

**Interfaz publica**:
```python
class Settings:
    DATABASE_URL: str
    LOG_LEVEL: str
```

**Dependencias**: entorno, `.env`, runtime de la aplicacion.

### Database bootstrap

**Responsabilidad**: crear el engine async y la session factory con opciones estables para Supabase.

**Interfaz publica**:
```python
engine = create_async_engine(settings.DATABASE_URL, ...)
async_session_maker = async_sessionmaker(...)
```

**Dependencias**: SQLAlchemy, asyncpg, settings.

### Deploy documentation

**Responsabilidad**: proveer el contrato de despliegue, checklist y smoke tests.

**Interfaz publica**:
```text
README.md
docs/deploy/supabase.md
```

**Dependencias**: estado real del sistema y comandos operativos soportados.

## Data Model

Sin cambios en modelo de datos.

## API Contract

Sin cambios en API publica.

## Error Handling

- Fallas de conexion a Supabase deben loguearse al inicio con mensajes accionables.
- Errores de migracion deben quedar documentados con comandos de recuperacion.
- La guia de deploy debe distinguir entre fallas de DB, fallas del runtime web y fallas de integraciones externas.

## Testing Strategy

- **Unit tests**: settings y parseo de configuracion critica.
- **Integration tests**: smoke de apertura de sesion y migraciones contra un entorno de Postgres compatible.
- **E2E tests**: no requeridos para esta feature.

Referencia a scenarios de `1-functional/spec.md`: REQ-01 se valida por documentacion y checklist, REQ-02 por smoke tests y migraciones, REQ-03 por validaciones operativas reproducibles.

## Non-Functional Requirements

- **Performance**: sin impacto funcional esperado.
- **Security**: secretos y cadenas de conexion no deben quedar hardcodeados en el repo.
- **Observability**: agregar logs claros de conexion y arranque para troubleshooting.

## Brownfield Annotations

<!-- extends: sdd/wip/001-finance-org-wpp-reverse-eng/2-technical/spec.md#adr-003-persistencia-hibrida-entre-google-sheets-y-postgresql -->
