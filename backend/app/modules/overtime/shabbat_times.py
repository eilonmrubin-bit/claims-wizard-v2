"""Shabbat times service.

Loads candle lighting and havdalah times from static CSV files.
"""

import csv
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import NamedTuple

from ...ssot import District


class ShabbatTime(NamedTuple):
    """Shabbat times for a specific Friday."""
    friday_date: date
    candles: datetime
    havdalah: datetime


# Map District enum to CSV filename
DISTRICT_FILES = {
    District.JERUSALEM: "jerusalem.csv",
    District.TEL_AVIV: "tel_aviv.csv",
    District.HAIFA: "haifa.csv",
    District.SOUTH: "beer_sheva.csv",
    District.GALIL: "nof_hagalil.csv",
}

# Cache for loaded data
_cache: dict[District, dict[date, ShabbatTime]] = {}


def _get_data_path() -> Path:
    """Get path to shabbat_times data directory."""
    # Go up from app/modules/overtime to app, then to data
    module_dir = Path(__file__).parent
    return module_dir.parent.parent.parent / "data" / "shabbat_times"


def _load_district_data(district: District) -> dict[date, ShabbatTime]:
    """Load all Shabbat times for a district from CSV."""
    if district in _cache:
        return _cache[district]

    data_path = _get_data_path()
    filename = DISTRICT_FILES.get(district)
    if not filename:
        raise ValueError(f"Unknown district: {district}")

    csv_path = data_path / filename
    if not csv_path.exists():
        raise FileNotFoundError(f"Shabbat times file not found: {csv_path}")

    result: dict[date, ShabbatTime] = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            friday_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            candles_time = datetime.strptime(row["candles"], "%H:%M").time()
            havdalah_time = datetime.strptime(row["havdalah"], "%H:%M").time()

            # Candles are on Friday, havdalah on Saturday
            candles_dt = datetime.combine(friday_date, candles_time)
            saturday = friday_date + timedelta(days=1)
            havdalah_dt = datetime.combine(saturday, havdalah_time)

            result[friday_date] = ShabbatTime(
                friday_date=friday_date,
                candles=candles_dt,
                havdalah=havdalah_dt,
            )

    _cache[district] = result
    return result


def get_shabbat_times(d: date, district: District) -> ShabbatTime | None:
    """Get Shabbat times for the week containing the given date.

    Args:
        d: Any date in the week
        district: District for candle lighting times

    Returns:
        ShabbatTime for that week's Shabbat, or None if not found
    """
    data = _load_district_data(district)

    # Find the Friday for this week
    # Friday is weekday 4
    days_until_friday = (4 - d.weekday()) % 7
    if days_until_friday == 0 and d.weekday() != 4:
        # It's not Friday, so go to next Friday
        days_until_friday = 7

    # If date is Saturday or Sunday, look at the previous Friday
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        days_since_friday = (d.weekday() - 4) % 7
        friday = d - timedelta(days=days_since_friday)
    else:
        friday = d + timedelta(days=days_until_friday)

    return data.get(friday)


def get_shabbat_times_range(
    start_date: date,
    end_date: date,
    district: District,
) -> dict[date, ShabbatTime]:
    """Get all Shabbat times in a date range.

    Args:
        start_date: Start of range
        end_date: End of range
        district: District for candle lighting times

    Returns:
        Dict mapping Friday dates to ShabbatTime
    """
    data = _load_district_data(district)

    result: dict[date, ShabbatTime] = {}

    # Find first Friday on or before start_date
    days_since_friday = (start_date.weekday() - 4) % 7
    first_friday = start_date - timedelta(days=days_since_friday)
    if first_friday > start_date:
        first_friday -= timedelta(days=7)

    # Find last Friday on or after end_date
    days_to_friday = (4 - end_date.weekday()) % 7
    last_friday = end_date + timedelta(days=days_to_friday)
    if last_friday < end_date:
        last_friday += timedelta(days=7)

    # Add extra week on each side to be safe
    first_friday -= timedelta(days=7)
    last_friday += timedelta(days=7)

    # Iterate through all Fridays
    current = first_friday
    while current <= last_friday:
        if current in data:
            result[current] = data[current]
        current += timedelta(days=7)

    return result


def clear_cache():
    """Clear the cache (for testing)."""
    _cache.clear()
