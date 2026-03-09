"""Tests for meal allowance (אש"ל) module.

Test cases from skill §13.
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.meal_allowance import compute_meal_allowance
from app.ssot import (
    LodgingInput,
    LodgingPeriod,
    VisitGroup,
    EmploymentPeriod,
    MealAllowanceData,
)


def make_lodging_period(
    id: str,
    start: date,
    end: date,
    pattern_type: str = "weekly",
    total_nights: int = 4,
    total_visits: int = 1,
    visit_groups: list[VisitGroup] | None = None,
) -> LodgingPeriod:
    """Helper to create a LodgingPeriod with visit groups.

    Args:
        total_nights: Total nights per unit (week or month)
        total_visits: Total visits per unit (week or month)
        visit_groups: Explicit visit groups (overrides total_nights/total_visits)

    Creates visit groups to match the total_nights and total_visits.
    """
    if visit_groups is None and pattern_type != "none":
        if total_visits == 0:
            visit_groups = []
        elif total_nights % total_visits == 0:
            nights_per = total_nights // total_visits
            visit_groups = [VisitGroup(id="VG1", nights_per_visit=nights_per, count=total_visits)]
        else:
            base_nights = total_nights // total_visits
            remainder = total_nights % total_visits
            visit_groups = []
            for i in range(total_visits):
                nights = base_nights + (1 if i < remainder else 0)
                visit_groups.append(VisitGroup(id=f"VG{i+1}", nights_per_visit=nights, count=1))
    elif visit_groups is None:
        visit_groups = []

    return LodgingPeriod(
        id=id,
        start=start,
        end=end,
        snap_to=None,
        snap_ref_id=None,
        pattern_type=pattern_type,
        visit_groups=visit_groups,
    )


def make_employment_period(
    id: str,
    start: date,
    end: date,
) -> EmploymentPeriod:
    """Helper to create an EmploymentPeriod."""
    return EmploymentPeriod(
        id=id,
        start=start,
        end=end,
    )


class TestCase1ConstructionWeeklyLodgingFullYear:
    """Case 1: Construction, weekly lodging, 4 nights/week, full year 2024.

    industry: "construction"
    employment: 2024-01-01 – 2024-12-31
    lodging: 1 period, weekly, 4 nights/week, 1 visit/week
    rate: 143.5 ₪/night (post 2017)

    ~52 weeks × 4 nights × 143.5 ≈ 29,848 ₪

    Expected:
        grand_total_nights ≈ 208
        grand_total_value ≈ 29,848 ₪
    """

    def test_full_year_calculation(self):
        employment_periods = [
            make_employment_period("EP1", date(2024, 1, 1), date(2024, 12, 31))
        ]
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        def get_rate(d: date) -> Decimal:
            return Decimal("143.50")

        result = compute_meal_allowance(
            industry="construction",
            lodging_input=lodging_input,
            employment_periods=employment_periods,
            get_rate=get_rate,
            right_enabled=True,
        )

        assert result.entitled is True
        assert result.not_entitled_reason is None
        # 52 weeks × 4 nights ≈ 208 nights
        # Allow some tolerance due to pro-rating
        assert result.grand_total_nights > Decimal("200")
        assert result.grand_total_nights < Decimal("220")
        # ~208 × 143.5 ≈ 29,848
        assert result.grand_total_value > Decimal("28000")
        assert result.grand_total_value < Decimal("32000")


class TestCase2RateChangeMidEmployment:
    """Case 2: Rate change mid-employment.

    industry: "construction"
    employment: 2017-01-01 – 2017-12-31
    lodging: 1 period, weekly, 4 nights/week, 1 visit/week

    Jan–May 2017 (21 weeks): 21 × 4 × 124.2 = 10,432.8 ₪
    Jun–Dec 2017 (31 weeks): 31 × 4 × 143.5 = 17,794 ₪
    Total ≈ 28,226.8 ₪
    """

    def test_rate_change(self):
        employment_periods = [
            make_employment_period("EP1", date(2017, 1, 1), date(2017, 12, 31))
        ]
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2017, 1, 1),
                    date(2017, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        def get_rate(d: date) -> Decimal:
            # Rate change on 2017-06-01
            if d >= date(2017, 6, 1):
                return Decimal("143.50")
            else:
                return Decimal("124.20")

        result = compute_meal_allowance(
            industry="construction",
            lodging_input=lodging_input,
            employment_periods=employment_periods,
            get_rate=get_rate,
            right_enabled=True,
        )

        assert result.entitled is True
        # Total should be around 28,000
        assert result.grand_total_value > Decimal("25000")
        assert result.grand_total_value < Decimal("32000")


class TestCase3MonthlyLodging:
    """Case 3: Monthly lodging, 15 nights/month, 3 visits/month.

    industry: "construction"
    employment: 2023-01-01 – 2023-12-31
    lodging: 1 period, monthly, 15 nights/month, 3 visits/month
    rate: 143.5 ₪/night

    12 months × 15 nights × 143.5 = 25,830 ₪
    """

    def test_monthly_lodging(self):
        employment_periods = [
            make_employment_period("EP1", date(2023, 1, 1), date(2023, 12, 31))
        ]
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2023, 1, 1),
                    date(2023, 12, 31),
                    pattern_type="monthly",
                    total_nights=15,
                    total_visits=3,
                )
            ]
        )

        def get_rate(d: date) -> Decimal:
            return Decimal("143.50")

        result = compute_meal_allowance(
            industry="construction",
            lodging_input=lodging_input,
            employment_periods=employment_periods,
            get_rate=get_rate,
            right_enabled=True,
        )

        assert result.entitled is True
        # 12 × 15 = 180 nights
        assert result.grand_total_nights == Decimal("180")
        # 180 × 143.5 = 25,830
        assert result.grand_total_value == Decimal("25830.00")


class TestNotConstruction:
    """Non-construction workers are not entitled."""

    def test_not_entitled(self):
        employment_periods = [
            make_employment_period("EP1", date(2024, 1, 1), date(2024, 12, 31))
        ]
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        def get_rate(d: date) -> Decimal:
            return Decimal("143.50")

        result = compute_meal_allowance(
            industry="general",
            lodging_input=lodging_input,
            employment_periods=employment_periods,
            get_rate=get_rate,
            right_enabled=True,
        )

        assert result.entitled is False
        assert result.not_entitled_reason == "not_construction"


class TestNoLodgingInput:
    """Construction worker without lodging input is not entitled."""

    def test_no_lodging(self):
        employment_periods = [
            make_employment_period("EP1", date(2024, 1, 1), date(2024, 12, 31))
        ]

        def get_rate(d: date) -> Decimal:
            return Decimal("143.50")

        result = compute_meal_allowance(
            industry="construction",
            lodging_input=None,
            employment_periods=employment_periods,
            get_rate=get_rate,
            right_enabled=True,
        )

        assert result.entitled is False
        assert result.not_entitled_reason == "no_lodging_input"


class TestDisabled:
    """Right disabled returns not entitled."""

    def test_disabled(self):
        employment_periods = [
            make_employment_period("EP1", date(2024, 1, 1), date(2024, 12, 31))
        ]
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        def get_rate(d: date) -> Decimal:
            return Decimal("143.50")

        result = compute_meal_allowance(
            industry="construction",
            lodging_input=lodging_input,
            employment_periods=employment_periods,
            get_rate=get_rate,
            right_enabled=False,
        )

        assert result.entitled is False
        assert result.not_entitled_reason == "disabled"


class TestPatternTypeNone:
    """Pattern type 'none' means no lodging nights."""

    def test_pattern_none(self):
        employment_periods = [
            make_employment_period("EP1", date(2024, 1, 1), date(2024, 12, 31))
        ]
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="none",
                )
            ]
        )

        def get_rate(d: date) -> Decimal:
            return Decimal("143.50")

        result = compute_meal_allowance(
            industry="construction",
            lodging_input=lodging_input,
            employment_periods=employment_periods,
            get_rate=get_rate,
            right_enabled=True,
        )

        # No active periods = not entitled
        assert result.entitled is False
        assert result.not_entitled_reason == "no_lodging_input"
