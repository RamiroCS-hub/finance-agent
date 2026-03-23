# Functional Spec: Landing CTA Priority

**Feature**: 014-landing-cta-priority
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature redefine la landing pública para que el visitante entienda rápido qué resuelve Anotamelo y tenga la acción principal disponible desde el primer pantallazo. En vez de pedir que el usuario recorra una página larga antes de anotarse, la experiencia debe priorizar conversión temprana y una narrativa más corta.

La nueva landing no cambia el producto ni el mecanismo de waitlist. Cambia la jerarquía: primero valor y registro, después prueba y contexto. El objetivo es que la página diga menos, pero mejor.

## Actors

| Actor | Description |
|-------|-------------|
| Visitante nuevo | Persona que llega por primera vez y necesita entender el valor del producto en segundos. |
| Interesado en la beta | Persona que ya entendió la propuesta y quiere dejar su email para conseguir acceso. |

## Requirements

### REQ-01: Conversión principal en el primer bloque

La landing MUST mostrar la propuesta de valor principal y la acción de registro dentro del primer bloque visible, sin depender de que el visitante navegue hasta el final para unirse a la waitlist.

#### Scenarios

**Scenario 01: CTA visible al cargar la página**
```text
Given un visitante entra a la landing desde desktop o mobile
When la página termina de cargar
Then el primer bloque visible muestra el beneficio principal y una acción clara para unirse a la waitlist
```

**Scenario 02: Registro accesible desde el inicio**
```text
Given un visitante decide registrarse apenas entiende la propuesta
When interactúa con el CTA principal del hero
Then puede completar el flujo de waitlist sin bajar hasta una sección lejana
```

### REQ-02: Narrativa más corta y menos repetitiva

La landing MUST condensar la propuesta comercial en menos bloques principales y SHOULD evitar repetir capacidades parecidas en secciones separadas.

#### Scenarios

**Scenario 01: Recorrido breve**
```text
Given un visitante recorre la landing de arriba hacia abajo
When evalúa rápidamente si el producto le interesa
Then encuentra una historia corta con pocos bloques principales y no una secuencia extensa de secciones largas
```

**Scenario 02: Capacidades agrupadas**
```text
Given el visitante quiere entender qué puede hacer el producto
When lee la landing compacta
Then ve funciones relacionadas agrupadas en resúmenes claros en lugar de múltiples bloques redundantes
```

### REQ-03: CTA consistente en toda la página

Todos los CTA de la landing MUST apuntar a la misma acción principal de registro y MUST mantener feedback claro de éxito o error durante el envío del email.

#### Scenarios

**Scenario 01: CTA secundarios reusan la acción principal**
```text
Given un visitante hace click en un CTA de la navbar o de una sección posterior
When el sitio lo redirige a la acción de registro
Then llega al mismo punto principal de waitlist sin encontrarse con recorridos alternativos confusos
```

**Scenario 02: Validación visible**
```text
Given un visitante ingresa un email inválido o falla el envío
When intenta unirse a la waitlist
Then la landing muestra un mensaje claro de error en el mismo flujo principal
```

## Brownfield Annotations

<!-- extends: frontend-claude/index.html#hero -->
<!-- overrides: frontend-claude/index.html#waitlist -->

## Out of Scope

- Cambios en el mecanismo de envío a FormSubmit.
- Nuevas integraciones de analytics o CRM.
- Cambios de copy para promesas no respaldadas por el producto actual.
