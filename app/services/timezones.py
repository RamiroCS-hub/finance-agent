from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings

DB_ZONE = ZoneInfo(settings.DATABASE_TIMEZONE)

_PREFIX_TIMEZONES: list[tuple[str, str]] = [
    ("598", "America/Montevideo"),
    ("595", "America/Asuncion"),
    ("593", "America/Guayaquil"),
    ("591", "America/La_Paz"),
    ("58", "America/Caracas"),
    ("57", "America/Bogota"),
    ("56", "America/Santiago"),
    ("55", "America/Sao_Paulo"),
    ("54", "America/Argentina/Buenos_Aires"),
    ("53", "America/Havana"),
    ("52", "America/Mexico_City"),
    ("51", "America/Lima"),
    ("44", "Europe/London"),
    ("34", "Europe/Madrid"),
    ("33", "Europe/Paris"),
    ("1", "America/New_York"),
]


def infer_timezone_for_phone(phone: str | None) -> str:
    normalized = _normalize_phone(phone)
    if not normalized:
        return settings.DEFAULT_USER_TIMEZONE
    for prefix, timezone_name in _PREFIX_TIMEZONES:
        if normalized.startswith(prefix):
            return timezone_name
    return settings.DEFAULT_USER_TIMEZONE


def local_now_for_phone(phone: str | None) -> datetime:
    timezone_name = infer_timezone_for_phone(phone)
    return datetime.now(ZoneInfo(timezone_name))


def utc_now() -> datetime:
    return datetime.now(DB_ZONE)


def to_utc(
    value: datetime | None,
    phone: str | None = None,
    source_timezone: str | None = None,
) -> tuple[datetime, str]:
    timezone_name = source_timezone or infer_timezone_for_phone(phone)
    local_zone = ZoneInfo(timezone_name)
    if value is None:
        local_value = datetime.now(local_zone)
    elif value.tzinfo is None:
        local_value = value.replace(tzinfo=local_zone)
    else:
        local_value = value.astimezone(local_zone)
    return local_value.astimezone(DB_ZONE), timezone_name


def utc_window_for_local_month(
    phone: str,
    year: int,
    month: int,
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(infer_timezone_for_phone(phone))
    start_local = datetime(year, month, 1, tzinfo=zone)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=zone)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=zone)
    return start_local.astimezone(DB_ZONE), end_local.astimezone(DB_ZONE)


def utc_window_for_local_date_range(
    phone: str,
    date_from: str | None,
    date_to: str | None,
) -> tuple[datetime | None, datetime | None]:
    zone = ZoneInfo(infer_timezone_for_phone(phone))
    start = None
    end = None
    if date_from:
        local_start = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=zone)
        start = local_start.astimezone(DB_ZONE)
    if date_to:
        local_end = datetime.strptime(date_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=zone
        )
        end = local_end.astimezone(DB_ZONE)
    return start, end


def display_datetime_for_phone(
    value: datetime,
    phone: str | None,
    source_timezone: str | None = None,
) -> datetime:
    zone = ZoneInfo(source_timezone or infer_timezone_for_phone(phone))
    if value.tzinfo is None:
        value = value.replace(tzinfo=DB_ZONE)
    return value.astimezone(zone)


def _normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    if ":" in phone:
        channel, raw_value = phone.split(":", 1)
        if channel and channel != "whatsapp":
            return ""
        phone = raw_value
    return "".join(ch for ch in phone if ch.isdigit())
