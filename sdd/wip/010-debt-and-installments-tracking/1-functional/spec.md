# Functional Spec: Debt and Installments Tracking

**Feature**: `010-debt-and-installments-tracking`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature permite registrar compras en cuotas y otras deudas para que el usuario entienda su presupuesto comprometido futuro. El producto deja de ver solo gastos ejecutados y pasa a modelar obligaciones pendientes.

La primera version se enfoca en cuotas fijas y deudas simples. La respuesta al usuario debe distinguir claramente entre gasto ya realizado y compromiso futuro.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Registra deudas o compras en cuotas y consulta pendientes. |
| Bot de WhatsApp | Persist e interpreta compromisos futuros en el contexto financiero. |

## Requirements

### REQ-01: Registro de cuotas y deudas simples

El sistema MUST permitir registrar compras en cuotas y deudas basicas con monto, periodicidad y saldo pendiente.

#### Scenarios

**Scenario 01: Compra en cuotas**
```text
Given un usuario que realiza una compra financiada
When informa monto por cuota y cantidad restante
Then el sistema guarda el compromiso futuro correspondiente
```

**Scenario 02: Dato incompleto**
```text
Given un pedido para registrar una deuda sin informacion minima suficiente
When el agente intenta procesarlo
Then solicita la informacion faltante antes de persistir
```

### REQ-02: Consulta de compromiso mensual

El sistema SHOULD mostrar cuanto tiene comprometido el usuario en meses futuros por cuotas o deudas activas.

#### Scenarios

**Scenario 01: Consultar mes actual**
```text
Given un usuario con cuotas pendientes
When pregunta su compromiso fijo del mes
Then el sistema devuelve el total comprometido y su desglose
```

**Scenario 02: Sin compromisos activos**
```text
Given un usuario sin cuotas ni deudas pendientes
When pregunta su compromiso futuro
Then el sistema responde que no hay obligaciones registradas
```

### REQ-03: Ciclo de vida de obligaciones

El sistema MAY permitir marcar cuotas como pagadas o completar una deuda para dejar de contarlas en los resumenes.

#### Scenarios

**Scenario 01: Cuota o deuda completada**
```text
Given una obligacion con saldo o cuotas restantes
When el usuario la completa o la cancela
Then el sistema deja de incluirla en compromisos futuros
```

**Scenario 02: Edicion invalida**
```text
Given una obligacion inexistente o ya cerrada
When el usuario intenta modificarla
Then el sistema rechaza la operacion con un mensaje claro
```

## Out of Scope

- Integraciones con bancos o tarjetas.
- Tasas variables y amortizaciones complejas.
