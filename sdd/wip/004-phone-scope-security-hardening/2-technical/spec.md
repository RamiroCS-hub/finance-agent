# Technical Spec: Phone Scope Security Hardening

**Feature**: `004-phone-scope-security-hardening`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La solucion agrega una barrera de seguridad en el ingreso del webhook y propaga un contexto de entidad confiable a lo largo del agente y las tools. La aplicacion deja de tratar `message.from` como verdad suficiente hasta validar el request.

```text
Incoming webhook
  -> verify request authenticity
  -> extract trusted entity context
  -> run paywall / feature checks
  -> invoke agent/tools within scoped entity
```

Ademas se revisan tools que hoy exponen recursos demasiado amplios, especialmente salidas derivadas de un spreadsheet global.

## Architecture Decision Records

### ADR-001: Validar autenticidad en el borde del webhook

- **Status**: Accepted
- **Context**: El riesgo mas alto actual es confiar en `message.from` sin verificar origen.
- **Decision**: Implementar verificacion de autenticidad del request en `app/api/webhook.py` antes de procesar el payload.
- **Consequences**: Se reduce drasticamente el riesgo de impersonacion. A cambio, se incorpora complejidad de manejo de headers y calculo de firma.
- **Alternatives considered**: Confiar solo en whitelist y secreto de verificacion GET. Se descarta por insuficiente.

### ADR-002: Introducir un contexto de entidad confiable

- **Status**: Accepted
- **Context**: El agente hoy opera solo con `phone`, incluso cuando el origen es grupal.
- **Decision**: Modelar un contexto de entidad confiable que acompañe al flujo y delimite el ambito de las tools.
- **Consequences**: El scoping se vuelve explicito y reusable. A cambio, hay que tocar varias interfaces.
- **Alternatives considered**: Seguir pasando strings sueltos de telefono y grupo.

### ADR-003: Eliminar salidas de recursos globales

- **Status**: Accepted
- **Context**: Algunas respuestas exponen identificadores globales que no respetan el minimo privilegio.
- **Decision**: Restringir o reemplazar tools que retornan recursos compartidos no segmentados.
- **Consequences**: Mejora la privacidad. A cambio, puede cambiar la UX de herramientas existentes.
- **Alternatives considered**: Mantener las tools y confiar en permisos externos del recurso.

## Component Design

### Webhook verifier

**Responsabilidad**: autenticar requests entrantes antes de parsear el mensaje como confiable.

**Interfaz publica**:
```python
def verify_incoming_webhook(request: Request, body: bytes) -> None: ...
```

**Dependencias**: FastAPI request, headers de Meta, settings.

### Trusted entity context

**Responsabilidad**: transportar identidad confiable, tipo de chat y alcance de acceso.

**Interfaz publica**:
```python
class TrustedEntityContext(TypedDict):
    actor_phone: str
    chat_type: str
    group_id: str | None
```

**Dependencias**: webhook parser, agent core, tool registry.

### Scoped tool guardrails

**Responsabilidad**: asegurar que cada tool use solo el ambito permitido por el contexto.

**Interfaz publica**:
```python
class ToolRegistry:
    def __init__(self, sheets: SheetsService, context: TrustedEntityContext) -> None: ...
```

**Dependencias**: agent core, services de DB y Sheets.

## Data Model

Sin cambios obligatorios en modelo de datos para la primera iteracion. El hardening ocurre principalmente en ingreso y capa de aplicacion.

## API Contract

### POST /webhook

**Request**:
```json
{
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "5491112345678",
                "type": "text"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

**Response 200**:
```json
{
  "status": "ok"
}
```

**Errors**:
| Status | Code | Description |
|--------|------|-------------|
| 401 | invalid_signature | El request no pudo autenticarse como proveniente de Meta |
| 403 | forbidden_scope | El request autentico intenta una operacion fuera de alcance |

## Error Handling

- Las fallas de autenticidad se responden sin procesar el payload.
- Las fallas de scope deben loguearse con contexto suficiente para auditoria sin filtrar datos sensibles.
- Los requests legitimos deben seguir devolviendo `200` cuando el contenido es no procesable, pero no cuando el origen es falso.

## Testing Strategy

- **Unit tests**: verificacion de firma, construccion de contexto confiable y guardrails de tools.
- **Integration tests**: requests validos e invalidos sobre `/webhook`, scoping de recursos por entidad.
- **E2E tests**: no requeridos en la primera iteracion.

Referencia a scenarios de `1-functional/spec.md`: REQ-01 se cubre con tests de autenticidad, REQ-02 con tests de entity scoping, REQ-03 con regresiones sobre tools y salidas expuestas.

## Non-Functional Requirements

- **Performance**: la validacion del webhook no debe agregar latencia significativa al ack HTTP.
- **Security**: el sistema no debe confiar en campos del payload antes de verificar autenticidad.
- **Observability**: logs de rechazo por firma invalida, scope invalido y decisiones de bloqueo.

## Brownfield Annotations

<!-- overrides: app/api/webhook.py -->
<!-- extends: app/agent/core.py -->
