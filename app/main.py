import logging

from fastapi import FastAPI

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
    logger.info("Iniciando bot de gastos...")
    llm = get_provider(settings)
    try:
        sheets = SheetsService()
        logger.info("Google Sheets conectado correctamente")
    except Exception as e:
        sheets = None
        logger.warning("Google Sheets no disponible: %s. El bot arranca pero no puede guardar gastos.", e)
    init_dependencies(llm, sheets)
    logger.info("Bot listo. Provider LLM: %s", settings.LLM_PROVIDER)


app.include_router(webhook_router)
