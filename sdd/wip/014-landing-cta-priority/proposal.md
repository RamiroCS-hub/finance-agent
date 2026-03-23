# Proposal: Landing CTA Priority

## Intent

La landing actual explica demasiado antes de pedir la acción principal, y el formulario queda enterrado al final de la página. El cambio busca acortar el recorrido, poner el acceso a la waitlist al inicio y dejar una historia más directa para convertir mejor sin rehacer el producto ni el backend.

## Scope

### In Scope
- Reordenar la landing para que el CTA principal y el formulario de waitlist estén en el primer bloque visible.
- Reducir la cantidad de secciones y condensar el contenido en menos bloques de valor/prueba.
- Mantener el flujo actual de waitlist con FormSubmit y un recorrido consistente entre navbar, hero y CTA secundarios.

### Out of Scope
- Cambios en el backend o en la persistencia de waitlist.
- Rebranding completo, rediseño del admin o reemplazo de assets/imágenes existentes.

## Approach

Se mantiene la landing estática en `frontend-claude/` y se resuelve con una rejerarquización de contenido, no con una migración de stack. La propuesta es convertir el hero en el punto de conversión principal, resumir promesas repetidas en menos módulos y ajustar estilos/JS solo lo necesario para que el CTA sea claro y funcione bien en desktop y mobile.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend-claude/index.html` | Modified | Reorganiza la estructura de la landing, mueve el formulario principal al inicio y recorta secciones. |
| `frontend-claude/styles.css` | Modified | Ajusta layout, jerarquía visual y responsive para una landing más compacta. |
| `frontend-claude/script.js` | Modified | Conserva el flujo de waitlist y mejora el comportamiento de CTA/anclas hacia el formulario principal. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Perder mensajes de producto valiosos por recortar demasiado | Med | Mantener solo claims respaldados por el producto actual y agrupar funciones relacionadas. |
| Romper el formulario al moverlo de sección | Med | Conservar IDs clave o adaptar el JS junto con smoke tests manuales. |
| Que el hero quede sobrecargado en mobile | Med | Diseñar una variante compacta con prioridad al formulario y revisar breakpoints existentes. |

## Rollback Plan

El cambio vive solo en archivos estáticos de `frontend-claude/`, así que se revierte con un rollback de git de esos tres archivos. No hay migraciones ni cambios persistentes del lado servidor.

## Dependencies

- Confirmar con el usuario el recorte de contenido y la prioridad del CTA antes de implementar.
- Ninguna dependencia externa adicional.

## Success Criteria

- [ ] El visitante ve el CTA principal y puede dejar su email sin scrollear hasta el final.
- [ ] La landing queda materialmente más corta, con menos bloques principales y menos repetición conceptual.
- [ ] El flujo de waitlist sigue funcionando con mensajes de éxito/error y navegación clara desde cualquier CTA.
