"""
Tests para app/services/llm_provider.py — Fase 2: Tool Calling.

Se ejecutan con mocks; no requieren API keys reales.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.agent import ChatResponse, Message, ToolCall, ToolDefinition
from app.services.llm_provider import DeepSeekProvider, GeminiProvider


# ---------------------------------------------------------------------------
# Fixtures comunes
# ---------------------------------------------------------------------------


@pytest.fixture
def test_settings():
    from app.config import Settings

    s = Settings()
    s.GEMINI_API_KEY = "test-gemini-key"
    s.GEMINI_MODEL = "gemini-2.0-flash"
    s.DEEPSEEK_API_KEY = "test-deepseek-key"
    s.DEEPSEEK_MODEL = "deepseek-chat"
    s.DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
    return s


@pytest.fixture
def expense_tool():
    return ToolDefinition(
        name="register_expense",
        description="Registra un gasto en la planilla.",
        parameters={
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Monto del gasto"},
                "description": {"type": "string", "description": "Descripción del gasto"},
                "category": {"type": "string", "description": "Categoría del gasto"},
            },
            "required": ["amount", "description"],
        },
        fn=lambda **kwargs: {"success": True},
    )


@pytest.fixture
def user_message():
    return [Message(role="user", content="850 farmacia")]


# ---------------------------------------------------------------------------
# GeminiProvider — chat_with_tools
# ---------------------------------------------------------------------------


class TestGeminiProviderChatWithTools:
    def _make_provider(self, test_settings):
        """Crea GeminiProvider parcheando el cliente para no necesitar API key."""
        with patch("google.genai.Client"):
            provider = GeminiProvider(test_settings)
        provider.client = MagicMock()
        return provider

    def _mock_tool_use_response(self, name: str, args: dict):
        """Construye un mock de respuesta Gemini con function_call."""
        mock_fc = MagicMock()
        mock_fc.name = name
        mock_fc.args = args

        mock_part = MagicMock()
        mock_part.function_call = mock_fc
        mock_part.text = None

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        return mock_response

    def _mock_stop_response(self, text: str):
        """Construye un mock de respuesta Gemini de texto puro."""
        mock_part = MagicMock()
        mock_part.function_call = None
        mock_part.text = text

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        return mock_response

    def test_tool_use_returns_correct_finish_reason(
        self, test_settings, expense_tool, user_message
    ):
        """Cuando el LLM decide usar una herramienta, finish_reason debe ser 'tool_use'."""
        provider = self._make_provider(test_settings)
        mock_resp = self._mock_tool_use_response(
            "register_expense", {"amount": 850, "description": "farmacia"}
        )
        provider.client.models.generate_content.return_value = mock_resp

        result = asyncio.run(
            provider.chat_with_tools(
                messages=user_message,
                tools=[expense_tool],
                system_prompt="Sos un asistente de gastos.",
            )
        )

        assert result.finish_reason == "tool_use"

    def test_tool_use_returns_correct_tool_call(
        self, test_settings, expense_tool, user_message
    ):
        """El ToolCall devuelto debe tener nombre y argumentos correctos."""
        provider = self._make_provider(test_settings)
        mock_resp = self._mock_tool_use_response(
            "register_expense", {"amount": 850.0, "description": "farmacia"}
        )
        provider.client.models.generate_content.return_value = mock_resp

        result = asyncio.run(
            provider.chat_with_tools(
                messages=user_message,
                tools=[expense_tool],
                system_prompt="Sos un asistente de gastos.",
            )
        )

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.name == "register_expense"
        assert tc.arguments["amount"] == 850.0
        assert tc.arguments["description"] == "farmacia"

    def test_stop_returns_text_content(self, test_settings, expense_tool):
        """Cuando el LLM responde con texto, finish_reason debe ser 'stop'."""
        provider = self._make_provider(test_settings)
        mock_resp = self._mock_stop_response("Hola, ¿en qué te puedo ayudar?")
        provider.client.models.generate_content.return_value = mock_resp

        result = asyncio.run(
            provider.chat_with_tools(
                messages=[Message(role="user", content="hola")],
                tools=[expense_tool],
                system_prompt="Sos un asistente de gastos.",
            )
        )

        assert result.finish_reason == "stop"
        assert result.content == "Hola, ¿en qué te puedo ayudar?"
        assert result.tool_calls is None

    def test_stop_has_no_tool_calls(self, test_settings, expense_tool):
        """En finish_reason='stop', tool_calls debe ser None."""
        provider = self._make_provider(test_settings)
        mock_resp = self._mock_stop_response("Respuesta de texto.")
        provider.client.models.generate_content.return_value = mock_resp

        result = asyncio.run(
            provider.chat_with_tools(
                messages=[Message(role="user", content="texto")],
                tools=[expense_tool],
                system_prompt="Sos un asistente.",
            )
        )

        assert result.tool_calls is None

    def test_messages_to_contents_user(self, test_settings):
        """_messages_to_contents convierte mensajes de usuario correctamente."""
        with patch("google.genai.Client"):
            provider = GeminiProvider(test_settings)
        provider.client = MagicMock()

        messages = [Message(role="user", content="hola")]
        contents = provider._messages_to_contents(messages)

        assert contents[0]["role"] == "user"
        assert contents[0]["parts"][0]["text"] == "hola"

    def test_messages_to_contents_assistant_text(self, test_settings):
        """_messages_to_contents convierte mensajes de assistant con texto."""
        with patch("google.genai.Client"):
            provider = GeminiProvider(test_settings)
        provider.client = MagicMock()

        messages = [Message(role="assistant", content="Entendido")]
        contents = provider._messages_to_contents(messages)

        assert contents[0]["role"] == "model"
        assert contents[0]["parts"][0]["text"] == "Entendido"

    def test_messages_to_contents_tool_result(self, test_settings):
        """_messages_to_contents convierte tool results como function_response."""
        with patch("google.genai.Client"):
            provider = GeminiProvider(test_settings)
        provider.client = MagicMock()

        messages = [
            Message(
                role="tool",
                content='{"success": true}',
                tool_name="register_expense",
            )
        ]
        contents = provider._messages_to_contents(messages)

        assert contents[0]["role"] == "user"
        fr = contents[0]["parts"][0]["function_response"]
        assert fr["name"] == "register_expense"
        assert fr["response"]["result"] == '{"success": true}'


# ---------------------------------------------------------------------------
# DeepSeekProvider — chat_with_tools
# ---------------------------------------------------------------------------


class TestDeepSeekProviderChatWithTools:
    def _make_provider(self, test_settings):
        return DeepSeekProvider(test_settings)

    def _mock_tool_use_response(self, tool_name: str, arguments: dict):
        """Construye mock de respuesta de HTTPX con tool_calls."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(arguments),
                                }
                            }
                        ]
                    }
                }
            ]
        }
        return mock_response

    def _mock_stop_response(self, text: str):
        """Construye mock de respuesta HTTPX con texto puro."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": text,
                    }
                }
            ]
        }
        return mock_response

    @patch("httpx.AsyncClient")
    def test_tool_use_returns_correct_finish_reason(
        self, mock_client_class, test_settings, expense_tool, user_message
    ):
        """Cuando DeepSeek devuelve tool_calls, finish_reason debe ser 'tool_use'."""
        provider = self._make_provider(test_settings)
        mock_resp = self._mock_tool_use_response(
            "register_expense", {"amount": 850, "description": "farmacia"}
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = asyncio.run(
            provider.chat_with_tools(
                messages=user_message,
                tools=[expense_tool],
                system_prompt="Sos un asistente de gastos.",
            )
        )

        assert result.finish_reason == "tool_use"

    @patch("httpx.AsyncClient")
    def test_tool_use_returns_correct_tool_call(
        self, mock_client_class, test_settings, expense_tool, user_message
    ):
        """El ToolCall devuelto debe tener nombre, id y argumentos correctos."""
        provider = self._make_provider(test_settings)
        mock_resp = self._mock_tool_use_response(
            "register_expense", {"amount": 850.0, "description": "farmacia"}
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = asyncio.run(
            provider.chat_with_tools(
                messages=user_message,
                tools=[expense_tool],
                system_prompt="Sos un asistente de gastos.",
            )
        )

        assert result.tool_calls is not None
        tc = result.tool_calls[0]
        assert tc.id == "call_abc123"
        assert tc.name == "register_expense"
        assert tc.arguments["amount"] == 850.0

    @patch("httpx.AsyncClient")
    def test_stop_returns_text_content(
        self, mock_client_class, test_settings, expense_tool
    ):
        """Cuando DeepSeek no usa tools, finish_reason debe ser 'stop'."""
        provider = self._make_provider(test_settings)
        mock_resp = self._mock_stop_response("Hola, ¿en qué te puedo ayudar?")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = asyncio.run(
            provider.chat_with_tools(
                messages=[Message(role="user", content="hola")],
                tools=[expense_tool],
                system_prompt="Sos un asistente.",
            )
        )

        assert result.finish_reason == "stop"
        assert result.content == "Hola, ¿en qué te puedo ayudar?"
        assert result.tool_calls is None

    def test_messages_to_openai_format_includes_system(self, test_settings):
        """El primer mensaje del formato OpenAI debe ser el system prompt."""
        provider = DeepSeekProvider(test_settings)
        messages = [Message(role="user", content="hola")]
        result = provider._messages_to_openai_format(messages, "Sos asistente.")

        assert result[0]["role"] == "system"
        assert result[0]["content"] == "Sos asistente."

    def test_messages_to_openai_format_tool_result(self, test_settings):
        """Los tool results se convierten correctamente con tool_call_id."""
        provider = DeepSeekProvider(test_settings)
        messages = [
            Message(
                role="tool",
                content='{"success": true}',
                tool_call_id="call_abc123",
            )
        ]
        result = provider._messages_to_openai_format(messages, "system")

        tool_msg = result[1]  # [0] es system
        assert tool_msg["role"] == "tool"
        assert tool_msg["content"] == '{"success": true}'
        assert tool_msg["tool_call_id"] == "call_abc123"

    @patch("app.services.llm_provider.GeminiProvider")
    @patch("httpx.AsyncClient")
    def test_chat_with_tools_falls_back_to_gemini_on_http_400(
        self,
        mock_client_class,
        mock_gemini_cls,
        test_settings,
        expense_tool,
        user_message,
    ):
        provider = self._make_provider(test_settings)
        request = httpx.Request("POST", test_settings.DEEPSEEK_BASE_URL)
        response = httpx.Response(
            400,
            request=request,
            text='{"error":"tools not supported"}',
        )
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad request",
            request=request,
            response=response,
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_class.return_value.__aenter__.return_value = mock_client

        fallback = AsyncMock(
            return_value=ChatResponse(
                content="respuesta fallback",
                tool_calls=None,
                finish_reason="stop",
            )
        )
        mock_gemini_cls.return_value.chat_with_tools = fallback

        result = asyncio.run(
            provider.chat_with_tools(
                messages=user_message,
                tools=[expense_tool],
                system_prompt="Sos un asistente de gastos.",
            )
        )

        assert result.finish_reason == "stop"
        assert result.content == "respuesta fallback"
        fallback.assert_awaited_once()
