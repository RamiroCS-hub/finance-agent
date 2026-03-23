# Proposal: WhatsApp Group Expenses and Goals

## Intent

Permitir que el bot viva de verdad dentro de grupos y no solo como un filtro superficial por `@`. El objetivo es que un grupo tenga identidad propia, ledger compartido, liquidación entre miembros y metas comunes, alineando el producto con la funcionalidad pedida y con lo que ya comunica la landing.

## Scope

### In Scope
- Detectar y persistir correctamente el contexto de grupo y sus miembros desde el webhook.
- Registrar gastos compartidos dentro del grupo, incluyendo repartos y balances entre participantes.
- Crear, consultar y actualizar metas compartidas del grupo desde el chat grupal y desde el privado cuando corresponda.

### Out of Scope
- Resolver en esta iteración pagos reales o transferencias fuera de WhatsApp.
- Diseñar un panel web de administración de grupos.

## Approach

La implementación debe partir de un cambio de modelo: dejar de tratar un mensaje grupal como si fuera un gasto privado del remitente. Sobre esa base se suman herramientas y reglas de dominio para asignar aportes, calcular saldos netos y sincronizar metas compartidas con el historial grupal.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/api/webhook.py` | Modified | Capturar entidad grupal y mención configurable del bot. |
| `app/agent/core.py` | Modified | Propagar contexto privado vs grupal al agente. |
| `app/agent/tools.py` | Modified | Nuevas tools para gastos compartidos, balances, liquidación y metas. |
| `app/db/models.py` | Modified | Ampliar modelo relacional de grupos, miembros y movimientos compartidos. |
| `app/services/goals.py` | Modified | Metas compartidas con progreso real por grupo. |
| `tests/` | Modified | Cobertura end-to-end de flujos grupales. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Mezclar gastos privados con grupales por no propagar bien el contexto | High | Introducir una entidad de contexto explícita y tests por cada tipo de chat. |
| Reglas de reparto y liquidación generan resultados inconsistentes | Med | Definir invariantes claros y testear escenarios de varios miembros. |
| La fuente de verdad actual en Google Sheets no alcanza para el modelo grupal | Med | Evaluar persistencia híbrida o migración selectiva para los movimientos de grupo. |

## Rollback Plan

Encapsular el soporte grupal detrás de nuevas rutas de dominio y feature flags lógicos. Si el flujo grupal falla, se puede revertir a la lógica privada actual sin tocar los registros privados existentes.

## Dependencies

- Confirmar cómo llega el identificador de grupo en el payload real de Meta.
- Definir persistencia canónica para balances y liquidaciones grupales.

## Success Criteria

- [ ] Un grupo puede invocar al bot con mención y registrar gastos compartidos contra el contexto correcto.
- [ ] El sistema calcula balances y liquidaciones mínimas entre integrantes.
- [ ] Las metas grupales se crean y actualizan desde el flujo conversacional.
