#!/usr/bin/env python3
"""Generate holiday_dates.csv from Hebrew calendar.

Generates 9 holidays × 200 years (1948-2148).
Uses pyluach for Hebrew-to-Gregorian date conversion.

Output format:
    year,holiday_id,hebrew_date,gregorian_date
    2024,rosh_hashana_1,א' תשרי,2024-10-03
"""

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pyluach import dates, hebrewcal


@dataclass
class HolidayDefinition:
    """Definition of a Hebrew holiday."""
    id: str
    name: str
    hebrew_date_display: str
    month: int  # Hebrew month (1=Nissan, 7=Tishrei)
    day: int


# 9 holidays as defined in the skill
HOLIDAYS = [
    HolidayDefinition("rosh_hashana_1", "ראש השנה א'", "א' תשרי", 7, 1),
    HolidayDefinition("rosh_hashana_2", "ראש השנה ב'", "ב' תשרי", 7, 2),
    HolidayDefinition("yom_kippur", "יום כיפור", "י' תשרי", 7, 10),
    HolidayDefinition("sukkot", "סוכות", "ט\"ו תשרי", 7, 15),
    HolidayDefinition("hoshana_raba", "הושענא רבה", "כ\"א תשרי", 7, 21),
    HolidayDefinition("pesach", "פסח", "ט\"ו ניסן", 1, 15),
    HolidayDefinition("pesach_7", "שביעי של פסח", "כ\"א ניסן", 1, 21),
    HolidayDefinition("yom_haatzmaut", "יום העצמאות", "ה' אייר", 2, 5),
    HolidayDefinition("shavuot", "שבועות", "ו' סיוון", 3, 6),
]

# Year range
START_YEAR = 1948
END_YEAR = 2148


def get_hebrew_year_for_gregorian(gregorian_year: int) -> int:
    """Get the Hebrew year that starts in the given Gregorian year.

    Hebrew year 5785 starts in Gregorian 2024.
    """
    # Approximate: Hebrew year = Gregorian year + 3760 or 3761
    # More precise: check when Rosh Hashana falls
    return gregorian_year + 3761


def hebrew_to_gregorian(hebrew_year: int, hebrew_month: int, hebrew_day: int) -> date:
    """Convert Hebrew date to Gregorian date."""
    try:
        heb_date = dates.HebrewDate(hebrew_year, hebrew_month, hebrew_day)
        greg_date = heb_date.to_pydate()
        return greg_date
    except ValueError:
        # Invalid date (e.g., 30 Cheshvan in a short year)
        return None


def adjust_yom_haatzmaut(greg_date: date) -> date:
    """Adjust Yom Ha'atzmaut to avoid Shabbat proximity.

    Official rules:
    - If 5 Iyyar falls on Friday or Saturday, move to Thursday (3 or 4 Iyyar)
    - If 5 Iyyar falls on Monday, move to Tuesday (6 Iyyar)

    This is the official Israeli government policy.
    """
    weekday = greg_date.weekday()  # 0=Monday, 6=Sunday

    if weekday == 4:  # Friday - move to Thursday
        return greg_date - timedelta(days=1)
    elif weekday == 5:  # Saturday - move to Thursday
        return greg_date - timedelta(days=2)
    elif weekday == 0:  # Monday - move to Tuesday
        return greg_date + timedelta(days=1)

    return greg_date


def generate_holidays_for_year(gregorian_year: int) -> list[dict]:
    """Generate all 9 holidays for a given Gregorian year."""
    results = []

    for holiday in HOLIDAYS:
        # For holidays in Tishrei (month 7), they occur at the START of the Hebrew year
        # which begins in the fall of the Gregorian year
        # For holidays in Nissan-Sivan (months 1-3), they occur in spring

        if holiday.month >= 7:  # Tishrei onwards (fall holidays)
            # These occur when the Hebrew year STARTS in this Gregorian year
            hebrew_year = get_hebrew_year_for_gregorian(gregorian_year)
        else:  # Nissan-Sivan (spring holidays)
            # These occur in the Hebrew year that STARTED the previous fall
            hebrew_year = get_hebrew_year_for_gregorian(gregorian_year - 1)

        greg_date = hebrew_to_gregorian(hebrew_year, holiday.month, holiday.day)

        if greg_date is None:
            continue

        # Check if this date is actually in the target Gregorian year
        if greg_date.year != gregorian_year:
            # Try adjacent Hebrew years
            if holiday.month >= 7:
                hebrew_year = get_hebrew_year_for_gregorian(gregorian_year - 1)
            else:
                hebrew_year = get_hebrew_year_for_gregorian(gregorian_year)

            greg_date = hebrew_to_gregorian(hebrew_year, holiday.month, holiday.day)

            if greg_date is None or greg_date.year != gregorian_year:
                continue

        # Special handling for Yom Ha'atzmaut
        if holiday.id == "yom_haatzmaut":
            greg_date = adjust_yom_haatzmaut(greg_date)

        results.append({
            "year": gregorian_year,
            "holiday_id": holiday.id,
            "hebrew_date": holiday.hebrew_date_display,
            "gregorian_date": greg_date.isoformat(),
        })

    # Sort by gregorian_date
    results.sort(key=lambda x: x["gregorian_date"])

    return results


def main():
    """Generate holiday_dates.csv."""
    output_path = Path(__file__).parent.parent / "data" / "holiday_dates.csv"

    all_holidays = []

    for year in range(START_YEAR, END_YEAR + 1):
        holidays = generate_holidays_for_year(year)
        all_holidays.extend(holidays)

        if year % 50 == 0:
            print(f"Processed year {year}...")

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "holiday_id", "hebrew_date", "gregorian_date"])
        writer.writeheader()
        writer.writerows(all_holidays)

    print(f"Generated {len(all_holidays)} holiday entries to {output_path}")
    print(f"Years: {START_YEAR}-{END_YEAR}")

    # Verify sample
    print("\nSample entries for 2024:")
    for h in all_holidays:
        if h["year"] == 2024:
            print(f"  {h['holiday_id']}: {h['gregorian_date']} ({h['hebrew_date']})")


if __name__ == "__main__":
    main()
