from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

from app.db.models import Goal


async def create_or_update_goal(
    session: AsyncSession,
    target_amount: float,
    user_id: Optional[int] = None,
    group_id: Optional[int] = None,
) -> Dict[str, Any]:
    query = select(Goal)
    if group_id is not None:
        query = query.where(Goal.group_id == group_id, Goal.status == "active")
    elif user_id is not None:
        query = query.where(Goal.user_id == user_id, Goal.status == "active")
    else:
        raise ValueError("user_id o group_id son requeridos")

    result = await session.execute(query)
    goal = result.scalar_one_or_none()

    if goal:
        goal.target_amount = target_amount
        goal.status = "active"
        action = "updated"
    else:
        goal = Goal(
            user_id=user_id,
            group_id=group_id,
            target_amount=target_amount,
            current_amount=0.0,
            status="active",
        )
        session.add(goal)
        action = "created"

    await session.commit()
    return {
        "status": action,
        "target_amount": goal.target_amount,
        "current_amount": goal.current_amount,
    }

async def update_goal_progress(
    session: AsyncSession, 
    user_id: Optional[int], 
    group_id: Optional[int], 
    amount: float
) -> Optional[Dict[str, Any]]:
    """
    Updates the active goal for a user or group by adding the amount.
    Returns a dictionary with status and message if a goal was active.
    """
    # Prefer group_id if it's a group, otherwise user_id
    query = select(Goal).where(Goal.status == "active")
    
    if group_id is not None:
        query = query.where(Goal.group_id == group_id)
    elif user_id is not None:
        query = query.where(Goal.user_id == user_id)
    else:
        return None

    result = await session.execute(query)
    goal = result.scalar_one_or_none()

    if not goal:
        return None

    goal.current_amount += amount
    
    payload = {
        "status": "active",
        "message": "Progreso actualizado."
    }

    if goal.current_amount >= goal.target_amount:
        goal.status = "completed"
        payload["status"] = "completed"
        payload["message"] = (
            "¡Felicidades! Has alcanzado tu meta de ahorro. "
            "Te invitamos a crear una nueva meta."
        )

    await session.commit()
    return payload
