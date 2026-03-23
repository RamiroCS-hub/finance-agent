"""
Tests para app/agent/core.py y app/agent/memory.py — Fase 4: Agent Core.

Usa mocks del LLMProvider y SheetsService para tests aislados y rápidos.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.core import AgentLoop, load_system_prompt_template
from app.agent.memory import ConversationMemory
from app.models.agent import ChatResponse, Message, ToolCall, ToolDefinition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def tool_use_response(name: str, arguments: dict, call_id: str = "call_1") -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        finish_reason="tool_use",
    )


def stop_response(text: str) -> ChatResponse:
    return ChatResponse(content=text, tool_calls=None, finish_reason="stop")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sheets():
    sheets = MagicMock()
    sheets.ensure_user.return_value = False
    sheets.append_expense.return_value = SimpleNamespace(id=3, user_id=1)
    sheets.get_monthly_total.return_value = 5000.0
    sheets.get_category_totals.return_value = {"Comida": 2000.0, "Transporte": 3000.0}
    sheets.get_recent_expenses.return_value = []
    sheets.search_expenses.return_value = []
    sheets.delete_last_expense.return_value = None
    sheets.get_sheet_url.return_value = "https://docs.google.com/spreadsheets/d/abc"
    return sheets


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat_with_tools = AsyncMock()
    return llm


@pytest.fixture
def memory():
    return ConversationMemory(ttl_minutes=60)


@pytest.fixture
def agent(mock_llm, mock_sheets, memory):
    return AgentLoop(
        llm=mock_llm,
        sheets=mock_sheets,
        memory=memory,
        max_iterations=5,
    )


PHONE = "5491123456789"


# ---------------------------------------------------------------------------
# AgentLoop — flujo básico
# ---------------------------------------------------------------------------


class TestAgentLoopEnsureUser:
    def test_ensure_user_exception_does_not_crash(self, agent, mock_llm, mock_sheets):
        """Si ensure_user lanza excepción, el agente continúa normalmente."""
        mock_sheets.ensure_user.side_effect = Exception("Sheets no disponible")
        mock_llm.chat_with_tools.return_value = stop_response("Hola.")

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert result == "Hola."  # el agente no crasheó


class TestAgentLoopBasicFlow:
    def test_direct_stop_returns_llm_text(self, agent, mock_llm):
        """Cuando el LLM responde stop sin tools, retorna el texto directamente."""
        mock_llm.chat_with_tools.return_value = stop_response("Hola, ¿en qué te puedo ayudar?")

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert result == "Hola, ¿en qué te puedo ayudar?"

    def test_strip_thinking_tags(self, agent, mock_llm):
        """Verifica que si el LLM devuelve tags <think> (modelos razonadores), se eliminen de la respuesta final."""
        mock_llm.chat_with_tools.return_value = stop_response(
            "<think>\nThis is a thinking process.\nWe should just say hi.\n</think>\nHola, ¿en qué te puedo ayudar?"
        )

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert result == "Hola, ¿en qué te puedo ayudar?"
        # Verificar también que en la memoria se guarde sin el think tag
        memory = agent.memory.get(PHONE)
        assert memory[-1].role == "assistant"
        assert memory[-1].content == "Hola, ¿en qué te puedo ayudar?"

    def test_strip_thinking_tags_prevents_text_concatenation(self, agent, mock_llm):
        """Verifica que texto antes/después de <think> no se pegue sin espacios."""
        mock_llm.chat_with_tools.return_value = stop_response(
            "Texto1<think>razonamiento intermedio</think>Texto2"
        )

        result = asyncio.run(agent.process(PHONE, "test"))

        # Debe quedar "Texto1 Texto2" (con espacio), no "Texto1Texto2"
        assert result == "Texto1 Texto2"

    def test_strip_escaped_thinking_tags(self, agent, mock_llm):
        mock_llm.chat_with_tools.return_value = stop_response(
            "&lt;think&gt;razonamiento&lt;/think&gt; Hola final"
        )

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert result == "Hola final"

    def test_redacts_internal_tool_names_from_final_reply(self, agent, mock_llm):
        mock_llm.chat_with_tools.return_value = stop_response(
            "No pude hacerlo con register_expense. Probá con get_monthly_summary."
        )

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert "register_expense" not in result
        assert "get_monthly_summary" not in result
        assert "esa opción" in result

    def test_redacts_unknown_snake_case_identifiers_from_final_reply(self, agent, mock_llm):
        mock_llm.chat_with_tools.return_value = stop_response(
            "No pude hacerlo con recurring_expense_create pero sí con otra alternativa."
        )

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert "recurring_expense_create" not in result
        assert "esa opción" in result

    def test_strips_plain_text_reasoning_with_response_marker(self, agent, mock_llm):
        """Verifica que razonamiento en texto plano (DeepSeek-R1 style) se elimine cuando hay 'Response:'."""
        reasoning_blob = (
            "We are in a private chat, so we don't have group context.\n"
            "The user said: '39k en uber' -> amount=39000, category=Transporte.\n"
            "We called register_expense and it returned a success.\n"
            "\nResponse:\n\n"
            "Gasto registrado:\n"
            "*Uber:* $39.000\n"
            "Categoría: Transporte 🚗"
        )
        mock_llm.chat_with_tools.return_value = stop_response(reasoning_blob)

        result = asyncio.run(agent.process(PHONE, "39k en uber"))

        assert "We are in a private chat" not in result
        assert "The user said" not in result
        assert "Gasto registrado" in result
        assert "Transporte" in result

    def test_strips_plain_text_reasoning_response_marker_case_insensitive(self, agent, mock_llm):
        """Verifica que el marcador 'response:' sea case-insensitive."""
        raw = "Razonamiento interno...\nresponse:\n\nRespuesta final del bot."
        mock_llm.chat_with_tools.return_value = stop_response(raw)

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert "Razonamiento interno" not in result
        assert "Respuesta final del bot." in result

    def test_strips_inline_final_response_marker(self, agent, mock_llm):
        """Verifica extracción con 'Final response: <respuesta>' en la misma línea."""
        raw = (
            "The user said '15k caños'. I'll call esa opción with amount=15000.\n\n"
            "The tool response shows it was successful.\n\n"
            "Final response: Gasto registrado: $15.000 en caños (Hogar)\n\n"
            "Gasto registrado: $15.000 en caños (Hogar)"
        )
        mock_llm.chat_with_tools.return_value = stop_response(raw)

        result = asyncio.run(agent.process(PHONE, "15k caños"))

        assert "The user said" not in result
        assert "I'll call" not in result
        # Debe aparecer una sola vez (sin duplicado)
        assert result.count("Gasto registrado") == 1
        assert "caños" in result

    def test_strips_reasoning_via_heuristic_no_marker(self, agent, mock_llm):
        """Verifica extracción heurística cuando no hay marcador 'Response:' y el primer
        párrafo inicia con un indicador de razonamiento reconocible."""
        raw = (
            "The user registered an expense of 10,000 ARS for csushi.\n"
            "The tool call was successful.\n\n"
            "I'll use WhatsApp formatting.\n\n"
            "🍔 *Comida:* $10.000 en csushi."
        )
        mock_llm.chat_with_tools.return_value = stop_response(raw)

        result = asyncio.run(agent.process(PHONE, "10k csushi"))

        assert "The user registered" not in result
        assert "🍔" in result
        assert "csushi" in result

    def test_preserves_bullet_points_on_separate_lines(self, agent, mock_llm):
        mock_llm.chat_with_tools.return_value = stop_response(
            "Opciones: • primera alternativa • segunda alternativa 1. tercer paso 2. cuarto paso"
        )

        result = asyncio.run(agent.process(PHONE, "hola"))

        assert "\n• primera alternativa" in result
        assert "\n• segunda alternativa" in result
        assert "\n1. tercer paso" in result
        assert "\n2. cuarto paso" in result

    def test_prefers_canonical_tool_reply_over_invented_stop_text(self, mock_llm, mock_sheets, memory):
        mock_llm.chat_with_tools.side_effect = [
            tool_use_response("create_liability", {"kind": "installment"}),
            stop_response(
                "✅ Registré la deuda\n- Cuotas restantes: 9\nCada mes se sumará automáticamente a tu compromiso"
            ),
        ]
        fake_registry = MagicMock()
        fake_registry.definitions.return_value = [
            ToolDefinition(
                name="create_liability",
                description="",
                parameters={},
                fn=MagicMock(),
            )
        ]
        fake_registry.run.return_value = {
            "success": True,
            "formatted_confirmation": (
                "✅ Registré la obligación: *Sofá en cuotas*\n"
                "- Cuotas restantes: 9\n"
                "- Monto mensual: *$30.000*"
            ),
        }
        agent = AgentLoop(
            llm=mock_llm,
            sheets=mock_sheets,
            memory=memory,
            max_iterations=5,
        )

        with patch("app.agent.core.ToolRegistry", return_value=fake_registry):
            result = asyncio.run(agent.process(PHONE, "registrá el sofá"))

        assert result == (
            "✅ Registré la obligación: *Sofá en cuotas*\n"
            "- Cuotas restantes: 9\n"
            "- Monto mensual: *$30.000*"
        )
        assert "automáticamente" not in result

    def test_system_prompt_template_is_loaded_from_markdown(self):
        template = load_system_prompt_template()

        assert "VERACIDAD:" in template
        assert "formatted_confirmation" in template
        assert "Nunca inventes automatismos" in template

    def test_tool_use_then_stop_returns_final_text(self, agent, mock_llm):
        """LLM llama a una tool y luego responde con texto; retorna el texto final."""
        mock_llm.chat_with_tools.side_effect = [
            tool_use_response("register_expense", {"amount": 850, "description": "farmacia"}),
            stop_response("✅ Registré $850 en farmacia (Salud)"),
        ]

        result = asyncio.run(agent.process(PHONE, "850 farmacia"))

        assert result == "✅ Registré $850 en farmacia (Salud)"
        assert mock_llm.chat_with_tools.call_count == 2

    def test_tool_is_executed(self, agent, mock_llm, mock_sheets):
        """Cuando el LLM llama register_expense, debe ejecutarse sheets.append_expense."""
        mock_llm.chat_with_tools.side_effect = [
            tool_use_response("register_expense", {"amount": 500, "description": "cafe"}),
            stop_response("Registrado."),
        ]

        asyncio.run(agent.process(PHONE, "500 cafe"))

        mock_sheets.append_expense.assert_called_once()

    def test_unknown_tool_does_not_crash(self, agent, mock_llm):
        """Si el LLM llama una herramienta que no existe, el agente no debe crashear."""
        mock_llm.chat_with_tools.side_effect = [
            tool_use_response("nonexistent_tool", {}),
            stop_response("Algo salió mal, pero sigo funcionando."),
        ]

        result = asyncio.run(agent.process(PHONE, "hola"))

        # No crasheó y devolvió respuesta del segundo turno
        assert result == "Algo salió mal, pero sigo funcionando."

    def test_unknown_tool_error_is_passed_to_llm(self, agent, mock_llm):
        """El error de la herramienta desconocida debe llegar al LLM en el siguiente turno."""
        mock_llm.chat_with_tools.side_effect = [
            tool_use_response("bad_tool", {}),
            stop_response("Entendido."),
        ]

        asyncio.run(agent.process(PHONE, "test"))

        # En el segundo call, los messages deben incluir un tool message con error
        second_call_messages = mock_llm.chat_with_tools.call_args_list[1][0][0]
        tool_messages = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_messages) == 1
        assert "error" in tool_messages[0].content


# ---------------------------------------------------------------------------
# AgentLoop — múltiples iteraciones
# ---------------------------------------------------------------------------


class TestAgentLoopIterations:
    def test_max_iterations_returns_fallback_message(self, agent, mock_llm):
        """Si se alcanza MAX_AGENT_ITERATIONS, retorna mensaje de error."""
        # Siempre responde con tool_use → nunca llega al stop
        mock_llm.chat_with_tools.return_value = tool_use_response(
            "get_sheet_url", {}
        )

        result = asyncio.run(agent.process(PHONE, "test"))

        assert "problema" in result.lower() or "error" in result.lower()
        assert mock_llm.chat_with_tools.call_count == 5  # max_iterations=5

    def test_multiple_tool_calls_in_sequence(self, agent, mock_llm, mock_sheets):
        """El agente puede encadenar múltiples tool calls antes de responder."""
        mock_llm.chat_with_tools.side_effect = [
            tool_use_response("register_expense", {"amount": 100, "description": "t1"}, "c1"),
            tool_use_response("register_expense", {"amount": 200, "description": "t2"}, "c2"),
            stop_response("Registré 2 gastos."),
        ]

        result = asyncio.run(agent.process(PHONE, "850 y 200"))

        assert result == "Registré 2 gastos."
        assert mock_sheets.append_expense.call_count == 2


# ---------------------------------------------------------------------------
# AgentLoop — memoria de conversación
# ---------------------------------------------------------------------------


class TestAgentLoopMemory:
    def test_user_message_saved_to_memory(self, agent, mock_llm, memory):
        """Después de procesar, el historial debe contener el mensaje del usuario."""
        mock_llm.chat_with_tools.return_value = stop_response("Hola.")

        asyncio.run(agent.process(PHONE, "hola"))

        history = memory.get(PHONE)
        user_msgs = [m for m in history if m.role == "user"]
        assert any(m.content == "hola" for m in user_msgs)

    def test_assistant_response_saved_to_memory(self, agent, mock_llm, memory):
        """La respuesta del LLM también debe guardarse en el historial."""
        mock_llm.chat_with_tools.return_value = stop_response("Entendido.")

        asyncio.run(agent.process(PHONE, "test"))

        history = memory.get(PHONE)
        assistant_msgs = [m for m in history if m.role == "assistant"]
        assert any(m.content == "Entendido." for m in assistant_msgs)

    def test_second_message_includes_previous_context(self, agent, mock_llm):
        """El segundo mensaje debe incluir el historial del primero."""
        mock_llm.chat_with_tools.return_value = stop_response("Respuesta.")

        asyncio.run(agent.process(PHONE, "primer mensaje"))
        asyncio.run(agent.process(PHONE, "segundo mensaje"))

        # En el segundo call, los messages deben incluir el historial del primero
        second_call_messages = mock_llm.chat_with_tools.call_args_list[1][0][0]
        contents = [m.content for m in second_call_messages if m.role == "user"]
        assert "primer mensaje" in contents
        assert "segundo mensaje" in contents

    def test_different_phones_have_separate_history(self, agent, mock_llm, memory):
        """Cada número de teléfono tiene su propio historial."""
        mock_llm.chat_with_tools.return_value = stop_response("Ok.")

        asyncio.run(agent.process("111", "mensaje para 111"))
        asyncio.run(agent.process("222", "mensaje para 222"))

        history_111 = memory.get("111")
        history_222 = memory.get("222")
        assert any("111" in m.content for m in history_111 if m.role == "user")
        assert any("222" in m.content for m in history_222 if m.role == "user")
        assert not any("222" in m.content for m in history_111 if m.role == "user")


# ---------------------------------------------------------------------------
# ConversationMemory
# ---------------------------------------------------------------------------


class TestConversationMemory:
    def test_get_empty_for_unknown_phone(self):
        memory = ConversationMemory()
        assert memory.get("unknown") == []

    def test_append_and_get(self):
        memory = ConversationMemory()
        messages = [Message(role="user", content="hola")]
        memory.append("123", messages)
        result = memory.get("123")
        assert len(result) == 1
        assert result[0].content == "hola"

    def test_get_returns_copy(self):
        """get() debe retornar una copia, no la referencia original."""
        memory = ConversationMemory()
        messages = [Message(role="user", content="hola")]
        memory.append("123", messages)
        result = memory.get("123")
        result.append(Message(role="user", content="extra"))
        # El store interno no debe verse afectado
        assert len(memory.get("123")) == 1

    def test_append_replaces_history(self):
        """append() debe reemplazar el historial anterior."""
        memory = ConversationMemory()
        memory.append("123", [Message(role="user", content="viejo")])
        memory.append("123", [Message(role="user", content="nuevo")])
        result = memory.get("123")
        assert len(result) == 1
        assert result[0].content == "nuevo"

    def test_clear_removes_history(self):
        memory = ConversationMemory()
        memory.append("123", [Message(role="user", content="hola")])
        memory.clear("123")
        assert memory.get("123") == []

    def test_clear_nonexistent_phone_does_not_raise(self):
        memory = ConversationMemory()
        memory.clear("no_existe")  # no debe lanzar excepción

    def test_ttl_expiration(self):
        """El historial debe expirar después del TTL."""
        memory = ConversationMemory(ttl_minutes=60)
        messages = [Message(role="user", content="hola")]
        memory.append("123", messages)

        # Manipular el timestamp para simular que pasaron 61 minutos
        old_msgs, _ = memory._store["123"]
        memory._store["123"] = (old_msgs, datetime.now() - timedelta(minutes=61))

        assert memory.get("123") == []

    def test_ttl_not_expired(self):
        """El historial NO debe expirar si el TTL no se cumplió."""
        memory = ConversationMemory(ttl_minutes=60)
        messages = [Message(role="user", content="hola")]
        memory.append("123", messages)

        # Solo pasaron 30 minutos
        old_msgs, _ = memory._store["123"]
        memory._store["123"] = (old_msgs, datetime.now() - timedelta(minutes=30))

        assert len(memory.get("123")) == 1

    def test_expired_entry_removed_from_store(self):
        """Después de expirar, la entrada debe eliminarse del store interno."""
        memory = ConversationMemory(ttl_minutes=60)
        memory.append("123", [Message(role="user", content="hola")])

        old_msgs, _ = memory._store["123"]
        memory._store["123"] = (old_msgs, datetime.now() - timedelta(minutes=61))

        memory.get("123")  # trigger la limpieza
        assert "123" not in memory._store
