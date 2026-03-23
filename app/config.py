from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


class Settings:
    # WhatsApp Meta Cloud API
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")

    # Google Sheets
    GOOGLE_SHEETS_CREDENTIALS_PATH: str = os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials/service_account.json"
    )
    GOOGLE_SPREADSHEET_ID: str = os.getenv("GOOGLE_SPREADSHEET_ID", "")

    # LLM Provider
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_BASE_URL: str = os.getenv(
        "DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1"
    )
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "5"))
    RECEIPT_OCR_PROVIDER: str = os.getenv("RECEIPT_OCR_PROVIDER", "gemini")
    RECEIPT_OCR_MODEL: str = os.getenv("RECEIPT_OCR_MODEL", "")
    RECEIPT_OCR_AUTO_CONFIDENCE: float = float(
        os.getenv("RECEIPT_OCR_AUTO_CONFIDENCE", "0.85")
    )
    RECEIPT_OCR_CONFIRM_CONFIDENCE: float = float(
        os.getenv("RECEIPT_OCR_CONFIRM_CONFIDENCE", "0.60")
    )

    # Transcription
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    TRANSCRIPTION_MODEL: str = os.getenv("TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/finance_bot"
    )
    DATABASE_TIMEZONE: str = os.getenv("DATABASE_TIMEZONE", "UTC")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    def __init__(self) -> None:
        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)

    # App
    DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "ARS")
    GROUP_BOT_MENTION: str = os.getenv("GROUP_BOT_MENTION", "@anotamelo")
    ALLOWED_PHONE_NUMBERS: List[str] = [
        n.strip()
        for n in os.getenv("ALLOWED_PHONE_NUMBERS", "").split(",")
        if n.strip()
    ]
    WHATSAPP_RATE_LIMIT_ENABLED: bool = os.getenv(
        "WHATSAPP_RATE_LIMIT_ENABLED", "true"
    ).lower() in {"1", "true", "yes", "on"}
    WHATSAPP_RATE_LIMIT_MAX_MESSAGES: int = int(
        os.getenv("WHATSAPP_RATE_LIMIT_MAX_MESSAGES", "8")
    )
    WHATSAPP_RATE_LIMIT_WINDOW_SECONDS: int = int(
        os.getenv("WHATSAPP_RATE_LIMIT_WINDOW_SECONDS", "60")
    )
    WHATSAPP_RATE_LIMIT_NOTIFY_COOLDOWN_SECONDS: int = int(
        os.getenv("WHATSAPP_RATE_LIMIT_NOTIFY_COOLDOWN_SECONDS", "120")
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Agente
    CONVERSATION_TTL_MINUTES: int = int(os.getenv("CONVERSATION_TTL_MINUTES", "60"))
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))
    MONTHLY_INFLATION_RATE: float = float(os.getenv("MONTHLY_INFLATION_RATE", "0"))


settings = Settings()
