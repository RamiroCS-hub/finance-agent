from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: "str | list[ToolCall] | None" = None  # str para texto, lista para tool calls
    tool_calls: "list[ToolCall] | None" = None # Lista de tool calls que hace el asistente
    tool_call_id: "str | None" = None  # Para tool results (OpenAI/DeepSeek)
    tool_name: "str | None" = None     # Para tool results (Gemini necesita el nombre)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema del input
    fn: Callable


@dataclass
class ChatResponse:
    content: "str | None"
    tool_calls: "list[ToolCall] | None"
    finish_reason: Literal["stop", "tool_use"]
