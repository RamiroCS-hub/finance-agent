# Functional Spec: Tools To Skills Separation

**Feature**: `013-tools-to-skills-separation`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta refactorización separa el registro de tools del agente en skills o módulos orientados a dominio. El objetivo no es cambiar lo que el bot sabe hacer, sino mejorar mantenibilidad, testabilidad y velocidad para agregar nuevas capacidades sin seguir engordando un único archivo.

## Actors

| Actor | Description |
|-------|-------------|
| Desarrollador del producto | Agrega o modifica capacidades del agente. |
| Agente de WhatsApp | Sigue exponiendo las mismas tools observables hacia el LLM. |

## Requirements

### REQ-01: Composición por skills

El sistema MUST permitir agrupar tools por dominio funcional sin perder el contrato observable actual.

#### Scenarios

**Scenario 01: Registro de skills**
```text
Given un conjunto de capacidades del agente
When se construye el registry
Then las definiciones se componen desde varias skills y no desde un único bloque monolítico
```

**Scenario 02: Contrato estable**
```text
Given una tool existente
When el refactor queda aplicado
Then su nombre, schema y comportamiento observable permanecen compatibles
```

### REQ-02: Contexto compartido

El sistema MUST inyectar un contexto común para que cada skill opere con el mismo teléfono, chat type y servicios disponibles.

#### Scenarios

**Scenario 01: Contexto privado**
```text
Given una conversación privada
When una skill ejecuta una tool
Then recibe el mismo contexto autenticado que hoy usa el ToolRegistry
```

**Scenario 02: Contexto grupal**
```text
Given una conversación grupal
When una skill grupal ejecuta una tool
Then conserva el scope del grupo y no mezcla contexto con otras skills
```

### REQ-03: Testabilidad aislada

El sistema SHOULD facilitar tests por skill además de tests integrados del registro final.

#### Scenarios

**Scenario 01: Test unitario por skill**
```text
Given una skill individual
When se testea una tool de ese dominio
Then puede validarse sin depender de todas las demás skills
```

**Scenario 02: Test de composición**
```text
Given el registry final
When se listan las tools disponibles
Then la composición final coincide con el conjunto esperado
```

## Out of Scope

- Cambios de UX conversacional.
- Nuevas capacidades de negocio.
