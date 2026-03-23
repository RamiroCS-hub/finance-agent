# Proposal: Webhook Hardening and Privacy Controls

## Intent

Corregir cuatro riesgos que siguen abiertos después del hardening inicial: autenticidad degradable del webhook, mutación persistente grupal sin autoridad verificable, exposición de datos sensibles en logs y procesamiento de media sin preflight suficiente. El objetivo es endurecer el borde operativo del bot sin cambiar el modelo de producto ni entrar todavía en una solución completa de auth end-user.

## Scope

### In Scope
- Exigir autenticidad criptográfica en `POST /webhook` por defecto y dejar cualquier bypass limitado a un modo local explícito.
- Bloquear por defecto los cambios persistentes de personalidad/configuración en grupos mientras no exista una autoridad confiable verificable.
- Redactar o minimizar logs que hoy exponen texto de mensajes, teléfonos completos o cuerpos remotos sensibles.
- Validar tipo y tamaño de media antes de disparar OCR, transcripción o descargas pesadas.

### Out of Scope
- Diseñar un sistema completo de roles administrativos de grupos sincronizado con WhatsApp.
- Introducir DLP avanzada, cifrado de application logs o antivirus de adjuntos.

## Approach

La solución endurece el pipeline donde hoy el riesgo es mayor: antes de confiar en el request, antes de persistir cambios compartidos y antes de enviar datos o media a servicios caros. Se privilegia un enfoque fail-closed en seguridad de borde, deny-by-default en configuración grupal y minimización explícita de datos para observabilidad.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/config.py` | Modified | Flags y límites de seguridad para webhook y media. |
| `app/api/webhook.py` | Modified | Enforce de autenticidad, redacción de logs y preflight de media. |
| `app/services/whatsapp.py` | Modified | Lectura de metadata de media y validaciones previas a descarga. |
| `app/services/personality.py` | Modified | Guardrails para impedir persistencia grupal no autorizada. |
| `app/agent/skills.py` | Modified | Ajuste de `save_personality` para scope privado seguro y rechazo grupal controlado. |
| `app/services/llm_provider.py` | Modified | Logging sanitizado de errores remotos. |
| `tests/test_webhook.py` | Modified | Casos de firma obligatoria, media inválida y logging seguro. |
| `tests/test_personality.py` | Modified | Cobertura de configuración privada permitida y grupal bloqueada. |
| `tests/test_whatsapp.py` | Modified | Casos de metadata de media y límites previos a descarga. |
| `docs/setup/local.md` | Modified | Semántica local segura para configurar el webhook y los límites. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Romper flujos locales existentes que dependían de webhook sin firma | Med | Introducir un bypass local explícito y documentado, nunca implícito por ausencia de secreto. |
| Rechazar cambios grupales legítimos al negar por defecto | High | Hacer explícito en UX y docs que la persistencia grupal queda deshabilitada hasta contar con autoridad verificable. |
| Cortar media válida por límites mal calibrados | Med | Configurar límites prudentes y cubrir bordes con tests sobre tipos y tamaños. |
| Perder capacidad diagnóstica por redacción excesiva | Med | Conservar metadata operativa y códigos de error, pero no contenido sensible. |

## Rollback Plan

La reversión puede hacerse por bloques pequeños: policy del webhook, guardrails grupales, logging y media preflight. No requiere migraciones ni cambios irreversibles en datos; el rollback principal es revertir el wiring y las validaciones nuevas si bloquean tráfico legítimo.

## Dependencies

- Variables de entorno nuevas o redefinidas para el modo local seguro y los límites de media.
- Confirmación de tamaños máximos aceptables para audio e imagen en el producto actual.

## Success Criteria

- [ ] Un `POST /webhook` sin firma válida ya no procesa mensajes salvo en un bypass local explícito.
- [ ] Un mensaje grupal no puede persistir reglas compartidas si el sistema no puede verificar autoridad suficiente.
- [ ] Los logs dejan de exponer texto de usuario y cuerpos remotos sensibles, pero conservan trazabilidad operativa.
- [ ] Audios e imágenes fuera de política se rechazan antes de OCR, transcripción o descargas costosas.
