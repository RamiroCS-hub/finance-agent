from types import SimpleNamespace

from app.db.database import build_engine_kwargs


def test_build_engine_kwargs_without_ssl():
    config = SimpleNamespace(
        DATABASE_USE_SSL=False,
        DATABASE_POOL_SIZE=5,
        DATABASE_MAX_OVERFLOW=10,
        DATABASE_POOL_RECYCLE_SECONDS=1800,
    )

    kwargs = build_engine_kwargs(config)

    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_recycle"] == 1800
    assert "connect_args" not in kwargs


def test_build_engine_kwargs_with_ssl():
    config = SimpleNamespace(
        DATABASE_USE_SSL=True,
        DATABASE_POOL_SIZE=3,
        DATABASE_MAX_OVERFLOW=6,
        DATABASE_POOL_RECYCLE_SECONDS=600,
    )

    kwargs = build_engine_kwargs(config)

    assert kwargs["pool_size"] == 3
    assert kwargs["max_overflow"] == 6
    assert kwargs["connect_args"] == {"ssl": True}
