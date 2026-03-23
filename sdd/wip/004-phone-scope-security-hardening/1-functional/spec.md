# Functional Spec: Phone Scope Security Hardening

**Feature**: `004-phone-scope-security-hardening`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature endurece la seguridad del producto para que cada identidad de WhatsApp solo pueda operar dentro de su propio ambito legitimo. La confianza en el numero remitente no puede apoyarse unicamente en el contenido del payload; tambien debe existir validacion del origen del webhook y controles de acceso consistentes sobre los recursos expuestos.

El objetivo es reducir la superficie de impersonacion, consulta indebida y exposicion accidental de informacion compartida. La experiencia funcional del usuario legitimo debe mantenerse igual o mejorar.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario legitimo de WhatsApp | Interactua con el bot sobre sus propios datos. |
| Meta WhatsApp Cloud API | Origen legitimo de webhooks hacia la aplicacion. |
| Actor malicioso | Intenta enviar requests falsos o consultar datos fuera de su ambito. |

## Requirements

### REQ-01: Autenticidad del webhook

El sistema MUST verificar la autenticidad del request entrante antes de confiar en el numero remitente o ejecutar logica de negocio.

#### Scenarios

**Scenario 01: Request valido de Meta**
```text
Given un request genuino emitido por Meta
When llega al endpoint POST /webhook con los headers esperados
Then el sistema acepta el evento y puede continuar el procesamiento normal
```

**Scenario 02: Request forjado**
```text
Given un request enviado por un tercero sin autenticidad valida
When intenta invocar POST /webhook con un numero arbitrario
Then el sistema rechaza el request y no procesa ningun mensaje
```

### REQ-02: Aislamiento por entidad autenticada

Toda accion sensible MUST ejecutarse solo dentro del ambito de la entidad autenticada, ya sea usuario individual o contexto grupal autorizado.

#### Scenarios

**Scenario 01: Usuario consulta sus propios datos**
```text
Given un usuario legitimo autenticado por el webhook
When solicita resumenes o busquedas
Then el sistema responde solo con informacion de su ambito permitido
```

**Scenario 02: Intento de acceso fuera de alcance**
```text
Given una operacion que resolveria datos de otra entidad
When el agente o una tool intenta ejecutarla sin autorizacion valida
Then el sistema la bloquea y no filtra informacion sensible
```

### REQ-03: Reduccion de exposicion de recursos compartidos

El sistema SHOULD evitar devolver identificadores o enlaces que otorguen acceso mas amplio del necesario.

#### Scenarios

**Scenario 01: Recurso compartido expuesto al usuario**
```text
Given una herramienta que hoy devuelve un recurso global
When se aplica el hardening
Then el sistema entrega una alternativa acotada o restringe esa salida
```

**Scenario 02: Regresion funcional legitima**
```text
Given un usuario que realiza una consulta permitida
When el hardening entra en vigor
Then la funcionalidad permitida sigue operando sin fuga de datos
```

## Brownfield Annotations

<!-- overrides: sdd/wip/001-finance-org-wpp-reverse-eng/1-functional/spec.md#REQ-01 -->
<!-- extends: sdd/wip/001-finance-org-wpp-reverse-eng/1-functional/spec.md#REQ-02 -->

## Out of Scope

- Introducir login propio o cuentas con password.
- Resolver controles de acceso para un panel web que hoy no existe.
