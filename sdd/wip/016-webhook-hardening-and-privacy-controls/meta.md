# Meta: Webhook Hardening and Privacy Controls

## Identificación
- **ID**: 016
- **Slug**: 016-webhook-hardening-and-privacy-controls
- **Tipo**: fix
- **Estado**: tasked

## Resumen
Cerrar degradaciones de seguridad todavía abiertas en el webhook, la configuración persistente grupal, los logs sensibles y la ingesta de media.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: fix/webhook-hardening-and-privacy-controls
- **Base branch**: main

## Artefactos
- [x] 1-functional/spec.md
- [x] 2-technical/spec.md
- [x] 3-tasks/tasks.json
- [ ] 4-implementation/progress.md
- [ ] 5-verify/report.md

## Fechas
- **Creada**: 2026-03-23
- **Última actualización**: 2026-03-23
- **Completada**: —

## Notas
- La feature `004-phone-scope-security-hardening` cerró la primera capa de hardening, pero el código actual todavía permite `POST /webhook` sin firma cuando `WHATSAPP_APP_SECRET` está vacío.
- Hoy cualquier mensaje grupal puede intentar persistir una personalidad/configuración compartida aunque no exista una autoridad verificable para ese cambio.
- Los logs actuales siguen incluyendo texto de mensajes y cuerpos de error remotos que pueden contener datos financieros o prompts sensibles.
- El pipeline de audio e imagen todavía no aplica límites de tamaño/tipo antes de OCR o transcripción.
