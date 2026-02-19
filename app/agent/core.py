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
- Para resúmenes, totales o "cuánto gasté" → get_monthly_summary.
- Para ver los últimos gastos → get_recent_expenses.
- Para buscar un gasto específico → search_expenses.
- Para borrar el último gasto → delete_last_expense.
- Para el link de la planilla → get_sheet_url.

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

    async def process(self, phone: str, user_text: str) -> str:
        """
        Procesa un mensaje del usuario y retorna la respuesta del agente.
        Actualiza el historial de conversación en memoria.
        """
        # Registrar usuario si es nuevo (operación rápida con caché de gspread)
        if self.sheets is not None:
            try:
                self.sheets.ensure_user(phone)
            except Exception as e:
                logger.warning("Error en ensure_user para %s: %s", phone, e)

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
