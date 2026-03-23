import pytest
from unittest.mock import AsyncMock, MagicMock
from app.db.models import Goal
from app.services.goals import create_or_update_goal, update_goal_progress

@pytest.mark.asyncio
async def test_update_goal_progress():
    """Test 1: Adding a saving/expense increases current_amount in DB."""
    session = AsyncMock()
    goal = Goal(id=1, target_amount=100.0, current_amount=50.0, status="active")
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = goal
    session.execute.return_value = mock_result
    
    result = await update_goal_progress(session, user_id=1, group_id=None, amount=20.0)
    
    assert goal.current_amount == 70.0
    assert result.get("status") == "active"
    assert session.commit.called

@pytest.mark.asyncio
async def test_trigger_goal_reached():
    """Test 2 & 3: Hitting the target_amount triggers a GoalReached state/event, and payload includes invite to create a new goal."""
    session = AsyncMock()
    goal = Goal(id=1, target_amount=100.0, current_amount=90.0, status="active")
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = goal
    session.execute.return_value = mock_result
    
    result = await update_goal_progress(session, user_id=1, group_id=None, amount=15.0)
        
    assert goal.current_amount == 105.0
    assert goal.status == "completed"
    assert session.commit.called
    
    assert result.get("status") == "completed"
    assert "¡Felicidades!" in result.get("message", "")
    assert "invitamos a crear una nueva meta" in result.get("message", "")

@pytest.mark.asyncio
async def test_update_goal_progress_no_active_goal():
    """Test when there is no active goal."""
    session = AsyncMock()
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    result = await update_goal_progress(session, user_id=1, group_id=None, amount=20.0)
    
    assert result is None
    assert not session.commit.called


@pytest.mark.asyncio
async def test_create_group_goal_when_missing():
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    result = await create_or_update_goal(session, target_amount=5000.0, group_id=7)

    assert result["status"] == "created"
    assert result["target_amount"] == 5000.0
    assert session.add.called
    assert session.commit.called
