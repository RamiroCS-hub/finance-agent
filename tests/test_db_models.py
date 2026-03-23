import pytest
from sqlalchemy import select

from app.db.models import (
    BudgetRule,
    ChatConfiguration,
    Goal,
    Group,
    GroupExpense,
    GroupExpenseShare,
    GroupMember,
    Liability,
    User,
    UserChannel,
)


def test_models_import():
    """Simple test to verify models can be imported and their table names are correct."""
    assert User.__tablename__ == "users"
    assert Group.__tablename__ == "groups"
    assert GroupMember.__tablename__ == "group_members"
    assert Goal.__tablename__ == "goals"
    assert ChatConfiguration.__tablename__ == "chat_configurations"
    assert GroupExpense.__tablename__ == "group_expenses"
    assert GroupExpenseShare.__tablename__ == "group_expense_shares"
    assert BudgetRule.__tablename__ == "budget_rules"
    assert Liability.__tablename__ == "liabilities"
    assert UserChannel.__tablename__ == "user_channels"


@pytest.mark.asyncio
async def test_user_model_instantiation():
    """Test that we can instantiate the User model."""
    user = User(whatsapp_number="+123456789", default_timezone="America/Argentina/Buenos_Aires")
    assert user.whatsapp_number == "+123456789"
    assert user.default_timezone == "America/Argentina/Buenos_Aires"


@pytest.mark.asyncio
async def test_group_model_instantiation():
    """Test that we can instantiate the Group model."""
    group = Group(whatsapp_group_id="group-123", name="My Group")
    assert group.whatsapp_group_id == "group-123"
    assert group.name == "My Group"


@pytest.mark.asyncio
async def test_user_channel_model_instantiation():
    user_channel = UserChannel(
        user_id=1,
        channel="telegram",
        external_user_id="777001",
        chat_id="777001",
        display_name="Ana",
    )
    assert user_channel.channel == "telegram"
    assert user_channel.external_user_id == "777001"
