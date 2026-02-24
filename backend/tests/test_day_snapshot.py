"""Tests for get_day_snapshot helper."""

from datetime import date, time
from decimal import Decimal

import pytest

from app.ssot import (
    SSOT,
    SSOTInput,
    DailyRecord,
    Shift,
    EffectivePeriod,
    SeniorityMonthly,
    PeriodMonthRecord,
    MonthAggregate,
    Week,
    WeekType,
    SalaryType,
    NetOrGross,
    get_day_snapshot,
    format_day_snapshot,
)


class TestGetDaySnapshot:
    """Tests for get_day_snapshot function."""

    def test_finds_daily_record(self):
        """Test that daily_record is found for the target date."""
        ssot = SSOT()
        ssot.daily_records = [
            DailyRecord(date=date(2023, 5, 14), is_work_day=False),
            DailyRecord(date=date(2023, 5, 15), is_work_day=True, day_of_week=1),
            DailyRecord(date=date(2023, 5, 16), is_work_day=True),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.daily_record is not None
        assert snapshot.daily_record.date == date(2023, 5, 15)
        assert snapshot.daily_record.is_work_day is True

    def test_finds_all_shifts_for_day(self):
        """Test that all shifts assigned to the day are collected."""
        ssot = SSOT()
        ssot.shifts = [
            Shift(id="s1", date=date(2023, 5, 15), assigned_day=date(2023, 5, 15),
                  net_hours=Decimal("8"), ot_tier1_hours=Decimal("1")),
            Shift(id="s2", date=date(2023, 5, 15), assigned_day=date(2023, 5, 15),
                  net_hours=Decimal("4"), ot_tier1_hours=Decimal("0")),
            Shift(id="s3", date=date(2023, 5, 16), assigned_day=date(2023, 5, 16),
                  net_hours=Decimal("8")),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert len(snapshot.shifts) == 2
        assert snapshot.total_hours == Decimal("12")
        assert snapshot.total_ot_hours == Decimal("1")

    def test_calculates_total_claim(self):
        """Test that total_claim sums claim_amount from all shifts."""
        ssot = SSOT()
        ssot.shifts = [
            Shift(id="s1", date=date(2023, 5, 15), assigned_day=date(2023, 5, 15),
                  net_hours=Decimal("8"), claim_amount=Decimal("100")),
            Shift(id="s2", date=date(2023, 5, 15), assigned_day=date(2023, 5, 15),
                  net_hours=Decimal("4"), claim_amount=Decimal("50.50")),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.total_claim == Decimal("150.50")

    def test_finds_effective_period(self):
        """Test that effective_period is found for the target date."""
        ssot = SSOT()
        ssot.effective_periods = [
            EffectivePeriod(id="ep1", start=date(2023, 1, 1), end=date(2023, 6, 30),
                            salary_amount=Decimal("5000"), salary_type=SalaryType.MONTHLY),
            EffectivePeriod(id="ep2", start=date(2023, 7, 1), end=date(2023, 12, 31),
                            salary_amount=Decimal("6000"), salary_type=SalaryType.MONTHLY),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.effective_period is not None
        assert snapshot.effective_period.id == "ep1"
        assert snapshot.effective_period.salary_amount == Decimal("5000")

    def test_finds_seniority_for_month(self):
        """Test that seniority is found for the month containing target date."""
        ssot = SSOT()
        ssot.seniority_monthly = [
            SeniorityMonthly(month=(2023, 4), at_defendant_cumulative=10),
            SeniorityMonthly(month=(2023, 5), at_defendant_cumulative=11),
            SeniorityMonthly(month=(2023, 6), at_defendant_cumulative=12),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.seniority is not None
        assert snapshot.seniority.month == (2023, 5)
        assert snapshot.seniority.at_defendant_cumulative == 11

    def test_finds_salary_for_period_and_month(self):
        """Test that salary is found for correct period×month."""
        ssot = SSOT()
        ssot.effective_periods = [
            EffectivePeriod(id="ep1", start=date(2023, 1, 1), end=date(2023, 12, 31)),
        ]
        ssot.period_month_records = [
            PeriodMonthRecord(effective_period_id="ep1", month=(2023, 4),
                              salary_hourly=Decimal("30")),
            PeriodMonthRecord(effective_period_id="ep1", month=(2023, 5),
                              salary_hourly=Decimal("35")),
            PeriodMonthRecord(effective_period_id="ep1", month=(2023, 6),
                              salary_hourly=Decimal("32")),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.salary is not None
        assert snapshot.salary.month == (2023, 5)
        assert snapshot.salary.salary_hourly == Decimal("35")

    def test_finds_week(self):
        """Test that week is found for the target date."""
        ssot = SSOT()
        ssot.weeks = [
            Week(id="2023-W19", start_date=date(2023, 5, 7), end_date=date(2023, 5, 13),
                 week_type=WeekType.FIVE_DAY),
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20),
                 week_type=WeekType.SIX_DAY, distinct_work_days=6),
            Week(id="2023-W21", start_date=date(2023, 5, 21), end_date=date(2023, 5, 27),
                 week_type=WeekType.FIVE_DAY),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.week is not None
        assert snapshot.week.id == "2023-W20"
        assert snapshot.week.week_type == WeekType.SIX_DAY

    def test_finds_month_aggregate(self):
        """Test that month_aggregate is found for the month."""
        ssot = SSOT()
        ssot.month_aggregates = [
            MonthAggregate(month=(2023, 4), total_regular_hours=Decimal("160")),
            MonthAggregate(month=(2023, 5), total_regular_hours=Decimal("176"),
                           job_scope=Decimal("0.97")),
            MonthAggregate(month=(2023, 6), total_regular_hours=Decimal("168")),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.month_aggregate is not None
        assert snapshot.month_aggregate.month == (2023, 5)
        assert snapshot.month_aggregate.total_regular_hours == Decimal("176")

    def test_empty_ssot_returns_empty_snapshot(self):
        """Test that empty SSOT returns snapshot with all None/empty values."""
        ssot = SSOT()

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.target_date == date(2023, 5, 15)
        assert snapshot.daily_record is None
        assert snapshot.shifts == []
        assert snapshot.effective_period is None
        assert snapshot.seniority is None
        assert snapshot.salary is None
        assert snapshot.month_aggregate is None
        assert snapshot.week is None
        assert snapshot.total_hours == Decimal("0")
        assert snapshot.total_claim == Decimal("0")

    def test_date_not_in_employment_returns_partial_snapshot(self):
        """Test date outside employment returns only what's available."""
        ssot = SSOT()
        ssot.effective_periods = [
            EffectivePeriod(id="ep1", start=date(2023, 6, 1), end=date(2023, 12, 31)),
        ]
        ssot.seniority_monthly = [
            SeniorityMonthly(month=(2023, 6), at_defendant_cumulative=1),
        ]

        # Query date before employment
        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))

        assert snapshot.effective_period is None  # Not employed yet
        assert snapshot.seniority is None  # No seniority for May


class TestFormatDaySnapshot:
    """Tests for format_day_snapshot function."""

    def test_formats_complete_snapshot(self):
        """Test formatting a complete snapshot."""
        ssot = SSOT()
        ssot.daily_records = [
            DailyRecord(date=date(2023, 5, 15), is_work_day=True, day_of_week=1,
                        effective_period_id="ep1"),
        ]
        ssot.shifts = [
            Shift(id="s1", date=date(2023, 5, 15), assigned_day=date(2023, 5, 15),
                  net_hours=Decimal("8.5"), regular_hours=Decimal("8"),
                  ot_tier1_hours=Decimal("0.5"), ot_tier2_hours=Decimal("0"),
                  claim_amount=Decimal("15.50")),
        ]
        ssot.effective_periods = [
            EffectivePeriod(id="ep1", start=date(2023, 1, 1), end=date(2023, 12, 31),
                            salary_amount=Decimal("5000"), salary_type=SalaryType.MONTHLY,
                            salary_net_or_gross=NetOrGross.GROSS),
        ]
        ssot.period_month_records = [
            PeriodMonthRecord(effective_period_id="ep1", month=(2023, 5),
                              salary_hourly=Decimal("31"), salary_daily=Decimal("248"),
                              salary_monthly=Decimal("5000")),
        ]
        ssot.seniority_monthly = [
            SeniorityMonthly(month=(2023, 5), at_defendant_cumulative=5,
                             total_industry_cumulative=5),
        ]
        ssot.weeks = [
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20),
                 week_type=WeekType.FIVE_DAY, distinct_work_days=5,
                 total_regular_hours=Decimal("40")),
        ]

        snapshot = get_day_snapshot(ssot, date(2023, 5, 15))
        formatted = format_day_snapshot(snapshot)

        # Check key elements are present
        assert "2023-05-15" in formatted
        assert "יום עבודה" in formatted
        assert "ep1" in formatted
        assert "8.5" in formatted or "8.50" in formatted
        assert "31" in formatted
        assert "5 חודשים" in formatted
        assert "15.50" in formatted or "15.5" in formatted

    def test_formats_empty_snapshot(self):
        """Test formatting an empty snapshot."""
        snapshot = get_day_snapshot(SSOT(), date(2023, 5, 15))
        formatted = format_day_snapshot(snapshot)

        assert "2023-05-15" in formatted
        assert "לא נמצאה" in formatted or "לא נמצא" in formatted
        assert "אין" in formatted
