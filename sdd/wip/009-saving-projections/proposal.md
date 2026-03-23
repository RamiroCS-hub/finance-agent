# Proposal: Saving Projections

## Intent

Dar respuestas prospectivas y no solo descriptivas, estimando cuánto podría ahorrar el usuario si cambia ciertos hábitos. Ese tipo de consejo cuantificado hoy aparece en la web, pero no existe en el producto operativo.

## Scope

### In Scope
- Proyección de ahorro a partir de recortes simples por categoría o hábito.
- Simulaciones mensuales y semestrales basadas en gasto histórico.
- Integración con metas para mostrar impacto esperado sobre objetivos.

### Out of Scope
- Predicciones financieras complejas o dependientes de variables macroeconómicas.
- Modelos probabilísticos avanzados en la primera versión.

## Approach

La feature se apoya en un modelo determinístico simple: partir del gasto observado, aplicar escenarios declarados por el usuario o sugeridos por heurísticas y proyectar su acumulación a lo largo del tiempo. Es suficiente para una primera experiencia útil y explicable.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/agent/tools.py` | Modified | Nueva tool de proyección/simulación. |
| `app/services/sheets.py` | Modified | Consultas históricas por categoría y período. |
| `app/services/` | New/Modified | Servicio de simulación de ahorro. |
| `app/services/goals.py` | Modified | Cruce opcional con metas activas. |
| `tests/` | Modified | Escenarios de proyección reproducibles. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Proyecciones percibidas como demasiado especulativas | Med | Mantenerlas explicables y basadas en supuestos visibles. |
| Datos históricos insuficientes | High | Degradar a simulaciones manuales ingresadas por el usuario. |
| Solapamiento con metas o insights ya existentes | Low | Delimitar claramente que esta feature simula escenarios futuros. |

## Rollback Plan

Revertir la tool y el servicio de simulación sin tocar los datos registrados ni las metas existentes.

## Dependencies

- Historial de gastos suficiente o inputs explícitos del usuario para simular.
- Definición de horizonte temporal soportado en la primera versión.

## Success Criteria

- [ ] El usuario puede pedir una proyección y recibir una estimación basada en datos o supuestos explícitos.
- [ ] Las proyecciones pueden vincularse con una meta activa cuando exista.
- [ ] La lógica de simulación está cubierta con tests determinísticos.
