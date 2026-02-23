from __future__ import annotations

import json
import logging
from datetime import datetime

from app.agent.memory import ConversationMemory
from app.agent.tools import ToolRegistry
from app.models.agent import Message
from app.services.llm_provider import LLMProvider
from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
Sos un asistente de gestión de gastos personales para WhatsApp.

Fecha de hoy: {today}
Moneda por defecto: {currency}

COMPORTAMIENTO:
- Si el usuario menciona un gasto (monto + descripción), registralo con register_expense.
- Si el mensaje tiene solo un monto sin descripción, preguntá qué fue el gasto antes de registrar.
- CÁLCULOS: Si el mensaje involucra CUALQUIER operación matemática (porcentajes, IVA, \
impuestos, sumas de varios montos, descuentos, propinas, divisiones), usá la herramienta \
"calculate" PRIMERO para obtener el monto exacto y DESPUÉS llamá a register_expense con el resultado. \
NUNCA le pidas al usuario que haga la cuenta. Ejemplos:
  · "22% iva 200" → calculate("200 - 200 * 0.22") → register_expense con el resultado
  · "200 + 300 + 400 + IVA" → IVA default 21%, calculate("(200 + 300 + 400) * 1.21")
  · "1500 dividido 3 personas" → calculate("1500 / 3")
  · "850 + 3% impuesto" → calculate("850 * 1.03")
- MÚLTIPLES GASTOS en un mismo mensaje: Registrá cada uno por separado con register_expense, \
pero TODOS deben tener la MISMA categoría. Determiná la categoría por el item más descriptivo \
(el que claramente indica un rubro). Si un item tiene un nombre de persona en vez de descripción \
de gasto, usá la misma categoría y poné el nombre como observación. Ejemplos:
  · "10k santi 40k uber" → categoría Transporte para ambos. register_expense(40000, "uber", "Transporte") \
y register_expense(10000, "uber - SANTI", "Transporte")
  · "500 juan 300 almuerzo" → categoría Comida para ambos. register_expense(300, "almuerzo", "Comida") \
y register_expense(500, "almuerzo - JUAN", "Comida")
- RESÚMENES: Para resúmenes, totales o "cuánto gasté" → get_monthly_summary. Si el usuario NO \
especifica el mes, el sistema usa el mes anterior automáticamente si estamos antes del día 15 \
del mes actual, o el mes actual si ya pasó el día 15. No necesitás llamar con parámetros.
- Para ver los últimos gastos → get_recent_expenses.
- Para buscar un gasto específico → search_expenses.
- Para borrar el último gasto → delete_last_expense.
- Para el link de la planilla → get_sheet_url.
- Para mandar una foto de gatito → send_cat_pic.
- MONEDAS EXTRANJERAS: Si el usuario menciona un monto en USD, UYU, CLP o COP:
  1. Llamá convert_currency para obtener el equivalente en ARS
  2. Llamá register_expense con el monto en ARS, y pasá original_amount y original_currency 
     con los valores originales para que queden registrados en la planilla
  3. Informá al usuario ambos valores (original y convertido)

FORMATO:
- Respondé siempre en español, de forma concisa y amigable.
- Usá formato WhatsApp: *negrita* para totales y montos importantes.
- En resúmenes usá emojis por categoría: 🍔 Comida, 🚗 Transporte, 💊 Salud,\
 🛒 Supermercado, 🎮 Entretenimiento, 👕 Ropa, 📚 Educación, 🏠 Hogar, 📦 Otros.
"""


class AgentLoop:
    """
    Núcleo del agente: orquesta el reasoning loop entre el LLM y las herramientas.
    """

    def __init__(
        self,
        llm: LLMProvider,
        sheets: SheetsService,
        memory: ConversationMemory,
        max_iterations: int = 10,
    ) -> None:
        self.llm = llm
        self.sheets = sheets
        self.memory = memory
        self.max_iterations = max_iterations

    async def process(
        self,
        phone: str,
        user_text: str,
        replied_to_id: str | None = None,
    ) -> str:
        """
        Procesa un mensaje del usuario y retorna la respuesta del agente.
        Si replied_to_id está presente, busca el texto del mensaje referenciado
        y lo antepone al mensaje del usuario para que el LLM tenga contexto del reply.
        Actualiza el historial de conversación en memoria.
        """
        # Registrar usuario si es nuevo (operación rápida con caché de gspread)
        if self.sheets is not None:
            try:
                self.sheets.ensure_user(phone)
            except Exception as e:
                logger.warning("Error en ensure_user para %s: %s", phone, e)

        # Si el usuario respondió a un mensaje específico del bot, inyectar contexto
        if replied_to_id:
            referenced = self.memory.get_by_wamid(phone, replied_to_id)
            if referenced:
                # Truncar el mensaje referenciado para no inflar el contexto
                preview = referenced[:200] + "..." if len(referenced) > 200 else referenced
                user_text = f'[En respuesta a: "{preview}"]\n{user_text}'
                logger.debug("Reply detectado para %s → referencia: %s", phone, replied_to_id)
            else:
                logger.debug(
                    "Reply con wamid %s no encontrado en memoria para %s", replied_to_id, phone
                )

        messages = self.memory.get(phone) + [Message(role="user", content=user_text)]
        tools = ToolRegistry(self.sheets, phone)
        system_prompt = self._build_system_prompt()

        for iteration in range(self.max_iterations):
            logger.debug("Iteración %d del agente para %s", iteration + 1, phone)

            response = await self.llm.chat_with_tools(
                messages, tools.definitions(), system_prompt
            )

            if response.finish_reason == "stop":
                messages.append(Message(role="assistant", content=response.content))
                self.memory.append(phone, messages)
                return response.content or ""

            # finish_reason == "tool_use": ejecutar herramientas y continuar
            messages.append(Message(role="assistant", content=response.tool_calls))

            for tool_call in (response.tool_calls or []):
                try:
                    result = tools.run(tool_call.name, **tool_call.arguments)
                except Exception as e:
                    logger.error("Error en herramienta '%s': %s", tool_call.name, e)
                    result = {"error": str(e)}

                messages.append(
                    Message(
                        role="tool",
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                    )
                )

        # Agotadas las iteraciones
        logger.error("AgentLoop alcanzó MAX_ITERATIONS (%d) para %s", self.max_iterations, phone)
        self.memory.append(phone, messages)
        return "Hubo un problema procesando tu mensaje. Intentá de nuevo."

    def _build_system_prompt(self) -> str:
        from app.config import settings

        return SYSTEM_PROMPT_TEMPLATE.format(
            today=datetime.now().strftime("%Y-%m-%d"),
            currency=settings.DEFAULT_CURRENCY,
        )
