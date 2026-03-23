from __future__ import annotations

import html
import json
import inspect
import logging
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.agent.memory import ConversationMemory
from app.agent.tools import ToolRegistry
from app.models.agent import Message
from app.services.expenses import ExpenseService
from app.services.channel_identity import ResolvedUserContext
from app.services.group_expenses import GroupExpenseService
from app.services.llm_provider import LLMProvider
from app.services.timezones import infer_timezone_for_phone, local_now_for_phone
from app.db.database import async_session_maker
from app.services.personality import get_custom_prompt

logger = logging.getLogger(__name__)
SYSTEM_PROMPT_PATH = Path(__file__).with_name("prompts") / "system_prompt.md"
FORMATTED_TOOL_REPLY_KEYS = (
    "formatted_confirmation",
    "formatted_result",
    "formatted_summary",
    "formatted_breakdown",
)


# Block-style markers:  "Response:\n\n<answer>"  or  "Final response:\n\n<answer>"
_BLOCK_RESPONSE_MARKER_RE = re.compile(
    r"(?:^|\n)(?:Final\s+)?[Rr]esponse:\s*\n+",
    re.MULTILINE,
)
# Inline marker:  "Final response: <answer on same line>"
_INLINE_RESPONSE_MARKER_RE = re.compile(
    r"(?:^|\n)Final\s+[Rr]esponse:\s+",
    re.MULTILINE,
)
# Reliable reasoning-text indicators (model is doing scratchpad, not responding)
_REASONING_FIRST_LINE_RE = re.compile(
    r"^(?:"
    r"The user (?:said|asked|wants|mentioned|registered)|"
    r"I need to |I(?:'ll| will) call|"
    r"The tool (?:call|response|result)|"
    r"We (?:are in|called |need )|"
    r"Since the user|"
    r"Okay,\s+the\s+user|"
    r"Note:\s+I"
    r")",
    re.IGNORECASE,
)


def _extract_response_from_plaintext_reasoning(text: str) -> str:
    """
    Remove scratchpad reasoning emitted as plain text.
    Three strategies (tried in order):
      1. Block marker  → "Response:\\n\\n<answer>" or "Final response:\\n\\n<answer>"
      2. Inline marker → "Final response: <answer>" (rest of text after marker)
      3. Heuristic     → first line looks like internal reasoning → keep only last paragraph
    """
    # 1. Block-style
    block_matches = list(_BLOCK_RESPONSE_MARKER_RE.finditer(text))
    if block_matches:
        return text[block_matches[-1].end():]

    # 2. Inline "Final response: ..."
    inline_match = _INLINE_RESPONSE_MARKER_RE.search(text)
    if inline_match:
        after = text[inline_match.end():]
        # Model sometimes repeats the answer immediately after → deduplicate
        paras = [p.strip() for p in after.split("\n\n") if p.strip()]
        seen: list[str] = []
        for p in paras:
            if not seen or seen[-1] != p:
                seen.append(p)
        return "\n\n".join(seen)

    # 3. Heuristic: first non-empty line looks like reasoning → last paragraph is the answer
    first_line = text.lstrip().split("\n")[0] if text.strip() else ""
    if _REASONING_FIRST_LINE_RE.match(first_line):
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paras) > 1:
            return paras[-1]

    return text


def sanitize_assistant_content(content: str, forbidden_terms: list[str] | None = None) -> str:
    content = html.unescape(content or "")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Strip explicit <think> tags (e.g. DeepSeek-R1 when think tags are emitted)
    content = re.sub(r"<think\b[^>]*>.*?</think>", " ", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<think\b[^>]*>.*$", "", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"</?think\b[^>]*>", " ", content, flags=re.IGNORECASE)
    # Strip plain-text scratchpad reasoning (DeepSeek-R1 / models without think-tag support)
    content = _extract_response_from_plaintext_reasoning(content)
    if forbidden_terms:
        sorted_terms = sorted((term for term in forbidden_terms if term), key=len, reverse=True)
        for term in sorted_terms:
            content = re.sub(rf"`?{re.escape(term)}`?", "esa opción", content, flags=re.IGNORECASE)
    content = re.sub(r"`?[a-z][a-z0-9]*(?:_[a-z0-9]+)+`?", "esa opción", content)
    content = re.sub(r"[ \t\f\v]+", " ", content)
    content = re.sub(r" *\n *", "\n", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = re.sub(r"(?<!\n)\s+(?=[•▪◦])", "\n", content)
    content = re.sub(r"(?<!\n)\s+(?=\d+\.\s)", "\n", content)
    content = content.strip()
    content = content.replace("**", "*")
    content = re.sub(r"^#+\s*", "", content, flags=re.MULTILINE)
    return content


@lru_cache(maxsize=1)
def load_system_prompt_template() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def extract_formatted_tool_reply(result: object) -> str | None:
    if not isinstance(result, dict):
        return None
    for key in FORMATTED_TOOL_REPLY_KEYS:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class AgentLoop:
    """
    Núcleo del agente: orquesta el reasoning loop entre el LLM y las herramientas.
    """

    def __init__(
        self,
        llm: LLMProvider,
        memory: ConversationMemory,
        max_iterations: int = 10,
        expense_store: ExpenseService | None = None,
        sheets: ExpenseService | None = None,
    ) -> None:
        self.llm = llm
        self.expense_store = expense_store or sheets
        self.group_expense_service = GroupExpenseService()
        self.memory = memory
        self.max_iterations = max_iterations

    async def process(
        self,
        phone: str | ResolvedUserContext,
        user_text: str,
        replied_to_id: str | None = None,
        chat_type: str = "private",
        group_id: str | None = None,
    ) -> str:
        """
        Procesa un mensaje del usuario y retorna la respuesta del agente.
        Si replied_to_id está presente, busca el texto del mensaje referenciado
        y lo antepone al mensaje del usuario para que el LLM tenga contexto del reply.
        Actualiza el historial de conversación en memoria.
        """
        user_ctx = phone if isinstance(phone, ResolvedUserContext) else None
        identity_key = user_ctx.identity_key if user_ctx is not None else phone
        conversation_key = self._conversation_key(identity_key, chat_type, group_id)

        # Registrar usuario si es nuevo (operación rápida con caché de gspread)
        if self.expense_store is not None:
            ensure_user_result = None
            try:
                ensure_user_result = self.expense_store.ensure_user(identity_key)
                if inspect.isawaitable(ensure_user_result):
                    await ensure_user_result
            except Exception as e:
                if inspect.iscoroutine(ensure_user_result):
                    ensure_user_result.close()
                logger.warning("Error en ensure_user para %s: %s", identity_key, e)

        # Si el usuario respondió a un mensaje específico del bot, inyectar contexto
        if replied_to_id:
            referenced = self.memory.get_by_message_ref(conversation_key, replied_to_id)
            if referenced:
                # Truncar el mensaje referenciado para no inflar el contexto
                preview = referenced[:200] + "..." if len(referenced) > 200 else referenced
                user_text = f'[En respuesta a: "{preview}"]\n{user_text}'
                logger.debug("Reply detectado para %s → referencia: %s", identity_key, replied_to_id)
            else:
                # wamid no disponible (reinicio de servidor o sesión cruzada):
                # informar al modelo para que pueda pedir aclaración si el mensaje es ambiguo
                user_text = (
                    "[El usuario está respondiendo a un mensaje anterior del bot, "
                    "pero no tengo el texto disponible. "
                    "Si el mensaje es ambiguo, pedí aclaración.]\n"
                    + user_text
                )
                logger.debug(
                    "Reply con id %s no encontrado en memoria para %s", replied_to_id, identity_key
                )

        # Obtener personalidad
        custom_prompt = None
        try:
            async with async_session_maker() as session:
                custom_prompt = await get_custom_prompt(
                    session,
                    group_id if chat_type == "group" and group_id else identity_key,
                    is_group=chat_type == "group" and group_id is not None,
                )
        except Exception as e:
            logger.error("Error al obtener personalidad: %s", e)

        messages = self.memory.get(conversation_key) + [Message(role="user", content=user_text)]
        tools = ToolRegistry(
            self.expense_store,
            identity_key,
            chat_type=chat_type,
            group_id=group_id,
        )
        system_prompt = self._build_system_prompt(identity_key, chat_type, group_id)
        if custom_prompt:
            system_prompt = f"{custom_prompt}\n\n{system_prompt}"

        canonical_tool_reply: str | None = None
        for iteration in range(self.max_iterations):
            logger.debug("Iteración %d del agente para %s", iteration + 1, identity_key)

            try:
                response = await self.llm.chat_with_tools(
                    messages, tools.definitions(), system_prompt
                )
            except Exception as exc:
                logger.error("Error en LLM (iteración %d) para %s: %s", iteration + 1, identity_key, exc)
                return "Estoy con problemas para conectarme en este momento. Intentá de nuevo en unos segundos 🙏"

            if response.finish_reason == "stop":
                raw_content = canonical_tool_reply or response.content or ""
                content = sanitize_assistant_content(
                    raw_content,
                    forbidden_terms=[tool.name for tool in tools.definitions()],
                )
                messages.append(Message(role="assistant", content=content))
                self.memory.append(conversation_key, messages)
                return content

            # finish_reason == "tool_use": ejecutar herramientas y continuar
            # No preservamos texto intermedio del modelo para evitar filtrar think/reasoning
            messages.append(
                Message(
                    role="assistant",
                    content=response.tool_calls,
                    tool_calls=response.tool_calls,
                )
            )
            
            # Si el modelo razonó en voz alta y quedó algo de texto para el usuario, 
            # podemos enviarlo parcialmetne, o simplemente no guardarlo en memory como texto
            # Para WhatsApp, no enviaremos texto parcial de tool_use para no confundir,
            # ya que el usuario recibe la respuesta final en "stop". Así evitamos dobles mensajes.

            canonical_tool_reply = None
            for tool_call in (response.tool_calls or []):
                try:
                    result = tools.run(tool_call.name, **tool_call.arguments)
                    if inspect.iscoroutine(result):
                        result = await result  # type: ignore
                except Exception as e:
                    logger.error("Error en herramienta '%s': %s", tool_call.name, e)
                    result = {"error": str(e)}
                formatted_reply = extract_formatted_tool_reply(result)
                if formatted_reply:
                    canonical_tool_reply = formatted_reply

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
        self.memory.append(conversation_key, messages)
        return "Hubo un problema procesando tu mensaje. Intentá de nuevo."

    def _build_system_prompt(
        self,
        phone: str,
        chat_type: str,
        group_id: str | None,
    ) -> str:
        from app.config import settings

        prompt = load_system_prompt_template().format(
            today=local_now_for_phone(phone).strftime("%Y-%m-%d %H:%M"),
            timezone=infer_timezone_for_phone(phone),
            currency=settings.DEFAULT_CURRENCY,
        )
        if chat_type == "group" and group_id:
            prompt += (
                "\n\nCONTEXTO ACTUAL:\n"
                f"- Estás respondiendo dentro del grupo {group_id}.\n"
                f"- El actor actual es el teléfono {phone}.\n"
                "- No registres gastos privados con register_expense si el pedido es grupal.\n"
                "- Para gastos compartidos y metas comunes usá exclusivamente las tools grupales."
            )
        return prompt

    def _conversation_key(self, phone: str, chat_type: str, group_id: str | None) -> str:
        if chat_type == "group" and group_id:
            return f"group:{group_id}"
        return phone
