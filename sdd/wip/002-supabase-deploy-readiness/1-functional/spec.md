# Functional Spec: Supabase Deploy Readiness

**Feature**: `002-supabase-deploy-readiness`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature define las condiciones necesarias para desplegar el producto con Supabase como plataforma de datos sin generar falsas suposiciones sobre el runtime. El resultado esperado no es solo una cadena de conexion valida, sino un contrato operativo claro sobre que parte del sistema vive en Supabase y que parte sigue corriendo como servicio Python externo.

Tambien debe dejar una ruta reproducible para ambientes nuevos, incluyendo secretos, migraciones, conectividad y smoke checks. La experiencia para el operador debe ser deterministica y documentada.

## Actors

| Actor | Description |
|-------|-------------|
| Operador del sistema | Configura variables, ejecuta migraciones y valida el deploy. |
| Servicio backend | Se conecta a la base de datos y expone el webhook del bot. |
| Proyecto Supabase | Provee PostgreSQL administrado y recursos asociados al entorno. |

## Requirements

### REQ-01: Contrato de despliegue explicito

El sistema MUST documentar de forma explicita que componentes se despliegan en Supabase y cuales requieren un runtime externo.

#### Scenarios

**Scenario 01: Operador revisa el modelo de despliegue**
```text
Given un operador que necesita desplegar el producto
When consulta la documentacion de deploy
Then encuentra una separacion clara entre base de datos Supabase y servicio backend externo
```

**Scenario 02: Evitar una expectativa incorrecta sobre el runtime**
```text
Given un operador que asume que Supabase puede alojar la aplicacion actual sin cambios mayores
When sigue la guia de despliegue
Then la documentacion aclara que el webhook FastAPI requiere un runtime compatible separado
```

### REQ-02: Conexion y migraciones compatibles

El backend MUST poder conectarse a Supabase Postgres con configuracion soportada y SHALL poder ejecutar migraciones sobre ese entorno de forma reproducible.

#### Scenarios

**Scenario 01: Conexion valida a Supabase**
```text
Given credenciales validas de Supabase
When el backend inicia con la configuracion documentada
Then puede abrir conexiones a PostgreSQL sin requerir cambios manuales ad hoc
```

**Scenario 02: Migracion en entorno nuevo**
```text
Given un proyecto Supabase vacio
When el operador ejecuta las migraciones documentadas
Then el esquema requerido por la aplicacion queda creado correctamente
```

### REQ-03: Preparacion operativa minima

El proceso de despliegue SHOULD incluir secretos, smoke checks y validaciones minimas para reducir errores de configuracion.

#### Scenarios

**Scenario 01: Checklist previo al deploy**
```text
Given un operador antes de publicar una nueva instancia
When revisa la guia de puesta en marcha
Then dispone de una checklist de variables, migraciones y verificaciones basicas
```

**Scenario 02: Falla por configuracion faltante**
```text
Given una variable critica ausente o invalida
When el operador ejecuta el deploy
Then la documentacion indica como detectarla y corregirla sin ambiguedad
```

## Brownfield Annotations

<!-- extends: sdd/wip/001-finance-org-wpp-reverse-eng/2-technical/spec.md#architecture-overview -->

## Out of Scope

- Reescribir el backend actual como edge functions nativas de Supabase.
- Migrar obligatoriamente Google Sheets fuera del flujo actual en esta primera etapa.
