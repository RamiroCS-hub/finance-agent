# Functional Spec: Financial Education Coach

**Feature**: `011-financial-education-coach`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature agrega una capa de educacion financiera personalizada basada en el historial real del usuario. El sistema puede evaluar reglas como 50/30/20, estimar fondo de emergencia, ajustar comparativas por inflacion y generar micro-tips accionables.

El valor diferencial no esta en respuestas genericas, sino en reglas explicables sobre datos concretos del usuario. La feature debe evitar parecer asesoramiento profesional y mantener un tono practico.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Pide lecturas educativas y recomendaciones sobre sus finanzas. |
| Bot de WhatsApp | Calcula benchmarks y genera tips personalizados. |

## Requirements

### REQ-01: Benchmarks financieros sobre historico real

El sistema SHOULD evaluar reglas como 50/30/20 y fondo de emergencia usando el historial del usuario.

#### Scenarios

**Scenario 01: Evaluacion 50/30/20**
```text
Given un usuario con suficiente historial categorizado
When pregunta como estan sus finanzas
Then el sistema muestra una lectura comparada contra el benchmark 50/30/20
```

**Scenario 02: Fondo de emergencia**
```text
Given un usuario con historico mensual suficiente
When pregunta cuanto necesita de fondo de emergencia
Then el sistema estima un rango basado en su nivel de gasto real
```

### REQ-02: Comparativas ajustadas por inflacion

El sistema MAY comparar periodos ajustando el valor real de los gastos por un indice configurable.

#### Scenarios

**Scenario 01: Ajuste por inflacion disponible**
```text
Given un indice de referencia configurado
When el usuario compara sus gastos entre meses
Then el sistema puede distinguir crecimiento nominal de crecimiento real
```

**Scenario 02: Sin indice disponible**
```text
Given que no hay una fuente de inflacion configurada
When el usuario pide esa comparativa
Then el sistema informa la limitacion o degrada a una comparativa nominal
```

### REQ-03: Tips personalizados y accionables

El sistema MUST poder generar tips breves basados en patrones reales del usuario.

#### Scenarios

**Scenario 01: Hallazgo accionable**
```text
Given un patron de gasto repetitivo y claro
When el sistema genera una recomendacion
Then produce un tip corto con impacto economico estimado
```

**Scenario 02: Sin patron suficiente**
```text
Given un historial sin señales fuertes
When el sistema intenta generar tips
Then evita recomendaciones artificiales y responde con honestidad
```

## Out of Scope

- Asesoramiento financiero regulado.
- Modelos macroeconomicos avanzados mas alla de un ajuste simple.
