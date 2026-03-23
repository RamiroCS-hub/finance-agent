from datetime import datetime

from app.services.timezones import (
    display_datetime_for_phone,
    infer_timezone_for_phone,
    to_utc,
)


def test_infer_timezone_for_argentina_number():
    assert infer_timezone_for_phone("5491112345678") == "America/Argentina/Buenos_Aires"


def test_to_utc_uses_phone_timezone():
    value, timezone_name = to_utc(datetime(2026, 3, 21, 10, 0), phone="5491112345678")
    assert timezone_name == "America/Argentina/Buenos_Aires"
    assert value.tzinfo is not None


def test_display_datetime_for_phone_roundtrips_timezone():
    stored, timezone_name = to_utc(datetime(2026, 3, 21, 10, 0), phone="59899111222")
    displayed = display_datetime_for_phone(stored, "59899111222", timezone_name)
    assert displayed.strftime("%Y-%m-%d %H:%M") == "2026-03-21 10:00"
