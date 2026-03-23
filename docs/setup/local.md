# Setup Local

## Requisitos

- Python 3.11+
- Cuenta de Meta WhatsApp Cloud API
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
- La base guarda timestamps en UTC y la app muestra fecha/hora en la zona inferida por el prefijo telefónico del usuario.
- En grupos, el bot responde cuando detecta la mención configurada en `GROUP_BOT_MENTION`.
- Para OCR de tickets por imagen, necesitás `GEMINI_API_KEY` y opcionalmente `RECEIPT_OCR_MODEL`.
- Podés definir presupuestos por categoría y el bot devuelve alertas dentro del flujo cuando detecta exceso o un gasto fuera de patrón.
- Si querés comparativas educativas ajustadas por inflación, configurá `MONTHLY_INFLATION_RATE` con una tasa mensual de referencia.
- Para importar histórico legacy: `python scripts/import_expenses_from_sheets.py --dry-run`
- `ALLOWED_PHONE_NUMBERS` permite limitar números durante pruebas.
- Si pegás una URL `postgresql://` o `postgres://`, la app la normaliza a `postgresql+asyncpg://`.
