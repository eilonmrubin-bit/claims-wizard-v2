"""Tests for snapshot utilities."""

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
)
from app.utils.snapshots import (
    DaySnapshot,
    WeekSnapshot,
    MonthSnapshot,
    get_day_snapshot,
    get_week_snapshot,
    get_month_snapshot,
    format_day_snapshot,
    format_week_snapshot,
    format_month_snapshot,
)


# =============================================================================
# Day Snapshot Tests
# =============================================================================

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


# =============================================================================
# Week Snapshot Tests
# =============================================================================

class TestGetWeekSnapshot:
    """Tests for get_week_snapshot function."""

    def test_finds_week(self):
        """Test that week is found by ID."""
        ssot = SSOT()
        ssot.weeks = [
            Week(id="2023-W19", start_date=date(2023, 5, 7), end_date=date(2023, 5, 13),
                 week_type=WeekType.FIVE_DAY),
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20),
                 week_type=WeekType.SIX_DAY, distinct_work_days=6),
        ]

        snapshot = get_week_snapshot(ssot, "2023-W20")

        assert snapshot.week is not None
        assert snapshot.week.id == "2023-W20"
        assert snapshot.week.week_type == WeekType.SIX_DAY

    def test_finds_daily_records_in_week(self):
        """Test that all daily records in the week are collected."""
        ssot = SSOT()
        ssot.weeks = [
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20),
                 week_type=WeekType.FIVE_DAY),
        ]
        ssot.daily_records = [
            DailyRecord(date=date(2023, 5, 13), is_work_day=True),  # Before
            DailyRecord(date=date(2023, 5, 14), is_work_day=True),  # In week
            DailyRecord(date=date(2023, 5, 15), is_work_day=True),  # In week
            DailyRecord(date=date(2023, 5, 16), is_work_day=False), # In week
            DailyRecord(date=date(2023, 5, 21), is_work_day=True),  # After
        ]

        snapshot = get_week_snapshot(ssot, "2023-W20")

        assert len(snapshot.daily_records) == 3
        assert snapshot.work_days_count == 2

    def test_finds_shifts_in_week(self):
        """Test that all shifts assigned to the week are collected."""
        ssot = SSOT()
        ssot.weeks = [
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20),
                 week_type=WeekType.FIVE_DAY),
        ]
        ssot.shifts = [
            Shift(id="s1", date=date(2023, 5, 15), assigned_week="2023-W20",
                  net_hours=Decimal("8"), regular_hours=Decimal("7"),
                  ot_tier1_hours=Decimal("1"), claim_amount=Decimal("50")),
            Shift(id="s2", date=date(2023, 5, 16), assigned_week="2023-W20",
                  net_hours=Decimal("9"), regular_hours=Decimal("8"),
                  ot_tier1_hours=Decimal("1"), claim_amount=Decimal("60")),
            Shift(id="s3", date=date(2023, 5, 21), assigned_week="2023-W21",
                  net_hours=Decimal("8")),
        ]

        snapshot = get_week_snapshot(ssot, "2023-W20")

        assert len(snapshot.shifts) == 2
        assert snapshot.shifts_count == 2
        assert snapshot.total_hours == Decimal("17")
        assert snapshot.total_regular_hours == Decimal("15")
        assert snapshot.total_ot_hours == Decimal("2")
        assert snapshot.total_claim == Decimal("110")

    def test_finds_effective_periods_in_week(self):
        """Test that effective periods overlapping the week are collected."""
        ssot = SSOT()
        ssot.weeks = [
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20),
                 week_type=WeekType.FIVE_DAY),
        ]
        ssot.effective_periods = [
            EffectivePeriod(id="ep1", start=date(2023, 1, 1), end=date(2023, 5, 15)),
            EffectivePeriod(id="ep2", start=date(2023, 5, 16), end=date(2023, 12, 31)),
            EffectivePeriod(id="ep3", start=date(2023, 6, 1), end=date(2023, 12, 31)),  # No overlap
        ]

        snapshot = get_week_snapshot(ssot, "2023-W20")

        assert len(snapshot.effective_periods) == 2
        ep_ids = {ep.id for ep in snapshot.effective_periods}
        assert ep_ids == {"ep1", "ep2"}

    def test_empty_week_id_returns_empty_snapshot(self):
        """Test that non-existent week ID returns empty snapshot."""
        ssot = SSOT()
        ssot.weeks = [
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20)),
        ]

        snapshot = get_week_snapshot(ssot, "2023-W99")

        assert snapshot.week is None
        assert snapshot.daily_records == []
        assert snapshot.shifts == []


class TestFormatWeekSnapshot:
    """Tests for format_week_snapshot function."""

    def test_formats_week_snapshot(self):
        """Test formatting a week snapshot."""
        ssot = SSOT()
        ssot.weeks = [
            Week(id="2023-W20", start_date=date(2023, 5, 14), end_date=date(2023, 5, 20),
                 week_type=WeekType.FIVE_DAY, distinct_work_days=5),
        ]
        ssot.daily_records = [
            DailyRecord(date=date(2023, 5, 15), is_work_day=True),
        ]
        ssot.shifts = [
            Shift(id="s1", date=date(2023, 5, 15), assigned_day=date(2023, 5, 15),
                  assigned_week="2023-W20", net_hours=Decimal("8"),
                  regular_hours=Decimal("8"), claim_amount=Decimal("50")),
        ]

        snapshot = get_week_snapshot(ssot, "2023-W20")
        formatted = format_week_snapshot(snapshot)

        assert "2023-W20" in formatted
        assert "5 ימים" in formatted
        assert "2023-05-14" in formatted
        assert "2023-05-20" in formatted
        assert "50" in formatted


# =============================================================================
# Month Snapshot Tests
# =============================================================================

class TestGetMonthSnapshot:
    """Tests for get_month_snapshot function."""

    def test_finds_month_aggregate(self):
        """Test that month aggregate is found."""
        ssot = SSOT()
        ssot.month_aggregates = [
            MonthAggregate(month=(2023, 4), total_regular_hours=Decimal("160")),
            MonthAggregate(month=(2023, 5), total_regular_hours=Decimal("176"),
                           job_scope=Decimal("0.97")),
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert snapshot.month_aggregate is not None
        assert snapshot.month_aggregate.month == (2023, 5)
        assert snapshot.month_aggregate.total_regular_hours == Decimal("176")

    def test_finds_period_month_records(self):
        """Test that all period month records for the month are collected."""
        ssot = SSOT()
        ssot.period_month_records = [
            PeriodMonthRecord(effective_period_id="ep1", month=(2023, 5),
                              salary_hourly=Decimal("30")),
            PeriodMonthRecord(effective_period_id="ep2", month=(2023, 5),
                              salary_hourly=Decimal("35")),
            PeriodMonthRecord(effective_period_id="ep1", month=(2023, 6),
                              salary_hourly=Decimal("32")),
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert len(snapshot.period_month_records) == 2
        assert snapshot.avg_salary_hourly == Decimal("32.5")

    def test_finds_seniority(self):
        """Test that seniority is found for the month."""
        ssot = SSOT()
        ssot.seniority_monthly = [
            SeniorityMonthly(month=(2023, 5), at_defendant_cumulative=10,
                             total_industry_cumulative=15),
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert snapshot.seniority is not None
        assert snapshot.seniority.at_defendant_cumulative == 10

    def test_finds_daily_records_in_month(self):
        """Test that daily records for the month are collected."""
        ssot = SSOT()
        ssot.daily_records = [
            DailyRecord(date=date(2023, 4, 30), is_work_day=True),  # April
            DailyRecord(date=date(2023, 5, 1), is_work_day=True),   # May
            DailyRecord(date=date(2023, 5, 15), is_work_day=True),  # May
            DailyRecord(date=date(2023, 5, 31), is_work_day=False), # May
            DailyRecord(date=date(2023, 6, 1), is_work_day=True),   # June
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert len(snapshot.daily_records) == 3
        assert snapshot.work_days_count == 2

    def test_finds_shifts_in_month(self):
        """Test that shifts for the month are collected."""
        ssot = SSOT()
        ssot.shifts = [
            Shift(id="s1", date=date(2023, 5, 15), assigned_day=date(2023, 5, 15),
                  net_hours=Decimal("8"), regular_hours=Decimal("7"),
                  ot_tier1_hours=Decimal("1"), claim_amount=Decimal("50")),
            Shift(id="s2", date=date(2023, 5, 16), assigned_day=date(2023, 5, 16),
                  net_hours=Decimal("9"), regular_hours=Decimal("8"),
                  ot_tier1_hours=Decimal("1"), claim_amount=Decimal("60")),
            Shift(id="s3", date=date(2023, 6, 1), assigned_day=date(2023, 6, 1),
                  net_hours=Decimal("8")),
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert len(snapshot.shifts) == 2
        assert snapshot.shifts_count == 2
        assert snapshot.total_hours == Decimal("17")
        assert snapshot.total_claim == Decimal("110")

    def test_finds_weeks_overlapping_month(self):
        """Test that weeks overlapping the month are collected."""
        ssot = SSOT()
        ssot.weeks = [
            # Week ending in April
            Week(id="2023-W17", start_date=date(2023, 4, 23), end_date=date(2023, 4, 29)),
            # Week spanning April-May
            Week(id="2023-W18", start_date=date(2023, 4, 30), end_date=date(2023, 5, 6)),
            # Full week in May
            Week(id="2023-W19", start_date=date(2023, 5, 7), end_date=date(2023, 5, 13)),
            # Week spanning May-June
            Week(id="2023-W22", start_date=date(2023, 5, 28), end_date=date(2023, 6, 3)),
            # Week in June
            Week(id="2023-W23", start_date=date(2023, 6, 4), end_date=date(2023, 6, 10)),
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert len(snapshot.weeks) == 3
        week_ids = {w.id for w in snapshot.weeks}
        assert week_ids == {"2023-W18", "2023-W19", "2023-W22"}

    def test_finds_effective_periods_in_month(self):
        """Test that effective periods overlapping the month are collected."""
        ssot = SSOT()
        ssot.effective_periods = [
            EffectivePeriod(id="ep1", start=date(2023, 1, 1), end=date(2023, 5, 15)),
            EffectivePeriod(id="ep2", start=date(2023, 5, 16), end=date(2023, 12, 31)),
            EffectivePeriod(id="ep3", start=date(2023, 6, 1), end=date(2023, 12, 31)),  # No overlap
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert len(snapshot.effective_periods) == 2
        ep_ids = {ep.id for ep in snapshot.effective_periods}
        assert ep_ids == {"ep1", "ep2"}

    def test_month_tuple_property(self):
        """Test month_tuple property returns correct tuple."""
        snapshot = MonthSnapshot(year=2023, month=5)

        assert snapshot.month_tuple == (2023, 5)

    def test_empty_ssot_returns_empty_snapshot(self):
        """Test that empty SSOT returns empty snapshot."""
        ssot = SSOT()

        snapshot = get_month_snapshot(ssot, 2023, 5)

        assert snapshot.year == 2023
        assert snapshot.month == 5
        assert snapshot.month_aggregate is None
        assert snapshot.period_month_records == []
        assert snapshot.seniority is None
        assert snapshot.daily_records == []
        assert snapshot.shifts == []


class TestFormatMonthSnapshot:
    """Tests for format_month_snapshot function."""

    def test_formats_month_snapshot(self):
        """Test formatting a month snapshot."""
        ssot = SSOT()
        ssot.month_aggregates = [
            MonthAggregate(month=(2023, 5), total_regular_hours=Decimal("176"),
                           total_ot_hours=Decimal("20"), total_work_days=22,
                           total_shifts=22, job_scope=Decimal("0.97")),
        ]
        ssot.period_month_records = [
            PeriodMonthRecord(effective_period_id="ep1", month=(2023, 5),
                              salary_hourly=Decimal("35"), salary_daily=Decimal("280"),
                              salary_monthly=Decimal("6160")),
        ]
        ssot.seniority_monthly = [
            SeniorityMonthly(month=(2023, 5), at_defendant_cumulative=10,
                             at_defendant_years_cumulative=Decimal("0.83"),
                             total_industry_cumulative=15,
                             total_industry_years_cumulative=Decimal("1.25")),
        ]

        snapshot = get_month_snapshot(ssot, 2023, 5)
        formatted = format_month_snapshot(snapshot)

        assert "מאי 2023" in formatted
        assert "176" in formatted
        assert "97.00%" in formatted or "97%" in formatted
        assert "35" in formatted
        assert "10 חודשים" in formatted

    def test_formats_empty_month_snapshot(self):
        """Test formatting an empty month snapshot."""
        snapshot = get_month_snapshot(SSOT(), 2023, 5)
        formatted = format_month_snapshot(snapshot)

        assert "מאי 2023" in formatted
        assert "לא נמצא" in formatted
