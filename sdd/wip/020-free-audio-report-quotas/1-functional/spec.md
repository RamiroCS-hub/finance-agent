# Functional Spec: Free Audio and Report Quotas

**Feature**: 020-free-audio-report-quotas
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature redefine parcialmente el contrato entre `FREE` y `PREMIUM`. El objetivo es que `FREE` tenga acceso acotado a audio y reportes con reglas claras y persistentes, mientras `PREMIUM` conserve acceso ilimitado. En concreto, cada usuario `FREE` puede procesar hasta 5 audios por semana y recibir hasta 3 reportes PDF por mes.

Las cuotas deben sobrevivir reinicios, funcionar igual en WhatsApp y Telegram para audio, y respetar el calendario local del usuario. También deben ser justas: si el sistema falla al descargar, transcribir o enviar un reporte, no debe “quemar” un cupo. `PREMIUM` no debe quedar alcanzado por esta nueva limitación.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario FREE | Persona que puede usar audio y reportes, pero con cuotas semanales/mensuales. |
| Usuario PREMIUM | Persona que debe mantener acceso ilimitado a audio y reportes. |
| Backend FastAPI | Servicio que valida plan, registra consumo y responde al usuario. |
| Base PostgreSQL | Persistencia del uso de cuotas para sobrevivir reinicios y múltiples réplicas. |

## Requirements

### REQ-01: Cuota semanal de audio para FREE

El sistema MUST permitir hasta 5 audios procesados exitosamente por semana calendario para cada usuario FREE. El sexto intento dentro de la misma semana local MUST bloquearse con un mensaje claro y no iniciar procesamiento pesado adicional. El sistema MUST dejar a `PREMIUM` sin límite para esta capacidad.

#### Scenarios

**Scenario 01: Audio free dentro del cupo semanal**
```text
Given un usuario FREE lleva menos de 5 audios procesados en su semana local actual
When envía un audio válido por un canal soportado
Then el sistema permite procesarlo y el consumo queda registrado contra su cuota semanal de audio
```

**Scenario 02: Audio free con cupo agotado**
```text
Given un usuario FREE ya consumió 5 audios en su semana local actual
When intenta enviar otro audio
Then el sistema rechaza el audio con un mensaje de límite semanal agotado y no ejecuta transcripción
```

**Scenario 03: Audio fallido no consume cuota**
```text
Given un usuario FREE todavía tiene cupo semanal de audio
When el audio falla al descargarse o transcribirse
Then el sistema informa el error pero no registra consumo de cuota
```

**Scenario 04: PREMIUM no tiene tope semanal**
```text
Given un usuario PREMIUM
When envía audios válidos dentro de semanas sucesivas o dentro de la misma semana
Then el sistema no aplica esta cuota semanal de audio
```

### REQ-02: Cuota mensual de reportes para FREE

El sistema MUST permitir hasta 3 reportes PDF enviados exitosamente por mes calendario para cada usuario FREE. El cuarto intento dentro del mismo mes local MUST bloquearse con un mensaje claro. El sistema MUST dejar a `PREMIUM` sin límite para esta capacidad.

#### Scenarios

**Scenario 01: Reporte free dentro del cupo mensual**
```text
Given un usuario FREE lleva menos de 3 reportes enviados en su mes local actual
When solicita un reporte PDF válido por el flujo soportado
Then el sistema genera y envía el reporte y registra ese consumo en su cuota mensual
```

**Scenario 02: Reporte free con cupo agotado**
```text
Given un usuario FREE ya recibió 3 reportes PDF en su mes local actual
When solicita un nuevo reporte
Then el sistema rechaza la operación con un mensaje de límite mensual agotado y no genera un PDF nuevo
```

**Scenario 03: Reporte fallido no consume cuota**
```text
Given un usuario FREE todavía tiene cupo mensual de reportes
When la generación o el envío del PDF falla
Then el sistema informa el error sin descontar un reporte de su cuota mensual
```

**Scenario 04: PREMIUM no tiene tope mensual**
```text
Given un usuario PREMIUM
When solicita reportes PDF válidos
Then el sistema no aplica esta cuota mensual de reportes
```

### REQ-03: Ventanas calendario basadas en timezone del usuario

El sistema MUST calcular la cuota semanal y mensual usando la timezone efectiva del usuario. La semana MUST interpretarse como semana calendario local y el reporte MUST resetear por mes calendario local.

#### Scenarios

**Scenario 01: Reset semanal local**
```text
Given un usuario FREE agotó su cuota de audio al final de una semana local
When comienza una nueva semana calendario en su timezone
Then el sistema vuelve a permitir hasta 5 audios para esa nueva ventana
```

**Scenario 02: Reset mensual local**
```text
Given un usuario FREE agotó su cuota de reportes al final de un mes local
When comienza un nuevo mes calendario en su timezone
Then el sistema vuelve a permitir hasta 3 reportes para esa nueva ventana
```

### REQ-04: Persistencia e idempotencia pragmática del consumo

El sistema MUST persistir los consumos de cuota en base de datos. Para audio, cuando exista un identificador fuente estable del mensaje entrante, el sistema SHOULD evitar contabilizar dos veces el mismo audio si el provider reintenta la entrega.

#### Scenarios

**Scenario 01: Persistencia survive restart**
```text
Given un usuario FREE ya consumió parte de su cuota
When el proceso del backend se reinicia
Then la cuota restante del usuario sigue reflejando los consumos previos
```

**Scenario 02: Retry del mismo audio no duplica consumo**
```text
Given el provider reintenta el mismo mensaje de audio con el mismo identificador fuente
When el sistema vuelve a evaluar el consumo
Then la cuota de audio no se incrementa por segunda vez
```

### REQ-05: Mensajes de límite claros y específicos

El sistema MUST informar de forma clara si el límite alcanzado es semanal de audio o mensual de reportes. El mensaje SHOULD orientar al usuario sin mezclarlo con errores técnicos de descarga o de proveedor.

#### Scenarios

**Scenario 01: Mensaje de límite de audio**
```text
Given un usuario FREE agotó su cuota semanal de audio
When intenta enviar un nuevo audio
Then recibe un mensaje explícito indicando que alcanzó el máximo semanal de audios
```

**Scenario 02: Mensaje de límite de reportes**
```text
Given un usuario FREE agotó su cuota mensual de reportes
When solicita otro reporte PDF
Then recibe un mensaje explícito indicando que alcanzó el máximo mensual de reportes
```

### REQ-06: Compatibilidad brownfield sin regresión funcional

La nueva lógica de cuotas MUST aplicarse solo a `audio` y `generate_expense_report`, manteniendo `PREMIUM` ilimitado y sin alterar otros tipos de media. El sistema SHOULD preservar la limitación actual de reportes en Telegram sin consumir cuota de reportes allí.

#### Scenarios

**Scenario 01: PREMIUM sigue ilimitado**
```text
Given un usuario PREMIUM
When envía texto, audio o imagen según el comportamiento actual
Then el sistema conserva acceso sin cuota nueva para audio y reportes, además del comportamiento actual para el resto de media
```

**Scenario 02: Telegram sin reportes no consume cupo**
```text
Given un usuario de Telegram solicita un reporte PDF
When el canal sigue sin soportar envío de reportes
Then el sistema devuelve el mensaje actual de limitación de canal y no descuenta cuota mensual de reportes
```

## Brownfield Annotations

<!-- extends: sdd/wip/017-telegram-channel-connection/1-functional/spec.md -->
<!-- extends: sdd/wip/018-telegram-audio-image-processing/1-functional/spec.md -->
<!-- extends: sdd/wip/016-webhook-hardening-and-privacy-controls/1-functional/spec.md -->

## Out of Scope

- Límites nuevos para imágenes, documentos o texto.
- Reportes PDF enviados por Telegram.
- Un panel para consultar consumo restante desde el producto.
- Cuotas compartidas entre usuarios o entre grupos.
