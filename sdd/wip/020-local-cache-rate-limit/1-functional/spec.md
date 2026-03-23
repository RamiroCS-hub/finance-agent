# Functional Spec: Local Cache Rate Limit

**Feature**: `020-local-cache-rate-limit`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23

## Overview

Esta feature reemplaza el backend distribuido del rate limit por un cache local en memoria del proceso. El objetivo es preservar la protección operativa del webhook sin exigir Redis como dependencia para el despliegue del bot.

El comportamiento visible hacia Meta y hacia el usuario debe permanecer estable: los mensajes excedidos no se procesan, el webhook sigue respondiendo correctamente y el sistema puede avisar al usuario con un cooldown para no repetir advertencias. La diferencia principal es operativa: el estado del límite vive en memoria local y ya no se comparte entre réplicas.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Envía mensajes al bot y puede quedar temporalmente limitado por exceso de tráfico. |
| Webhook del bot | Evalúa el cupo antes de encolar trabajo costoso. |
| Cache local del proceso | Guarda contadores y cooldowns temporales mientras vive la instancia del backend. |

## Requirements

### REQ-01: Límite local por número antes del procesamiento pesado

El sistema MUST evaluar un cupo configurable por número de WhatsApp antes de encolar OCR, transcripción o procesamiento del agente, usando un estado local del proceso.

#### Scenarios

**Scenario 01: Mensaje dentro del límite**
```text
Given un número de WhatsApp con tráfico por debajo del umbral configurado en la instancia actual
When llega un mensaje soportado al webhook
Then el sistema permite el procesamiento normal y encola la tarea de background
```

**Scenario 02: Mensaje por encima del límite**
```text
Given un número de WhatsApp que ya consumió su cupo en la ventana activa de la instancia actual
When llega un nuevo mensaje soportado al webhook
Then el sistema no encola procesamiento pesado para ese mensaje
```

### REQ-02: Consistencia local explícita y sin dependencias externas

El rate limit MUST operar sin Redis ni otro servicio externo y SHOULD dejar explícito que el enforcement es local a la instancia en ejecución.

#### Scenarios

**Scenario 01: Arranque sin Redis**
```text
Given un entorno donde no existe REDIS_URL
When la aplicación inicia con el rate limit habilitado
Then el webhook puede operar igualmente usando el cache local
```

**Scenario 02: Réplicas múltiples**
```text
Given dos instancias del backend sin estado compartido
When un mismo número reparte mensajes entre ambas
Then la documentación aclara que el límite se aplica por instancia y no globalmente
```

### REQ-03: Expiración y notificación mínima

El sistema MUST expirar contadores y cooldowns locales al terminar su ventana correspondiente y MAY avisar al usuario cuando queda limitado, evitando repeticiones excesivas dentro del cooldown.

#### Scenarios

**Scenario 01: Nueva ventana**
```text
Given un número que agotó su cupo en la ventana anterior
When comienza una nueva ventana de tiempo
Then el sistema vuelve a permitir mensajes según el umbral configurado
```

**Scenario 02: Exceso repetido en la misma ventana**
```text
Given un número que sigue enviando mensajes mientras está limitado
When el webhook vuelve a bloquear esos mensajes
Then el sistema no repite la advertencia en cada intento durante el cooldown configurado
```

## Brownfield Annotations

<!-- extends: sdd/wip/015-whatsapp-number-rate-limit/1-functional/spec.md -->

Esta feature reemplaza la dependencia operativa de Redis introducida en la feature 015, pero preserva el objetivo funcional de proteger el webhook antes del trabajo pesado.

## Out of Scope

- Garantías globales entre múltiples procesos o nodos.
- Persistencia del estado del rate limit entre reinicios del backend.
