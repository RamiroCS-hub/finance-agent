# Functional Spec: DB Expense Storage

**Feature**: `012-db-expense-storage`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature reemplaza Google Sheets como almacenamiento operativo de gastos para que el bot registre y consulte movimientos directamente en la base de datos. Desde la perspectiva del usuario de WhatsApp, el comportamiento esperado no cambia: sigue pudiendo registrar gastos, pedir resúmenes, buscar historial y borrar el último movimiento, pero ahora esos datos viven en un backend relacional controlado por la aplicación.

Adicionalmente, la transición debe contemplar que ya existe histórico en planillas. El sistema no puede mezclar gastos entre teléfonos y debe ofrecer una forma segura de pasar el historial previo a la nueva fuente de verdad sin depender de Google Sheets para la operación cotidiana.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Persona que registra y consulta sus gastos desde una conversación privada con el bot. |
| Operador del sistema | Persona que despliega la aplicación y ejecuta la transición del storage o la importación histórica. |
| Base de datos del producto | Fuente de verdad para usuarios, gastos y configuraciones del bot. |

## Requirements

### REQ-01: Persistencia operativa de gastos en base de datos

El sistema MUST registrar los gastos nuevos en la base de datos y MUST poder operar aunque Google Sheets no esté configurado.

#### Scenarios

**Scenario 01: Registro exitoso de gasto sin Google Sheets**
```text
Given un usuario envia un gasto valido por WhatsApp
When el agente decide registrarlo y la aplicacion no tiene credenciales de Google configuradas
Then el sistema guarda el gasto en la base de datos y responde con una confirmacion exitosa
```

**Scenario 02: Consulta posterior sobre el gasto recien creado**
```text
Given un gasto fue registrado correctamente en la base de datos
When el usuario pide ver sus gastos recientes o un resumen
Then el sistema devuelve informacion construida desde la base de datos que incluye ese gasto
```

### REQ-02: Consultas y borrado consistentes sobre historial por telefono

Las consultas de resumen, busqueda, recientes y borrado MUST resolverse sobre el historial almacenado en DB y MUST mantenerse aisladas por telefono.

#### Scenarios

**Scenario 01: Resumen y busqueda del usuario autenticado**
```text
Given un usuario tiene varios gastos guardados en la base de datos
When solicita un resumen mensual o busca un gasto por texto o fecha
Then el sistema responde usando solo los gastos asociados a su telefono
```

**Scenario 02: Borrado del ultimo gasto del usuario**
```text
Given un usuario tiene al menos un gasto guardado en la base de datos
When pide borrar el ultimo gasto
Then el sistema elimina solo el gasto mas reciente de ese usuario y confirma la accion
```

### REQ-03: Transicion controlada desde Google Sheets

El sistema SHOULD ofrecer un mecanismo seguro para importar historial desde Google Sheets hacia DB sin mezclar datos entre usuarios ni duplicar informacion silenciosamente.

#### Scenarios

**Scenario 01: Importacion historica por usuario**
```text
Given existe una planilla con gastos historicos asociados a un telefono
When el operador ejecuta la importacion hacia la base de datos
Then los movimientos quedan asociados al usuario correcto en DB y disponibles para las consultas del bot
```

**Scenario 02: Reejecucion o filas invalidas en la importacion**
```text
Given la importacion se vuelve a ejecutar o encuentra filas mal formadas
When el proceso analiza el historico
Then el sistema evita duplicados silenciosos o reporta claramente los registros omitidos sin abortar toda la corrida
```

## Brownfield Annotations

<!-- extends: sdd/wip/001-finance-org-wpp-reverse-eng/1-functional/spec.md#REQ-03 -->
<!-- deprecates: sdd/wip/001-finance-org-wpp-reverse-eng/1-functional/spec.md#REQ-04 -->

## Out of Scope

- Soporte funcional completo para gastos compartidos o grupos.
- Exportacion continua a Google Sheets una vez que DB sea la fuente de verdad.
- Nuevas interfaces fuera de WhatsApp para visualizar el historial.
