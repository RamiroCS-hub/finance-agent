# Functional Spec: Saving Projections

**Feature**: `009-saving-projections`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature permite proyectar cuanto podria ahorrar el usuario si reduce determinados gastos o habitos. La idea es responder preguntas prospectivas del tipo "si gasto menos en delivery" o "si ahorro X por semana" usando datos historicos o supuestos explicitos.

Las proyecciones deben ser transparentes respecto de sus supuestos. Si faltan datos, el sistema debe degradar a una simulacion manual en vez de dar una prediccion falsa.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Pide simulaciones y proyecciones de ahorro. |
| Bot de WhatsApp | Calcula escenarios y los relaciona con metas existentes. |

## Requirements

### REQ-01: Simulaciones sobre gasto historico

El sistema SHOULD poder proyectar ahorro a partir de recortes sobre categorias o patrones observados.

#### Scenarios

**Scenario 01: Escenario basado en historico**
```text
Given un usuario con historial suficiente en una categoria
When pide estimar cuanto ahorraria reduciendo ese gasto
Then el sistema devuelve una proyeccion para un horizonte definido
```

**Scenario 02: Historial insuficiente**
```text
Given un usuario sin base suficiente en esa categoria
When pide una proyeccion
Then el sistema informa la limitacion o solicita un supuesto manual
```

### REQ-02: Escenarios manuales explicitos

El sistema MUST soportar simulaciones con supuestos ingresados por el usuario aunque no haya historial suficiente.

#### Scenarios

**Scenario 01: Usuario define su propio supuesto**
```text
Given un usuario que indica un monto y una frecuencia de ahorro deseada
When pide una simulacion
Then el sistema calcula la acumulacion esperada para el horizonte solicitado
```

**Scenario 02: Supuesto ambiguo**
```text
Given un pedido sin monto, frecuencia u horizonte claros
When el sistema intenta simular
Then solicita la informacion faltante antes de proyectar
```

### REQ-03: Relacion con metas

El sistema MAY vincular una proyeccion con una meta activa para mostrar impacto estimado sobre su cumplimiento.

#### Scenarios

**Scenario 01: Meta activa relacionada**
```text
Given un usuario con una meta activa
When recibe una proyeccion de ahorro
Then el sistema puede informar en cuanto acercaria ese escenario a la meta
```

**Scenario 02: Sin meta activa**
```text
Given un usuario sin metas vigentes
When pide una proyeccion
Then el sistema responde la simulacion sin depender de una meta existente
```

## Out of Scope

- Predicciones macroeconomicas complejas.
- Modelos probabilisticos avanzados.
