import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ChatConfiguration, User, Group
from app.services.llm_provider import get_provider

logger = logging.getLogger(__name__)

async def generate_personality_prompt(entity_id: str, description: str, is_group: bool = False) -> str:
    """Genera un prompt de personalidad usando el LLM mockeado/real."""
    provider = get_provider(settings)
    system_prompt = "Genera un prompt de sistema para un bot de finanzas."
    user_message = f"Crea un prompt de comportamiento de unas 3 o 4 líneas para este bot, basado en la siguiente descripción: {description}"
    
    try:
        response = await provider.complete(system_prompt, user_message)
        return response.strip()
    except Exception as e:
        logger.error("Error generando personalidad: %s", e)
        return ""

async def save_custom_prompt(session: AsyncSession, entity_id: str, prompt: str, is_group: bool = False) -> None:
    """Guarda el custom prompt en la base de datos para el usuario o grupo dado."""
    # Buscar si ya existe la configuración
    stmt = select(ChatConfiguration)
    
    if is_group:
        # En una app real buscaríamos el group.id por el whatsapp_group_id
        # Simplificación: Asumimos que entity_id ya es el ID de BD, o lo buscamos
        group_stmt = select(Group).where(Group.whatsapp_group_id == entity_id)
        result = await session.execute(group_stmt)
        group = result.scalars().first()
        if not group:
            logger.warning("Grupo no encontrado: %s", entity_id)
            return
        
        stmt = stmt.where(ChatConfiguration.group_id == group.id)
    else:
        user_stmt = select(User).where(User.whatsapp_number == entity_id)
        result = await session.execute(user_stmt)
        user = result.scalars().first()
        if not user:
            logger.warning("Usuario no encontrado: %s", entity_id)
            return
            
        stmt = stmt.where(ChatConfiguration.user_id == user.id)
        
    result = await session.execute(stmt)
    config = result.scalars().first()
    
    if config:
        config.custom_prompt = prompt
    else:
        if is_group:
            config = ChatConfiguration(group_id=group.id, custom_prompt=prompt)
        else:
            config = ChatConfiguration(user_id=user.id, custom_prompt=prompt)
        session.add(config)
        
    await session.commit()

async def get_custom_prompt(session: AsyncSession, entity_id: str, is_group: bool = False) -> Optional[str]:
    """Obtiene el custom prompt desde la base de datos."""
    stmt = select(ChatConfiguration)
    
    if is_group:
        group_stmt = select(Group).where(Group.whatsapp_group_id == entity_id)
        result = await session.execute(group_stmt)
        group = result.scalars().first()
        if not group:
            return None
        stmt = stmt.where(ChatConfiguration.group_id == group.id)
    else:
        user_stmt = select(User).where(User.whatsapp_number == entity_id)
        result = await session.execute(user_stmt)
        user = result.scalars().first()
        if not user:
            return None
        stmt = stmt.where(ChatConfiguration.user_id == user.id)
        
    result = await session.execute(stmt)
    config = result.scalars().first()
    
    return config.custom_prompt if config else None
