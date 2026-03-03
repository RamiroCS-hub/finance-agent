import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.agent.tools import ToolRegistry

@pytest.mark.asyncio
async def test_get_user_groups_info_tool():
    """Test 7.3: Validate get_user_groups_info returns expected JSON payload."""
    
    mock_goal = MagicMock()
    mock_goal.target_amount = 50000.0
    mock_goal.current_amount = 15000.0

    mock_group = MagicMock()
    mock_group.name = "Grupo de Viaje"
    mock_group.whatsapp_group_id = "123456@g.us"
    mock_group.id = 1

    mock_membership = MagicMock()
    mock_membership.group = mock_group

    mock_user = MagicMock()
    mock_user.whatsapp_number = "+5491112345678"
    mock_user.group_memberships = [mock_membership]

    mock_session = AsyncMock()
    
    async def mock_execute(query):
        mock_result = MagicMock()
        query_str = str(query).lower()
        if "users" in query_str:
            mock_result.scalar_one_or_none.return_value = mock_user
        elif "goals" in query_str:
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = [mock_goal]
            mock_result.scalars.return_value = mock_scalars
        return mock_result

    mock_session.execute.side_effect = mock_execute

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.db.database.async_session_maker", mock_session_maker):
        registry = ToolRegistry(sheets=MagicMock(), phone="+5491112345678")
        
        result = await registry.run("get_user_groups_info")
        
        assert result["success"] is True
        assert len(result["groups"]) == 1
        group_info = result["groups"][0]
        assert group_info["name"] == "Grupo de Viaje"
        assert group_info["whatsapp_group_id"] == "123456@g.us"
        assert len(group_info["active_goals"]) == 1
        assert group_info["active_goals"][0]["target_amount"] == 50000.0
        assert group_info["active_goals"][0]["current_amount"] == 15000.0

@pytest.mark.asyncio
async def test_get_user_groups_info_tool_no_user():
    """Test when the user is not found."""
    mock_session = AsyncMock()
    
    async def mock_execute(query):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        return mock_result

    mock_session.execute.side_effect = mock_execute

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.db.database.async_session_maker", mock_session_maker):
        registry = ToolRegistry(sheets=MagicMock(), phone="+5491112345678")
        result = await registry.run("get_user_groups_info")
        
        assert result["success"] is False
        assert "Usuario no encontrado" in result["error"]
