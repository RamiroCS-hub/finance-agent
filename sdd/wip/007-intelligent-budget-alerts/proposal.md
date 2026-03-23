# Proposal: Intelligent Budget Alerts

## Intent

Convertir al bot en un asistente proactivo capaz de avisar cuando el usuario se desvía de sus límites o patrones normales. Esa capacidad hoy está comunicada en la landing, pero el producto actual solo responde a pedidos explícitos y no conserva reglas de presupuesto ni modelos de anomalía.

## Scope

### In Scope
- Definir presupuestos por categoría o período.
- Detectar desvíos contra presupuesto y gastos anómalos contra histórico reciente.
- Entregar alertas conversacionales claras y accionables al usuario.

### Out of Scope
- Construir un motor avanzado de machine learning en esta primera iteración.
- Notificaciones fuera de WhatsApp.

## Approach

La primera versión puede operar con heurísticas robustas: límites declarados por el usuario y comparaciones contra medianas o promedios recientes por categoría. Con eso alcanza para una capa de inteligencia útil sin agregar complejidad estadística innecesaria.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/db/models.py` | Modified | Persistencia de presupuestos y reglas de alerta. |
| `app/agent/tools.py` | Modified | Tools para configurar y consultar presupuestos/alertas. |
| `app/services/` | New/Modified | Evaluación de desvíos y anomalías. |
| `app/agent/core.py` | Modified | Inyección de alertas relevantes en respuestas o mensajes proactivos. |
| `tests/` | Modified | Cobertura de reglas de presupuesto y detección básica. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Alertas demasiado ruidosas o poco relevantes | Med | Ajustar umbrales y permitir configuración por usuario. |
| Falta de datos históricos suficientes para anomalías | High | Usar fallbacks simples y degradar a presupuesto explícito. |
| La proactividad por WhatsApp se percibe invasiva | Low | Empezar con alertas dentro del flujo conversacional y opt-in. |

## Rollback Plan

Mantener la lógica de alertas encapsulada en un servicio nuevo. Si la calidad es baja, se revierte el feature y el resto del registro/consulta de gastos permanece intacto.

## Dependencies

- Modelo persistente para presupuestos por usuario.
- Definición de frecuencia y canal exacto para alertas.

## Success Criteria

- [ ] El usuario puede definir presupuestos y recibir alertas de desvío.
- [ ] El sistema detecta al menos anomalías básicas contra el histórico reciente.
- [ ] Las alertas son configurables y están cubiertas por tests.
