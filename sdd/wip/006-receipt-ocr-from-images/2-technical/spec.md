# Technical Spec: Receipt OCR From Images

**Feature**: `006-receipt-ocr-from-images`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

El webhook ya soporta mensajes de imagen y descarga media desde Meta. La feature agrega una etapa de OCR/vision y una normalizacion de campos extraidos antes de entrar al flujo de registro.

```text
Image message -> download_media -> OCR service -> normalized candidate
                                           -> confidence gate
                                           -> register_expense or ask confirmation
```

## Architecture Decision Records

### ADR-001: Reusar la descarga de media existente

- **Status**: Accepted
- **Context**: Ya existe soporte para descargar audio e imagen desde WhatsApp.
- **Decision**: Reusar `download_media` y agregar una capa OCR separada.
- **Consequences**: Menor duplicacion y menor riesgo. A cambio, el webhook concentra mas branching por tipo de media.
- **Alternatives considered**: Implementar un downloader dedicado para imagenes.

### ADR-002: Introducir una compuerta de confianza antes de registrar

- **Status**: Accepted
- **Context**: El OCR puede devolver datos erroneos o ambiguos.
- **Decision**: Normalizar campos y evaluar confianza antes de registrar automaticamente.
- **Consequences**: Se reduce el riesgo de basura en los datos. A cambio, algunas imagenes requeriran una segunda interaccion.
- **Alternatives considered**: Registrar siempre y corregir despues.

### ADR-003: Mantener el registro final en el flujo actual de gastos

- **Status**: Accepted
- **Context**: Ya existe una ruta madura de persistencia y confirmacion para gastos.
- **Decision**: Convertir el resultado OCR en un candidato compatible con `register_expense`.
- **Consequences**: Los resumenes y busquedas quedan unificados. A cambio, hay que mapear bien campos y errores.
- **Alternatives considered**: Crear un pipeline de persistencia aparte para tickets.

## Component Design

### OCR service

**Responsabilidad**: enviar la imagen al proveedor de vision y devolver un candidato estructurado.

**Interfaz publica**:
```python
async def extract_receipt_fields(image_bytes: bytes) -> dict: ...
```

**Dependencias**: proveedor OCR/vision, settings.

### OCR normalizer

**Responsabilidad**: convertir el resultado bruto en monto, comercio, categoria y score de confianza.

**Interfaz publica**:
```python
def normalize_receipt_payload(raw_payload: dict) -> dict: ...
```

**Dependencias**: formato de respuesta del proveedor, reglas de dominio.

### Webhook image flow

**Responsabilidad**: orquestar descarga, OCR, compuerta de confianza y registro final.

**Interfaz publica**:
```python
async def _process_message_background(..., msg_type="image", media_id=...) -> None: ...
```

**Dependencias**: whatsapp service, OCR service, agent/tools.

## Data Model

Sin cambios obligatorios en modelo de datos. Los metadatos OCR pueden mantenerse fuera del storage principal en la primera version.

## API Contract

Sin cambios en API publica HTTP.

## Error Handling

- Fallas del proveedor OCR deben terminar en mensaje de fallback al usuario.
- Si la confianza es baja, se pide confirmacion y no se persiste nada automaticamente.
- Los errores de persistencia despues de una extraccion valida no deben duplicar el gasto.

## Testing Strategy

- **Unit tests**: normalizacion de payload OCR y evaluacion de confianza.
- **Integration tests**: flujo de imagen completa con proveedor mockeado.
- **E2E tests**: webhook de imagen con caso exitoso y fallo de OCR.

## Non-Functional Requirements

- **Performance**: el ack HTTP no debe esperar el OCR; el procesamiento sigue en background.
- **Security**: no persistir imagenes ni datos sensibles mas alla de lo necesario.
- **Observability**: logs de OCR exitoso, baja confianza y errores del proveedor.

## Brownfield Annotations

<!-- extends: app/api/webhook.py -->
<!-- extends: app/services/whatsapp.py -->
