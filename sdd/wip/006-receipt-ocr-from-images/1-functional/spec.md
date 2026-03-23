# Functional Spec: Receipt OCR From Images

**Feature**: `006-receipt-ocr-from-images`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature permite registrar gastos a partir de fotos de tickets o comprobantes enviados por WhatsApp. El usuario deberia poder mandar una imagen y recibir una confirmacion con el monto, el comercio y la categoria detectada, sin reescribir la informacion.

La primera version se enfoca en tickets simples y claros. Cuando la confianza del OCR no alcanza, el sistema debe pedir confirmacion o rechazar la extraccion en vez de inventar datos.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Envia una foto de ticket para registrar un gasto. |
| Bot de WhatsApp | Descarga la imagen, ejecuta OCR y responde con el resultado. |
| Proveedor OCR/vision | Extrae texto o campos estructurados desde la imagen. |

## Requirements

### REQ-01: Ingesta de imagen y extraccion de campos

El sistema MUST descargar la imagen enviada por WhatsApp y SHOULD extraer al menos monto y comercio cuando el ticket sea legible.

#### Scenarios

**Scenario 01: Ticket legible**
```text
Given una imagen de ticket clara y soportada
When el usuario la envia al bot
Then el sistema extrae monto y comercio y prepara un gasto candidato
```

**Scenario 02: Imagen no soportada o ilegible**
```text
Given una imagen borrosa o no documental
When el sistema intenta procesarla
Then responde que no pudo extraer datos confiables y no registra el gasto
```

### REQ-02: Confirmacion segura del gasto detectado

El sistema MUST evitar registrar automaticamente informacion incierta y MAY pedir confirmacion cuando la confianza no sea suficiente.

#### Scenarios

**Scenario 01: Confianza alta**
```text
Given un ticket con extraccion confiable
When el OCR devuelve campos consistentes
Then el sistema confirma y registra el gasto en el flujo normal
```

**Scenario 02: Confianza intermedia**
```text
Given una extraccion parcial o ambigua
When el sistema detecta dudas en monto, comercio o categoria
Then solicita confirmacion antes de persistir el gasto
```

### REQ-03: Integracion con el registro actual

El flujo OCR SHALL integrarse con el mismo registro de gastos usado por mensajes de texto y audio.

#### Scenarios

**Scenario 01: Registro exitoso desde OCR**
```text
Given una extraccion confirmada
When el sistema la persiste
Then el gasto queda disponible en resumenes, busquedas y consultas posteriores
```

**Scenario 02: Error en integracion final**
```text
Given un OCR exitoso pero una falla de persistencia
When el sistema intenta registrar el gasto
Then informa el error sin duplicar registros
```

## Brownfield Annotations

<!-- overrides: sdd/wip/001-finance-org-wpp-reverse-eng/1-functional/spec.md#REQ-06 -->

## Out of Scope

- Lectura linea por linea completa del ticket.
- Soportar cualquier imagen generica no relacionada con comprobantes.
