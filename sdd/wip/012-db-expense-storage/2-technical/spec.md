# Technical Spec: DB Expense Storage

**Feature**: `012-db-expense-storage`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La solucion reemplaza la persistencia operativa basada en `SheetsService` por una capa de gastos respaldada por PostgreSQL. El flujo runtime queda:

```text
WhatsApp webhook
  -> AgentLoop
  -> ToolRegistry
  -> Expense service
  -> expenses table
```

Google Sheets deja de ser una dependencia obligatoria del arranque y pasa a un rol secundario de importacion historica. La experiencia conversacional del usuario no cambia; cambia la fuente de verdad y la forma de resolver altas, consultas y borrados.

## Architecture Decision Records

### ADR-001: Introducir una capa de persistencia de gastos desacoplada de Sheets

- **Status**: Accepted
- **Context**: El agente y las tools hoy dependen directamente de `SheetsService`, lo que mezcla reglas de negocio con una tecnologia de storage puntual.
- **Decision**: Crear un servicio de gastos en DB con operaciones explicitas de alta, consulta, resumen y borrado, y cablear el runtime del agente contra esa capa.
- **Consequences**: El storage operativo queda reemplazable y testeable. A cambio, hay que refactorizar firmas, mocks y wiring en varias capas.
- **Alternatives considered**: Mantener `SheetsService` y agregar dual write a DB. Se descarta para no prolongar una dependencia operativa que el usuario quiere eliminar.

### ADR-002: Modelar gastos como entidad relacional propia

- **Status**: Accepted
- **Context**: La base actual tiene usuarios, grupos, metas y configuraciones, pero no existe una tabla de gastos para consultas transaccionales.
- **Decision**: Agregar una tabla `expenses` relacionada con `users`, con columnas suficientes para conservar la semantica actual de Sheets: fecha/hora, monto, moneda, descripcion, categoria, calculo, mensaje original, monto original y moneda original.
- **Consequences**: Se habilitan queries consistentes e indexables por usuario y fecha. A cambio, se incorpora una migracion de schema y una estrategia de ordenamiento estable para "ultimo gasto".
- **Alternatives considered**: Guardar un blob JSON de gastos por usuario en otra tabla. Se descarta por pobre capacidad de consulta y mantenimiento.

### ADR-003: Mantener Google Sheets solo como utilidad de importacion transitoria

- **Status**: Accepted
- **Context**: Existe historico operativo en planillas y no puede ignorarse la transicion, pero tampoco conviene que el runtime diario siga dependiendo de Google.
- **Decision**: Limitar `app/services/sheets.py` a lectura/importacion historica y sacar su inicializacion del camino critico de startup.
- **Consequences**: El deploy queda mas simple y alineado con Supabase. A cambio, la importacion historica debe tener una interfaz administrativa explicita y cobertura propia.
- **Alternatives considered**: Eliminar Sheets por completo en la misma iteracion. Se descarta porque deja sin plan de migracion el historico existente.

## Component Design

### Expense ORM model

**Responsabilidad**: representar un gasto persistido y su relacion con el usuario propietario.

**Interfaz publica**:
```python
class Expense(Base):
    id: Mapped[int]
    user_id: Mapped[int]
    spent_at: Mapped[datetime]
    amount: Mapped[float]
    currency: Mapped[str]
    description: Mapped[str]
    category: Mapped[str]
    calculation: Mapped[str | None]
    raw_message: Mapped[str]
    source: Mapped[str]
    original_amount: Mapped[float | None]
    original_currency: Mapped[str | None]
    created_at: Mapped[datetime]
```

**Dependencias**: `User`, Alembic, SQLAlchemy ORM.

### Expense service

**Responsabilidad**: encapsular escritura, lectura, agregados y borrado de gastos usando la DB como fuente de verdad.

**Interfaz publica**:
```python
class ExpenseService:
    async def ensure_user(self, phone: str) -> User: ...
    async def create_expense(self, phone: str, expense: ParsedExpense) -> dict: ...
    async def get_monthly_total(self, phone: str, month: int, year: int) -> float: ...
    async def get_category_totals(self, phone: str, month: int, year: int) -> dict[str, float]: ...
    async def get_recent_expenses(self, phone: str, limit: int = 10) -> list[dict]: ...
    async def search_expenses(
        self, phone: str, query: str | None = None, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict]: ...
    async def delete_last_expense(self, phone: str) -> dict | None: ...
```

**Dependencias**: `async_session_maker`, `User`, `Expense`, `ParsedExpense`.

### Sheets import utility

**Responsabilidad**: importar historico desde Google Sheets a la tabla `expenses` de forma controlada e idempotente o explicitamente segura ante reruns.

**Interfaz publica**:
```python
async def import_expenses_from_sheets(phone: str | None = None, dry_run: bool = False) -> ImportReport: ...
```

**Dependencias**: `SheetsService`, `ExpenseService`, base de datos, logging.

## Data Model

Se agrega una entidad relacional de gastos:

```python
class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spent_at: Mapped[datetime] = mapped_column(index=True)
    amount: Mapped[float]
    currency: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, default="General")
    calculation: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_message: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="agent")
    original_amount: Mapped[float | None] = mapped_column(nullable=True)
    original_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

Notas de modelado:
- `spent_at` captura la fecha/hora efectiva del gasto para preservar orden cronologico y agregados mensuales.
- Las queries de usuario deben filtrar siempre por `user_id`, nunca por telefono crudo sin resolver al usuario.
- Si la estrategia de importacion requiere idempotencia fuerte, puede agregarse una clave tecnica adicional en la migracion para registrar origen legacy.

## API Contract

Sin cambios en API publica. El cambio ocurre detras del webhook y las tools internas del agente.

## Error Handling

- Si la DB falla al guardar un gasto, la tool debe devolver un error controlado y no confirmar registro al usuario.
- Si la importacion desde Sheets encuentra filas invalidas, debe registrarlas y continuar con el resto del lote salvo corrupcion estructural.
- Si el usuario pide borrar el ultimo gasto y no tiene historial en DB, se responde con el mismo tipo de error funcional actual.

## Testing Strategy

- **Unit tests**: servicio de gastos DB, agregados mensuales, busqueda por texto/fecha, borrado del ultimo gasto y comportamiento sin Google Sheets.
- **Integration tests**: wiring del agente con `ToolRegistry`, creacion de usuario + gasto en DB y regresion de aislamiento por telefono.
- **E2E tests**: no requeridos para esta iteracion.

Referencia a scenarios de `1-functional/spec.md`:
- REQ-01 Scenario 01 y 02 se cubren con tests del servicio de gastos y del startup/runtime sin Sheets.
- REQ-02 Scenario 01 y 02 se cubren con tests de tools y del servicio sobre multiples usuarios.
- REQ-03 Scenario 01 y 02 se cubren con tests del importador y fixtures de planilla.

## Non-Functional Requirements

- **Performance**: consultas de recientes y resumen mensual deben resolverse con filtros/indexes por usuario y fecha, sin recorrer historicos completos en memoria.
- **Security**: toda query de gastos debe quedar acotada al `user_id` resuelto para el telefono autenticado.
- **Observability**: registrar altas fallidas, importaciones ejecutadas, filas omitidas y cantidad de registros migrados por usuario.

## Brownfield Annotations

<!-- extends: app/db/models.py -->
<!-- overrides: app/agent/tools.py -->
<!-- overrides: app/main.py -->
<!-- deprecates: app/services/sheets.py -->
