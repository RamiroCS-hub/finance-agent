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


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        self.WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
        self.WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        self.WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
        self.WHATSAPP_REQUIRE_SIGNATURE = env_bool("WHATSAPP_REQUIRE_SIGNATURE", True)
        self.WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS = env_bool(
            "WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS", False
        )
        self.WHATSAPP_MAX_AUDIO_BYTES = int(
            os.getenv("WHATSAPP_MAX_AUDIO_BYTES", str(16 * 1024 * 1024))
        )
        self.WHATSAPP_MAX_IMAGE_BYTES = int(
            os.getenv("WHATSAPP_MAX_IMAGE_BYTES", str(10 * 1024 * 1024))
        )
        self.WHATSAPP_ALLOWED_AUDIO_MIME_TYPES = env_list(
            "WHATSAPP_ALLOWED_AUDIO_MIME_TYPES",
            "audio/ogg,audio/opus,audio/mpeg,audio/mp4,audio/aac,audio/amr",
        )
        self.WHATSAPP_ALLOWED_IMAGE_MIME_TYPES = env_list(
            "WHATSAPP_ALLOWED_IMAGE_MIME_TYPES",
            "image/jpeg,image/png,image/webp",
        )
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
        self.TELEGRAM_API_BASE_URL = os.getenv(
            "TELEGRAM_API_BASE_URL", "https://api.telegram.org"
        )
        self.ALLOWED_TELEGRAM_CHAT_IDS = env_list("ALLOWED_TELEGRAM_CHAT_IDS", "")
        self.TELEGRAM_MAX_AUDIO_BYTES = int(
            os.getenv("TELEGRAM_MAX_AUDIO_BYTES", str(16 * 1024 * 1024))
        )
        self.TELEGRAM_MAX_IMAGE_BYTES = int(
            os.getenv("TELEGRAM_MAX_IMAGE_BYTES", str(10 * 1024 * 1024))
        )
        self.TELEGRAM_ALLOWED_AUDIO_MIME_TYPES = env_list(
            "TELEGRAM_ALLOWED_AUDIO_MIME_TYPES",
            "audio/ogg,audio/opus,audio/mpeg,audio/mp4,audio/aac",
        )
        self.TELEGRAM_ALLOWED_IMAGE_MIME_TYPES = env_list(
            "TELEGRAM_ALLOWED_IMAGE_MIME_TYPES",
            "image/jpeg,image/png,image/webp",
        )
        self.TELEGRAM_UPDATE_DEDUP_TTL_SECONDS = int(
            os.getenv("TELEGRAM_UPDATE_DEDUP_TTL_SECONDS", "300")
        )
        self.GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv(
            "GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials/service_account.json"
        )
        self.GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")
        self.LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
        self.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.DEEPSEEK_BASE_URL = os.getenv(
            "DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "5"))
        self.RECEIPT_OCR_PROVIDER = os.getenv("RECEIPT_OCR_PROVIDER", "gemini")
        self.RECEIPT_OCR_MODEL = os.getenv("RECEIPT_OCR_MODEL", "")
        self.RECEIPT_OCR_AUTO_CONFIDENCE = float(
            os.getenv("RECEIPT_OCR_AUTO_CONFIDENCE", "0.85")
        )
        self.RECEIPT_OCR_CONFIRM_CONFIDENCE = float(
            os.getenv("RECEIPT_OCR_CONFIRM_CONFIDENCE", "0.60")
        )
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
        self.TRANSCRIPTION_MODEL = os.getenv(
            "TRANSCRIPTION_MODEL", "whisper-large-v3-turbo"
        )
        self.DATABASE_URL = normalize_database_url(
            os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5433/finance_bot",
            )
        )
        self.DATABASE_TIMEZONE = os.getenv("DATABASE_TIMEZONE", "UTC")
        self.DATABASE_USE_SSL = env_bool("DATABASE_USE_SSL", False)
        self.DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))
        self.DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
        self.DATABASE_POOL_RECYCLE_SECONDS = int(
            os.getenv("DATABASE_POOL_RECYCLE_SECONDS", "1800")
        )
        self.DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "ARS")
        self.DEFAULT_USER_TIMEZONE = os.getenv(
            "DEFAULT_USER_TIMEZONE", self.DATABASE_TIMEZONE
        )
        self.GROUP_BOT_MENTION = os.getenv("GROUP_BOT_MENTION", "@anotamelo")
        self.ALLOWED_PHONE_NUMBERS = env_list("ALLOWED_PHONE_NUMBERS", "")
        self.WHATSAPP_RATE_LIMIT_ENABLED = env_bool("WHATSAPP_RATE_LIMIT_ENABLED", True)
        self.WHATSAPP_RATE_LIMIT_MAX_MESSAGES = int(
            os.getenv("WHATSAPP_RATE_LIMIT_MAX_MESSAGES", "8")
        )
        self.WHATSAPP_RATE_LIMIT_WINDOW_SECONDS = int(
            os.getenv("WHATSAPP_RATE_LIMIT_WINDOW_SECONDS", "60")
        )
        self.WHATSAPP_RATE_LIMIT_NOTIFY_COOLDOWN_SECONDS = int(
            os.getenv("WHATSAPP_RATE_LIMIT_NOTIFY_COOLDOWN_SECONDS", "120")
        )
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.CONVERSATION_TTL_MINUTES = int(os.getenv("CONVERSATION_TTL_MINUTES", "60"))
        self.MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))
        self.MONTHLY_INFLATION_RATE = float(os.getenv("MONTHLY_INFLATION_RATE", "0"))


settings = Settings()
