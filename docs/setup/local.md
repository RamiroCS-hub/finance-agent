# Setup Local

## Requisitos

- Python 3.11+
- Cuenta de Meta WhatsApp Cloud API
- Bot de Telegram si querés habilitar el canal adicional
- API key de LLM
- PostgreSQL local o remoto
- Google Service Account + spreadsheet compartido solo si vas a importar histórico legacy

## Instalación

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Variables mínimas

```env
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=mi_token_secreto
WHATSAPP_APP_SECRET=
WHATSAPP_REQUIRE_SIGNATURE=true
WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS=false
WHATSAPP_MAX_AUDIO_BYTES=16777216
WHATSAPP_MAX_IMAGE_BYTES=10485760
ALLOWED_PHONE_NUMBERS=

TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_API_BASE_URL=https://api.telegram.org
ALLOWED_TELEGRAM_CHAT_IDS=
TELEGRAM_MAX_AUDIO_BYTES=16777216
TELEGRAM_MAX_IMAGE_BYTES=10485760
TELEGRAM_ALLOWED_AUDIO_MIME_TYPES=audio/ogg,audio/opus,audio/mpeg,audio/mp4,audio/aac
TELEGRAM_ALLOWED_IMAGE_MIME_TYPES=image/jpeg,image/png,image/webp

# Opcional: solo para importar histórico desde Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials/service_account.json
GOOGLE_SPREADSHEET_ID=

LLM_PROVIDER=gemini
GEMINI_API_KEY=
RECEIPT_OCR_PROVIDER=gemini
RECEIPT_OCR_AUTO_CONFIDENCE=0.85
RECEIPT_OCR_CONFIRM_CONFIDENCE=0.60

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/finance_bot
DATABASE_TIMEZONE=UTC
DATABASE_USE_SSL=false
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_RECYCLE_SECONDS=1800
DEFAULT_USER_TIMEZONE=UTC
GROUP_BOT_MENTION=@anotamelo
MONTHLY_INFLATION_RATE=0
```

## Credenciales

- Guardá la service account en `credentials/service_account.json` solo si vas a correr la importación legacy
- Si usás audios con Groq, seguí [groq-api-key.md](/Users/rcarnicer/Desktop/anotamelo/docs/setup/groq-api-key.md)

## Ejecutar

```bash
uvicorn app.main:app --reload --port 8000
```

## Notas

- La app persiste gastos en PostgreSQL; Google Sheets ya no es requisito para el runtime diario.
- El rate limit de WhatsApp usa cache local por proceso; ya no requiere Redis para funcionar.
- `WHATSAPP_VERIFY_TOKEN` lo elegís vos y se usa solo para el `GET /webhook` del challenge inicial.
- `WHATSAPP_APP_SECRET` te lo da Meta en `App Settings > Basic` y se usa para verificar la firma de cada `POST /webhook`.
- Telegram usa `POST /telegram/webhook` y valida el header `X-Telegram-Bot-Api-Secret-Token` contra `TELEGRAM_WEBHOOK_SECRET`.
- La integración actual de Telegram soporta chats privados de texto, audio e imágenes.
- El plan `FREE` permite hasta `5` audios por semana y `3` reportes PDF por mes; `PREMIUM` queda ilimitado para esas dos capacidades.
- Telegram todavía no procesa grupos, documentos, videos, stickers ni otras media fuera de ese alcance.
- Para desarrollo local, si querés aceptar webhooks sin firma, usá `WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS=true`. Ya no se habilita por omisión cuando falta `WHATSAPP_APP_SECRET`.
- La base guarda timestamps en UTC; para WhatsApp la app infiere zona horaria por prefijo telefónico y para identidades sin teléfono usa `DEFAULT_USER_TIMEZONE`.
- En grupos, el bot responde cuando detecta la mención configurada en `GROUP_BOT_MENTION`.
- Para OCR de tickets por imagen, necesitás `GEMINI_API_KEY` y opcionalmente `RECEIPT_OCR_MODEL`.
- Podés definir presupuestos por categoría y el bot devuelve alertas dentro del flujo cuando detecta exceso o un gasto fuera de patrón.
- Si querés comparativas educativas ajustadas por inflación, configurá `MONTHLY_INFLATION_RATE` con una tasa mensual de referencia.
- Para importar histórico legacy: `python scripts/import_expenses_from_sheets.py --dry-run`
- `ALLOWED_PHONE_NUMBERS` permite limitar números de WhatsApp durante pruebas.
- `ALLOWED_TELEGRAM_CHAT_IDS` permite limitar chats de Telegram durante pruebas.
- Si pegás una URL `postgresql://` o `postgres://`, la app la normaliza a `postgresql+asyncpg://`.
- Si usás la URL interna de Render para Postgres, el default `DATABASE_USE_SSL=false` suele ser suficiente.
