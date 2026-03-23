# Functional Spec: Spending Leak Insights

**Feature**: `008-spending-leak-insights`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature agrega insights para detectar donde se esta yendo la plata del usuario, con comparativas entre periodos y senales de gastos repetitivos o potencialmente prescindibles. El objetivo es traducir el historial de gastos en observaciones accionables.

Los insights deben ser explicables y anclados en datos concretos del usuario. No se busca una clasificacion perfecta de suscripciones desde el dia uno, sino una primera capa util de lectura automatica.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Consulta insights y comparativas sobre sus gastos. |
| Bot de WhatsApp | Analiza historico y responde con hallazgos concretos. |

## Requirements

### REQ-01: Comparativas entre periodos

El sistema MUST permitir comparar gasto por categoria o patron entre periodos recientes.

#### Scenarios

**Scenario 01: Comparativa mensual**
```text
Given un usuario con gastos en varios meses
When pide una comparativa de categorias
Then el sistema muestra subas y bajas relevantes entre periodos
```

**Scenario 02: Sin datos suficientes**
```text
Given un usuario con poco historico
When solicita una comparativa
Then el sistema informa que faltan datos en lugar de inventar una conclusion
```

### REQ-02: Deteccion de patrones repetitivos

El sistema SHOULD identificar merchants o descripciones repetidas que sugieran fugas o gastos evitables.

#### Scenarios

**Scenario 01: Patron repetitivo claro**
```text
Given un usuario con muchos gastos similares en un merchant o rubro
When solicita insights
Then el sistema destaca ese patron y su impacto acumulado
```

**Scenario 02: Patron poco concluyente**
```text
Given datos ambiguos o descripciones inconsistentes
When el motor analiza el historico
Then evita marcar un patron fuerte sin suficiente evidencia
```

### REQ-03: Respuesta accionable

Los insights MUST entregarse como sugerencias claras y no como un dump de datos crudos.

#### Scenarios

**Scenario 01: Insight util**
```text
Given un hallazgo relevante en el historial
When el sistema responde
Then entrega una conclusion breve con impacto economico estimado
```

**Scenario 02: Sin hallazgos fuertes**
```text
Given un historial sin señales claras
When el usuario pide insights
Then el sistema responde honestamente sin forzar recomendaciones artificiales
```

## Out of Scope

- Dashboards visuales fuera de WhatsApp.
- Clasificacion perfecta y automatica de todas las suscripciones.
