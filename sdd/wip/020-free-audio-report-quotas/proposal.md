# Proposal: Free Audio and Report Quotas

## Intent

El cambio pedido redefine la diferencia entre planes: `PREMIUM` debe conservar audio y reportes sin tope, mientras `FREE` pasa a tener un límite de 5 audios por semana y 3 reportes PDF por mes. Para que el comportamiento sea confiable en producción, no alcanza con tocar constantes; hace falta introducir contabilización persistente por usuario, enforcement por período y mensajes claros cuando el cupo se agota.

## Scope

### In Scope
- Limitar el procesamiento de audio del plan `FREE` a 5 consumos por semana calendario.
- Limitar la generación de reportes PDF del plan `FREE` a 3 consumos por mes calendario.
- Persistir consumo de cuotas por usuario en base de datos, sobreviviendo reinicios y múltiples procesos.
- Aplicar el límite de audio cuando el usuario sea `FREE` y use un canal que hoy soporte audio privado: WhatsApp o Telegram.
- Aplicar el límite de reportes cuando el usuario sea `FREE` en el flujo actual de `generate_expense_report`.
- Dar mensajes claros al usuario cuando la cuota semanal o mensual esté agotada.
- Mantener `PREMIUM` ilimitado para audio y reportes.

### Out of Scope
- Cambios en límites de imágenes, documentos o videos.
- Rediseño general de precios o planes más allá de `FREE`/`PREMIUM`.
- Soporte de reportes PDF en Telegram.
- Dashboards de uso, backoffice o paneles administrativos de cuotas.
- Deduplicación perfecta de todos los tipos de consumo en todos los canales; en esta iteración se cubre especialmente audio cuando exista identificador fuente estable.

## Approach

La solución extiende el paywall actual con una capa de cuotas persistentes. En lugar de modelar el límite como un contador en memoria o un flag de feature, la propuesta agrega un ledger liviano de consumos por usuario y capacidad (`audio_processing`, `expense_report_pdf`). El enforcement se hace con ventanas calendario en timezone del usuario: semana local para audios y mes local para reportes. Las cuotas se aplican al plan `FREE`; `PREMIUM` conserva acceso ilimitado y solo pasa por los gates estáticos ya existentes.

Para evitar cobrar consumos fallidos, el diseño separa dos momentos:
- un precheck barato antes del trabajo pesado para cortar rápido cuando el cupo ya está agotado;
- un consumo autoritativo al completar con éxito el audio o el envío del reporte.

En audio, cuando el canal provea un identificador fuente estable, se guarda como `source_ref` para no consumir dos veces el mismo mensaje por reintentos del provider. En reportes, como hoy el tool no recibe un `message_id` del turno, el consumo queda ligado al éxito del envío y sin deduplicación fuerte en esta iteración.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/paywall.py` | Modified | Deja de ser solo allowlist de media y pasa a exponer cuotas por plan/capacidad. |
| `app/services/plan_usage.py` | New | Servicio de contabilización y consulta de cuotas periódicas por usuario. |
| `app/services/timezones.py` | Modified | Helpers para ventanas UTC de semana y mes calendario según timezone local del usuario. |
| `app/db/models.py` | Modified | Nuevo modelo persistente para consumos de cuota. |
| `migrations/versions/*.py` | New | Migración Alembic para la tabla de uso de cuotas. |
| `app/api/webhook.py` | Modified | Enforcement de cuota de audio en WhatsApp cuando el usuario sea FREE. |
| `app/api/telegram_webhook.py` | Modified | Enforcement de cuota de audio en Telegram cuando el usuario sea FREE. |
| `app/services/private_media.py` | Modified | Hook para consumo exitoso de audio y propagación de `source_ref` cuando exista. |
| `app/agent/skills.py` | Modified | Enforcement de cuota mensual de reportes PDF para usuarios FREE en `ReportSkill`. |
| `tests/test_paywall.py` | Modified | Cobertura nueva de cuotas por plan y preservación de PREMIUM ilimitado. |
| `tests/test_webhook.py` | Modified | Casos de audio dentro/fuera de cuota en WhatsApp. |
| `tests/test_telegram_webhook.py` | Modified | Casos de audio dentro/fuera de cuota en Telegram. |
| `tests/test_tools.py` / `tests/test_agent.py` | Modified | Casos del tool de reportes y mensajes de límite. |
| `tests/test_db_models.py` | Modified | Cobertura del nuevo modelo de uso persistente. |
| `.env.example`, `README.md`, `docs/setup/local.md` | Modified | Documentación del contrato de cuotas para FREE y PREMIUM. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cobrar dos veces el mismo audio por reintentos del webhook | Med | Persistir `source_ref` único cuando el canal aporte un identificador estable. |
| Ambigüedad sobre si la corrección movía solo el plan o también el período de audio | Med | Mantener el período original de audio semanal y dejarlo explícito en la spec actualizada. |
| Consumir cuota aunque el procesamiento falle | Med | Cobrar solo en éxito y hacer precheck previo como optimización, no como fuente de verdad final. |
| Abrir una carrera entre dos requests simultáneos cerca del límite | Med | Hacer el consumo autoritativo en DB dentro de transacción, con recheck final antes de insertar. |
| Romper el comportamiento actual de PREMIUM o de imágenes | Med | Mantener tests de regresión y aislar la nueva lógica a `audio_processing` y `expense_report_pdf` para FREE. |

## Rollback Plan

El rollback consiste en revertir el commit que introduzca la tabla de consumos, el servicio de cuotas y el wiring en audio/reportes. Si ya existieran registros de cuota en la base, pueden quedar huérfanos sin afectar el resto del producto, porque el dominio principal no dependería de ellos para leer gastos ni usuarios.

## Dependencies

- PostgreSQL/Alembic disponibles para agregar una tabla nueva de consumos.
- `make migrate` ejecutado al aplicar la feature.
- Capacidad de resolver `user_id` y timezone del usuario antes de cobrar la cuota.

## Success Criteria

- [ ] FREE permite hasta 5 audios procesados por semana calendario y bloquea el sexto con un mensaje claro.
- [ ] FREE permite hasta 3 reportes PDF enviados por mes calendario y bloquea el cuarto con un mensaje claro.
- [ ] PREMIUM queda ilimitado para audio y reportes.
- [ ] Fallos de descarga/transcripción/audio o fallos de generación/envío de reportes no consumen cuota.
- [ ] El cómputo de ventanas usa la timezone del usuario y resetea correctamente al comenzar una nueva semana o un nuevo mes local.
