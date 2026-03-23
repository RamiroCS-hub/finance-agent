# Cómo obtener tu API Key de Groq

Groq ofrece un motor de inferencia de muy baja latencia, útil para transcribir audios de WhatsApp.

## Pasos

1. Crear una cuenta en `console.groq.com`.
2. Ir a `API Keys`.
3. Crear una nueva key y copiarla en el momento.
4. Configurarla en `.env`:

```env
GROQ_API_KEY=gsk_tu_clave_super_secreta_aqui
TRANSCRIPTION_MODEL=whisper-large-v3-turbo
```

## Nota

Groq no vuelve a mostrar la key luego de crearla. Si la perdés, tenés que generar una nueva.
