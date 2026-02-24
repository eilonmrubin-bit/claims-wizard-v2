"""Tests for salary conversion module.

Test cases from docs/skills/salary-conversion/SKILL.md.
"""

import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import os

from app.modules.salary_conversion import (
    convert_salary,
    get_minimum_wage,
    process_period_month_record,
    _clear_minimum_wage_cache,
    NET_TO_GROSS_MULTIPLIER,
)
from app.ssot import PeriodMonthRecord, SalaryType, NetOrGross, WeekType


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear minimum wage cache before each test."""
    _clear_minimum_wage_cache()
    yield
    _clear_minimum_wage_cache()


@pytest.fixture
def test_data_path():
    """Create a test minimum wage CSV file."""
    content = """effective_date,hourly,daily_5day,daily_6day,monthly
2018-04-01,29.12,244.62,212.00,5300.00
2023-04-01,30.61,257.16,222.87,5571.75
2024-04-01,32.30,271.38,235.20,5880.02
2025-04-01,34.32,288.35,249.90,6247.67
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(content)
        path = Path(f.name)
    yield path
    os.unlink(path)


class TestMinimumWageLookup:
    """Test minimum wage historical table lookup."""

    def test_lookup_exact_date(self, test_data_path):
        """Lookup on exact effective date."""
        result = get_minimum_wage(date(2024, 4, 1), "hourly", test_data_path)
        assert result == Decimal("32.30")

    def test_lookup_date_after_effective(self, test_data_path):
        """Lookup date after effective date uses that rate."""
        result = get_minimum_wage(date(2024, 6, 15), "hourly", test_data_path)
        assert result == Decimal("32.30")

    def test_lookup_date_before_next_effective(self, test_data_path):
        """Lookup date before next change uses current rate."""
        result = get_minimum_wage(date(2025, 3, 31), "hourly", test_data_path)
        assert result == Decimal("32.30")  # Still 2024 rate

    def test_lookup_different_types(self, test_data_path):
        """Lookup different wage types."""
        target = date(2024, 6, 1)

        hourly = get_minimum_wage(target, "hourly", test_data_path)
        daily_5 = get_minimum_wage(target, "daily_5day", test_data_path)
        daily_6 = get_minimum_wage(target, "daily_6day", test_data_path)
        monthly = get_minimum_wage(target, "monthly", test_data_path)

        assert hourly == Decimal("32.30")
        assert daily_5 == Decimal("271.38")
        assert daily_6 == Decimal("235.20")
        assert monthly == Decimal("5880.02")

    def test_lookup_old_date(self, test_data_path):
        """Lookup date from old period uses old rate."""
        result = get_minimum_wage(date(2020, 1, 1), "hourly", test_data_path)
        assert result == Decimal("29.12")  # 2018 rate


class TestGrossNormalization:
    """Test Step 1: Net to Gross conversion."""

    def test_net_to_gross_multiplier(self, test_data_path):
        """Net input multiplied by 1.12."""
        result = convert_salary(
            input_amount=Decimal("4800"),
            input_type=SalaryType.MONTHLY,
            input_net_or_gross=NetOrGross.NET,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 4800 * 1.12 = 5376, still below minimum 5880.02
        assert result.minimum_applied is True
        assert result.effective_amount == Decimal("5880.02")

    def test_gross_unchanged(self, test_data_path):
        """Gross input unchanged."""
        result = convert_salary(
            input_amount=Decimal("6000"),
            input_type=SalaryType.MONTHLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 6000 gross > minimum 5880.02
        assert result.minimum_applied is False
        assert result.effective_amount == Decimal("6000")


class TestMinimumWageCheck:
    """Test Step 2: Minimum wage enforcement."""

    def test_below_minimum_hourly(self, test_data_path):
        """Hourly below minimum is flagged and replaced."""
        result = convert_salary(
            input_amount=Decimal("25"),  # Below 32.30
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.minimum_applied is True
        assert result.minimum_wage_value == Decimal("32.30")
        assert result.minimum_wage_type == "hourly"
        assert result.minimum_gap == Decimal("7.30")  # 32.30 - 25
        assert result.effective_amount == Decimal("32.30")
        assert result.salary_hourly == Decimal("32.30")

    def test_above_minimum_hourly(self, test_data_path):
        """Hourly above minimum passes through."""
        result = convert_salary(
            input_amount=Decimal("45"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.minimum_applied is False
        assert result.minimum_gap == Decimal("0")
        assert result.effective_amount == Decimal("45")
        assert result.salary_hourly == Decimal("45")

    def test_daily_5day_minimum(self, test_data_path):
        """Daily input compared to daily_5day minimum."""
        result = convert_salary(
            input_amount=Decimal("200"),  # Below 271.38
            input_type=SalaryType.DAILY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8.4"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.minimum_applied is True
        assert result.minimum_wage_type == "daily_5day"
        assert result.effective_amount == Decimal("271.38")

    def test_daily_6day_minimum(self, test_data_path):
        """Daily input compared to daily_6day minimum for 6-day week."""
        result = convert_salary(
            input_amount=Decimal("200"),  # Below 235.20
            input_type=SalaryType.DAILY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("7"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.SIX_DAY,
            data_path=test_data_path,
        )

        assert result.minimum_applied is True
        assert result.minimum_wage_type == "daily_6day"
        assert result.effective_amount == Decimal("235.20")

    def test_per_shift_uses_daily_minimum(self, test_data_path):
        """Per-shift input compared to daily minimum."""
        result = convert_salary(
            input_amount=Decimal("200"),  # Below daily minimum
            input_type=SalaryType.PER_SHIFT,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=Decimal("8"),
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.minimum_applied is True
        assert result.minimum_wage_type == "daily_5day"  # Not hourly!
        assert result.effective_amount == Decimal("271.38")


class TestConversions:
    """Test Step 3: Conversion to all types."""

    def test_hourly_to_all(self, test_data_path):
        """Convert from hourly to all types."""
        result = convert_salary(
            input_amount=Decimal("45"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8.4"),
            avg_regular_hours_per_month=Decimal("182"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.salary_hourly == Decimal("45")
        assert result.salary_daily == Decimal("45") * Decimal("8.4")  # 378
        assert result.salary_monthly == Decimal("45") * Decimal("182")  # 8190

    def test_daily_to_all(self, test_data_path):
        """Convert from daily to all types."""
        result = convert_salary(
            input_amount=Decimal("378"),
            input_type=SalaryType.DAILY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8.4"),
            avg_regular_hours_per_month=Decimal("182"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 378 / 8.4 = 45 hourly
        assert result.salary_hourly == Decimal("45")
        assert result.salary_daily == Decimal("378")
        # 45 * 182 = 8190
        assert result.salary_monthly == Decimal("45") * Decimal("182")

    def test_monthly_to_all(self, test_data_path):
        """Convert from monthly to all types."""
        result = convert_salary(
            input_amount=Decimal("8190"),
            input_type=SalaryType.MONTHLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8.4"),
            avg_regular_hours_per_month=Decimal("182"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 8190 / 182 = 45 hourly
        assert result.salary_hourly == Decimal("45")
        # 45 * 8.4 = 378
        assert result.salary_daily == Decimal("45") * Decimal("8.4")
        assert result.salary_monthly == Decimal("8190")

    def test_per_shift_to_all(self, test_data_path):
        """Convert from per-shift to all types."""
        result = convert_salary(
            input_amount=Decimal("360"),  # Per shift
            input_type=SalaryType.PER_SHIFT,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=Decimal("8"),
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 360 / 8 = 45 hourly
        assert result.salary_hourly == Decimal("45")
        # 45 * 8 = 360
        assert result.salary_daily == Decimal("360")
        # 45 * 182 = 8190 (always uses full_time_hours_base)
        assert result.salary_monthly == Decimal("8190")


class TestEdgeCases:
    """Test edge cases from skill documentation."""

    def test_minimum_wage_changes_mid_period(self, test_data_path):
        """Minimum wage changes mid-tier - different months use different rates."""
        # March 2024 - still 2023 rate
        result_mar = convert_salary(
            input_amount=Decimal("25"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 3, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # April 2024 - new rate
        result_apr = convert_salary(
            input_amount=Decimal("25"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 4, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result_mar.minimum_wage_value == Decimal("30.61")  # 2023 rate
        assert result_apr.minimum_wage_value == Decimal("32.30")  # 2024 rate

    def test_net_below_minimum_after_gross(self, test_data_path):
        """Net input still below minimum after ×1.12."""
        # Net 4800 * 1.12 = 5376, still below monthly minimum 5880.02
        result = convert_salary(
            input_amount=Decimal("4800"),
            input_type=SalaryType.MONTHLY,
            input_net_or_gross=NetOrGross.NET,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.minimum_applied is True
        assert result.effective_amount == Decimal("5880.02")
        # Gap is from gross (5376) to minimum
        assert result.minimum_gap == Decimal("5880.02") - (Decimal("4800") * NET_TO_GROSS_MULTIPLIER)

    def test_zero_salary(self, test_data_path):
        """Zero salary - minimum wage still applies."""
        result = convert_salary(
            input_amount=Decimal("0"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.minimum_applied is True
        assert result.effective_amount == Decimal("32.30")
        assert result.minimum_gap == Decimal("32.30")

    def test_varying_shift_lengths(self, test_data_path):
        """Per-shift with varying shift lengths uses average."""
        # Average 7.5 hours per shift
        result = convert_salary(
            input_amount=Decimal("300"),
            input_type=SalaryType.PER_SHIFT,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=Decimal("7.5"),
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 300 / 7.5 = 40 hourly
        assert result.salary_hourly == Decimal("40")


class TestAntiPatterns:
    """Test anti-patterns from skill doc."""

    def test_monthly_uses_full_time_base(self, test_data_path):
        """salary_monthly always uses full_time_hours_base (182), not actual hours."""
        # Even with 160 actual hours/month, monthly = hourly * 182
        result = convert_salary(
            input_amount=Decimal("45"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("160"),  # Actual hours
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 45 * 182 = 8190 (always uses full_time_hours_base, not actual hours)
        assert result.salary_monthly == Decimal("8190")

    def test_conversion_through_hourly_pivot(self, test_data_path):
        """All conversions go through hourly pivot."""
        # Daily to monthly should go daily → hourly → monthly
        result = convert_salary(
            input_amount=Decimal("336"),  # Daily
            input_type=SalaryType.DAILY,
            input_net_or_gross=NetOrGross.GROSS,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 336 / 8 = 42 hourly
        # 42 * 182 = 7644 monthly (always uses full_time_hours_base)
        assert result.salary_hourly == Decimal("42")
        assert result.salary_monthly == Decimal("42") * Decimal("182")

    def test_minimum_after_gross_not_before(self, test_data_path):
        """Minimum check happens AFTER net→gross, not before."""
        # Net 30 → gross 33.60 > minimum 32.30
        result = convert_salary(
            input_amount=Decimal("30"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.NET,
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_month=Decimal("176"),
            avg_regular_hours_per_shift=None,
            target_date=date(2024, 6, 1),
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        # 30 * 1.12 = 33.60 > 32.30
        assert result.minimum_applied is False
        assert result.effective_amount == Decimal("33.60")


class TestPeriodMonthRecordProcessing:
    """Test processing of PeriodMonthRecord."""

    def test_process_record(self, test_data_path):
        """Process a period month record fills all salary fields."""
        pmr = PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2024, 6),
            work_days_count=22,
            shifts_count=22,
            total_regular_hours=Decimal("176"),
            total_ot_hours=Decimal("10"),
            avg_regular_hours_per_day=Decimal("8"),
            avg_regular_hours_per_shift=Decimal("8"),
        )

        result = process_period_month_record(
            pmr=pmr,
            input_amount=Decimal("45"),
            input_type=SalaryType.HOURLY,
            input_net_or_gross=NetOrGross.GROSS,
            week_type=WeekType.FIVE_DAY,
            data_path=test_data_path,
        )

        assert result.salary_input_amount == Decimal("45")
        assert result.salary_input_type == SalaryType.HOURLY
        assert result.salary_input_net_or_gross == NetOrGross.GROSS
        assert result.salary_gross_amount == Decimal("45")
        assert result.minimum_applied is False
        assert result.salary_hourly == Decimal("45")
        assert result.salary_daily == Decimal("360")
        # 45 * 182 = 8190 (always uses full_time_hours_base)
        assert result.salary_monthly == Decimal("8190")
