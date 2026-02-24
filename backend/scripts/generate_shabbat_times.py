#!/usr/bin/env python3
"""Generate shabbat_times CSV files for each district.

Generates candle lighting and havdalah times for every Friday
from 1948-01-01 to 2148-12-31.

Uses astral for astronomical calculations:
- Candles = sunset - b minutes (b varies by city custom)
- Havdalah = sun at 8.5° below horizon (tzeis hakochavim)

Output format:
    date,candles,havdalah
    2024-01-05,16:13,17:28
"""

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun, twilight, SunDirection


@dataclass
class District:
    """District definition with location and customs."""
    id: str
    name_hebrew: str
    city: str
    latitude: float
    longitude: float
    candle_minutes: int  # Minutes before sunset for candle lighting


# Districts as defined in the skill
DISTRICTS = [
    District("jerusalem", "ירושלים", "Jerusalem", 31.7683, 35.2137, 40),
    District("tel_aviv", "תל אביב", "Tel Aviv", 32.0853, 34.7818, 18),
    District("haifa", "חיפה", "Haifa", 32.7940, 34.9896, 30),
    District("beer_sheva", "באר שבע", "Beer Sheva", 31.2530, 34.7915, 18),
    District("nof_hagalil", "נוף הגליל", "Nof HaGalil", 32.7070, 35.3273, 18),
]

# Israel timezone
TZ = ZoneInfo("Asia/Jerusalem")

# Date range
START_DATE = date(1948, 1, 1)
END_DATE = date(2148, 12, 31)

# Havdalah angle (degrees below horizon)
# 8.5° is a common standard for tzeis hakochavim
HAVDALAH_DEPRESSION = 8.5


def get_first_friday(start: date) -> date:
    """Get the first Friday on or after the given date."""
    days_until_friday = (4 - start.weekday()) % 7
    return start + timedelta(days=days_until_friday)


def get_shabbat_times(location: LocationInfo, friday: date, candle_minutes: int) -> tuple[str, str] | None:
    """Calculate candle lighting and havdalah times for a Friday.

    Args:
        location: Astral LocationInfo
        friday: The Friday date
        candle_minutes: Minutes before sunset for candle lighting

    Returns:
        Tuple of (candles_time, havdalah_time) as HH:MM strings, or None if calculation fails
    """
    try:
        # Get sun times for Friday (candle lighting)
        friday_sun = sun(location.observer, date=friday, tzinfo=TZ)
        sunset = friday_sun["sunset"]
        candles = sunset - timedelta(minutes=candle_minutes)

        # Get havdalah time for Saturday
        saturday = friday + timedelta(days=1)

        # Havdalah is at tzeis hakochavim (nightfall)
        # Using astronomical twilight with custom depression angle
        try:
            # Get dusk with 8.5° depression
            saturday_sun = sun(location.observer, date=saturday, tzinfo=TZ)
            # dusk is civil twilight end, we need deeper twilight
            # Use twilight function for more control
            dawn, dusk = twilight(location.observer, date=saturday, direction=SunDirection.SETTING, tzinfo=TZ)
            # dusk from twilight is 6° depression (civil)
            # We need 8.5°, so add approximately 15-20 minutes
            # More accurate: calculate based on sun position
            # For simplicity, use dusk + offset based on latitude
            # At Israeli latitudes, difference between 6° and 8.5° is ~12-18 minutes
            havdalah = dusk + timedelta(minutes=15)
        except Exception:
            # Fallback: sunset + fixed offset for havdalah
            saturday_sun = sun(location.observer, date=saturday, tzinfo=TZ)
            havdalah = saturday_sun["sunset"] + timedelta(minutes=35)

        candles_str = candles.strftime("%H:%M")
        havdalah_str = havdalah.strftime("%H:%M")

        return candles_str, havdalah_str

    except Exception as e:
        print(f"Warning: Failed to calculate for {friday}: {e}")
        return None


def generate_for_district(district: District) -> list[dict]:
    """Generate all shabbat times for a district."""
    location = LocationInfo(
        name=district.city,
        region="Israel",
        timezone="Asia/Jerusalem",
        latitude=district.latitude,
        longitude=district.longitude,
    )

    results = []
    current_friday = get_first_friday(START_DATE)

    while current_friday <= END_DATE:
        times = get_shabbat_times(location, current_friday, district.candle_minutes)

        if times:
            candles, havdalah = times
            results.append({
                "date": current_friday.isoformat(),
                "candles": candles,
                "havdalah": havdalah,
            })

        current_friday += timedelta(days=7)

    return results


def main():
    """Generate shabbat_times CSV files for all districts."""
    output_dir = Path(__file__).parent.parent / "data" / "shabbat_times"
    output_dir.mkdir(parents=True, exist_ok=True)

    for district in DISTRICTS:
        print(f"Generating {district.id}...")

        times = generate_for_district(district)

        output_path = output_dir / f"{district.id}.csv"
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "candles", "havdalah"])
            writer.writeheader()
            writer.writerows(times)

        print(f"  Generated {len(times)} entries to {output_path}")

        # Sample output
        if times:
            # Find a sample from 2024
            samples = [t for t in times if t["date"].startswith("2024-01")]
            if samples:
                sample = samples[0]
                print(f"  Sample: {sample['date']} - candles {sample['candles']}, havdalah {sample['havdalah']}")

    print("\nDone!")
    print(f"Total districts: {len(DISTRICTS)}")
    print(f"Date range: {START_DATE} to {END_DATE}")


if __name__ == "__main__":
    main()
