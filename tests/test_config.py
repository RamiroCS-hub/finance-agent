from app.config import Settings


def test_settings_normalize_render_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://render_user:secret@render-host:5432/finance_bot",
    )

    settings = Settings()

    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://render_user:secret@render-host:5432/finance_bot"
    )


def test_settings_load_render_database_flags(monkeypatch):
    monkeypatch.setenv("DATABASE_USE_SSL", "true")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "7")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "13")
    monkeypatch.setenv("DATABASE_POOL_RECYCLE_SECONDS", "900")

    settings = Settings()

    assert settings.DATABASE_USE_SSL is True
    assert settings.DATABASE_POOL_SIZE == 7
    assert settings.DATABASE_MAX_OVERFLOW == 13
    assert settings.DATABASE_POOL_RECYCLE_SECONDS == 900
