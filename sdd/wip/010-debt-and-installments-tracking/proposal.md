# Proposal: Debt and Installments Tracking

## Intent

Permitir que el usuario vea el impacto futuro de compras financiadas y otras deudas dentro de su presupuesto. Hoy el sistema solo captura gastos corrientes y pierde de vista compromisos ya adquiridos, lo que deja incumplida una promesa importante de la landing.

## Scope

### In Scope
- Registrar compras en cuotas con cantidad, monto por cuota y calendario restante.
- Consultar compromisos mensuales futuros y totales pendientes.
- Incorporar deudas simples al contexto de análisis y resumen.

### Out of Scope
- Integración bancaria o scraping de tarjetas.
- Amortizaciones complejas o tasas variables en la primera versión.

## Approach

La feature requiere un dominio separado del gasto puntual: obligaciones futuras con estado y vencimientos. A partir de ese modelo, el agente puede responder preguntas de presupuesto comprometido y reflejar cuotas activas en resúmenes mensuales.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/db/models.py` | Modified | Nuevas entidades para cuotas y deudas. |
| `app/agent/tools.py` | Modified | Tools para registrar y consultar compromisos. |
| `app/services/` | New/Modified | Servicio de calendario de cuotas y agregados mensuales. |
| `tests/` | Modified | Casos de cuotas pendientes, cierre y resumen. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Modelo insuficiente para distintos tipos de deuda | Med | Empezar con un alcance explícito y extensible. |
| Resúmenes mezclan mal gastos realizados con compromisos futuros | High | Mantener conceptos separados en la respuesta y en la persistencia. |
| Alta carga manual para el usuario | Med | Diseñar comandos conversacionales cortos y defaults razonables. |

## Rollback Plan

Como se trata de un dominio nuevo, se puede revertir el feature completo sin afectar el historial de gastos existente. Si hay migraciones nuevas, se revierten junto con el código.

## Dependencies

- Definición del modelo mínimo de deuda/cuota soportado.
- Persistencia relacional para compromisos futuros.

## Success Criteria

- [ ] El usuario puede registrar compras en cuotas y consultar cuánto tiene comprometido por mes.
- [ ] Los resúmenes distinguen entre gasto ejecutado y obligación futura.
- [ ] El ciclo de vida de cuotas pendientes queda cubierto por tests.
