# Functional Spec: Telegram Channel Connection

**Feature**: 017-telegram-channel-connection
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature agrega Telegram como segundo canal conversacional del producto, además de WhatsApp. La primera entrega se concentra en chats privados de texto usando Telegram Bot API, con la misma expectativa funcional básica: el usuario escribe al asistente, recibe respuesta y puede operar sus finanzas sin depender de que exista un número de WhatsApp detrás.

Como el sistema actual todavía modela usuarios, memoria y varios servicios con claves específicas de WhatsApp, la feature también define el comportamiento esperado de una identidad multi-canal. El usuario no debería ver cruces de sesiones entre Telegram y WhatsApp, ni respuestas inconsistentes por diferencias internas de transporte.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de Telegram | Persona que conversa con el bot desde un chat privado de Telegram. |
| Usuario de WhatsApp existente | Persona que ya usa el producto por WhatsApp y no debe sufrir regresiones por la nueva integración. |
| Operador del sistema | Persona que configura secrets, webhook y monitorea los canales activos. |
| Telegram Bot API | Plataforma que entrega updates y transporta respuestas del bot. |

## Requirements

### REQ-01: Ingreso privado de texto por Telegram

El sistema MUST aceptar updates válidos de Telegram para chats privados de texto y enrutarlos al mismo asistente conversacional del producto. Los updates no soportados o fuera de alcance MUST NOT disparar procesamiento del agente.

#### Scenarios

**Scenario 01: Mensaje privado válido**
```text
Given un usuario envía un mensaje de texto desde un chat privado de Telegram
When el webhook de Telegram recibe un update válido con la configuración activa
Then el sistema procesa el mensaje con el asistente y genera una respuesta para ese mismo chat
```

**Scenario 02: Update fuera de alcance**
```text
Given llega un update de Telegram que corresponde a un grupo, canal o tipo de mensaje no soportado
When el sistema evalúa el payload entrante
Then el update se descarta de forma segura sin invocar al asistente
```

### REQ-02: Respuesta por el mismo canal de origen

Las respuestas iniciadas desde Telegram MUST volver por Telegram y conservar el contexto de ese chat. Un fallo de entrega SHOULD quedar registrado operativamente sin provocar reenvíos duplicados ni mezclar el estado de la conversación.

#### Scenarios

**Scenario 01: Respuesta normal al usuario**
```text
Given un mensaje de Telegram fue aceptado para procesamiento
When el asistente genera una respuesta final
Then el sistema envía esa respuesta al mismo chat privado de Telegram
```

**Scenario 02: Falla del proveedor saliente**
```text
Given el asistente generó una respuesta pero Telegram rechaza o falla la entrega
When el backend intenta enviar el mensaje saliente
Then el sistema registra el error con contexto técnico suficiente y evita producir una segunda respuesta espuria al mismo update
```

### REQ-03: Identidad y sesión aisladas por canal

El sistema MUST resolver la identidad de un usuario usando el canal y el identificador externo de ese canal. Las sesiones, replies y memoria conversacional MUST permanecer separadas entre Telegram y WhatsApp aunque los identificadores crudos coincidan.

#### Scenarios

**Scenario 01: Reutilización de sesión en Telegram**
```text
Given un usuario de Telegram ya interactuó previamente con el bot
When vuelve a escribir dentro del mismo chat privado antes de que expire su sesión
Then el sistema reutiliza su contexto conversacional correcto de Telegram
```

**Scenario 02: No mezclar canales**
```text
Given existe un usuario de WhatsApp cuyo identificador numérico coincide con el chat o user id de un usuario de Telegram
When ambos canales interactúan con el sistema
Then el estado, la memoria y las respuestas se mantienen aislados por canal y no se cruzan entre sí
```

### REQ-04: Compatibilidad funcional para usuarios sin teléfono

El producto MUST seguir permitiendo operaciones financieras básicas a usuarios de Telegram aunque su identidad primaria no sea un número telefónico. Cuando una regla dependa de datos no disponibles en Telegram, el sistema MUST aplicar un default explícito o rechazar la operación de manera comprensible.

#### Scenarios

**Scenario 01: Operación financiera privada desde Telegram**
```text
Given un usuario de Telegram conversa en privado con el bot
When registra o consulta información financiera soportada por el producto actual
Then el sistema completa la operación usando una identidad interna válida sin requerir un número de WhatsApp
```

**Scenario 02: Regla dependiente de teléfono no disponible**
```text
Given una operación necesita inferencias que antes dependían del prefijo telefónico
When el usuario solo existe en Telegram
Then el sistema usa un default configurado o informa claramente la limitación sin romper la conversación
```

### REQ-05: Activación segura y no intrusiva de Telegram

Telegram MUST funcionar como una capacidad opt-in. Si la configuración requerida no está presente o el update falla autenticidad suficiente, el sistema MUST rechazar ese tráfico sin degradar el canal de WhatsApp ya existente.

#### Scenarios

**Scenario 01: Telegram deshabilitado**
```text
Given el despliegue no tiene configurados los secretos mínimos de Telegram
When llega tráfico al webhook del nuevo canal
Then el sistema lo rechaza o lo deja inactivo de forma explícita sin afectar el webhook de WhatsApp
```

**Scenario 02: Update con autenticidad inválida**
```text
Given llega un request al webhook de Telegram con secreto inválido o faltante
When el backend valida el request
Then el sistema rechaza el update y no procesa mensajes del payload
```

## Brownfield Annotations

<!-- extends: sdd/wip/005-whatsapp-group-expenses-and-goals/1-functional/spec.md -->
<!-- extends: sdd/wip/015-whatsapp-number-rate-limit/1-functional/spec.md -->
<!-- extends: sdd/wip/016-webhook-hardening-and-privacy-controls/1-functional/spec.md#REQ-01 -->

## Out of Scope

- Soporte de grupos, supergrupos o canales de Telegram.
- Audio, OCR, imágenes, documentos y automatizaciones ricas específicas de Telegram.
- Unificación explícita de una misma persona entre WhatsApp y Telegram.
- Flujos de crecimiento o marketing para publicar el nuevo canal en landing o legal pages.
