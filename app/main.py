import logging

from fastapi import FastAPI
from redis import asyncio as redis_asyncio

from app.agent.core import AgentLoop
from app.agent.memory import ConversationMemory
from app.api.telegram_webhook import (
    init_dependencies as init_telegram_dependencies,
    router as telegram_webhook_router,
)
from app.api.webhook import init_dependencies, router as webhook_router
from app.config import settings
from app.services.channel_identity import ChannelIdentityService
from app.services.expenses import ExpenseService
from app.services.llm_provider import get_provider
from app.services.message_dispatch import MessageDispatcher
from app.services.rate_limit import RateLimitService

# Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bot de Gastos WhatsApp")
app.state.redis = None


@app.on_event("startup")
async def startup():
    logger.info("Iniciando bot de gastos (modo agente)...")
    llm = get_provider(settings)
    expense_store = ExpenseService()

    memory = ConversationMemory(ttl_minutes=settings.CONVERSATION_TTL_MINUTES)
    agent = AgentLoop(
        llm=llm,
        expense_store=expense_store,
        memory=memory,
        max_iterations=settings.MAX_AGENT_ITERATIONS,
    )
    dispatcher = MessageDispatcher()
    identity_service = ChannelIdentityService()

    rate_limiter = None
    if settings.WHATSAPP_RATE_LIMIT_ENABLED:
        redis_client = redis_asyncio.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        app.state.redis = redis_client
        rate_limiter = RateLimitService(
            redis_client=redis_client,
            max_messages=settings.WHATSAPP_RATE_LIMIT_MAX_MESSAGES,
            window_seconds=settings.WHATSAPP_RATE_LIMIT_WINDOW_SECONDS,
            notify_cooldown_seconds=settings.WHATSAPP_RATE_LIMIT_NOTIFY_COOLDOWN_SECONDS,
        )

    init_dependencies(agent, rate_limiter=rate_limiter)
    init_telegram_dependencies(
        agent,
        dispatcher=dispatcher,
        identity_service=identity_service,
    )
    logger.info(
        "Bot listo. Provider: %s | TTL: %dmin | Max iter: %d | Rate limit: %s",
        settings.LLM_PROVIDER,
        settings.CONVERSATION_TTL_MINUTES,
        settings.MAX_AGENT_ITERATIONS,
        "on" if settings.WHATSAPP_RATE_LIMIT_ENABLED else "off",
    )


@app.on_event("shutdown")
async def shutdown():
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        await redis_client.aclose()
        app.state.redis = None


app.include_router(webhook_router)
app.include_router(telegram_webhook_router)
