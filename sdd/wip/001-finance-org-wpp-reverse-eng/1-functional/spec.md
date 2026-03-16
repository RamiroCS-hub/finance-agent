# Functional Spec: Finance Org WPP Reverse Engineering

**Feature**: `001-finance-org-wpp-reverse-eng`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-13

> **NOTA**: Esta spec fue generada por reverse engineering del código existente.
> Puede estar incompleta o imprecisa. Verificar contra el código fuente antes de usar como referencia.
> Generada el 2026-03-13 por sdd-reverse-engineer.

## Overview

El sistema es un bot de WhatsApp orientado a finanzas personales que recibe mensajes por webhook, decide si debe procesarlos y responde con ayuda conversacional para registrar gastos, consultar resúmenes y ejecutar utilidades relacionadas. La interacción principal ocurre en chats privados de WhatsApp, aunque existen capacidades parciales para grupos, paywall por plan y procesamiento de audio.

El comportamiento observable está repartido entre el webhook, el agente LLM, Google Sheets, una base de datos PostgreSQL y servicios externos de WhatsApp, LLM y transcripción. Parte de la documentación del repositorio describe funcionalidades futuras; esta spec cubre solo lo que el código y los tests muestran como implementado o intencionado de forma directa.

## Actors

| Actor | Description |
|-------|-------------|
| Usuario de WhatsApp | Persona que envía mensajes de texto, audio o imagen al bot para gestionar gastos. |
| Participante de grupo | Usuario que interactúa con el bot dentro de un grupo, siempre que mencione explícitamente al bot. |
| Administrador del sistema | Operador que configura credenciales, proveedores, whitelist y planes fuera del flujo conversacional. |
| Servicios externos | Meta WhatsApp Cloud API, Google Sheets, proveedor LLM y Groq para transcripción. |

## Requirements

### REQ-01: Verificación e ingesta del webhook

El sistema MUST exponer un endpoint de verificación de webhook y MUST aceptar payloads entrantes de Meta sin provocar reintentos innecesarios cuando el contenido no es procesable.

#### Scenarios

**Scenario 01: Verificación exitosa del webhook**
```text
Given que Meta invoca la verificación del webhook con el token configurado
When el sistema recibe una petición GET a /webhook con hub.mode=subscribe y un hub.verify_token válido
Then el sistema responde con el hub.challenge provisto por Meta
```

**Scenario 02: Token inválido en la verificación**
```text
Given que Meta o un tercero invoca la verificación con un token distinto al configurado
When el sistema recibe una petición GET a /webhook
Then el sistema rechaza la verificación con estado 403
```

**Scenario 03: Payload sin mensaje utilizable**
```text
Given que WhatsApp envía un POST sin mensajes o con un body inválido
When el sistema procesa la petición POST a /webhook
Then el sistema responde 200 con estado ok y no intenta procesar al agente
```

### REQ-02: Filtrado inicial del mensaje antes del agente

El sistema MUST decidir si un mensaje es elegible para procesamiento según tipo de mensaje, whitelist y contexto de grupo antes de invocar al agente.

#### Scenarios

**Scenario 01: Mensaje privado permitido**
```text
Given un mensaje privado de un número permitido y un tipo soportado
When el webhook recibe el evento
Then el sistema encola el procesamiento del mensaje para el agente
```

**Scenario 02: Número fuera de whitelist**
```text
Given que existe una whitelist configurada y el número remitente no pertenece a ella
When el webhook recibe el mensaje
Then el sistema ignora el mensaje y no envía respuesta
```

**Scenario 03: Mensaje grupal sin mención**
```text
Given un mensaje proveniente de un grupo de WhatsApp
When el texto no contiene la mención @Tesorero
Then el sistema ignora el mensaje y no activa el agente
```

**Scenario 04: Mensaje de grupo con mención**
```text
Given un mensaje grupal que incluye @Tesorero
When el webhook lo recibe
Then el sistema elimina la mención del texto y procesa el resto del mensaje
```

### REQ-03: Asistencia conversacional para gestión de gastos

El sistema MUST responder en español por WhatsApp usando un agente conversacional que pueda decidir entre contestar directamente o usar herramientas para registrar y consultar gastos.

#### Scenarios

**Scenario 01: Registro de gasto a partir de un mensaje claro**
```text
Given que el usuario envía un mensaje con monto y descripción de gasto
When el agente interpreta que corresponde registrar un gasto
Then el sistema persiste el gasto y responde con una confirmación breve
```

**Scenario 02: Consulta de resumen o historial**
```text
Given que el usuario pide un resumen, un total o los últimos gastos
When el agente interpreta la intención
Then el sistema consulta la información almacenada y devuelve una respuesta resumida
```

**Scenario 03: Herramienta desconocida o error interno**
```text
Given que el modelo intenta ejecutar una herramienta inválida o una herramienta falla
When el agente procesa la iteración
Then el sistema no se cae y conserva la conversación para que el modelo pueda recuperarse o terminar con un mensaje de fallback
```

**Scenario 04: Exceso de iteraciones del agente**
```text
Given que el modelo no logra terminar y sigue pidiendo herramientas
When el agente alcanza su máximo de iteraciones configurado
Then el sistema responde con un mensaje genérico de error y conserva el historial acumulado
```

### REQ-04: Persistencia de gastos y consultas en Google Sheets

El sistema MUST usar Google Sheets como almacenamiento operativo de usuarios y gastos, incluyendo altas de usuario, registración de filas y consultas derivadas de la conversación.

#### Scenarios

**Scenario 01: Primer uso de un usuario**
```text
Given un usuario que todavía no existe en la planilla
When el agente procesa su primer mensaje y el servicio de Sheets está disponible
Then el sistema registra al usuario en la hoja Usuarios y crea su hoja individual de gastos
```

**Scenario 02: Registro exitoso de gasto**
```text
Given un gasto válido interpretado por el agente
When se ejecuta la acción de registrar gasto
Then el sistema agrega una nueva fila con fecha, hora, monto, moneda, descripción y categoría
```

**Scenario 03: Búsqueda o resumen sobre gastos previos**
```text
Given que el usuario ya tiene gastos registrados
When el agente solicita resumen mensual, desglose por categoría, búsqueda o últimos gastos
Then el sistema calcula la información sobre la hoja del usuario y devuelve resultados serializables
```

**Scenario 04: Eliminación del último gasto**
```text
Given que el usuario tiene al menos un gasto registrado
When el agente solicita borrar el último gasto
Then el sistema identifica la última fila relevante y la elimina de la planilla
```

### REQ-05: Contexto conversacional y replies nativos

El sistema MUST mantener contexto temporal por usuario y SHOULD usar el reply nativo de WhatsApp para enriquecer el mensaje actual con el contenido previamente enviado por el bot.

#### Scenarios

**Scenario 01: Conversación multi-turno activa**
```text
Given que un usuario ya intercambió mensajes recientes con el bot
When envía un nuevo mensaje antes de que expire el TTL de conversación
Then el agente recibe el historial previo junto con el nuevo mensaje
```

**Scenario 02: Contexto expirado**
```text
Given que el usuario estuvo inactivo más allá del TTL configurado
When vuelve a escribir
Then el sistema inicia la conversación sin historial previo
```

**Scenario 03: Reply a un mensaje del bot**
```text
Given que el usuario responde usando la función nativa de reply de WhatsApp a un mensaje emitido por el bot
When el webhook recibe el identificador de mensaje referenciado
Then el agente incorpora una referencia textual breve del mensaje original en el nuevo input
```

### REQ-06: Control por plan y soporte de medios

El sistema MUST validar el plan del usuario antes de procesar medios y MUST bloquear tipos no permitidos por el plan vigente.

#### Scenarios

**Scenario 01: Usuario FREE envía audio o imagen**
```text
Given un usuario con plan FREE
When envía un mensaje de audio o imagen
Then el sistema responde con un mensaje de upsell y no procesa el contenido
```

**Scenario 02: Usuario PREMIUM envía audio**
```text
Given un usuario con plan PREMIUM
When envía un audio válido
Then el sistema descarga el medio, lo transcribe y pasa el texto transcripto al agente
```

**Scenario 03: Imagen recibida por un usuario habilitado**
```text
Given un usuario cuyo plan permite imágenes
When envía una imagen
Then el sistema responde que aún no puede leer texto en imágenes y termina el flujo sin invocar al agente
```

### REQ-07: Personalidad persistente por chat

El sistema SHOULD permitir generar o guardar instrucciones persistentes de comportamiento para un chat y MUST inyectarlas en el prompt del agente cuando existan.

#### Scenarios

**Scenario 01: Chat con personalidad guardada**
```text
Given que existe una configuración de personalidad para el usuario
When el agente arma el prompt del sistema
Then el sistema antepone esa personalidad al prompt base del asistente
```

**Scenario 02: Guardado de una nueva personalidad**
```text
Given que el agente decide persistir un nuevo estilo o conjunto de instrucciones
When se ejecuta la acción de guardar personalidad
Then el sistema crea o actualiza la configuración del chat en la base de datos
```

### REQ-08: Metas y contexto grupal persistente

El sistema MAY mantener datos persistentes de metas y grupos en base de datos, y actualmente expone esas capacidades de forma parcial al agente.

#### Scenarios

**Scenario 01: Actualización de progreso de meta individual**
```text
Given que existe una meta activa asociada al usuario
When el sistema registra un gasto mediante la herramienta correspondiente
Then el progreso de la meta se actualiza y el resultado puede incluir estado y mensaje de cumplimiento
```

**Scenario 02: Meta alcanzada**
```text
Given una meta activa cuyo monto objetivo se alcanza o supera
When se actualiza el progreso
Then el sistema marca la meta como completada y devuelve un mensaje invitando a crear una nueva meta
```

**Scenario 03: Consulta de grupos del usuario**
```text
Given que el usuario pertenece a uno o más grupos persistidos en base de datos
When el agente solicita información de grupos
Then el sistema devuelve los grupos asociados y las metas activas detectadas para cada uno
```

## Out of Scope

- OCR o extracción de texto desde imágenes.
- Sincronización bidireccional completa entre grupos de WhatsApp, miembros y goals más allá de lo que reflejan el modelo y las tools actuales.
- Actualización automática de cotizaciones de moneda desde una fuente externa.
- UI administrativa, onboarding visual o panel de gestión.
- Garantías de durabilidad de memoria conversacional más allá del proceso actual.
