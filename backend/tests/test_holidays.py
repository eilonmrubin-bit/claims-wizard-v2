"""Tests for holiday pay module.

Test cases from docs/skills/holidays/SKILL.md.
"""

import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import os

from app.modules.holidays import (
    calculate_year_entitlement,
    calculate_all_years,
    calculate_threshold,
    get_holiday_dates,
    _get_day_of_week,
    _get_eve_of_rest,
    _clear_holiday_cache,
    HOLIDAY_NAMES,
)
from app.ssot import RestDay, WeekType


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear holiday cache before each test."""
    _clear_holiday_cache()
    yield
    _clear_holiday_cache()


@pytest.fixture
def test_data_path():
    """Create a test holiday CSV file."""
    content = """year,holiday_id,hebrew_date,gregorian_date
2024,rosh_hashana_1,א' תשרי,2024-10-03
2024,rosh_hashana_2,ב' תשרי,2024-10-04
2024,yom_kippur,י' תשרי,2024-10-12
2024,sukkot,"ט""ו תשרי",2024-10-17
2024,hoshana_raba,"כ""א תשרי",2024-10-23
2024,pesach,"ט""ו ניסן",2024-04-23
2024,pesach_7,"כ""א ניסן",2024-04-29
2024,yom_haatzmaut,ה' אייר,2024-05-14
2024,shavuot,ו' סיוון,2024-06-12
2023,rosh_hashana_1,א' תשרי,2023-09-16
2023,rosh_hashana_2,ב' תשרי,2023-09-17
2023,yom_kippur,י' תשרי,2023-09-25
2023,sukkot,"ט""ו תשרי",2023-09-30
2023,hoshana_raba,"כ""א תשרי",2023-10-06
2023,pesach,"ט""ו ניסן",2023-04-06
2023,pesach_7,"כ""א ניסן",2023-04-12
2023,yom_haatzmaut,ה' אייר,2023-04-26
2023,shavuot,ו' סיוון,2023-05-26
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(content)
        path = Path(f.name)
    yield path
    os.unlink(path)


class TestThreshold:
    """Test the 1/10 threshold calculation."""

    def test_threshold_365_days(self):
        """1/10 of 365 = 36.5, rounded up = 37."""
        assert calculate_threshold(365) == 37

    def test_threshold_366_days(self):
        """1/10 of 366 = 36.6, rounded up = 37."""
        assert calculate_threshold(366) == 37


class TestDayOfWeek:
    """Test day of week calculations."""

    def test_sunday(self):
        """2024-10-06 is Sunday."""
        assert _get_day_of_week(date(2024, 10, 6)) == 0

    def test_saturday(self):
        """2024-10-05 is Saturday."""
        assert _get_day_of_week(date(2024, 10, 5)) == 6

    def test_friday(self):
        """2024-10-04 is Friday."""
        assert _get_day_of_week(date(2024, 10, 4)) == 5

    def test_thursday(self):
        """2024-10-03 is Thursday."""
        assert _get_day_of_week(date(2024, 10, 3)) == 4


class TestEveOfRest:
    """Test eve of rest resolution."""

    def test_eve_of_saturday_is_friday(self):
        """Eve of Saturday rest = Friday."""
        assert _get_eve_of_rest(RestDay.SATURDAY) == 5

    def test_eve_of_friday_is_thursday(self):
        """Eve of Friday rest = Thursday."""
        assert _get_eve_of_rest(RestDay.FRIDAY) == 4

    def test_eve_of_sunday_is_saturday(self):
        """Eve of Sunday rest = Saturday."""
        assert _get_eve_of_rest(RestDay.SUNDAY) == 6


class TestHolidayLoading:
    """Test loading holidays from CSV."""

    def test_load_holidays_for_year(self, test_data_path):
        """Load holidays for a specific year."""
        holidays = get_holiday_dates(2024, test_data_path)

        assert len(holidays) == 9
        assert holidays[0].holiday_id == "rosh_hashana_1"
        assert holidays[0].name == "ראש השנה א'"

    def test_missing_year_returns_empty(self, test_data_path):
        """Missing year returns empty list."""
        holidays = get_holiday_dates(2025, test_data_path)
        assert holidays == []


class TestBelowThreshold:
    """Test cases where worker is below 1/10 threshold."""

    def test_below_threshold_no_entitlement(self, test_data_path):
        """Worker below threshold gets 0 holidays."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 30,  # Below 37
            data_path=test_data_path,
        )

        assert result.met_threshold is False
        assert result.total_entitled_days == 0
        assert result.total_claim == Decimal("0")
        assert result.election_day_entitled is False


class TestRestDayExclusion:
    """Test holidays excluded when falling on rest day."""

    def test_holiday_on_saturday_excluded(self, test_data_path):
        """Holiday on Saturday (rest day) is excluded."""
        # Yom Kippur 2024 is on Saturday (2024-10-12)
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        yom_kippur = next(h for h in result.holidays if h.name == "יום כיפור")
        assert yom_kippur.excluded is True
        assert yom_kippur.exclude_reason == "חג שחל ביום המנוחה"
        assert yom_kippur.entitled is False

    def test_holiday_on_friday_with_friday_rest(self, test_data_path):
        """Holiday on Friday excluded when Friday is rest day."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.FRIDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.SIX_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # Rosh Hashana 2024-10-04 is Friday
        rosh_hashana_2 = next(h for h in result.holidays if h.name == "ראש השנה ב'")
        assert rosh_hashana_2.is_rest_day is True
        assert rosh_hashana_2.excluded is True


class TestEveOfRestExclusion:
    """Test holidays excluded on eve of rest (5-day week only)."""

    def test_friday_excluded_in_5day_week(self, test_data_path):
        """Friday holiday excluded in 5-day week (eve of Saturday rest)."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # Rosh Hashana 2 (2024-10-04) is Friday
        rosh_hashana_2 = next(h for h in result.holidays if h.name == "ראש השנה ב'")
        assert rosh_hashana_2.is_eve_of_rest is True
        assert rosh_hashana_2.excluded is True
        assert rosh_hashana_2.exclude_reason == "חג שחל בערב מנוחה (שבוע 5 ימים)"

    def test_friday_entitled_in_6day_week(self, test_data_path):
        """Friday holiday entitled in 6-day week."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.SIX_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # Rosh Hashana 2 (2024-10-04) is Friday
        rosh_hashana_2 = next(h for h in result.holidays if h.name == "ראש השנה ב'")
        assert rosh_hashana_2.is_eve_of_rest is True
        assert rosh_hashana_2.excluded is False  # Not excluded in 6-day week!
        assert rosh_hashana_2.entitled is True


class TestWeekTypePerHoliday:
    """Test that week type is determined per holiday individually."""

    def test_different_week_types_per_holiday(self, test_data_path):
        """Different holidays can have different week types."""
        def get_week_type(d: date) -> WeekType:
            # April holidays: 5-day week, October holidays: 6-day week
            if d.month == 4:
                return WeekType.FIVE_DAY
            return WeekType.SIX_DAY

        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=get_week_type,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # October holiday on Friday should be entitled (6-day week)
        rosh_hashana_2 = next(h for h in result.holidays if h.name == "ראש השנה ב'")
        assert rosh_hashana_2.week_type == WeekType.SIX_DAY
        assert rosh_hashana_2.entitled is True


class TestElectionDay:
    """Test election day entitlement."""

    def test_election_day_always_entitled(self, test_data_path):
        """Election day always entitled if threshold met."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("300"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        assert result.election_day_entitled is True

    def test_election_day_uses_max_salary(self, test_data_path):
        """Election day uses highest salary_daily in year."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("350"),  # Higher than daily
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # Election day value should be 350, not 250
        # Total should include the 350 for election day
        # We can verify by checking total claim includes the max salary
        entitled_holidays = [h for h in result.holidays if h.entitled]
        holiday_sum = sum(h.claim_amount for h in entitled_holidays)

        # Total = holiday_sum + election_day_value (350)
        assert result.total_claim == holiday_sum + Decimal("350")


class TestPartialYear:
    """Test partial year scenarios."""

    def test_partial_year_started_late(self, test_data_path):
        """Partial year - started in October."""
        # Only employed from Oct 1, 2024 onwards (92 days)
        # Threshold = 37, so eligible
        # Only holidays from Oct onward should be considered

        def is_employed(d: date) -> bool:
            return d >= date(2024, 10, 1)

        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=is_employed,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 92,
            data_path=test_data_path,
        )

        assert result.met_threshold is True

        # April holidays should be excluded (not employed)
        pesach = next(h for h in result.holidays if h.name == "פסח")
        assert pesach.employed_on_date is False
        assert pesach.excluded is True

        # October holidays should be checked
        rosh_hashana_1 = next(h for h in result.holidays if h.name == "ראש השנה א'")
        assert rosh_hashana_1.employed_on_date is True

    def test_partial_year_ended_early(self, test_data_path):
        """Partial year - ended in March."""

        def is_employed(d: date) -> bool:
            return d <= date(2024, 3, 31)

        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=is_employed,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 91,
            data_path=test_data_path,
        )

        assert result.met_threshold is True

        # October holidays should be excluded (not employed)
        rosh_hashana_1 = next(h for h in result.holidays if h.name == "ראש השנה א'")
        assert rosh_hashana_1.employed_on_date is False


class TestMultipleYears:
    """Test calculation across multiple years."""

    def test_calculate_all_years(self, test_data_path):
        """Calculate for 2023 and 2024."""
        result = calculate_all_years(
            start_year=2023,
            end_year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        assert len(result.per_year) == 2
        assert result.per_year[0].year == 2023
        assert result.per_year[1].year == 2024
        assert result.grand_total_days > 0
        assert result.grand_total_claim > Decimal("0")


class TestDayValue:
    """Test day value calculation."""

    def test_day_value_from_salary(self, test_data_path):
        """Day value comes from salary_daily for that date."""

        def get_daily_salary(d: date) -> Decimal:
            if d.month >= 7:
                return Decimal("300")
            return Decimal("250")

        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.SIX_DAY,
            get_daily_salary=get_daily_salary,
            get_max_daily_salary_in_year=lambda y: Decimal("300"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # April holiday (Pesach) should have 250
        pesach = next(h for h in result.holidays if h.name == "פסח")
        if pesach.entitled:
            assert pesach.day_value == Decimal("250")

        # October holiday should have 300
        rosh_hashana_1 = next(h for h in result.holidays if h.name == "ראש השנה א'")
        if rosh_hashana_1.entitled:
            assert rosh_hashana_1.day_value == Decimal("300")


class TestEdgeCases:
    """Test edge cases from skill doc."""

    def test_edge_case_1_saturday_rest_saturday_holiday(self, test_data_path):
        """Edge case 1: Holiday on Saturday AND rest day is Saturday."""
        # Yom Kippur 2024 is Saturday
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        yom_kippur = next(h for h in result.holidays if h.name == "יום כיפור")
        assert yom_kippur.excluded is True
        assert yom_kippur.is_rest_day is True

    def test_edge_case_2_friday_eve_5day(self, test_data_path):
        """Edge case 2: Friday holiday, Saturday rest, 5-day week = excluded."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # 2024-10-04 (Rosh Hashana 2) is Friday
        rh2 = next(h for h in result.holidays if h.name == "ראש השנה ב'")
        assert rh2.excluded is True
        assert rh2.exclude_reason == "חג שחל בערב מנוחה (שבוע 5 ימים)"

    def test_edge_case_3_friday_eve_6day(self, test_data_path):
        """Edge case 3: Friday holiday, Saturday rest, 6-day week = entitled."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.SIX_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        rh2 = next(h for h in result.holidays if h.name == "ראש השנה ב'")
        assert rh2.excluded is False
        assert rh2.entitled is True

    def test_edge_case_4_friday_rest_friday(self, test_data_path):
        """Edge case 4: Friday holiday, Friday rest = excluded (it IS rest day)."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.FRIDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.SIX_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        rh2 = next(h for h in result.holidays if h.name == "ראש השנה ב'")
        assert rh2.is_rest_day is True
        assert rh2.excluded is True

    def test_edge_case_10_election_day_highest_salary(self, test_data_path):
        """Edge case 10: Election day uses highest salary, not chronological."""

        def get_max_salary(year: int) -> Decimal:
            # Simulate: ₪250/day Jan-Jun, ₪300/day Jul-Dec
            # Max is ₪300
            return Decimal("300")

        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.FIVE_DAY,
            get_daily_salary=lambda d: Decimal("250") if d.month < 7 else Decimal("300"),
            get_max_daily_salary_in_year=get_max_salary,
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        # The total includes election day at max value
        entitled_holidays = [h for h in result.holidays if h.entitled]
        holiday_sum = sum(h.claim_amount for h in entitled_holidays)

        # Total = holidays + election day (300)
        assert result.total_claim == holiday_sum + Decimal("300")


class TestTotalCalculation:
    """Test total entitled days and claim calculation."""

    def test_total_includes_election_day(self, test_data_path):
        """Total entitled days includes election day."""
        result = calculate_year_entitlement(
            year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.SIX_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        entitled_holidays = len([h for h in result.holidays if h.entitled])

        # Total = entitled holidays + 1 (election day)
        assert result.total_entitled_days == entitled_holidays + 1

    def test_grand_total_across_years(self, test_data_path):
        """Grand total sums all years."""
        result = calculate_all_years(
            start_year=2023,
            end_year=2024,
            rest_day=RestDay.SATURDAY,
            is_employed_on_date=lambda d: True,
            get_week_type=lambda d: WeekType.SIX_DAY,
            get_daily_salary=lambda d: Decimal("250"),
            get_max_daily_salary_in_year=lambda y: Decimal("250"),
            count_employment_days_in_year=lambda y: 300,
            data_path=test_data_path,
        )

        expected_days = sum(y.total_entitled_days for y in result.per_year)
        expected_claim = sum(y.total_claim for y in result.per_year)

        assert result.grand_total_days == expected_days
        assert result.grand_total_claim == expected_claim
