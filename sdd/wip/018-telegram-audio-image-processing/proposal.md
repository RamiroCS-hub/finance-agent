# Proposal: Telegram Audio and Image Processing

## Intent

Completar el canal de Telegram para que no quede limitado a texto privado cuando el producto ya sabe transcribir audios y leer tickets por imagen en WhatsApp. Hoy el usuario recibe un aviso de limitación, pero la experiencia es claramente incompleta y genera una brecha funcional entre canales que ya comparten identidad, memoria y dispatcher.

## Scope

### In Scope
- Aceptar audios privados de Telegram y transcribirlos reutilizando el pipeline actual de audio.
- Aceptar imágenes privadas de Telegram y procesarlas con el flujo actual de OCR de tickets.
- Descargar archivos de Telegram Bot API con validación explícita de tamaño y MIME antes del procesamiento pesado.
- Mantener avisos claros para media todavía fuera de alcance como documentos, stickers o video.
- Documentar setup, límites y validación operativa de Telegram media.

### Out of Scope
- Soporte de grupos, canales o supergrupos de Telegram para media.
- Documentos, videos, stickers, notas de video o automatizaciones ricas de Telegram.
- Cambios en pricing o rediseño amplio del paywall más allá de reutilizar las reglas existentes para `audio` e `image`.
- Refactor completo del pipeline multimedia de WhatsApp más allá de la extracción mínima necesaria para compartir lógica.

## Approach

La solución debe extender el webhook de Telegram para reconocer `voice` y `photo`, obtener metadata/bytes vía Bot API y normalizar esos inputs al mismo contrato interno que hoy usa WhatsApp para audio e imágenes. En lugar de duplicar toda la lógica de OCR, transcripción, persistencia y mensajes de progreso, la feature propone extraer un flujo privado compartido de media que ambos canales puedan invocar con adaptadores específicos de transporte.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/api/telegram_webhook.py` | Modified | Parseo de `voice` y `photo`, avisos de progreso y fallback explícito para media todavía no soportada. |
| `app/services/telegram.py` | Modified | Métodos para resolver `getFile`, metadata normalizada y descarga segura de bytes desde Bot API. |
| `app/services/message_dispatch.py` | Modified | Posible reutilización de helpers de salida si los mensajes de progreso se unifican. |
| `app/api/webhook.py` | Modified | Extracción mínima del pipeline privado de audio/OCR para compartirlo con Telegram sin regresión. |
| `app/services/` | Modified/New | Nuevo servicio/helper compartido para procesar media privada reutilizando transcripción, OCR, store y alertas. |
| `app/config.py` | Modified | Settings explícitas de policy para media de Telegram y límites operativos. |
| `tests/test_telegram_webhook.py` | Modified | Casos de audio, imagen, rechazos por policy y media fuera de alcance. |
| `tests/test_telegram.py` | Modified | Cobertura del cliente Telegram para metadata/descarga. |
| `tests/test_webhook.py` | Modified | Regresión de WhatsApp después de extraer lógica común. |
| `docs/setup/local.md` | Modified | Variables y notas de setup para media en Telegram. |
| `README.md` | Modified | Actualización del alcance del canal Telegram. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Duplicar la lógica de OCR/transcripción entre WhatsApp y Telegram | High | Extraer un helper compartido de media privada antes de implementar Telegram media. |
| Telegram entregue metadata distinta o incompleta respecto de WhatsApp | Med | Definir un contrato normalizado mínimo y rechazar temprano cuando falten tamaño/MIME o file path utilizable. |
| Los límites de media queden acoplados a Meta y no a Telegram | Med | Introducir policy explícita de Telegram en config, separada de la de WhatsApp. |
| La extracción del pipeline de WhatsApp introduzca regresiones funcionales | High | Mantener tests de regresión de WhatsApp y validar mapping escenario a escenario antes de mergear. |
| El usuario espere que todo tipo de media ya esté soportado en Telegram | Med | Conservar respuestas explícitas para media fuera de alcance y documentar límites en setup/README. |

## Rollback Plan

La feature puede revertirse con `git revert` sin rollback de datos, porque no introduce migraciones nuevas. Si la extracción del pipeline compartido causara regresiones, el rollback debe restaurar `app/api/webhook.py` y remover los helpers/adaptadores de Telegram media en una sola reversión para evitar estados híbridos entre canales.

## Dependencies

- `TELEGRAM_BOT_TOKEN` activo con permisos de Bot API.
- `TELEGRAM_WEBHOOK_SECRET` registrado en el webhook ya existente.
- `GROQ_API_KEY` para transcripción de audio cuando se habilite ese flujo.
- `GEMINI_API_KEY` y configuración OCR si se habilita procesamiento de tickets por imagen.

## Success Criteria

- [ ] Un audio privado de Telegram puede transcribirse y seguir el flujo conversacional existente.
- [ ] Una imagen privada de Telegram puede ejecutar OCR de ticket con comportamiento equivalente al de WhatsApp cuando aplique.
- [ ] Las media fuera de policy o fuera de alcance devuelven una respuesta clara al usuario y no disparan procesamiento pesado.
- [ ] WhatsApp conserva su comportamiento actual de audio e imágenes sin regresiones relevantes después de compartir lógica.
- [ ] La documentación operativa deja explícitos setup, límites y tipos soportados de media en Telegram.
