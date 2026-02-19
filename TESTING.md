# Guía de Testing — Bot de WhatsApp con Cuenta Developer de Meta

Guía completa para probar el bot end-to-end usando el entorno de desarrollo de Meta (sin necesidad de verificación de la app).

> **Prerequisito**: Tener el `.env` configurado según `SETUP.md`. Las secciones de Google Sheets y Gemini deben estar listas antes de empezar.

---

## 1. Levantar el servidor local

```bash
# Activar venv e instalar dependencias
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copiar y completar el .env
cp .env.example .env
# Editar con tus claves (ver SETUP.md)

# Levantar el bot
uvicorn app.main:app --reload --port 8000
```

Deberías ver en los logs:
```
INFO     app.main: Iniciando bot de gastos (modo agente)...
INFO     app.main: Google Sheets conectado correctamente
INFO     app.main: Bot listo. Provider: gemini | TTL: 60min | Max iter: 10
```

---

## 2. Exponer el servidor con ngrok

Meta necesita una URL HTTPS pública para enviarle los mensajes. ngrok crea un túnel desde internet hasta tu `localhost:8000`.

### 2.1 Instalar ngrok

```bash
# macOS con Homebrew
brew install ngrok

# O descargar desde https://ngrok.com/download
```

### 2.2 Crear cuenta y autenticar (solo la primera vez)

1. Crear cuenta gratuita en [ngrok.com](https://ngrok.com).
2. Ir al [dashboard de ngrok](https://dashboard.ngrok.com/get-started/your-authtoken) y copiar tu authtoken.
3. Autenticar:
   ```bash
   ngrok config add-authtoken TU_AUTHTOKEN
   ```

### 2.3 Levantar el túnel

En una **segunda terminal** (con el servidor ya corriendo):

```bash
ngrok http 8000
```

Verás algo como:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

**Copiar esa URL HTTPS** — la vas a necesitar en el paso siguiente.

> **Importante**: La URL de ngrok cambia cada vez que reiniciás el túnel (plan free). Si reiniciás ngrok, tenés que actualizar el webhook en Meta.

---

## 3. Configurar la app en Meta Developer Portal

### 3.1 Crear la app (si no la tenés)

1. Ir a [developers.facebook.com](https://developers.facebook.com) → **My Apps → Create App**.
2. Elegir tipo **Business** → Siguiente.
3. Nombre: "Bot Gastos Dev" → **Create App**.

### 3.2 Agregar el producto WhatsApp

1. En el dashboard, buscar **WhatsApp** en la lista de productos → **Set Up**.
2. Aceptar los términos de servicio.

### 3.3 Anotar las credenciales

En **WhatsApp → API Setup**:

| Variable `.env`           | Dónde encontrarla                        |
|---------------------------|------------------------------------------|
| `WHATSAPP_TOKEN`          | "Temporary access token" (expira en 24h) |
| `WHATSAPP_PHONE_NUMBER_ID`| Campo "Phone number ID" (número de prueba) |

Copiar estos valores al `.env`:
```env
WHATSAPP_TOKEN=EAAxxxxxx...
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=mi_token_secreto   # el string que vos elijas
```

> El token temporal expira en **24 horas**. Si el bot deja de enviar mensajes, generá uno nuevo desde esta misma página.

### 3.4 Configurar el Webhook

1. En **WhatsApp → Configuration → Webhook** → click en **Edit**.
2. Completar:
   - **Callback URL**: `https://TU_URL_NGROK/webhook`
   - **Verify Token**: el mismo valor que pusiste en `WHATSAPP_VERIFY_TOKEN`
3. Click en **Verify and Save**.

Si la verificación falla, revisar:
- Que el servidor esté corriendo (`uvicorn` activo).
- Que ngrok esté corriendo y la URL sea la correcta.
- Que `WHATSAPP_VERIFY_TOKEN` en el `.env` coincida exactamente con lo que pusiste en Meta.

### 3.5 Suscribirse al campo `messages`

En la misma sección **Webhook**, click en **Manage** y activar el campo **messages**.

Sin este paso el bot no recibirá mensajes entrantes.

### 3.6 Agregar números de prueba

En modo desarrollo, solo pueden escribirle al bot los números que están en la lista de prueba.

1. Ir a **WhatsApp → API Setup → To**.
2. Click en **Manage phone number list**.
3. Agregar tu número de WhatsApp personal (con código de país, sin `+`).
   - Ejemplo: `5491123456789` para Argentina.
4. Meta enviará un mensaje de verificación al número.

---

## 4. Verificar la conexión

Antes de enviar mensajes reales, verificá que el webhook responde correctamente:

```bash
# Verificación manual del endpoint GET
curl "https://TU_URL_NGROK/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=mi_token_secreto"
# Debe responder: test123
```

En los logs del servidor deberías ver:
```
INFO     app.api.webhook: Webhook verificado correctamente
```

---

## 5. Casos de prueba

Enviar estos mensajes desde WhatsApp al número de prueba de Meta. Verificar tanto la respuesta del bot como la fila en el spreadsheet.

### 5.1 Registro de gastos

| Mensaje a enviar        | Respuesta esperada del bot                                  | Acción en Sheets         |
|-------------------------|-------------------------------------------------------------|--------------------------|
| `850 farmacia`          | Confirma registro con monto, descripción y categoría        | Nueva fila en Gastos_... |
| `$1200 uber`            | Confirma registro con Transporte                            | Nueva fila               |
| `gasté 3500 en super`   | Confirma registro con Supermercado                          | Nueva fila               |
| `500`                   | Pregunta qué fue el gasto (sin registrar aún)               | Sin cambios              |
| `500` → `almuerzo`      | Después de aclarar, registra $500 en Comida                 | Nueva fila               |

### 5.2 Consultas

| Mensaje a enviar        | Respuesta esperada                                          |
|-------------------------|-------------------------------------------------------------|
| `resumen`               | Total del mes + desglose por categoría con emojis           |
| `cuánto gasté este mes` | Igual que resumen                                           |
| `últimos gastos`        | Lista de los 5 gastos más recientes                         |
| `últimos 10`            | Lista de los 10 gastos más recientes                        |
| `link`                  | URL del Google Spreadsheet                                  |
| `planilla`              | Igual que link                                              |

### 5.3 Búsqueda y borrado

| Mensaje a enviar                  | Respuesta esperada                                    |
|-----------------------------------|-------------------------------------------------------|
| `buscar uber`                     | Lista de gastos con "uber" en la descripción          |
| `gastos del 1 al 15 de febrero`   | Lista filtrada por fechas                             |
| `borrar el último gasto`          | Confirma borrado con detalle del gasto eliminado      |
| `eliminar`                        | Igual que borrar                                      |

### 5.4 Contexto multi-turno

Estos casos verifican que la memoria conversacional funciona:

| Secuencia de mensajes                         | Comportamiento esperado                                   |
|-----------------------------------------------|-----------------------------------------------------------|
| `resumen` → `¿y el mes pasado?`               | Responde con datos de enero sin que lo repitas            |
| `500` → `uber` → `¿en qué categoría quedó?`   | Recuerda el gasto registrado y responde correctamente     |
| `nueva conversación`                          | Limpia el historial y empieza de cero                     |

### 5.5 Casos borde

| Mensaje a enviar        | Comportamiento esperado                                     |
|-------------------------|-------------------------------------------------------------|
| `hola`                  | Responde amigablemente y ofrece ayuda                       |
| `ayuda`                 | Explica qué puede hacer                                     |
| `abc xyz`               | Responde que no entendió y sugiere cómo usar el bot         |
| `0 cafe`                | Puede registrar monto 0 o preguntar si es correcto          |

---

## 6. Verificar en Google Sheets

Después de los tests de registro, abrir el spreadsheet y confirmar:

1. **Hoja "Usuarios"**: debe aparecer una fila con tu número de teléfono.
2. **Hoja "Gastos_54911..."** (con tu número): deben aparecer las filas de cada gasto registrado con las columnas:
   - `Fecha` | `Hora` | `Monto` | `Moneda` | `Descripción` | `Categoría` | `Cálculo` | `Mensaje Original`
3. Después del test de borrado: la última fila debe haber desaparecido.

---

## 7. Troubleshooting

### El bot no responde

1. **Revisar los logs del servidor** (`uvicorn`). ¿Llegan los POST al `/webhook`?
2. Si no llegan: revisar que el webhook esté configurado en Meta y suscripto a `messages`.
3. Si llegan pero hay error: leer el traceback en los logs.

### Error 403 en la verificación del webhook

- Verificar que `WHATSAPP_VERIFY_TOKEN` en `.env` sea idéntico al que pusiste en Meta (case-sensitive).
- Reiniciar el servidor después de cambiar el `.env`.

### "Token expirado" / no se envían respuestas

- El token temporal de Meta dura **24 horas**.
- Ir a **WhatsApp → API Setup** y generar un nuevo token.
- Actualizar `WHATSAPP_TOKEN` en `.env` y reiniciar el servidor.

### La URL de ngrok cambió

- Cada vez que reiniciás ngrok (plan free) cambia la URL.
- Ir a **WhatsApp → Configuration → Webhook → Edit** y actualizar la Callback URL.

### "Google Sheets no disponible" en los logs del startup

- Verificar que `credentials/service_account.json` existe y es válido.
- Verificar que `GOOGLE_SPREADSHEET_ID` es correcto.
- Verificar que el spreadsheet está compartido con el email de la service account (`client_email` en el JSON).

### El bot responde pero no guarda en Sheets

- Revisar logs por errores de `SheetsService`.
- Verificar permisos del spreadsheet (la service account debe ser **Editor**, no Viewer).

### El LLM no entiende el mensaje / responde en inglés

- Verificar que `GEMINI_API_KEY` es válida y no expiró.
- Probar con un mensaje más claro: `"850 farmacia"` en lugar de texto ambiguo.
- Si el modelo responde en inglés: puede ser un problema con el system prompt. Reiniciar el servidor.

---

## 8. Generar un token permanente (para no renovarlo cada 24h)

Para pruebas prolongadas conviene un **System User Token**:

1. Ir a [Meta Business Settings](https://business.facebook.com/settings).
2. En el menú lateral: **Users → System Users → Add**.
3. Asignar rol **Admin** al system user.
4. Click en **Generate New Token**.
5. Seleccionar la app → marcar el permiso `whatsapp_business_messaging`.
6. Copiar el token generado → actualizar `WHATSAPP_TOKEN` en `.env`.

> Este token no expira salvo que lo revoques manualmente.

---

## 9. Checklist de testing

```
Setup:
[ ] Servidor corriendo en localhost:8000
[ ] ngrok activo con URL HTTPS
[ ] .env configurado con token vigente

Meta Portal:
[ ] Webhook configurado con URL ngrok + /webhook
[ ] Webhook verificado (✅ en el portal)
[ ] Campo "messages" suscrito
[ ] Tu número en la lista de prueba

Tests básicos:
[ ] Registro de gasto simple (ej: "850 farmacia")
[ ] Nueva fila visible en Google Sheets
[ ] Consulta de resumen mensual
[ ] Últimos gastos
[ ] Link de la planilla

Tests avanzados:
[ ] Mensaje ambiguo → bot pide aclaración → registra
[ ] Consulta de mes anterior (contexto multi-turno)
[ ] Borrado del último gasto
[ ] Verificar que la fila desapareció del sheet
```
