## Design Document

**Feature**: 019-render-managed-db-readiness
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

La solución conserva el backend FastAPI actual y reemplaza la suposición tácita de "base local en Docker" por un contrato explícito de servicios administrados en Render. En producción, el webhook y el loop del agente viven en un web service y PostgreSQL vive como servicio administrado enlazado por variable de entorno. El rate limiting deja de empujar una dependencia de Redis para el primer deploy porque se planifica migrarlo a un cache local por proceso.

El cambio central no es de dominio sino de frontera operativa. La app debe poder distinguir entre local y producción solo por configuración, mientras `docker-compose.yml` queda limitado al desarrollo local y deja de sugerir que la base de datos productiva pueda correr en el mismo stack del deploy.

```text
WhatsApp / Telegram
        -> Render Web Service (FastAPI)
             -> Render Postgres (DATABASE_URL)

Local dev
   -> docker-compose up
        -> local Postgres
        -> local Redis
```

### ADRs

#### ADR-001: Producción usa base administrada separada del contenedor

- **Context**: El repo ya tiene Docker para desarrollo local, pero el pedido actual requiere que la base de producción viva como servicio aparte en Render.
- **Decision**: Modelar producción con un servicio web y un servicio PostgreSQL administrado separados, enlazados solo por configuración.
- **Consequences**: Se evita acoplar datos al ciclo de vida del contenedor y el deploy se vuelve más cercano al entorno real de Render. A cambio, la documentación y el wiring deben dejar muy clara la separación.
- **Alternatives considered**: Ejecutar PostgreSQL dentro de Docker en producción. Se descarta porque contradice el objetivo del usuario y aumenta riesgo operativo.

#### ADR-002: `render.yaml` se vuelve el contrato canónico de infraestructura

- **Context**: Hoy no hay un artefacto en el repo que describa servicios, enlaces y variables de Render.
- **Decision**: Introducir `render.yaml` como blueprint declarativo para el servicio web y sus dependencias administradas.
- **Consequences**: El deploy se vuelve reproducible y revisable en git; la plataforma queda explícita en el repo. A cambio, hay que mantener ese archivo alineado con los settings reales.
- **Alternatives considered**: Configuración manual desde el dashboard. Se descarta como única fuente porque es difícil de revisar y repetir.

#### ADR-003: Docker queda reservado a desarrollo local

- **Context**: `docker-compose.yml` ya resuelve Postgres/Redis para el developer loop, pero esa topología no debe confundirse con la de producción.
- **Decision**: Mantener `docker-compose.yml` para local y reforzar por documentación/config que no participa del deploy productivo.
- **Consequences**: No se rompe la experiencia local existente y se minimizan cambios brownfield. A cambio, el repo convive con dos contratos de infraestructura que deben estar bien señalizados.
- **Alternatives considered**: Eliminar Docker por completo. Se descarta porque hoy sigue siendo útil para el setup local.

#### ADR-004: El primer deploy en Render asume rate limiting local, no Redis

- **Context**: El rate limit actual fue implementado con Redis, pero el usuario quiere simplificar la operación y evitar desplegar esa pieza aparte.
- **Decision**: Planificar el deploy inicial de Render sobre la refactorización a cache local de la feature `020-local-cache-rate-limit`, eliminando Redis del contrato base de producción.
- **Consequences**: La infraestructura productiva mínima queda reducida a web service + Postgres. A cambio, el rate limiting pasa a ser por instancia y no distribuido.
- **Alternatives considered**: Mantener Redis como servicio gestionado adicional. Se descarta en esta etapa por complejidad operativa innecesaria.

### Component Design

#### `render.yaml`

**Responsabilidad**: Declarar servicios, enlaces y variables mínimas para un deploy reproducible en Render.

**Interfaz pública**:
```yaml
services:
  - type: web
    env: docker
    ...
databases:
  - name: anotamelo-db
    ...
```

**Dependencias**: contrato actual de Blueprint en Render, `Dockerfile`, variables de aplicación.

**Invariantes**:
- El web service no define PostgreSQL como contenedor interno.
- `DATABASE_URL` proviene del servicio de base administrado.
- El blueprint productivo mínimo no depende de Redis.

#### `app/config.py`

**Responsabilidad**: Normalizar y exponer la configuración necesaria para distinguir entorno local de managed Postgres sin hacks manuales.

**Interfaz pública**:
```python
class Settings:
    DATABASE_URL: str
    DATABASE_SSL_MODE: str
    DATABASE_POOL_SIZE: int
    DATABASE_MAX_OVERFLOW: int
```

**Dependencias**: entorno, `.env`, contrato de variables de Render.

**Invariantes**:
- La app acepta una URL de Postgres administrado sin edición manual del código.
- Los defaults siguen funcionando en local con Docker.
- Los toggles de SSL/pooling son explícitos y testeables.

#### `app/db/database.py`

**Responsabilidad**: Construir el engine async de SQLAlchemy con opciones adecuadas para un entorno administrado.

**Interfaz pública**:
```python
def build_engine(database_url: str | None = None):
    ...
```

**Dependencias**: `Settings`, SQLAlchemy async, `asyncpg`.

**Invariantes**:
- El engine puede inicializarse con la URL inyectada por Render.
- El comportamiento local existente no se rompe.
- El wiring de SSL/pool queda derivado de settings, no hardcodeado.

#### `Dockerfile`

**Responsabilidad**: Construir una imagen apta para un web service productivo en Render cuando el runtime se despliega desde Docker.

**Interfaz pública**:
```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**Dependencias**: `requirements.txt`, código de app, `PORT` del runtime.

**Invariantes**:
- No usa `--reload` en producción.
- El puerto puede ser inyectado por la plataforma.
- La imagen no contiene ni arranca PostgreSQL.

#### `docs/deploy/render.md`

**Responsabilidad**: Definir el procedimiento operativo de provisionado, migración, checklist y smoke checks en Render.

**Interfaz pública**:
```text
README.md
docs/deploy/render.md
docs/setup/local.md
```

**Dependencias**: estado real de la app y decisiones de deploy.

**Invariantes**:
- La guía distingue claramente local vs. producción.
- Incluye el orden correcto: provisionar, setear env, migrar, validar, abrir tráfico.
- Menciona que el rate limiting inicial es local por proceso y no requiere Redis.

### Data Model Changes

Sin cambios en el modelo de datos ni en migraciones de esquema por esta feature.

### API Contract

Sin cambios en la API pública. Los endpoints `/webhook` y `/telegram/webhook` conservan su contrato; cambia solo la infraestructura y el wiring de runtime/datos.

### Testing Strategy

**Unit tests**:
- Parseo y normalización de `DATABASE_URL` y nuevas variables de configuración.
- Construcción del engine con opciones de SSL/pool según settings.

**Integration tests**:
- Smoke test de apertura de sesión usando configuración compatible con managed Postgres.
- Validación del arranque de la app sin Redis, apoyada en la refactorización del rate limiting a cache local.

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | doc/smoke | El deploy target queda definido como web service + managed Postgres. |
| REQ-01 Scenario 02 | doc/review | La guía excluye explícitamente DB en Docker para producción. |
| REQ-02 Scenario 01 | unit/integration | La app acepta la URL inyectada por Render y puede inicializar el engine. |
| REQ-02 Scenario 02 | integration/manual | Existe un flujo reproducible para correr Alembic sobre Render. |
| REQ-03 Scenario 01 | manual/doc | Docker sigue funcionando para local sin contaminar la topología productiva. |
| REQ-03 Scenario 02 | doc/review | El checklist de producción no requiere `docker-compose`. |
| REQ-04 Scenario 01 | doc/config | El despliegue deja explícito que el primer release usa rate limiting local y no requiere Redis. |
| REQ-04 Scenario 02 | smoke/manual | La checklist detecta migraciones, variables faltantes y el alcance por instancia del rate limit. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Configurar SSL/pooling incorrectamente para el servicio administrado | Med | High | Hacer la configuración explícita y cubrirla con tests de settings/engine. |
| Mantener un comando de arranque solo apto para desarrollo | High | High | Cambiar el `Dockerfile` o el start command en la misma feature. |
| Documentar Render sin aclarar el carácter local del rate limiting | Med | Med | Hacer referencia explícita a la feature 020 y a los trade-offs por instancia. |
| Ambigüedad entre Supabase histórico y Render actual | Med | Med | Añadir guía específica de Render y actualizar README para que el entrypoint sea inequívoco. |

### Notes for sdd-spec-writer

La spec técnica debe dejar explícito que esta feature no reabre el debate arquitectónico sobre el bot: solo aterriza la capa de deploy a Render. También conviene remarcar que `render.yaml` y la guía de deploy son parte del producto operativo, no documentación opcional.
