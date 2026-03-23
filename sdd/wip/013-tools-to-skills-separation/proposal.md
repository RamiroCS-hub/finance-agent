# Proposal: Tools To Skills Separation

## Intent

Reducir el acoplamiento creciente del `ToolRegistry` actual separando las tools en skills o módulos de dominio reutilizables. El sistema ya tiene herramientas de gastos, grupos, OCR, insights, presupuestos y proyecciones; mantener todo en un único archivo vuelve más costoso agregar features y testearlas.

## Scope

### In Scope
- Definir una arquitectura de skills/módulos para agrupar tools por dominio.
- Mantener compatibilidad con el contrato actual que consume el `LLMProvider`.
- Permitir que el agente componga skills sin romper aislamiento por teléfono o grupo.

### Out of Scope
- Cambiar el comportamiento funcional de las tools existentes.
- Reescribir el agente o el proveedor LLM completo.

## Approach

Extraer las tools en skills con una interfaz común de definiciones y handlers. `ToolRegistry` pasa a ser un compositor liviano que junta skills concretas como `ExpenseSkill`, `BudgetSkill`, `GroupSkill`, `InsightSkill` y `UtilitySkill`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/agent/tools.py` | Modified | Deja de ser un monolito y pasa a componer skills. |
| `app/agent/` | New/Modified | Nuevos módulos de skills y helpers compartidos. |
| `app/models/agent.py` | Possible | Interfaces o tipos auxiliares para skills. |
| `tests/` | Modified | Cobertura por skill y por composición final. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Romper contratos de tools ya usadas por el LLM | Med | Mantener nombres, schemas y outputs estables durante el refactor. |
| Duplicar dependencias o estado entre skills | Med | Definir un contexto común inyectado por el registry compositor. |
| Refactor grande con regresiones en features ya cerradas | High | Ejecutar por etapas y con cobertura fuerte de `tests/test_tools.py` y `tests/test_agent.py`. |

## Rollback Plan

Revertir la composición por skills y volver temporalmente al `ToolRegistry` monolítico sin tocar servicios de negocio.

## Dependencies

- Estado actual estable de las tools existentes.
- Definición clara de límites por dominio.

## Success Criteria

- [ ] Las tools quedan separadas por dominio en skills coherentes.
- [ ] `ToolRegistry` pasa a ser un compositor chico y testeable.
- [ ] La suite actual del agente y tools sigue verde tras el refactor.
