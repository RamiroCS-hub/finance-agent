# Functional Spec: WhatsApp Group Expenses and Goals

**Feature**: `005-whatsapp-group-expenses-and-goals`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature permite que Anotamelo opere de forma real dentro de grupos de WhatsApp. Un grupo pasa a ser una entidad conversacional propia: el bot puede ser mencionado, registrar gastos compartidos, calcular balances entre miembros y mantener metas grupales separadas del historial privado de cada participante.

Tambien se habilita una experiencia cruzada entre privado y grupo para consultar el estado de grupos asociados. La funcionalidad debe preservar la claridad del contexto para que un gasto privado no termine contaminando un balance grupal y viceversa.

## Actors

| Actor | Description |
|-------|-------------|
| Miembro de grupo | Participa de un grupo de WhatsApp y registra gastos compartidos. |
| Administrador del grupo | Crea o gestiona el espacio compartido y sus metas. |
| Bot de WhatsApp | Interpreta menciones, registra movimientos y devuelve balances. |

## Requirements

### REQ-01: Identidad real de grupo y activacion por mencion

El sistema MUST reconocer el contexto de grupo como una entidad distinta y SHALL procesar solo mensajes grupales dirigidos al bot.

#### Scenarios

**Scenario 01: Grupo menciona al bot**
```text
Given un mensaje enviado en un grupo de WhatsApp
When incluye la mencion configurada del bot
Then el sistema procesa el pedido dentro del contexto del grupo correspondiente
```

**Scenario 02: Grupo sin mencion**
```text
Given un mensaje grupal no dirigido al bot
When el webhook lo recibe
Then el sistema lo ignora sin registrar gastos ni invocar al agente
```

### REQ-02: Registro de gastos compartidos y balances

El sistema MUST registrar gastos asociados al grupo y SHOULD calcular balances entre integrantes y liquidaciones minimas.

#### Scenarios

**Scenario 01: Miembro registra un gasto grupal**
```text
Given un grupo con miembros conocidos
When una persona menciona al bot con un gasto compartido
Then el sistema guarda el aporte en el ledger del grupo y confirma quien puso el dinero
```

**Scenario 02: Grupo pide balance**
```text
Given un grupo con multiples gastos compartidos
When alguien pide el balance o la liquidacion
Then el sistema responde cuanto puso cada integrante, cuanto le deben o debe, y las transferencias minimas sugeridas
```

### REQ-03: Metas compartidas y consulta cruzada

El sistema MUST permitir metas grupales y MAY exponer su estado desde el grupo o desde el chat privado de un miembro autorizado.

#### Scenarios

**Scenario 01: Grupo crea o actualiza una meta**
```text
Given un grupo activo
When un miembro autorizado crea una meta compartida o registra un movimiento relevante
Then el progreso de la meta del grupo se actualiza dentro de ese contexto
```

**Scenario 02: Miembro consulta sus grupos en privado**
```text
Given un usuario que participa en uno o mas grupos
When pregunta desde su chat privado por el estado de sus grupos
Then el sistema devuelve solo los grupos a los que pertenece y sus metas activas
```

## Brownfield Annotations

<!-- overrides: sdd/wip/001-finance-org-wpp-reverse-eng/1-functional/spec.md#REQ-02 -->
<!-- extends: sdd/wip/001-finance-org-wpp-reverse-eng/1-functional/spec.md#REQ-08 -->

## Out of Scope

- Integraciones de pago o transferencias reales entre miembros.
- Panel web administrativo para grupos.
