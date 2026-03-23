# Proposal: Phone Scope Security Hardening

## Intent

Garantizar que nadie pueda consultar, mutar o gatillar flujos usando el número de otra persona por fuera del canal legítimo de WhatsApp. Hoy el modelo de aislamiento depende en gran medida del `phone` recibido en el webhook, pero el endpoint no verifica la firma de Meta y algunas salidas comparten recursos demasiado amplios.

## Scope

### In Scope
- Verificar autenticidad del webhook antes de confiar en `message.from`.
- Revisar y endurecer los accesos a datos por usuario y por grupo.
- Agregar tests de seguridad para impersonación, aislamiento de datos y exposición accidental.

### Out of Scope
- Cambiar en esta iteración el modelo de identidad del producto fuera de WhatsApp.
- Introducir un sistema completo de auth end-user con login propio.

## Approach

La corrección se apoya sobre el flujo actual: primero se autentica el origen del webhook, luego se refuerza el scoping de lectura/escritura por entidad y finalmente se eliminan o encapsulan salidas que hoy podrían exponer información más amplia de la necesaria. El objetivo es hardening incremental sin rediseñar todo el producto.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/api/webhook.py` | Modified | Validación de firma y controles de origen. |
| `app/agent/core.py` | Modified | Propagación explícita de contexto de entidad segura. |
| `app/agent/tools.py` | Modified | Revisión de tools sensibles y su ámbito de acceso. |
| `app/services/sheets.py` | Modified | Reducción de exposición de recursos globales. |
| `tests/` | Modified | Nuevos tests de seguridad y regresión. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Rechazar payloads válidos por validar mal la firma | Med | Implementar contra el contrato oficial de Meta y cubrirlo con tests de fixtures reales. |
| Endurecer demasiado el scoping y romper flujos legítimos | Med | Agregar tests de regresión sobre casos privados y grupales permitidos. |
| Mantener enlaces o recursos compartidos que filtren datos | High | Revisar toda salida que referencie recursos globales y reemplazarla por vistas acotadas. |

## Rollback Plan

El hardening debe quedar encapsulado por commits pequeños y tests. Si alguna validación bloquea tráfico real, se puede revertir el cambio puntual y dejar el resto del aislamiento por entidad intacto mientras se corrige el matcher.

## Dependencies

- Acceso al formato de firma o headers enviados por Meta en producción.
- Definición clara de qué recursos son per-user y cuáles son compartidos por diseño.

## Success Criteria

- [ ] Un POST arbitrario al webhook no puede hacerse pasar por otro teléfono.
- [ ] Cada tool sensible opera solo sobre el ámbito de la entidad autenticada.
- [ ] Existen tests que cubren impersonación y aislamiento de datos.
