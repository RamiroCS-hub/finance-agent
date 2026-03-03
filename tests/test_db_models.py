import pytest
from sqlalchemy import select

from app.db.models import ChatConfiguration, Goal, Group, GroupMember, User


def test_models_import():
    """Simple test to verify models can be imported and their table names are correct."""
    assert User.__tablename__ == "users"
    assert Group.__tablename__ == "groups"
    assert GroupMember.__tablename__ == "group_members"
    assert Goal.__tablename__ == "goals"
    assert ChatConfiguration.__tablename__ == "chat_configurations"


@pytest.mark.asyncio
async def test_user_model_instantiation():
    """Test that we can instantiate the User model."""
    user = User(whatsapp_number="+123456789")
    assert user.whatsapp_number == "+123456789"


@pytest.mark.asyncio
async def test_group_model_instantiation():
    """Test that we can instantiate the Group model."""
    group = Group(whatsapp_group_id="group-123", name="My Group")
    assert group.whatsapp_group_id == "group-123"
    assert group.name == "My Group"
