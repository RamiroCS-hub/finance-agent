# Meta: Landing CTA Priority

## Identificación
- **ID**: 014
- **Slug**: 014-landing-cta-priority
- **Tipo**: feature
- **Estado**: verifying

## Resumen
Acortar la landing y llevar el CTA principal de acceso al inicio para que la conversión no dependa de scrollear hasta el final.

## Stack detectado
- **Lenguaje**: Python + HTML/CSS/JavaScript
- **Framework**: FastAPI + landing estática vanilla
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: feature/landing-cta-priority
- **Base branch**: main

## Artefactos
- [x] 1-functional/spec.md
- [x] 2-technical/spec.md
- [x] 3-tasks/tasks.json
- [x] 4-implementation/progress.md
- [x] 5-verify/report.md

## Fechas
- **Creada**: 2026-03-23
- **Última actualización**: 2026-03-23
- **Completada**: —

## Notas
- La landing pública vive en `frontend-claude/` y hoy funciona como sitio estático sin backend propio.
- El formulario actual usa `FormSubmit` desde `frontend-claude/script.js` y depende de los IDs `waitlist-form` y `email-input`.
- La versión actual tenía hero + seis bloques largos antes del formulario final; la implementación lo recortó a hero, prueba, demo y cierre.
- Queda pendiente smoke visual manual en navegador para darla por cerrada sin riesgo de layout.
