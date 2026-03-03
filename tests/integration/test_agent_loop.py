import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.agent.core import AgentLoop
from app.agent.memory import ConversationMemory
from app.models.agent import ChatResponse

@pytest.mark.asyncio
async def test_agent_loop_process_simple_message():
    # Arrange
    mock_llm = MagicMock()
    # LLM responde directamente con "stop" y un texto
    mock_llm.chat_with_tools = AsyncMock(return_value=ChatResponse(
        content="Hola, ¿en qué te puedo ayudar?",
        tool_calls=None,
        finish_reason="stop"
    ))
    
    # Mock sheets service que no hace nada
    mock_sheets = MagicMock()
    mock_sheets.ensure_user.return_value = None
    
    memory = ConversationMemory(ttl_minutes=10)
    agent = AgentLoop(llm=mock_llm, sheets=mock_sheets, memory=memory)
    
    # Act
    response = await agent.process("123456789", "Hola bot")
    
    # Assert
    assert response == "Hola, ¿en qué te puedo ayudar?"
    
    # Verify memory
    history = memory.get("123456789")
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Hola bot"
    assert history[1].role == "assistant"
    assert history[1].content == "Hola, ¿en qué te puedo ayudar?"

@pytest.mark.asyncio
async def test_agent_loop_with_reply():
    # Arrange
    mock_llm = MagicMock()
    mock_llm.chat_with_tools = AsyncMock(return_value=ChatResponse(
        content="Entendido.",
        tool_calls=None,
        finish_reason="stop"
    ))
    mock_sheets = MagicMock()
    
    memory = ConversationMemory(ttl_minutes=10)
    # Simulamos que hubo un mensaje previo que el bot mandó
    memory.store_wamid("123456789", "wamid_abc", "Mensaje previo del bot")
    
    agent = AgentLoop(llm=mock_llm, sheets=mock_sheets, memory=memory)
    
    # Act
    # Usuario responde al mensaje referenciado
    response = await agent.process("123456789", "Respondo a eso", replied_to_id="wamid_abc")
    
    # Assert
    assert response == "Entendido."
    
    history = memory.get("123456789")
    assert len(history) == 2
    assert history[0].role == "user"
    # El core inyecta el contexto de a qué mensaje estaba respondiendo
    assert '[En respuesta a: "Mensaje previo del bot"]' in history[0].content
    assert "Respondo a eso" in history[0].content
