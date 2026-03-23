# Anotamelo

Bot de gastos conversacional sobre FastAPI. El producto actual combina:

- WhatsApp Cloud API como canal principal y Telegram Bot API como canal adicional `private text only`
- LLM configurable para interpretación
- PostgreSQL como storage operativo de gastos y metadata relacional
- OCR de tickets por imagen con extracción de monto y comercio
- presupuestos por categoría con alertas por desvío y gasto inusual
- insights conversacionales para comparativas y detección de gastos repetidos
- proyecciones de ahorro por escenarios manuales o recortes sobre histórico
- seguimiento de cuotas/deudas y lectura educativa personalizada
- Google Sheets solo como fuente legacy para importar histórico

## Punto de entrada

- Setup local: [docs/setup/local.md](/Users/rcarnicer/Desktop/anotamelo/docs/setup/local.md)
- Guía de Groq para audios: [docs/setup/groq-api-key.md](/Users/rcarnicer/Desktop/anotamelo/docs/setup/groq-api-key.md)
- Estado actual de arquitectura: [docs/architecture/current-state.md](/Users/rcarnicer/Desktop/anotamelo/docs/architecture/current-state.md)
- Readiness de deploy con Supabase: [docs/deploy/supabase.md](/Users/rcarnicer/Desktop/anotamelo/docs/deploy/supabase.md)

## SDD

La fuente viva para features, specs, diseño y task plans es [sdd/](/Users/rcarnicer/Desktop/anotamelo/sdd).

- Config del proyecto: [sdd/PROJECT.md](/Users/rcarnicer/Desktop/anotamelo/sdd/PROJECT.md)
- Features activas: [sdd/wip](/Users/rcarnicer/Desktop/anotamelo/sdd/wip)

`openspec/` queda como material histórico en transición. Ver [openspec/README.md](/Users/rcarnicer/Desktop/anotamelo/openspec/README.md).

## Desarrollo rápido

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Importación legacy

Si necesitás pasar histórico viejo desde Google Sheets a DB:

```bash
python scripts/import_expenses_from_sheets.py --dry-run
python scripts/import_expenses_from_sheets.py --phone 5491123456789
```

## Webhook

- Verificación: `GET /webhook`
- Recepción: `POST /webhook`
- Telegram: `POST /telegram/webhook`

Para producción, además de `WHATSAPP_VERIFY_TOKEN`, configurá `WHATSAPP_APP_SECRET` para validar la firma `X-Hub-Signature-256` de Meta.
Para Telegram configurá `TELEGRAM_BOT_TOKEN` + `TELEGRAM_WEBHOOK_SECRET`; la primera versión solo soporta chats privados de texto.

## Tiempo y zonas horarias

- La base persiste timestamps en `UTC`.
- La app infiere la zona horaria local del usuario a partir del prefijo internacional del número de WhatsApp.
- Si la identidad no trae teléfono, usa `DEFAULT_USER_TIMEZONE`.
- Las fechas y horas que se muestran al usuario se renderizan en esa zona horaria resultante.
