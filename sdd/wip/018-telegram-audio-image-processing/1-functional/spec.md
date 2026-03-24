# Functional Spec: Telegram Audio and Image Processing

**Feature**: 018-telegram-audio-image-processing
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature extiende el canal de Telegram para que los chats privados no queden limitados a texto. El objetivo es que un usuario pueda mandar un audio y obtener su transcripción dentro del flujo normal del asistente, o mandar una foto de un ticket y activar el mismo comportamiento de OCR que hoy existe en WhatsApp.

La experiencia esperada no es “Telegram como un canal distinto con menos producto”, sino un segundo borde de ingreso que reutiliza las capacidades multimedia ya disponibles cuando el tipo de media está soportado. A la vez, el sistema debe seguir avisando con claridad cuando un tipo de archivo todavía no se puede procesar, en lugar de ignorarlo o fallar en silencio.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de Telegram | Persona que interactúa con el bot desde un chat privado y quiere enviar texto, audio o una imagen de ticket. |
| Operador del sistema | Persona que configura secrets, límites de media y monitorea el funcionamiento del canal Telegram. |
| Telegram Bot API | Plataforma que entrega updates, metadatos de archivos y permite descargar la media del bot. |
| Usuario de WhatsApp existente | Persona que ya usa audio e imágenes por WhatsApp y no debe sufrir regresiones por la extracción de lógica compartida. |

## Requirements

### REQ-01: Audio privado de Telegram procesable

El sistema MUST aceptar audios privados soportados de Telegram y convertirlos a texto usando el pipeline existente de transcripción. La respuesta final MUST seguir el flujo conversacional normal del asistente para ese usuario y canal.

#### Scenarios

**Scenario 01: Audio privado válido**
```text
Given un usuario envía un audio desde un chat privado de Telegram
When el webhook recibe un update válido con media soportada y el archivo supera el preflight
Then el sistema descarga el audio, lo transcribe y procesa la transcripción como un mensaje del usuario en ese mismo chat
```

**Scenario 02: Audio no procesable**
```text
Given un usuario envía un audio privado de Telegram
When el archivo no puede descargarse o la transcripción falla
Then el sistema informa claramente el problema al usuario y no ejecuta una respuesta conversacional espuria
```

### REQ-02: Imagen privada de Telegram con OCR de ticket

El sistema MUST aceptar imágenes privadas soportadas de Telegram y reutilizar el flujo actual de OCR de tickets. Cuando la imagen no permita una extracción suficientemente confiable, el sistema MUST devolver una guía clara para continuar por texto o reenviar una foto mejor.

#### Scenarios

**Scenario 01: Ticket con alta confianza**
```text
Given un usuario envía una imagen privada de Telegram que contiene un ticket legible
When el backend procesa la imagen con OCR y obtiene un resultado confiable
Then el sistema registra o prepara la operación financiera correspondiente y responde en ese mismo chat privado
```

**Scenario 02: OCR insuficiente**
```text
Given un usuario envía una imagen privada de Telegram con baja calidad o datos ambiguos
When el OCR no alcanza suficiente confianza para operar automáticamente
Then el sistema explica la limitación y ofrece una continuación comprensible sin romper la conversación
```

### REQ-03: Validación temprana y policy explícita para media de Telegram

Antes de descargar o procesar media pesada, el sistema MUST validar que el archivo cumpla la policy configurada de tamaño y MIME para Telegram. Si la media no es elegible, el sistema MUST rechazarla temprano con una respuesta entendible para el usuario.

#### Scenarios

**Scenario 01: Media fuera de policy**
```text
Given un usuario envía un audio o imagen privada de Telegram
When la metadata del archivo indica un tamaño excesivo o un MIME no soportado
Then el sistema rechaza esa media antes del procesamiento pesado y comunica la razón de forma segura
```

**Scenario 02: Metadata insuficiente**
```text
Given Telegram entrega un update de media pero la metadata necesaria no puede resolverse correctamente
When el backend intenta validar el archivo
Then el sistema no procesa la media y devuelve un mensaje claro de reintento al usuario
```

### REQ-04: Aviso explícito para media de Telegram fuera de alcance

El sistema MUST seguir notificando al usuario cuando reciba tipos de media de Telegram que todavía no están soportados por esta iteración, como documentos o video. Ese aviso SHOULD ser comprensible y consistente con el alcance actual del canal.

#### Scenarios

**Scenario 01: Documento o video no soportado**
```text
Given un usuario envía una media privada de Telegram que está fuera del alcance soportado
When el webhook clasifica el tipo de update
Then el usuario recibe una respuesta explícita indicando que ese tipo de media todavía no puede procesarse
```

**Scenario 02: Grupo o chat fuera de alcance**
```text
Given llega un update de Telegram que no corresponde a un chat privado soportado
When el sistema evalúa el payload entrante
Then el update se descarta sin procesamiento multimedia ni respuesta funcional engañosa
```

### REQ-05: Paridad funcional sin regresión entre canales

La incorporación de audio e imágenes en Telegram MUST preservar el comportamiento ya soportado para WhatsApp. La extracción de lógica compartida SHOULD mantener el mismo resultado observable para ambos canales cuando el caso funcional sea equivalente.

#### Scenarios

**Scenario 01: Reuso correcto del pipeline**
```text
Given existen pipelines de audio e imagen ya soportados en WhatsApp
When la nueva implementación comparte lógica para Telegram
Then ambos canales conservan resultados coherentes para transcripción, OCR y mensajes de error comparables
```

**Scenario 02: Regresión evitada en WhatsApp**
```text
Given un usuario de WhatsApp envía audio o imagen en un caso previamente soportado
When la feature de Telegram media ya está integrada
Then el flujo de WhatsApp sigue funcionando sin cambios regresivos relevantes
```

## Brownfield Annotations

<!-- extends: sdd/wip/017-telegram-channel-connection/1-functional/spec.md#REQ-01 -->
<!-- extends: sdd/wip/017-telegram-channel-connection/1-functional/spec.md#REQ-02 -->
<!-- extends: sdd/wip/016-webhook-hardening-and-privacy-controls/1-functional/spec.md#REQ-04 -->
<!-- extends: sdd/wip/006-receipt-ocr-from-images/1-functional/spec.md -->

## Out of Scope

- Soporte de documentos, videos, stickers, animaciones y notas de video de Telegram.
- Soporte multimedia en grupos, canales o supergrupos de Telegram.
- Unificación de cuentas entre WhatsApp y Telegram para una misma persona.
- Rediseño completo del paywall o del pricing de media.
