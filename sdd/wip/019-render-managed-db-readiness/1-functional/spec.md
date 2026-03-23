# Functional Spec: Render Managed DB Deploy Readiness

**Feature**: `019-render-managed-db-readiness`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature define cómo debe desplegarse el producto cuando la base de datos vive como servicio administrado en Render y no como contenedor de producción. El objetivo es que el operador tenga un contrato operativo claro: la app FastAPI corre como servicio web independiente, PostgreSQL corre como recurso administrado por la plataforma y Docker queda restringido al desarrollo local.

También debe dejar un camino reproducible para configurar variables, correr migraciones y verificar dependencias mínimas antes de abrir tráfico. La salida esperada no es solo "conectar la app a otra URL", sino eliminar la ambigüedad entre entorno local y entorno productivo.

## Actors

| Actor | Description |
|-------|-------------|
| Operador del sistema | Configura Render, variables, migraciones y valida el readiness del deploy. |
| Servicio backend | Ejecuta FastAPI, recibe webhooks y consume PostgreSQL más dependencias runtime según la configuración activa. |
| Servicio PostgreSQL de Render | Provee la base de datos relacional administrada usada por la app en producción. |
| Desarrollador local | Usa Docker solo para levantar dependencias locales sin replicar la topología productiva completa. |

## Requirements

### REQ-01: Contrato de despliegue separado entre app y base de datos

El sistema MUST documentar y configurar explícitamente que el runtime del backend y la base de datos de producción viven como servicios separados en Render.

#### Scenarios

**Scenario 01: Operador revisa el deploy target**
```text
Given un operador que necesita publicar el backend en Render
When consulta los artefactos de deploy y la documentación
Then encuentra que la app web y PostgreSQL están definidos como servicios separados
```

**Scenario 02: Evitar la suposición de base embebida**
```text
Given un operador acostumbrado al entorno local con Docker
When prepara producción en Render
Then la guía deja claro que PostgreSQL no corre dentro del contenedor de la aplicación
```

### REQ-02: Conexión y migraciones reproducibles sobre Render Postgres

El backend MUST poder arrancar usando una conexión inyectada por Render y SHALL tener un flujo reproducible para aplicar migraciones antes de recibir tráfico.

#### Scenarios

**Scenario 01: Arranque con base administrada**
```text
Given un servicio web con la cadena de conexión de Render configurada
When la aplicación inicia
Then puede crear sesiones contra PostgreSQL sin requerir cambios manuales fuera de configuración
```

**Scenario 02: Provisionar un entorno nuevo**
```text
Given una base Render nueva sin esquema aplicado
When el operador ejecuta el flujo documentado de migración
Then el esquema requerido por la aplicación queda creado de forma reproducible
```

### REQ-03: Docker queda restringido al desarrollo local

La solución SHOULD preservar `docker-compose` como herramienta de desarrollo local y MUST evitar que se interprete como mecanismo de base de datos para producción.

#### Scenarios

**Scenario 01: Desarrollador local levanta dependencias**
```text
Given un desarrollador trabajando en local
When ejecuta la infraestructura de desarrollo
Then obtiene Postgres y Redis locales mediante Docker sin alterar el contrato productivo
```

**Scenario 02: Operador no usa compose en producción**
```text
Given un operador siguiendo la guía de Render
When despliega el backend productivo
Then no necesita levantar `docker-compose` ni un contenedor de PostgreSQL para que la app funcione
```

### REQ-04: Dependencias operativas adicionales quedan explícitas

El proceso de deploy MUST exponer qué dependencias aparte de PostgreSQL siguen siendo necesarias en producción y cómo resolverlas.

#### Scenarios

**Scenario 01: Rate limiting en producción**
```text
Given un operador que quiere mantener el rate limiting activo
When prepara el deploy en Render
Then la guía indica que el primer deploy usa un cache local por instancia y no requiere Redis para esa función
```

**Scenario 02: Falta una dependencia de runtime**
```text
Given una configuración productiva incompleta
When el operador revisa la checklist de readiness
Then puede identificar si faltan migraciones, variables críticas o aclaraciones sobre el alcance local del rate limit antes de abrir tráfico
```

## Brownfield Annotations

<!-- extends: sdd/wip/002-supabase-deploy-readiness/1-functional/spec.md -->

Esta feature reaprovecha la decisión previa de separar runtime y plataforma de datos, pero la aterriza al contrato operativo concreto de Render y reemplaza la orientación a Supabase como target principal de despliegue.

## Out of Scope

- Ejecutar PostgreSQL dentro del contenedor de la app en producción.
- Reescribir el backend actual para otro runtime o plataforma.
- Migrar el dominio financiero o Google Sheets como parte de esta iteración.
