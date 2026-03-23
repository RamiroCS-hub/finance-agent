# Estado Técnico Actual

## Stack

- Backend: FastAPI
- Tests: pytest
- LLM: Gemini o DeepSeek/OpenRouter
- Audio: Groq Whisper
- Storage operativo: PostgreSQL
- Fuente legacy opcional: Google Sheets para importación histórica

## Flujo principal

1. Meta envía el webhook a `POST /webhook`
2. La app valida el request y parsea el mensaje
3. El procesamiento real corre en background
4. El agente usa tools para registrar o consultar gastos
5. La respuesta vuelve a WhatsApp

## Persistencia

- PostgreSQL guarda usuarios, gastos, presupuestos, planes, grupos, metas y configuraciones adicionales
- Google Sheets quedó relegado a importación histórica, fuera del camino crítico del bot
- Los timestamps se persisten en UTC y se presentan en la zona horaria inferida desde el número del usuario

## Estado funcional

- Registro y consulta de gastos personales operativos en DB
- OCR de tickets por imagen con extracción de monto y comercio
- Soporte grupal MVP para gastos compartidos, balances y metas grupales
- Presupuestos por categoría y alertas dentro del flujo conversacional por exceso o gasto inusual
- Comparativas de gasto e insights de fugas sobre el histórico del usuario
- Proyecciones de ahorro con escenarios manuales o basados en histórico y cruce opcional con metas
- Seguimiento de obligaciones futuras como cuotas y deudas simples
- Capa educativa con benchmark, fondo de emergencia, inflación opcional y tips
- Otras capacidades promocionadas en la landing siguen siendo roadmap y viven en `sdd/wip/`
