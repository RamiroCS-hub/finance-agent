# Proposal: Receipt OCR From Images

## Intent

Hacer real la experiencia de registrar gastos a partir de una foto de ticket, que hoy está prometida en la web pero no existe en el producto. Actualmente las imágenes se aceptan a nivel de webhook, pero se cortan con un mensaje informando que la lectura todavía no está implementada.

## Scope

### In Scope
- Descargar imágenes de WhatsApp y enviarlas a un servicio OCR/vision.
- Extraer monto, comercio y categoría candidata desde tickets o comprobantes simples.
- Confirmar o registrar automáticamente el gasto cuando la confianza del parseo sea suficiente.

### Out of Scope
- Soportar cualquier tipo de imagen no documental en la primera versión.
- Resolver conciliación avanzada de múltiples ítems línea por línea del ticket.

## Approach

La primera versión debe enfocarse en tickets claros y en un contrato de extracción simple. El pipeline toma la imagen desde Meta, la procesa con OCR/vision y devuelve una estructura compatible con el flujo actual del agente, permitiendo confirmar o registrar el gasto con trazabilidad.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/api/webhook.py` | Modified | Procesamiento real de imágenes en lugar de respuesta stub. |
| `app/services/whatsapp.py` | Modified | Reutilizar descarga de media para imágenes. |
| `app/services/` | New/Modified | Servicio OCR/vision y normalización de resultados. |
| `app/agent/tools.py` | Modified | Integración del parseo OCR con el flujo de registro. |
| `tests/` | Modified | Fixtures de OCR y regresiones de imágenes. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| OCR devuelve montos erróneos o categorías débiles | High | Introducir umbral de confianza y paso de confirmación conversacional. |
| Costo o latencia excesiva del proveedor de visión | Med | Limitar tamaño, tipos de imagen y timeouts desde el inicio. |
| Imágenes borrosas generan mala UX | Med | Mensajes claros de fallback y ejemplos de uso soportado. |

## Rollback Plan

Mantener la respuesta stub actual como fallback. Si el OCR falla en producción, se revierte el cambio y las imágenes vuelven a responder con el mensaje de funcionalidad no disponible.

## Dependencies

- Proveedor OCR/vision compatible con imágenes enviadas por WhatsApp.
- Definición de criterios mínimos de confianza para auto-registro.

## Success Criteria

- [ ] Una foto de ticket compatible permite extraer monto y comercio de forma confiable.
- [ ] El gasto se registra o confirma sin que el usuario tenga que reescribirlo.
- [ ] Existen tests para imágenes válidas, inválidas y de baja confianza.
