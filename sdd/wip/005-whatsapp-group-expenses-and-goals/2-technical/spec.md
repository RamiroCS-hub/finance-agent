# Technical Spec: WhatsApp Group Expenses and Goals

**Feature**: `005-whatsapp-group-expenses-and-goals`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La feature introduce un contexto grupal de primera clase. El flujo de webhook debe identificar chats de grupo, resolver miembros y propagar esa identidad al agente. El agente, a su vez, usa tools especificas para registrar aportes, calcular balances y operar metas compartidas sin mezclar datos privados con grupales.

```text
Webhook -> group context resolver -> AgentLoop
                                -> Group tool set
                                -> relational DB for group state
                                -> optional Sheets/private storage bridge
```

El ledger compartido y las metas grupales deben vivir en persistencia relacional, porque el modelo excede lo que hoy resulta natural en una hoja por telefono.

## Architecture Decision Records

### ADR-001: El contexto grupal se resuelve antes de invocar al agente

- **Status**: Accepted
- **Context**: Hoy el grupo se detecta tarde y se degrada al telefono del remitente.
- **Decision**: Resolver identidad de grupo, actor y mencion en el borde del webhook.
- **Consequences**: El agente recibe contexto limpio y coherente. A cambio, hay que cambiar la interfaz del flujo principal.
- **Alternatives considered**: Seguir parseando grupos dentro del prompt del LLM.

### ADR-002: El ledger grupal vive en la base relacional

- **Status**: Accepted
- **Context**: Balances, aportes y liquidaciones requieren joins y consistencia transaccional.
- **Decision**: Persistir gastos compartidos, splits y settlements en PostgreSQL.
- **Consequences**: Los calculos se vuelven auditables y consistentes. A cambio, se agrega modelo de datos nuevo.
- **Alternatives considered**: Reutilizar Google Sheets por grupo. Se descarta por complejidad de consultas y reglas de balance.

### ADR-003: Las metas grupales comparten motor con metas individuales pero con owner explicito

- **Status**: Accepted
- **Context**: Ya existe logica parcial de metas, pero sin contexto grupal completo.
- **Decision**: Extender el servicio de metas para aceptar un owner de tipo grupo o usuario y actualizar progreso segun el flujo correspondiente.
- **Consequences**: Se reutiliza logica existente. A cambio, el servicio necesita abstraer mejor su contexto.
- **Alternatives considered**: Implementar un servicio de metas totalmente separado para grupos.

## Component Design

### Group context resolver

**Responsabilidad**: extraer identidad de grupo, actor y texto limpio desde el payload.

**Interfaz publica**:
```python
def resolve_group_context(message: dict) -> dict: ...
```

**Dependencias**: webhook payload, settings, parser de menciones.

### Group expense service

**Responsabilidad**: registrar aportes, splits y calcular balances del grupo.

**Interfaz publica**:
```python
async def register_group_expense(...) -> dict: ...
async def get_group_balance(group_id: str) -> dict: ...
async def settle_group(group_id: str) -> dict: ...
```

**Dependencias**: AsyncSession, modelos de grupo y gastos compartidos.

### Shared goals service

**Responsabilidad**: crear, consultar y actualizar metas compartidas por grupo.

**Interfaz publica**:
```python
async def create_group_goal(...) -> dict: ...
async def update_group_goal_progress(...) -> dict: ...
```

**Dependencias**: modelos `Goal`, `Group`, `GroupMember`.

## Data Model

```python
class GroupExpense(Base):
    id: int
    group_id: int
    payer_user_id: int
    amount: float
    description: str
    category: str
    created_at: datetime

class GroupExpenseShare(Base):
    id: int
    expense_id: int
    user_id: int
    share_amount: float
```

Se mantienen `Group`, `GroupMember` y `Goal`, pero sus relaciones deben ampliarse para soportar ledger y calculo de balances.

## API Contract

Sin cambios en API publica HTTP mas alla de ampliar el comportamiento de `POST /webhook`.

## Error Handling

- Mensajes grupales sin contexto suficiente o sin miembros resueltos deben responder con errores conversacionales claros.
- Fallas de balance o consistencia transaccional deben loguearse y no dejar el grupo en estado parcial.
- Las consultas privadas sobre grupos deben rechazar grupos ajenos al usuario.

## Testing Strategy

- **Unit tests**: parser de contexto grupal, balanceador y settlement minimizer.
- **Integration tests**: persistencia de gastos compartidos, metas grupales y consultas cruzadas.
- **E2E tests**: webhook grupal con y sin mencion.

Cada scenario funcional debe mapearse a tests especificos sobre contexto de grupo, registro y consulta.

## Non-Functional Requirements

- **Performance**: el calculo de balance debe responder en tiempo razonable para grupos pequenos y medianos.
- **Security**: un usuario no debe consultar balances de grupos a los que no pertenece.
- **Observability**: logs de resolucion de grupo, registro de aportes y generacion de liquidaciones.

## Brownfield Annotations

<!-- overrides: app/api/webhook.py -->
<!-- extends: app/services/goals.py -->
<!-- extends: app/db/models.py -->
