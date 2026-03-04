"""Tests for static data loading."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.utils.static_data import (
    StaticDataLoader,
    lookup_by_date,
    parse_date,
    parse_time,
)


@pytest.fixture
def loader():
    """Create a loader with test data directory."""
    data_dir = Path(__file__).parent.parent / "data"
    settings_path = Path(__file__).parent.parent / "settings.json"
    return StaticDataLoader(data_dir=data_dir, settings_path=settings_path)


def test_parse_date():
    """Test date parsing."""
    assert parse_date("2024-01-15") == date(2024, 1, 15)
    assert parse_date("2023-12-31") == date(2023, 12, 31)


def test_parse_time():
    """Test time parsing."""
    t = parse_time("16:30")
    assert t.hour == 16
    assert t.minute == 30


def test_lookup_by_date():
    """Test lookup_by_date function."""
    table = [
        {"effective_date": date(2023, 1, 1), "value": 100},
        {"effective_date": date(2024, 1, 1), "value": 200},
        {"effective_date": date(2025, 1, 1), "value": 300},
    ]

    # Exact match
    result = lookup_by_date(table, date(2024, 1, 1))
    assert result["value"] == 200

    # Between dates
    result = lookup_by_date(table, date(2024, 6, 15))
    assert result["value"] == 200

    # After last
    result = lookup_by_date(table, date(2025, 6, 15))
    assert result["value"] == 300


def test_lookup_by_date_no_match():
    """Test lookup_by_date raises error when no match."""
    table = [
        {"effective_date": date(2024, 1, 1), "value": 100},
    ]

    with pytest.raises(ValueError):
        lookup_by_date(table, date(2023, 1, 1))


def test_loader_settings(loader):
    """Test loading settings.json."""
    loader.load_all()
    settings = loader.settings

    assert settings.ot_config.weekly_cap == Decimal("42")
    assert settings.ot_config.threshold_5day == Decimal("8.4")
    assert settings.full_time_hours_base == Decimal("182")


def test_loader_minimum_wage(loader):
    """Test loading minimum wage."""
    loader.load_all()

    # Get wage for April 2024
    wage = loader.get_minimum_wage((2024, 4))
    assert wage.hourly == Decimal("32.30")
    assert wage.monthly == Decimal("5880.02")

    # Get wage for January 2024 (should get 2023 rate)
    wage = loader.get_minimum_wage((2024, 1))
    assert wage.hourly == Decimal("30.61")


def test_loader_recreation_days(loader):
    """Test loading recreation days."""
    loader.load_all()

    # General industry, 2 years
    days = loader.get_recreation_days("general", 2)
    assert days == 6

    # Construction, 5 years (range 5-10 = 9 days)
    days = loader.get_recreation_days("construction", 5)
    assert days == 9

    # Unknown industry falls back to general
    days = loader.get_recreation_days("unknown", 5)
    assert days == 7


def test_loader_recreation_day_value(loader):
    """Test loading recreation day value."""
    loader.load_all()

    value, effective_date = loader.get_recreation_day_value(date(2024, 1, 1), "general")
    assert value == Decimal("418.00")
    assert effective_date == date(2023, 7, 1)


def test_loader_travel_allowance(loader):
    """Test loading travel allowance."""
    loader.load_all()

    amount = loader.get_travel_allowance(date(2025, 3, 1))
    assert amount == Decimal("22.60")


def test_loader_holiday_dates(loader):
    """Test loading holiday dates."""
    loader.load_all()

    holidays = loader.get_holiday_dates(2024)

    # Should have 9 holidays
    assert len(holidays) == 9

    # Check specific holidays
    holiday_ids = {h.holiday_id for h in holidays}
    assert "rosh_hashana_1" in holiday_ids
    assert "yom_kippur" in holiday_ids
    assert "pesach" in holiday_ids
    assert "shavuot" in holiday_ids

    # Check Rosh Hashana 2024 date
    rosh_hashana = next(h for h in holidays if h.holiday_id == "rosh_hashana_1")
    assert rosh_hashana.gregorian_date == date(2024, 10, 3)


def test_loader_shabbat_times(loader):
    """Test loading shabbat times."""
    loader.load_all()

    # Get shabbat times for a specific Friday in Jerusalem
    friday = date(2024, 1, 5)
    times = loader.get_shabbat_times(friday, "jerusalem")

    assert times.date == friday
    assert times.candles.hour == 16
    assert times.havdalah.hour == 17


def test_loader_shabbat_times_tel_aviv(loader):
    """Test shabbat times for Tel Aviv."""
    loader.load_all()

    friday = date(2024, 1, 5)
    times = loader.get_shabbat_times(friday, "tel_aviv")

    assert times.date == friday
    # Tel Aviv has later candle lighting than Jerusalem (18 min vs 40 min before sunset)
    assert times.candles.hour == 16
