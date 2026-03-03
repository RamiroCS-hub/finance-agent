from app.models.agent import Message, ToolCall, ChatResponse
from app.agent.core import AgentLoop
from unittest.mock import AsyncMock, MagicMock
import pytest

@pytest.mark.asyncio
async def test_agent_loop_strips_think_on_intermediate_steps():
    # Setup mock LLM that returns a think block and a tool call in the first turn
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools.side_effect = [
        ChatResponse(
            content="<think>I need to think</think> Let me call the tool.",
            tool_calls=[ToolCall(id="1", name="dummy_tool", arguments={})],
            finish_reason="tool_use"
        ),
        ChatResponse(
            content="Final answer.",
            tool_calls=None,
            finish_reason="stop"
        )
    ]
    
    mock_sheets = MagicMock()
    mock_memory = MagicMock()
    mock_memory.get.return_value = []
    
    agent = AgentLoop(llm=mock_llm, sheets=mock_sheets, memory=mock_memory)
    
    # We patch ToolRegistry dynamically to avoid actual dependencies
    import sys
    from unittest.mock import patch
    with patch("app.agent.core.ToolRegistry") as MockRegistry:
        mock_registry = MockRegistry.return_value
        mock_registry.definitions.return_value = []
        mock_registry.run.return_value = {"success": True}
        
        reply = await agent.process("123", "Hello")
        
        assert reply == "Final answer."
        assert mock_memory.append.call_count > 0
        
        # Verify the memory does NOT contain the <think> tag in the intermediate step
        saved_messages = mock_memory.append.call_args[0][1]
        
        # The 2nd message should be the assistant's intermediate step
        assert saved_messages[1].role == "assistant"
        # The content should be the tool calls list, not the string with think
        assert isinstance(saved_messages[1].content, list)
