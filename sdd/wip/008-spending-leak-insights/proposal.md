# Proposal: Spending Leak Insights

## Intent

Ayudar al usuario a entender en qué rubros o patrones se le está yendo la plata, más allá del mero registro. La landing promete comparativas y hallazgos accionables, pero el backend actual solo expone consultas descriptivas básicas sin capa analítica de insights.

## Scope

### In Scope
- Comparativas semanales y mensuales por categoría, comercio o patrón repetido.
- Detección de gastos recurrentes potencialmente prescindibles.
- Respuestas de insight accionables con foco en ahorro potencial.

### Out of Scope
- Dashboards visuales fuera de WhatsApp.
- Clasificación perfecta de suscripciones o merchants en la primera versión.

## Approach

La base es explotar el histórico ya registrado para derivar comparativas y señales simples: subas sostenidas, merchants repetidos, frecuencia de uso y concentración por categoría. El resultado debe consumirse conversacionalmente desde el agente, no como un dashboard separado.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/sheets.py` | Modified | Queries históricas adicionales y agregaciones. |
| `app/agent/tools.py` | Modified | Nuevas tools de insights y comparativas. |
| `app/services/` | New/Modified | Motor analítico para fugas y patrones repetidos. |
| `tests/` | Modified | Casos de comparativas y detección de patrones. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Datos sucios o categorías inconsistentes reducen calidad del insight | Med | Normalización incremental y mensajes con nivel de confianza implícito. |
| Falsos positivos sobre suscripciones o fugas | Med | Empezar con reglas simples y ejemplos claros de criterio. |
| Cálculos costosos sobre Google Sheets | Med | Cachear o mover agregados críticos a storage relacional si hace falta. |

## Rollback Plan

Al ser una capa analítica adicional, el rollback consiste en revertir las tools y servicios nuevos sin afectar el registro base de gastos.

## Dependencies

- Acceso consistente al histórico de gastos por usuario.
- Criterios iniciales para definir gasto repetitivo, comparativa y ahorro potencial.

## Success Criteria

- [ ] El usuario puede pedir insights y recibir comparativas claras entre períodos.
- [ ] El sistema detecta al menos un conjunto inicial de fugas o gastos repetitivos potencialmente evitables.
- [ ] La lógica queda cubierta con tests determinísticos.
