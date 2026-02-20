from __future__ import annotations

import json
import logging
from typing import Protocol

from google import genai
from openrouter import OpenRouter

from app.config import Settings
from app.models.agent import ChatResponse, Message, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    async def complete(self, system_prompt: str, user_message: str) -> str: ...

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system_prompt: str,
    ) -> ChatResponse: ...


class GeminiProvider:
    """Google AI Studio — Tier gratuito (15 RPM, 1M tokens/min)."""

    def __init__(self, config: Settings) -> None:
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL

    async def complete(self, system_prompt: str, user_message: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        return response.text

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system_prompt: str,
    ) -> ChatResponse:
        gemini_tools = self._build_gemini_tools(tools)
        contents = self._messages_to_contents(messages)

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=gemini_tools,
                temperature=0.1,
            ),
        )

        candidate = response.candidates[0]
        tool_calls: list[ToolCall] = []
        text_content: str | None = None

        for part in candidate.content.parts:
            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", None):
                tool_calls.append(
                    ToolCall(
                        id=fc.name,  # Gemini no tiene IDs únicos; usa el nombre
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    )
                )
            else:
                text = getattr(part, "text", None)
                if text:
                    text_content = text

        if tool_calls:
            return ChatResponse(
                content=None,
                tool_calls=tool_calls,
                finish_reason="tool_use",
            )

        return ChatResponse(
            content=text_content,
            tool_calls=None,
            finish_reason="stop",
        )

    def _build_gemini_tools(self, tools: list[ToolDefinition]) -> list:
        declarations = []
        for tool in tools:
            params_schema = self._json_schema_to_gemini(tool.parameters)
            declarations.append(
                genai.types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=params_schema,
                )
            )
        return [genai.types.Tool(function_declarations=declarations)]

    def _json_schema_to_gemini(self, schema: dict) -> genai.types.Schema:
        """Convierte JSON Schema dict a Gemini Schema."""
        type_map = {
            "string": genai.types.Type.STRING,
            "number": genai.types.Type.NUMBER,
            "integer": genai.types.Type.INTEGER,
            "boolean": genai.types.Type.BOOLEAN,
            "array": genai.types.Type.ARRAY,
            "object": genai.types.Type.OBJECT,
        }
        schema_type = schema.get("type", "string")
        gemini_type = type_map.get(schema_type, genai.types.Type.STRING)

        kwargs: dict = {
            "type": gemini_type,
            "description": schema.get("description", ""),
        }

        if gemini_type == genai.types.Type.OBJECT:
            properties = {
                name: self._json_schema_to_gemini(prop)
                for name, prop in schema.get("properties", {}).items()
            }
            kwargs["properties"] = properties
            if schema.get("required"):
                kwargs["required"] = schema["required"]

        elif gemini_type == genai.types.Type.ARRAY and "items" in schema:
            kwargs["items"] = self._json_schema_to_gemini(schema["items"])

        return genai.types.Schema(**kwargs)

    def _messages_to_contents(self, messages: list[Message]) -> list[dict]:
        """Convierte lista de Message al formato contents de Gemini."""
        contents: list[dict] = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
                i += 1

            elif msg.role == "assistant":
                if isinstance(msg.content, list):
                    # Tool calls del assistant
                    parts = [
                        {"function_call": {"name": tc.name, "args": tc.arguments}}
                        for tc in msg.content
                    ]
                    contents.append({"role": "model", "parts": parts})
                else:
                    contents.append({"role": "model", "parts": [{"text": msg.content}]})
                i += 1

            elif msg.role == "tool":
                # Agrupa resultados de tools consecutivos en un único turn de usuario
                tool_parts = []
                while i < len(messages) and messages[i].role == "tool":
                    tm = messages[i]
                    tool_parts.append(
                        {
                            "function_response": {
                                "name": tm.tool_name or "unknown",
                                "response": {"result": tm.content},
                            }
                        }
                    )
                    i += 1
                contents.append({"role": "user", "parts": tool_parts})

            else:
                i += 1

        return contents


class DeepSeekProvider:
    """OpenRouter / DeepSeek — Usa el SDK oficial de OpenRouter."""

    def __init__(self, config: Settings) -> None:
        self.model = config.DEEPSEEK_MODEL
        self.client = OpenRouter(api_key=config.DEEPSEEK_API_KEY)

    async def complete(self, system_prompt: str, user_message: str) -> str:
        response = await self.client.chat.send_async(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            stream=False,
        )
        return response.choices[0].message.content or ""

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system_prompt: str,
    ) -> ChatResponse:
        openai_messages = self._messages_to_openai_format(messages, system_prompt)
        openai_tools = self._build_openai_tools(tools)

        response = await self.client.chat.send_async(
            model=self.model,
            messages=openai_messages,
            tools=openai_tools,
            temperature=0.1,
            stream=False,
        )

        choice = response.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason or "stop"

        if finish_reason == "tool_calls" or message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in (message.tool_calls or [])
            ]
            return ChatResponse(content=None, tool_calls=tool_calls, finish_reason="tool_use")

        return ChatResponse(
            content=message.content,
            tool_calls=None,
            finish_reason="stop",
        )

    def _build_openai_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _messages_to_openai_format(
        self, messages: list[Message], system_prompt: str
    ) -> list[dict]:
        result: list[dict] = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            if msg.role == "user":
                result.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                if isinstance(msg.content, list):
                    tool_calls_data = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.content
                    ]
                    result.append(
                        {"role": "assistant", "content": None, "tool_calls": tool_calls_data}
                    )
                else:
                    result.append({"role": "assistant", "content": msg.content})
            elif msg.role == "tool":
                result.append(
                    {
                        "role": "tool",
                        "content": msg.content,
                        "tool_call_id": msg.tool_call_id or "unknown",
                    }
                )
        return result


def get_provider(config: Settings) -> LLMProvider:
    provider = config.LLM_PROVIDER
    if provider == "gemini":
        logger.info("Usando LLM provider: Gemini (%s)", config.GEMINI_MODEL)
        return GeminiProvider(config)
    elif provider == "deepseek":
        logger.info("Usando LLM provider: DeepSeek (%s)", config.DEEPSEEK_MODEL)
        return DeepSeekProvider(config)
    else:
        raise ValueError(f"LLM_PROVIDER no soportado: {provider}")
