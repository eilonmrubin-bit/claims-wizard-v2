"""Holiday pay (דמי חגים) calculation module.

Calculates holiday pay entitlement based on Israeli labor law.

See docs/skills/holidays/SKILL.md for complete documentation.
"""

import csv
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from app.ssot import (
    RestDay,
    WeekType,
    HolidayEntry,
    HolidayYearResult,
    HolidaysResult,
)


# Holiday names mapping
HOLIDAY_NAMES = {
    "rosh_hashana_1": "ראש השנה א'",
    "rosh_hashana_2": "ראש השנה ב'",
    "yom_kippur": "יום כיפור",
    "sukkot": "סוכות",
    "hoshana_raba": "הושענא רבה",
    "pesach": "פסח",
    "pesach_7": "שביעי של פסח",
    "yom_haatzmaut": "יום העצמאות",
    "shavuot": "שבועות",
}

# Day of week names
DAY_NAMES = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}

@dataclass
class HolidayDate:
    """Holiday date from static data."""
    holiday_id: str
    name: str
    hebrew_date: str
    gregorian_date: date


# Module-level cache for holiday data
_holiday_cache: dict[int, list[HolidayDate]] | None = None


def _load_holiday_data(data_path: Path | None = None) -> dict[int, list[HolidayDate]]:
    """Load holiday dates from CSV file, grouped by year."""
    global _holiday_cache

    if _holiday_cache is not None:
        return _holiday_cache

    if data_path is None:
        data_path = Path(__file__).parent.parent.parent / "data" / "holiday_dates.csv"

    holidays_by_year: dict[int, list[HolidayDate]] = {}

    with open(data_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year = int(row["year"])
            holiday_id = row["holiday_id"]

            holiday = HolidayDate(
                holiday_id=holiday_id,
                name=HOLIDAY_NAMES.get(holiday_id, holiday_id),
                hebrew_date=row["hebrew_date"],
                gregorian_date=date.fromisoformat(row["gregorian_date"]),
            )

            if year not in holidays_by_year:
                holidays_by_year[year] = []
            holidays_by_year[year].append(holiday)

    _holiday_cache = holidays_by_year
    return holidays_by_year


def _clear_holiday_cache():
    """Clear holiday cache (for testing)."""
    global _holiday_cache
    _holiday_cache = None


def get_holiday_dates(year: int, data_path: Path | None = None) -> list[HolidayDate]:
    """Get all holiday dates for a given year."""
    holidays_by_year = _load_holiday_data(data_path)
    return holidays_by_year.get(year, [])


def _get_day_of_week(d: date) -> int:
    """Get day of week (0=Sunday, 6=Saturday)."""
    # Python weekday(): 0=Monday, 6=Sunday
    # Convert to 0=Sunday, 6=Saturday
    return (d.weekday() + 1) % 7


def _rest_day_to_dow(rest_day: RestDay) -> int:
    """Convert RestDay enum to day of week number."""
    if rest_day == RestDay.SATURDAY:
        return 6
    elif rest_day == RestDay.FRIDAY:
        return 5
    elif rest_day == RestDay.SUNDAY:
        return 0
    return 6  # Default to Saturday


def _get_eve_of_rest(rest_day: RestDay) -> int:
    """Get the day of week that is eve of rest."""
    if rest_day == RestDay.SATURDAY:
        return 5  # Friday
    elif rest_day == RestDay.FRIDAY:
        return 4  # Thursday
    elif rest_day == RestDay.SUNDAY:
        return 6  # Saturday
    return 5  # Default to Friday


def calculate_year_entitlement(
    year: int,
    rest_day: RestDay,
    is_employed_on_date: Callable[[date], bool],
    get_week_type: Callable[[date], WeekType],
    get_daily_salary: Callable[[date], Decimal],
    get_max_daily_salary_in_year: Callable[[int], Decimal],
    seniority_eligibility_date: date | None,
    is_employed_in_year: Callable[[int], bool],
    data_path: Path | None = None,
) -> HolidayYearResult:
    """Calculate holiday entitlement for a single calendar year.

    Args:
        year: The calendar year
        rest_day: Worker's rest day
        is_employed_on_date: Function to check if worker was employed on a date
        get_week_type: Function to get week type (5/6) for a date
        get_daily_salary: Function to get salary_daily for a date
        get_max_daily_salary_in_year: Function to get max salary_daily in a year
        seniority_eligibility_date: Date when worker became eligible for holidays (None if never)
        is_employed_in_year: Function to check if at least 1 daily_record exists in the year
        data_path: Optional path to holiday CSV

    Returns:
        HolidayYearResult with entitlement details
    """
    result = HolidayYearResult(
        year=year,
        holidays=[],
        election_day_entitled=False,
        total_entitled_days=0,
        total_claim=Decimal("0"),
    )

    # Step 0: If no seniority eligibility — no entitlement at all
    if seniority_eligibility_date is None:
        return result

    # Step 1: Get holiday dates for this year
    holidays = get_holiday_dates(year, data_path)

    rest_dow = _rest_day_to_dow(rest_day)
    eve_of_rest_dow = _get_eve_of_rest(rest_day)

    total_claim = Decimal("0")
    entitled_count = 0

    # Step 2-3: Process each holiday
    for h in holidays:
        dow = _get_day_of_week(h.gregorian_date)
        employed = is_employed_on_date(h.gregorian_date)

        # Check if holiday is before seniority eligibility date
        before_seniority = h.gregorian_date < seniority_eligibility_date

        # Get week type for this specific holiday (None if not employed)
        week_type = get_week_type(h.gregorian_date) if employed else None

        is_rest = dow == rest_dow
        is_eve = dow == eve_of_rest_dow

        # Determine exclusion
        excluded = False
        exclude_reason = None

        if not employed:
            excluded = True
            exclude_reason = "לא הועסק בתאריך החג"
        elif before_seniority:
            excluded = True
            exclude_reason = "טרם השלמת 3 חודשי ותק"
        elif is_rest:
            excluded = True
            exclude_reason = "חג שחל ביום המנוחה"
        elif week_type == WeekType.FIVE_DAY and is_eve:
            excluded = True
            exclude_reason = "חג שחל בערב מנוחה (שבוע 5 ימים)"

        entitled = employed and not before_seniority and not excluded

        # Get day value if entitled
        day_value = None
        claim_amount = None
        if entitled:
            day_value = get_daily_salary(h.gregorian_date)
            claim_amount = day_value
            total_claim += claim_amount
            entitled_count += 1

        entry = HolidayEntry(
            name=h.name,
            hebrew_date=h.hebrew_date,
            gregorian_date=h.gregorian_date,
            employed_on_date=employed,
            before_seniority=before_seniority,
            day_of_week=DAY_NAMES[dow],
            week_type=week_type,
            is_rest_day=is_rest,
            is_eve_of_rest=is_eve,
            excluded=excluded,
            exclude_reason=exclude_reason,
            entitled=entitled,
            day_value=day_value,
            claim_amount=claim_amount,
        )
        result.holidays.append(entry)

    # Step 4: Election day
    # Entitled if: (a) seniority gate passed before end of year, AND (b) at least 1 daily_record in this year
    year_end = date(year, 12, 31)
    election_day_entitled = (
        seniority_eligibility_date <= year_end
        and is_employed_in_year(year)
    )

    if election_day_entitled:
        result.election_day_entitled = True
        election_day_value = get_max_daily_salary_in_year(year)
        result.election_day_value = election_day_value
        entitled_count += 1
        total_claim += election_day_value

    result.total_entitled_days = entitled_count
    result.total_claim = total_claim

    return result


def calculate_all_years(
    start_year: int,
    end_year: int,
    rest_day: RestDay,
    is_employed_on_date: Callable[[date], bool],
    get_week_type: Callable[[date], WeekType],
    get_daily_salary: Callable[[date], Decimal],
    get_max_daily_salary_in_year: Callable[[int], Decimal],
    seniority_eligibility_date: date | None,
    is_employed_in_year: Callable[[int], bool],
    data_path: Path | None = None,
) -> HolidaysResult:
    """Calculate holiday entitlement for all years in employment period.

    Args:
        start_year: First calendar year of employment
        end_year: Last calendar year of employment
        rest_day: Worker's rest day
        is_employed_on_date: Function to check if worker was employed on a date
        get_week_type: Function to get week type (5/6) for a date
        get_daily_salary: Function to get salary_daily for a date
        get_max_daily_salary_in_year: Function to get max salary_daily in a year
        seniority_eligibility_date: Date when worker became eligible for holidays (None if never)
        is_employed_in_year: Function to check if at least 1 daily_record exists in the year
        data_path: Optional path to holiday CSV

    Returns:
        HolidaysResult with all years
    """
    result = HolidaysResult(
        seniority_eligibility_date=seniority_eligibility_date,
        per_year=[],
        grand_total_days=0,
        grand_total_claim=Decimal("0"),
    )

    for year in range(start_year, end_year + 1):
        year_result = calculate_year_entitlement(
            year=year,
            rest_day=rest_day,
            is_employed_on_date=is_employed_on_date,
            get_week_type=get_week_type,
            get_daily_salary=get_daily_salary,
            get_max_daily_salary_in_year=get_max_daily_salary_in_year,
            seniority_eligibility_date=seniority_eligibility_date,
            is_employed_in_year=is_employed_in_year,
            data_path=data_path,
        )
        result.per_year.append(year_result)
        result.grand_total_days += year_result.total_entitled_days
        result.grand_total_claim += year_result.total_claim

    return result
