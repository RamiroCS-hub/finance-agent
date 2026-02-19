import logging

from fastapi import FastAPI

from app.agent.core import AgentLoop
from app.agent.memory import ConversationMemory
from app.api.webhook import init_dependencies, router as webhook_router
from app.config import settings
from app.services.llm_provider import get_provider
from app.services.sheets import SheetsService

# Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bot de Gastos WhatsApp")


@app.on_event("startup")
async def startup():
    logger.info("Iniciando bot de gastos (modo agente)...")
    llm = get_provider(settings)

    try:
        sheets = SheetsService()
        logger.info("Google Sheets conectado correctamente")
    except Exception as e:
        sheets = None
        logger.warning(
            "Google Sheets no disponible: %s. El bot arranca pero no puede guardar gastos.", e
        )

    memory = ConversationMemory(ttl_minutes=settings.CONVERSATION_TTL_MINUTES)
    agent = AgentLoop(
        llm=llm,
        sheets=sheets,
        memory=memory,
        max_iterations=settings.MAX_AGENT_ITERATIONS,
    )

    init_dependencies(agent)
    logger.info(
        "Bot listo. Provider: %s | TTL: %dmin | Max iter: %d",
        settings.LLM_PROVIDER,
        settings.CONVERSATION_TTL_MINUTES,
        settings.MAX_AGENT_ITERATIONS,
    )


app.include_router(webhook_router)
