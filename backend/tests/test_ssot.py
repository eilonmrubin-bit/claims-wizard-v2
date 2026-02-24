"""Tests for SSOT data structures."""

from datetime import date, time
from decimal import Decimal

from app.ssot import (
    SSOT,
    SSOTInput,
    Duration,
    EmploymentPeriod,
    WorkPattern,
    SalaryTier,
    TimeRange,
    SalaryType,
    NetOrGross,
    RestDay,
    District,
)


def test_ssot_creation():
    """Test creating an empty SSOT."""
    ssot = SSOT()
    assert ssot.input is not None
    assert ssot.effective_periods == []
    assert ssot.shifts == []


def test_ssot_input_creation():
    """Test creating SSOT input with employment data."""
    ssot_input = SSOTInput(
        employment_periods=[
            EmploymentPeriod(
                id="EP1",
                start=date(2023, 1, 1),
                end=date(2023, 12, 31),
            )
        ],
        work_patterns=[
            WorkPattern(
                id="WP1",
                start=date(2023, 1, 1),
                end=date(2023, 12, 31),
                work_days=[0, 1, 2, 3, 4],  # Sunday-Thursday
                default_shifts=[
                    TimeRange(start_time=time(8, 0), end_time=time(17, 0))
                ],
            )
        ],
        salary_tiers=[
            SalaryTier(
                id="ST1",
                start=date(2023, 1, 1),
                end=date(2023, 12, 31),
                amount=Decimal("50"),
                type=SalaryType.HOURLY,
                net_or_gross=NetOrGross.GROSS,
            )
        ],
        rest_day=RestDay.SATURDAY,
        district=District.TEL_AVIV,
        filing_date=date(2024, 1, 15),
    )

    assert len(ssot_input.employment_periods) == 1
    assert len(ssot_input.work_patterns) == 1
    assert len(ssot_input.salary_tiers) == 1
    assert ssot_input.rest_day == RestDay.SATURDAY


def test_duration():
    """Test Duration structure."""
    duration = Duration(
        days=410,
        months_decimal=Decimal("13.67"),
        years_decimal=Decimal("1.139"),
        months_whole=13,
        days_remainder=20,
        years_whole=1,
        months_remainder=1,
        display="שנה, חודש ו-20 יום",
    )

    assert duration.days == 410
    assert duration.years_whole == 1
    assert duration.display == "שנה, חודש ו-20 יום"


def test_salary_types():
    """Test salary type enum values."""
    assert SalaryType.HOURLY.value == "hourly"
    assert SalaryType.DAILY.value == "daily"
    assert SalaryType.MONTHLY.value == "monthly"
    assert SalaryType.PER_SHIFT.value == "per_shift"


def test_rest_day_enum():
    """Test rest day enum values."""
    assert RestDay.SATURDAY.value == "saturday"
    assert RestDay.FRIDAY.value == "friday"
    assert RestDay.SUNDAY.value == "sunday"
