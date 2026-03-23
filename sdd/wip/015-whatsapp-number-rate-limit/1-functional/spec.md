# Functional Spec: WhatsApp Number Rate Limit

**Feature**: 015-whatsapp-number-rate-limit
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature agrega un freno operativo por número de WhatsApp para evitar que un mismo remitente dispare demasiados mensajes en un intervalo corto. El objetivo es proteger el webhook y los flujos costosos del bot sin cambiar la identidad del usuario ni el contrato externo con Meta.

El límite se aplica sobre mensajes entrantes que el sistema sí procesaría. Cuando el remitente supera el cupo, el mensaje deja de recorrer el pipeline principal y el sistema mantiene una respuesta estable hacia Meta.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Envía mensajes al bot desde su número. |
| Webhook del bot | Recibe eventos válidos y decide si procesa o limita por número. |
| Redis | Guarda el estado compartido del rate limit entre requests e instancias. |

## Requirements

### REQ-01: Límite por número antes del procesamiento pesado

El sistema MUST evaluar un cupo configurable por número de WhatsApp antes de encolar OCR, transcripción o procesamiento del agente.

#### Scenarios

**Scenario 01: Mensaje dentro del límite**
```text
Given un número de WhatsApp con tráfico por debajo del umbral configurado
When llega un mensaje soportado al webhook
Then el sistema permite el procesamiento normal y encola la tarea de background
```

**Scenario 02: Mensaje por encima del límite**
```text
Given un número de WhatsApp que ya consumió su cupo en la ventana activa
When llega un nuevo mensaje soportado al webhook
Then el sistema no encola procesamiento pesado para ese mensaje
```

### REQ-02: Scope consistente por número remitente

El rate limit MUST usar como clave el número remitente autenticado por el webhook y SHOULD aplicar de forma consistente sin importar si el mensaje es privado o grupal.

#### Scenarios

**Scenario 01: Mismo remitente en contextos distintos**
```text
Given un mismo número envía mensajes privados y en grupos donde el bot fue mencionado
When el webhook evalúa el rate limit
Then ambos mensajes consumen el mismo presupuesto asociado a ese número
```

**Scenario 02: Mensajes no procesables**
```text
Given un evento que el sistema igual descartaría por tipo no soportado o por grupo sin mención
When el webhook lo recibe
Then ese evento no consume cupo del rate limiter
```

### REQ-03: Degradación segura y comunicación mínima

Si la infraestructura del rate limit falla, el sistema SHOULD seguir operativo. Cuando un número queda limitado, el sistema MAY avisar al usuario, pero MUST evitar notificaciones repetitivas dentro de la misma ventana de enfriamiento.

#### Scenarios

**Scenario 01: Redis no disponible**
```text
Given el backend del rate limiter no puede responder
When llega un mensaje válido al webhook
Then el sistema continúa procesando el mensaje y registra el incidente en logs
```

**Scenario 02: Usuario excedido repetidamente**
```text
Given un número que sigue enviando mensajes mientras está limitado
When cada nuevo mensaje vuelve a ser bloqueado
Then el sistema evita mandar la misma advertencia en cada intento durante el cooldown configurado
```

## Brownfield Annotations

<!-- extends: sdd/wip/004-phone-scope-security-hardening/1-functional/spec.md#REQ-01 -->
<!-- extends: sdd/wip/005-whatsapp-group-expenses-and-goals/1-functional/spec.md#REQ-01 -->

## Out of Scope

- Penalizaciones permanentes, listas negras o bloqueo administrativo.
- Cuotas diferenciadas por tipo de plan o por operación interna.
