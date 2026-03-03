import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.db.models import ChatConfiguration, User, Group

@pytest.mark.asyncio
async def test_personality_generation():
    from app.services.personality import generate_personality_prompt
    
    with patch("app.services.personality.get_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = "Sos un bot enojado y respondés mal."
        mock_get_provider.return_value = mock_provider
        
        prompt = await generate_personality_prompt("123", "Quiero que el bot sea enojón")
        
        assert prompt == "Sos un bot enojado y respondés mal."
        mock_provider.complete.assert_called_once()

@pytest.mark.asyncio
async def test_personality_persistence():
    from app.services.personality import save_custom_prompt, get_custom_prompt
    
    mock_session = AsyncMock()
    mock_user = User(id=1, whatsapp_number="user_456")
    mock_config = ChatConfiguration(user_id=1, custom_prompt="Sos un pirata")
    
    # Mockear las llamadas a execute
    async def mock_execute(stmt):
        mock_result = MagicMock()
        # Verificar qué statement se está ejecutando analizando sus atributos o con strings (simplificado acá)
        # Retornamos user/group o config dependiendo
        if "users" in str(stmt):
            mock_result.scalars().first.return_value = mock_user
        elif "chat_configurations" in str(stmt):
            mock_result.scalars().first.return_value = mock_config
        else:
            mock_result.scalars().first.return_value = None
        return mock_result

    mock_session.execute.side_effect = mock_execute
    
    # Prueba get_custom_prompt
    saved = await get_custom_prompt(mock_session, "user_456")
    assert saved == "Sos un pirata"
    
    # Prueba save_custom_prompt
    # Para esto redefinimos execute si es necesario o simplemente verificamos que llame a commit
    await save_custom_prompt(mock_session, "user_456", "Nuevo prompt")
    assert mock_config.custom_prompt == "Nuevo prompt"
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_personality_context_injection():
    # Probamos que el AgentLoop inyecta el custom_prompt
    from app.agent.core import AgentLoop
    from app.models.agent import Message
    
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools.return_value = AsyncMock(finish_reason="stop", content="Respuesta")
    mock_sheets = MagicMock()
    mock_memory = MagicMock()
    mock_memory.get.return_value = []
    
    # Como process puede no recibir db_session, tal vez AgentLoop necesita ser parchado
    with patch("app.agent.core.get_custom_prompt", new_callable=AsyncMock) as mock_get_custom_prompt:
        mock_get_custom_prompt.return_value = "Sos un bot sarcástico."
        
        # Opcion: parchear DB local si core usa db.
        with patch("app.agent.core.async_session_maker") as mock_db:
            
            agent = AgentLoop(llm=mock_llm, sheets=mock_sheets, memory=mock_memory)
            # Para hacer la prueba, necesitamos modificar AgentLoop para que inyecte la personalidad
            
            await agent.process("123", "Hola")
            
            # Verificamos que se haya llamado a chat_with_tools
            assert mock_llm.chat_with_tools.called
            
            # El system_prompt pasado a chat_with_tools debe contener la personalidad
            args, kwargs = mock_llm.chat_with_tools.call_args
            system_prompt = args[2] if len(args) > 2 else kwargs.get("system_prompt")
            
            assert "Sos un bot sarcástico." in system_prompt
