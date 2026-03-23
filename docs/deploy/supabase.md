# Deploy con Supabase

## Qué sí vive en Supabase

- PostgreSQL administrado
- Gasto operativo del bot
- Migraciones del esquema relacional
- Variables y secretos asociados a la capa de datos

## Qué no vive en Supabase en el estado actual

- El webhook FastAPI
- El loop del agente
- Las integraciones con WhatsApp, LLM y transcripción
- Google Sheets salvo que quieras importar histórico legacy

En el estado actual, Supabase es la plataforma de datos. El runtime web sigue siendo un servicio Python aparte.

## Configuración

Definí `DATABASE_URL` con la cadena de conexión de Supabase. La app acepta:

- `postgresql+asyncpg://...`
- `postgresql://...`
- `postgres://...`

Las dos últimas se normalizan automáticamente a `asyncpg`.

## Checklist mínima

1. Crear el proyecto en Supabase.
2. Obtener la connection string de Postgres.
3. Configurar `DATABASE_URL` en el runtime del backend.
4. Ejecutar migraciones de Alembic antes de abrir tráfico.
5. Verificar arranque de la app y apertura de sesión de DB.
6. Confirmar que las otras credenciales siguen disponibles:
   - WhatsApp Cloud API
   - LLM provider
   - Groq si se usan audios
   - Google Sheets solo si vas a importar histórico legacy

## Smoke checks

```bash
pytest -q tests/test_config.py
```

Validaciones manuales recomendadas:

1. Arranque del backend sin error de conexión.
2. `GET /webhook` responde correctamente.
3. Un `POST /webhook` válido puede crear o recuperar usuario en PostgreSQL y persistir gastos ahí.

## Riesgos conocidos

- El webhook no corre dentro de Supabase; necesitás un host para FastAPI.
- Si tenés histórico en Sheets, todavía necesitás una corrida explícita de importación para consolidarlo en DB.
