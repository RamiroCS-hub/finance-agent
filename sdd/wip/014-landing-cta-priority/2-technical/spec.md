# Technical Spec: Landing CTA Priority

**Feature**: 014-landing-cta-priority
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La solución modifica la landing estática existente en `frontend-claude/` sin introducir framework ni backend nuevo. El flujo queda centrado en un único formulario de waitlist reubicado en el hero, mientras la estructura HTML se reduce a menos secciones y los estilos se ajustan para sostener una jerarquía visual más compacta y orientada a conversión.

El flujo principal queda así:

```text
Navbar CTA / Hero CTA / CTA secundarios
                ->
       Formulario principal en hero
                ->
         Validación client-side básica
                ->
       POST a FormSubmit + feedback inline
```

## Architecture Decision Records

### ADR-001: Mantener el stack estático actual

- **Status**: Accepted
- **Context**: `frontend-claude/` está desplegado como sitio estático y no tiene build step ni framework de UI.
- **Decision**: Implementar el cambio solo con HTML, CSS y JavaScript vanilla.
- **Consequences**: Menor costo y riesgo de entrega; responsive y comportamiento quedan a cargo de CSS/JS manuales.
- **Alternatives considered**: Migrar a un framework de frontend. Se descarta por desproporcionado para un cambio de estructura y copy.

### ADR-002: Unificar la conversión en un solo formulario principal

- **Status**: Accepted
- **Context**: El código actual maneja un único formulario con IDs específicos y el usuario quiere que el CTA principal quede al principio.
- **Decision**: Mover el formulario principal al hero y hacer que todos los CTA apunten a ese mismo punto.
- **Consequences**: Se evita duplicidad de lógica y estados; el hero debe simplificarse para absorber el formulario sin ruido.
- **Alternatives considered**: Duplicar formularios en varias secciones. Se descarta por complejidad innecesaria y riesgo de inconsistencias.

### ADR-003: Compactar la landing en pocos módulos de alto impacto

- **Status**: Accepted
- **Context**: La landing actual separa demasiadas promesas en bloques largos, lo que retrasa la conversión.
- **Decision**: Consolidar contenido en pocos módulos: hero con conversión, prueba/capacidades resumidas y cierre breve.
- **Consequences**: Mejor foco y menor scroll; algunos detalles pasan a segundo plano o salen de esta iteración.
- **Alternatives considered**: Mantener todas las secciones y solo mover botones. Se descarta porque no resuelve la longitud excesiva.

## Component Design

### `frontend-claude/index.html`

**Responsabilidad**: Definir una estructura más corta con CTA principal arriba y menos bloques narrativos.

**Interfaz pública**:
```html
<nav class="navbar">...</nav>
<section class="hero">...</section>
<section class="proof">...</section>
<section class="closing-cta">...</section>
```

**Dependencias**: `styles.css`, `script.js`, `logo.png`.

### `frontend-claude/styles.css`

**Responsabilidad**: Soportar la nueva jerarquía visual y responsive de una landing más breve.

**Interfaz pública**:
```css
.hero
.hero-form
.proof-grid
.closing-cta
```

**Dependencias**: Clases definidas en `index.html`.

### `frontend-claude/script.js`

**Responsabilidad**: Mantener el envío de waitlist, la validación y la navegación hacia el formulario principal.

**Interfaz pública**:
```javascript
function initWaitlistForm() {}
function initSmoothScroll() {}
function initMobileMenu() {}
```

**Dependencias**: IDs del formulario y anchors internos del documento.

## Data Model

Sin cambios en modelo de datos.

## API Contract

Sin cambios en API pública. Se mantiene la integración existente con FormSubmit:

```text
POST https://formsubmit.co/ajax/ramirocarnicersouble8@gmail.com
```

## Error Handling

- Si el email es inválido, el formulario MUST mostrar un mensaje inline y no disparar el envío.
- Si FormSubmit responde con error o `success = false`, el flujo MUST mostrar el mensaje en `waitlist-error`.
- Si el alta es exitosa, el formulario MUST ocultarse y mostrarse el bloque `waitlist-success`.
- Los CTA con hash MUST seguir funcionando aunque el formulario cambie de ubicación dentro del documento.

## Testing Strategy

- **Unit tests**: no hay runner automatizado configurado para esta landing estática.
- **Integration tests**: smoke tests manuales sobre navegación, validación y envío del formulario.
- **E2E tests**: no aplica en esta iteración.

Mapeo a scenarios de `1-functional/spec.md`:

- **REQ-01 Scenario 01**: revisar en desktop y mobile que el CTA y el formulario se vean al cargar.
- **REQ-01 Scenario 02**: confirmar que el registro puede iniciarse desde el hero sin scrollear al footer.
- **REQ-02 Scenario 01**: validar que la página tenga menos bloques principales que la versión actual.
- **REQ-02 Scenario 02**: revisar que las funciones aparezcan agrupadas y sin repetición evidente.
- **REQ-03 Scenario 01**: clickear CTA de navbar y CTA secundarios para confirmar que llevan al mismo formulario.
- **REQ-03 Scenario 02**: probar email inválido y revisar feedback de error.

## Non-Functional Requirements

- **Performance**: Mantener assets y JS livianos; no introducir librerías nuevas.
- **Security**: No exponer datos adicionales del usuario ni cambiar el endpoint externo actual.
- **Observability**: Mantener compatibilidad con Vercel Insights ya cargado en la página.

## Brownfield Annotations

<!-- extends: frontend-claude/script.js#initWaitlistForm -->
<!-- overrides: frontend-claude/index.html#waitlist -->
