# Proposal: Financial Education Coach

## Intent

Hacer que el producto no solo registre gastos sino que enseñe y acompañe con benchmarks financieros útiles y personalizados. La landing promete ese rol educativo, pero el backend actual no modela reglas, inflación, fondo de emergencia ni generación de tips accionables.

## Scope

### In Scope
- Evaluaciones conversacionales como 50/30/20 y fondo de emergencia basadas en el historial.
- Comparativas temporales con ajuste por inflación cuando haya fuente de referencia definida.
- Generación de tips breves y personalizados a partir de patrones reales de gasto.

### Out of Scope
- Asesoramiento financiero regulado o personalizado a nivel profesional.
- Modelos macroeconómicos complejos más allá del ajuste simple por índice elegido.

## Approach

La feature se resuelve como una capa educativa sobre el histórico del usuario: reglas conocidas, benchmarks configurables e insights explicables. El valor está en que cada consejo se ancle a datos concretos del usuario y no en respuestas genéricas del LLM.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/agent/tools.py` | Modified | Tools de evaluación educativa y tips. |
| `app/services/sheets.py` | Modified | Agregaciones y breakdowns adicionales. |
| `app/services/` | New/Modified | Reglas 50/30/20, fondo de emergencia, inflación y tips. |
| `app/config.py` | Modified | Configuración de fuente o índice de inflación si aplica. |
| `tests/` | Modified | Casos de benchmark, cálculos y recomendaciones. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Consejos demasiado genéricos o poco confiables | Med | Basarlos en reglas determinísticas y datos explícitos. |
| Dependencia de datos externos para inflación | Med | Empezar con una fuente configurable y fallback sin ajuste. |
| Confusión entre educación y recomendación financiera formal | Low | Mantener copy claro y no prescriptivo. |

## Rollback Plan

Al ser una capa adicional, se revierte sin tocar el registro central de gastos. Si se agregan fuentes externas de inflación, se apagan por configuración y se vuelve a consultas descriptivas.

## Dependencies

- Definición del índice o fuente de inflación a usar.
- Criterios de benchmark iniciales para 50/30/20 y fondo de emergencia.

## Success Criteria

- [ ] El usuario puede pedir una lectura educativa de sus finanzas y recibir métricas basadas en sus datos.
- [ ] El sistema cubre al menos 50/30/20, fondo de emergencia y tips personalizados.
- [ ] La lógica determinística queda testeada y explicable.
