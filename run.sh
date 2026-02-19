#!/bin/bash

# Bot de Gastos WhatsApp — Script de inicio
# Levanta el servidor FastAPI + ngrok en paralelo

PORT=8080

# Verificar que existe el .env
if [ ! -f .env ]; then
    echo "ERROR: No se encontró el archivo .env"
    echo "Copiá .env.example a .env y completá los valores."
    exit 1
fi

# Crear venv si no existe
if [ ! -d venv ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

# Instalar dependencias
echo "Instalando dependencias..."
source venv/bin/activate
pip install --index-url https://pypi.org/simple/ -q -r requirements.txt

# Matar procesos previos en el puerto
lsof -ti:$PORT 2>/dev/null | xargs kill -9 2>/dev/null

# Levantar servidor
echo "Iniciando servidor en puerto $PORT..."
uvicorn app.main:app --port $PORT &
SERVER_PID=$!
sleep 2

# Verificar que arrancó
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "ERROR: El servidor no arrancó. Revisá los logs."
    exit 1
fi

# Levantar ngrok
if command -v ngrok &>/dev/null; then
    echo "Iniciando ngrok..."
    ngrok http $PORT --log=stdout &
    NGROK_PID=$!
    sleep 3
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)
    echo ""
    echo "============================================"
    echo "  Bot corriendo!"
    echo "============================================"
    echo "  Local:   http://localhost:$PORT"
    echo "  Público: $NGROK_URL"
    echo "  Webhook: $NGROK_URL/webhook"
    echo "============================================"
    echo ""
    echo "Ctrl+C para detener todo."
else
    echo ""
    echo "============================================"
    echo "  Bot corriendo (sin ngrok)"
    echo "============================================"
    echo "  Local: http://localhost:$PORT"
    echo "  Instalá ngrok para exponer públicamente."
    echo "============================================"
fi

# Esperar y limpiar al salir
trap "kill $SERVER_PID $NGROK_PID 2>/dev/null; echo 'Bot detenido.'; exit 0" INT TERM
wait
