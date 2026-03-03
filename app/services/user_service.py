from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import User

async def get_or_create_user(session: AsyncSession, whatsapp_number: str) -> User:
    """
    Get a user by whatsapp_number, or create a new one if it doesn't exist.
    """
    result = await session.execute(
        select(User).where(User.whatsapp_number == whatsapp_number)
    )
    user = result.scalars().first()

    if not user:
        user = User(whatsapp_number=whatsapp_number)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user
