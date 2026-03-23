# Functional Spec: Webhook Hardening and Privacy Controls

**Feature**: 016-webhook-hardening-and-privacy-controls
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature endurece el borde de seguridad del bot de WhatsApp en cuatro puntos donde hoy todavía existe riesgo real: requests entrantes que pueden degradar a webhook sin firma, configuración persistente grupal que se puede mutar sin autoridad verificable, logs que exponen más información de la necesaria y media que entra al pipeline sin suficientes controles previos.

La meta no es rediseñar identidad ni permisos del producto. La meta es reducir superficie de abuso, fuga de datos y costo innecesario con reglas simples y seguras por defecto. La experiencia legítima debe seguir siendo fluida para chats privados normales y para mensajes multimodales dentro de la política permitida.

## Actors

| Actor | Description |
|-------|-------------|
| Meta WhatsApp Cloud API | Origen legítimo de eventos hacia el webhook del producto. |
| Usuario legítimo | Persona que usa el bot en chat privado o grupal para registrar y consultar finanzas. |
| Operador del sistema | Persona que necesita logs útiles para operar el servicio sin ver datos sensibles innecesarios. |
| Actor no confiable | Tercero o miembro no autorizado que intenta forzar requests, mutar configuración compartida o disparar procesamiento caro. |

## Requirements

### REQ-01: Autenticidad obligatoria del webhook

El sistema MUST exigir autenticidad verificable para procesar eventos entrantes del webhook en cualquier entorno normal. La ausencia de secreto o firma válida MUST NOT degradar silenciosamente el control. Un bypass local MAY existir solo cuando esté habilitado de forma explícita para desarrollo.

#### Scenarios

**Scenario 01: Evento legítimo firmado**
```text
Given un evento genuino enviado por Meta con autenticidad válida
When llega a POST /webhook
Then el sistema lo acepta y puede continuar con el flujo normal de procesamiento
```

**Scenario 02: Evento sin autenticidad suficiente**
```text
Given un request sin firma válida o con autenticidad no verificable
When intenta invocar POST /webhook fuera de un bypass local explícito
Then el sistema lo rechaza y no procesa ningún mensaje del payload
```

### REQ-02: Configuración persistente compartida negada por defecto

Los cambios persistentes que afectan a un grupo MUST requerir autoridad verificable. Cuando el producto no pueda verificar esa autoridad con confianza, MUST rechazar el cambio compartido sin modificar la configuración existente.

#### Scenarios

**Scenario 01: Configuración privada permitida**
```text
Given un usuario legítimo en un chat privado
When pide guardar reglas persistentes que solo afectan su propio asistente
Then el sistema puede guardar ese cambio dentro de su ámbito individual
```

**Scenario 02: Configuración grupal no verificable**
```text
Given un mensaje enviado desde un grupo sin una autoridad verificable para cambiar reglas compartidas
When intenta guardar una personalidad o comportamiento persistente para todo el grupo
Then el sistema rechaza el cambio y la configuración grupal previa permanece intacta
```

### REQ-03: Minimización de datos sensibles en observabilidad

La observabilidad del sistema MUST preservar capacidad diagnóstica sin registrar contenido sensible innecesario. El sistema SHOULD registrar metadata operativa suficiente, pero MUST evitar texto crudo de mensajes, prompts o cuerpos remotos que puedan contener datos financieros o personales.

#### Scenarios

**Scenario 01: Mensaje normal procesado**
```text
Given un usuario envía un mensaje válido al bot
When el sistema registra la operación
Then los logs muestran contexto operativo útil sin incluir el texto completo enviado por el usuario
```

**Scenario 02: Error remoto del proveedor**
```text
Given un proveedor externo responde con un error
When el backend registra el incidente
Then el sistema conserva código y contexto técnico del fallo sin volcar cuerpos remotos sensibles a los logs
```

### REQ-04: Preflight de media antes de procesamiento costoso

El sistema MUST validar que la media entrante respete la política permitida antes de OCR, transcripción o descargas costosas. Si el archivo no cumple tipo o tamaño, MUST rechazarlo con una respuesta segura y no continuar el procesamiento pesado.

#### Scenarios

**Scenario 01: Media válida dentro de política**
```text
Given un audio o imagen compatible y dentro de los límites configurados
When llega al webhook
Then el sistema lo admite y puede continuar con el flujo correspondiente
```

**Scenario 02: Media fuera de política**
```text
Given un audio o imagen con tipo no soportado o tamaño excesivo
When el webhook evalúa la media
Then el sistema detiene el procesamiento antes de OCR o transcripción y responde con una indicación segura al usuario
```

## Brownfield Annotations

<!-- extends: sdd/wip/004-phone-scope-security-hardening/1-functional/spec.md#REQ-01 -->
<!-- extends: sdd/wip/006-receipt-ocr-from-images/1-functional/spec.md -->

## Out of Scope

- Sincronización completa de roles administrativos de grupos desde WhatsApp.
- Política de retención/cifrado de logs a nivel plataforma.
- Moderación de contenido o scanning profundo de adjuntos más allá de tipo y tamaño.
