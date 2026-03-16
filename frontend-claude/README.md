# Frontend Claude

Landing estatica para Tesorero con waitlist enviada por email usando FormSubmit, sin backend propio.

## Deploy en Vercel

Configura el proyecto con:

- Root Directory: `frontend-claude`
- Framework Preset: `Other`
- Build Command: vacio

## Como funciona

El formulario hace un `POST` a `https://formsubmit.co/ajax/ramirocarnicersouble8@gmail.com`.
Cuando alguien se anota, FormSubmit reenvia la inscripcion por email.

La primera vez que se use el formulario, FormSubmit manda un correo de activacion al destinatario. Hay que confirmarlo una sola vez para habilitar el flujo.

## Uso

- Landing publica: `index.html`
- Admin informativo: `admin.html`

No hay backend ni base de datos. Si queres persistencia real despues, conviene volver a Sheets o a una base.
