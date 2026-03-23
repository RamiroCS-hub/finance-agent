# Deploy en Render

## Contrato de despliegue

- `anotamelo-api`: web service que corre FastAPI desde `Dockerfile`
- `anotamelo-db`: PostgreSQL administrado por Render
- Sin Redis en el contrato mínimo del primer deploy

Docker queda reservado para desarrollo local. En producción, la base no corre dentro del contenedor de la app.

## Artefactos del repo

- Blueprint: [render.yaml](/Users/rcarnicer/Desktop/anotamelo/render.yaml)
- Imagen de app: [Dockerfile](/Users/rcarnicer/Desktop/anotamelo/Dockerfile)
- Variables de ejemplo: [.env.example](/Users/rcarnicer/Desktop/anotamelo/.env.example)

## Variables clave

- `DATABASE_URL`: se inyecta desde Render Postgres con `fromDatabase.connectionString`
- `DATABASE_USE_SSL=false`: default pensado para la URL interna de Render
- `WHATSAPP_RATE_LIMIT_ENABLED=true`: el rate limit actual usa cache local por proceso
- `WHATSAPP_*`, `TELEGRAM_*`, `GEMINI_API_KEY`, `GROQ_API_KEY`: secretos cargados en Render con `sync: false`

Si usás una conexión externa o un proxy que exija SSL, activá `DATABASE_USE_SSL=true`.

## Flujo recomendado

1. Crear el Postgres de Render desde [render.yaml](/Users/rcarnicer/Desktop/anotamelo/render.yaml) o desde el dashboard.
2. Crear el web service `anotamelo-api` usando el mismo blueprint.
3. Cargar los secretos requeridos durante la creación del Blueprint.
4. Ejecutar migraciones antes de abrir tráfico.
   El blueprint ya define `preDeployCommand: python -m alembic upgrade head`.
5. Configurar los webhooks de Meta y Telegram apuntando al dominio público del servicio.

## Smoke checks

1. Verificar que el deploy completa build y `preDeployCommand` sin error.
2. Confirmar que el servicio arranca con `DATABASE_URL` inyectado y sin errores de conexión.
3. Probar `GET /webhook` con el verify token correcto.
4. Enviar un `POST /webhook` válido y confirmar que el backend procesa el mensaje.
5. Si Telegram está habilitado, probar `POST /telegram/webhook`.

## Trade-offs operativos

- El rate limit ya no depende de Redis.
- El rate limit es local por proceso: no se comparte entre réplicas.
- Si el proceso reinicia, los contadores y cooldowns se reinician.

Para una primera salida simple en Render, ese trade-off reduce complejidad y deja la infraestructura mínima en `web service + Postgres`.
