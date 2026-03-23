# Proposal: Docs Consolidation and SDD Merge

## Intent

Ordenar la documentación para reducir contradicciones y hacer que el equipo tenga una sola fuente confiable de trabajo. Hoy `openspec/` y `sdd/` compiten por ese rol, y además el README y `docs/` no reflejan con claridad qué es estado actual, qué es roadmap y qué es deuda.

## Scope

### In Scope
- Diseñar una estructura documental final bajo `docs/` y `sdd/`.
- Migrar o resumir el contenido útil de `openspec/` dentro de `sdd/` o `docs/` según corresponda.
- Marcar `sdd/` como única fuente viva para features y decisiones futuras.

### Out of Scope
- Reescribir cada documento histórico en profundidad si alcanza con archivarlo o enlazarlo.
- Cambiar el comportamiento del producto más allá de lo necesario para reflejar la realidad actual.

## Approach

La refactorización documental va a clasificar primero cada documento existente como setup, estado actual, histórico o roadmap. Luego se moverá el contenido aprovechable a ubicaciones canónicas y se dejarán redirecciones o notas de archivo para no perder trazabilidad.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `README.md` | Modified | Reducirlo a entrada principal y enlaces canónicos. |
| `docs/` | Modified | Centralizar setup, operación y despliegue. |
| `openspec/` | Modified | Archivar o migrar contenido útil hacia `sdd/`/`docs/`. |
| `sdd/` | Modified | Consolidar planificación viva y reverse engineering. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Perder contexto histórico al mover archivos | Med | Dejar referencias de archivo y migración explícitas. |
| Mezclar documentación aspiracional con comportamiento real | High | Basarse en código y tests como fuente primaria para el estado actual. |
| Romper enlaces o hábitos existentes del equipo | Low | Mantener README como punto de entrada y agregar notas de transición. |

## Rollback Plan

Los movimientos documentales pueden revertirse íntegramente por git. Si la nueva estructura genera confusión, se restaura la jerarquía previa y se preservan los nuevos documentos como borrador fuera de la ruta principal.

## Dependencies

- Inventario de documentos existentes y criterio explícito de qué queda como histórico versus vivo.
- Aprobación del esquema final de carpetas.

## Success Criteria

- [ ] `sdd/` queda definido como fuente única de trabajo para features activas.
- [ ] `openspec/` deja de ser una fuente paralela de verdad.
- [ ] La documentación operativa y de onboarding queda agrupada y navegable.
