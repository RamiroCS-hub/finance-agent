# Functional Spec: Intelligent Budget Alerts

**Feature**: `007-intelligent-budget-alerts`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature convierte al bot en un asistente proactivo capaz de avisar cuando el usuario se desvía de sus presupuestos o cuando un gasto luce anomalo respecto de su historial. El objetivo es pasar de una experiencia puramente reactiva a una que tambien advierta riesgos y excesos.

La primera version prioriza reglas simples y comprensibles: presupuestos por categoria y comparacion contra historicos recientes. El usuario debe poder entender por que recibio una alerta.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Define presupuestos y recibe alertas o avisos. |
| Bot de WhatsApp | Evalua desvíos y comunica alertas accionables. |

## Requirements

### REQ-01: Presupuestos configurables por categoria

El sistema MUST permitir definir y consultar presupuestos por categoria o periodo.

#### Scenarios

**Scenario 01: Crear presupuesto**
```text
Given un usuario sin presupuesto configurado para una categoria
When define un limite de gasto
Then el sistema guarda la regla y la recuerda para futuras evaluaciones
```

**Scenario 02: Consultar presupuesto vigente**
```text
Given un usuario con presupuestos activos
When pregunta por sus limites
Then el sistema devuelve las reglas vigentes de forma clara
```

### REQ-02: Alertas por desvio de presupuesto

El sistema SHOULD alertar cuando el gasto acumulado supera o amenaza con superar un presupuesto configurado.

#### Scenarios

**Scenario 01: Presupuesto superado**
```text
Given un presupuesto vigente para una categoria
When el gasto acumulado supera ese limite
Then el sistema emite una alerta explicando el desvio
```

**Scenario 02: Presupuesto todavia valido**
```text
Given un presupuesto vigente
When el gasto acumulado sigue por debajo del limite
Then el sistema no genera una alerta incorrecta
```

### REQ-03: Deteccion de gasto anomalo

El sistema MAY detectar gastos anormalmente altos respecto del historico reciente del usuario.

#### Scenarios

**Scenario 01: Gasto por encima del patron**
```text
Given un usuario con historial suficiente
When registra un gasto muy por encima de su promedio reciente
Then el sistema le avisa que detecto una anomalia
```

**Scenario 02: Datos insuficientes**
```text
Given un usuario sin historial suficiente
When registra un gasto nuevo
Then el sistema evita afirmar una anomalia sin base
```

## Out of Scope

- Modelos avanzados de machine learning.
- Notificaciones fuera de WhatsApp en la primera version.
