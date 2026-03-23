## Design Document

**Feature**: 014-landing-cta-priority
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

La solución mantiene el sitio estático actual y trabaja sobre tres piezas: estructura HTML, estilos CSS y comportamiento mínimo en JavaScript. El cambio principal es jerárquico: el formulario de waitlist pasa al hero para convertirse en el punto de conversión primario, mientras el resto del contenido se compacta en menos secciones con mayor densidad informativa.

No se introduce un segundo flujo de captura ni un nuevo backend. La página sigue usando una sola fuente de verdad para el alta a la waitlist, con el mismo endpoint de FormSubmit y el mismo feedback de éxito/error, pero reubicado en el recorrido principal.

```text
[Visitor]
   -> [Navbar CTA / Hero CTA]
   -> [Primary waitlist form in hero]
   -> [FormSubmit endpoint]
   -> [Inline success/error feedback]
```

### ADRs

#### ADR-001: Mantener la landing como frontend estático vanilla

- **Context**: El sitio vive en `frontend-claude/` sin framework, build step ni backend propio.
- **Decision**: Resolver el recorte y la priorización del CTA editando `index.html`, `styles.css` y `script.js` sin migrar a otro stack.
- **Consequences**: El cambio es rápido de implementar y fácil de revertir, pero obliga a cuidar manualmente responsive, anchors y estados del formulario.
- **Alternatives considered**: Rehacer la landing con framework o componentes. Se descarta porque aumenta costo y no resuelve un problema de conversión/copy que hoy es principalmente estructural.

#### ADR-002: Usar un único formulario principal ubicado en el hero

- **Context**: El JS actual asume un solo formulario con IDs fijos y hoy ese formulario está al final de la página.
- **Decision**: Mover el formulario principal al primer bloque y hacer que los demás CTA redirijan a ese mismo punto en vez de duplicar formularios.
- **Consequences**: Se simplifica el mantenimiento y se evita sincronizar múltiples estados de éxito/error. El hero requiere más cuidado visual para no quedar saturado.
- **Alternatives considered**: Duplicar el formulario en hero y footer. Se descarta porque complica el JS y multiplica estados inconsistentes.

#### ADR-003: Compactar el contenido en tres capas narrativas

- **Context**: La landing actual distribuye funciones, impacto, educación, grupos, pasos y demo en demasiados bloques separados.
- **Decision**: Reorganizar el contenido en una secuencia más corta: hero con conversión, bloque resumido de capacidades/prueba y cierre breve de confianza o recordatorio.
- **Consequences**: Mejora el foco y acorta el scroll, pero exige seleccionar mejor qué claims sobreviven.
- **Alternatives considered**: Mantener todas las secciones y solo agregar un botón arriba. Se descarta porque deja intacto el exceso de contenido que el usuario ya identificó como problema.

### Component Design

#### Landing structure

**Responsabilidad**: Ordenar el contenido para que el valor y el registro aparezcan primero.

**Interfaz pública**:
```html
<nav>...</nav>
<section class="hero">...</section>
<section class="proof">...</section>
<section class="closing-cta">...</section>
```

**Dependencias**: `frontend-claude/styles.css`, `frontend-claude/script.js`, assets existentes.

**Invariantes**:
- El CTA principal aparece en el primer viewport.
- La landing completa es más corta que la versión actual.
- Los claims visibles siguen alineados con capacidades ya presentes o planeadas del producto.

#### Waitlist form controller

**Responsabilidad**: Validar email, enviar a FormSubmit y renderizar feedback inline.

**Interfaz pública**:
```javascript
function initWaitlistForm() {}
function submitToWaitlist(email) {}
```

**Dependencias**: DOM con `waitlist-form`, `email-input`, `waitlist-success`, `waitlist-error`.

**Invariantes**:
- Solo existe un flujo primario de envío.
- El usuario ve error o éxito sin cambiar de página.
- Los CTA con hash llevan al mismo punto de conversión.

### Data Model Changes

Sin cambios en modelo de datos.

### API Contract

Sin cambios en API pública propia. Se conserva el `POST` actual al endpoint externo de FormSubmit.

### Testing Strategy

**Unit tests**:
- No hay runner frontend configurado para esta landing estática.

**Integration tests**:
- Smoke test manual en desktop y mobile para CTA, navegación y feedback del formulario.

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | manual | El CTA y el formulario principal se ven al cargar. |
| REQ-01 Scenario 02 | manual | El visitante puede iniciar el alta sin llegar al footer. |
| REQ-02 Scenario 01 | manual | La landing quedó recortada y con menos bloques. |
| REQ-02 Scenario 02 | manual | Las capacidades aparecen agrupadas y sin redundancia marcada. |
| REQ-03 Scenario 01 | manual | Navbar y CTA secundarios llevan al mismo formulario. |
| REQ-03 Scenario 02 | manual | Los estados de error y éxito siguen visibles en el flujo principal. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Hero demasiado cargado en mobile | Med | High | Reducir copy y limitar elementos simultáneos arriba del fold. |
| Rotura del JS por cambios de markup | Med | Med | Mantener IDs existentes o adaptar selectores con smoke tests inmediatos. |
| Pérdida de claims valiosos al recortar | Med | Med | Priorizar capacidades diferenciadoras y dejar el resto fuera de esta iteración. |

### Notes for sdd-spec-writer

La spec técnica debe reflejar explícitamente que se reutiliza un único formulario principal y que no hay cambios de backend. Conviene enfatizar en `Error Handling` y `Testing Strategy` que la validación será manual porque esta landing no tiene harness de tests.
