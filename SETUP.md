# Guía de Setup — Bot de Gastos WhatsApp

Paso a paso para configurar el `.env` y tener el bot funcionando.

---

## 1. Google Sheets (Spreadsheet + Credenciales)

### 1.1 Crear proyecto en Google Cloud

1. Ir a [Google Cloud Console](https://console.cloud.google.com/).
2. Crear un proyecto nuevo (ej: "bot-gastos-wpp").
3. En el menú lateral: **APIs & Services → Library**.
4. Buscar **Google Sheets API** → **Enable**.

### 1.2 Crear Service Account

1. Ir a **APIs & Services → Credentials**.
2. Click en **Create Credentials → Service Account**.
3. Nombre: `bot-gastos` (el que quieras).
4. Click en **Done** (no hace falta dar roles extra).
5. Click en el service account recién creado.
6. Ir a la pestaña **Keys → Add Key → Create new key → JSON**.
7. Se descarga un archivo `.json`. **Mover ese archivo a** `credentials/service_account.json` dentro del proyecto.

### 1.3 Crear el Spreadsheet

1. Ir a [Google Sheets](https://sheets.google.com/) y crear un spreadsheet nuevo.
   - Nombre sugerido: "Bot Gastos WhatsApp".
2. **Copiar el ID del spreadsheet** desde la URL:
   ```
   https://docs.google.com/spreadsheets/d/ESTE_ES_EL_ID/edit
   ```
3. **Compartir el spreadsheet** con el email de la service account:
   - Abrir el JSON de credenciales y buscar `"client_email"`.
   - En el spreadsheet: **Compartir → pegar ese email → Editor → Enviar**.

### 1.4 Configurar en `.env`

```env
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials/service_account.json
GOOGLE_SPREADSHEET_ID=ESTE_ES_EL_ID
```

> El bot crea automáticamente la hoja "Usuarios" y una hoja de gastos por cada número que escriba.

---

## 2. WhatsApp (Meta Cloud API)

### 2.1 Crear App en Meta

1. Ir a [Meta for Developers](https://developers.facebook.com/).
2. Click en **My Apps → Create App**.
3. Elegir tipo **Business** → Siguiente.
4. Nombre de la app (ej: "Bot Gastos") → **Create App**.

### 2.2 Configurar WhatsApp

1. En el dashboard de la app, buscar el producto **WhatsApp** → **Set Up**.
2. Anotar:
   - **Phone Number ID** (en la sección "From"): va en `WHATSAPP_PHONE_NUMBER_ID`.
   - **Temporary Access Token**: va en `WHATSAPP_TOKEN`.

### 2.3 Configurar Webhook

1. En la sección **Configuration → Webhook**:
   - **Callback URL**: la URL de tu servidor + `/webhook` (ej: `https://tu-app.railway.app/webhook`).
   - **Verify Token**: un string cualquiera que vos elijas (ej: `mi_token_secreto`).
2. Suscribirse al campo **messages**.

### 2.4 Número de prueba

En modo desarrollo, Meta te da un número de prueba. Podés enviarle mensajes desde hasta 5 números que configures en **Quickstart → Add phone number**.

### 2.5 Configurar en `.env`

```env
WHATSAPP_TOKEN=EAAxxxxxx...
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=mi_token_secreto
```

> **Nota**: El token temporal de Meta expira en 24hs. Para producción necesitás un **System User Token** permanente (desde Business Settings → System Users).

---

## 3. Gemini (LLM para parsing — Gratis)

### 3.1 Obtener API Key

1. Ir a [Google AI Studio](https://aistudio.google.com/).
2. Click en **Get API Key → Create API Key**.
3. Seleccionar el proyecto de Google Cloud (o crear uno nuevo).
4. Copiar la API key.

### 3.2 Configurar en `.env`

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.0-flash
```

> El tier gratuito de Gemini permite 15 requests/minuto y 1M tokens/minuto. Más que suficiente para uso personal y testing.

---

## 4. DeepSeek (Opcional — Para producción)

### 4.1 Obtener API Key

1. Ir a [DeepSeek Platform](https://platform.deepseek.com/).
2. Crear cuenta → Ir a **API Keys**.
3. Crear una key nueva y copiarla.

### 4.2 Configurar en `.env`

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
```

> Solo cambiar `LLM_PROVIDER` de `gemini` a `deepseek`. No hace falta tocar código.

---

## 5. Opciones de la App

```env
# Moneda por defecto (ISO 4217). El bot asume esta moneda salvo que el usuario diga otra.
DEFAULT_CURRENCY=ARS

# Números autorizados (separados por coma). Vacío = cualquiera puede usar el bot.
ALLOWED_PHONE_NUMBERS=

# Timeout del LLM en segundos. Si se excede, usa el regex fallback.
LLM_TIMEOUT_SECONDS=5

# Nivel de log: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

---

## 6. Levantar el Bot

```bash
# Instalar dependencias
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copiar y completar el .env
cp .env.example .env
# Editar .env con tus valores

# Levantar el servidor
uvicorn app.main:app --reload --port 8000
```

### Para testing local con ngrok:

```bash
# En otra terminal
ngrok http 8000
```

Copiar la URL de ngrok (ej: `https://abc123.ngrok-free.app`) y configurarla como Callback URL del webhook en Meta.

---

## Checklist Final

- [ ] `credentials/service_account.json` existe y es válido
- [ ] El spreadsheet está compartido con el email de la service account
- [ ] `GOOGLE_SPREADSHEET_ID` tiene el ID correcto
- [ ] `WHATSAPP_TOKEN` tiene un token válido (no expirado)
- [ ] `WHATSAPP_PHONE_NUMBER_ID` tiene el ID del número
- [ ] `WHATSAPP_VERIFY_TOKEN` coincide con el configurado en Meta
- [ ] `GEMINI_API_KEY` tiene una key válida de Google AI Studio
- [ ] El webhook de Meta apunta a tu URL + `/webhook`
- [ ] El campo `messages` está suscrito en el webhook
