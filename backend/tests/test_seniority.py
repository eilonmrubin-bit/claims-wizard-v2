"""Tests for seniority module.

Test fixtures from docs/skills/seniority/SENIORITY_TEST_FIXTURES.md
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.seniority import (
    compute_seniority_method_a,
    compute_seniority_method_b,
    compute_seniority_method_c,
    get_seniority_at_date,
    check_no_industry_records,
)
from app.ssot import MatashRecord, SeniorityMethod


class TestMethodA:
    """Test Method א: Prior seniority + work pattern."""

    def test_1_simple_no_gaps(self):
        """Test 1: Simple case, no gaps - worked every weekday."""
        # Prior: 24 months, Employment: 2020-01-01 to 2022-12-31

        def did_work_in_month(year: int, month: int) -> bool:
            # Worker worked every weekday throughout employment
            return True

        result = compute_seniority_method_a(
            prior_months=24,
            employment_start=date(2020, 1, 1),
            employment_end=date(2022, 12, 31),
            did_work_in_month=did_work_in_month,
        )

        assert result.totals.at_defendant_months == 36
        assert result.totals.total_industry_months == 60
        assert result.totals.total_industry_years == Decimal("5")
        assert result.totals.at_defendant_years == Decimal("3")

    def test_2_with_employment_gaps(self):
        """Test 2: With employment gaps - July and August 2021 absent."""
        # Employment: 2020-01-15 to 2022-06-20
        # Gaps: July 2021, August 2021

        gap_months = {(2021, 7), (2021, 8)}

        def did_work_in_month(year: int, month: int) -> bool:
            return (year, month) not in gap_months

        result = compute_seniority_method_a(
            prior_months=0,
            employment_start=date(2020, 1, 15),
            employment_end=date(2022, 6, 20),
            did_work_in_month=did_work_in_month,
        )

        # Jan 2020 - Jun 2021 = 18 months
        # Sep 2021 - Jun 2022 = 10 months
        # Total = 28 months
        assert result.totals.at_defendant_months == 28
        assert result.totals.total_industry_months == 28
        # 28/12 = 2.333...
        assert result.totals.total_industry_years == Decimal(28) / Decimal(12)

    def test_3_started_and_ended_mid_month(self):
        """Test 3: Started and ended mid-month."""
        # Employment: 2023-03-20 to 2023-09-05, prior: 12 months

        def did_work_in_month(year: int, month: int) -> bool:
            return True

        result = compute_seniority_method_a(
            prior_months=12,
            employment_start=date(2023, 3, 20),
            employment_end=date(2023, 9, 5),
            did_work_in_month=did_work_in_month,
        )

        # March-September = 7 months (partial months count)
        assert result.totals.at_defendant_months == 7
        assert result.totals.total_industry_months == 19
        # 19/12 = 1.583...
        assert result.totals.total_industry_years == Decimal(19) / Decimal(12)

    def test_8_zero_prior_short_employment(self):
        """Test 8: Zero prior seniority, short employment."""
        # Employment: 2023-11-10 to 2023-11-25 (single month)

        def did_work_in_month(year: int, month: int) -> bool:
            return True

        result = compute_seniority_method_a(
            prior_months=0,
            employment_start=date(2023, 11, 10),
            employment_end=date(2023, 11, 25),
            did_work_in_month=did_work_in_month,
        )

        assert result.totals.at_defendant_months == 1
        assert result.totals.total_industry_months == 1
        # 1/12 = 0.083...
        assert result.totals.total_industry_years == Decimal(1) / Decimal(12)

    def test_10_worker_worked_only_1_day_in_month(self):
        """Test 10: Worker worked only 1 day in a month."""
        # Employment: 2023-01-01 to 2023-03-31
        # Worked: Jan 15, Feb (not at all), Mar 1

        worked_months = {(2023, 1), (2023, 3)}

        def did_work_in_month(year: int, month: int) -> bool:
            return (year, month) in worked_months

        result = compute_seniority_method_a(
            prior_months=0,
            employment_start=date(2023, 1, 1),
            employment_end=date(2023, 3, 31),
            did_work_in_month=did_work_in_month,
        )

        assert result.totals.at_defendant_months == 2
        # 2/12 = 0.166...
        assert result.totals.total_industry_years == Decimal(2) / Decimal(12)


class TestMethodB:
    """Test Method ב: Manual entry."""

    def test_4_manual_entry(self):
        """Test 4: Manual entry."""
        # Total: 8 years 3 months = 99 months
        # At defendant: 4 years 6 months = 54 months

        result = compute_seniority_method_b(
            total_industry_months=99,
            at_defendant_months=54,
        )

        assert result.totals.total_industry_months == 99
        assert result.totals.total_industry_years == Decimal("8.25")
        assert result.totals.at_defendant_months == 54
        assert result.totals.at_defendant_years == Decimal("4.5")
        assert result.totals.input_method == SeniorityMethod.MANUAL


class TestMethodC:
    """Test Method ג: מת"ש PDF extraction."""

    def test_5_multiple_employers_same_industry(self):
        """Test 5: Multiple employers in same industry."""
        matash_records = [
            MatashRecord(
                employer_name="Employer A",
                start_date=date(2015, 3, 1),
                end_date=date(2017, 8, 31),
                industry="construction",
            ),
            MatashRecord(
                employer_name="Employer B",
                start_date=date(2017, 9, 1),
                end_date=date(2018, 6, 30),
                industry="food service",
            ),
            MatashRecord(
                employer_name="Employer C Defendant",
                start_date=date(2018, 7, 1),
                end_date=date(2023, 5, 15),
                industry="construction",
            ),
            MatashRecord(
                employer_name="Employer D",
                start_date=date(2019, 1, 1),
                end_date=date(2019, 6, 30),
                industry="construction",
            ),
        ]

        result = compute_seniority_method_c(
            matash_records=matash_records,
            target_industry="construction",
            defendant_name="Defendant",
            employment_start=date(2018, 7, 1),
            employment_end=date(2023, 5, 15),
        )

        # A: Mar 2015 - Aug 2017 = 30 months
        # C: Jul 2018 - May 2023 = 59 months
        # D: Jan 2019 - Jun 2019 = 6 months (overlap with C, so 0 new)
        # Union = 30 + 59 = 89 months
        assert result.totals.at_defendant_months == 59
        assert result.totals.total_industry_months == 89
        # 89/12 = 7.416...
        assert result.totals.total_industry_years == Decimal(89) / Decimal(12)
        # 59/12 = 4.916...
        assert result.totals.at_defendant_years == Decimal(59) / Decimal(12)

    def test_6_overlapping_employers_deduplication(self):
        """Test 6: Overlapping employers, deduplication."""
        matash_records = [
            MatashRecord(
                employer_name="Employer A Defendant",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
                industry="construction",
            ),
            MatashRecord(
                employer_name="Employer B",
                start_date=date(2020, 6, 1),
                end_date=date(2021, 6, 30),
                industry="construction",
            ),
        ]

        result = compute_seniority_method_c(
            matash_records=matash_records,
            target_industry="construction",
            defendant_name="Defendant",
            employment_start=date(2020, 1, 1),
            employment_end=date(2020, 12, 31),
        )

        # A: Jan-Dec 2020 = 12 months
        # B: Jun 2020 - Jun 2021 = 13 months
        # Union: Jan 2020 - Jun 2021 = 18 months (not 25)
        assert result.totals.total_industry_months == 18
        assert result.totals.at_defendant_months == 12

    def test_9_no_records_for_industry(self):
        """Test 9: No records for specified industry."""
        matash_records = [
            MatashRecord(
                employer_name="Employer A",
                start_date=date(2018, 1, 1),
                end_date=date(2020, 12, 31),
                industry="food service",
            ),
        ]

        has_no_records = check_no_industry_records(matash_records, "construction")
        assert has_no_records is True


class TestGetSeniorityAtDate:
    """Test getSeniority with as_of_date."""

    def test_7_seniority_at_date(self):
        """Test 7: getSeniority with as_of_date."""
        # Method א, prior: 10 months
        # Employment: 2020-01-01 to 2023-12-31
        # Query: 2021-06-15

        def did_work_in_month(year: int, month: int) -> bool:
            return True

        result = compute_seniority_method_a(
            prior_months=10,
            employment_start=date(2020, 1, 1),
            employment_end=date(2023, 12, 31),
            did_work_in_month=did_work_in_month,
        )

        seniority_at_date = get_seniority_at_date(
            result.monthly, date(2021, 6, 15)
        )

        # at_defendant up to June 2021: 18 months (Jan 2020 - Jun 2021)
        assert seniority_at_date["at_defendant_months"] == 18
        # total: 10 + 18 = 28
        assert seniority_at_date["total_industry_months"] == 28
        # 28/12 = 2.333...
        assert seniority_at_date["total_industry_years"] == Decimal(28) / Decimal(12)


class TestCumulativeMonthlySeries:
    """Test cumulative monthly series generation."""

    def test_11_cumulative_monthly_series(self):
        """Test 11: Cumulative monthly series with gap."""
        # Prior: 24 months
        # Employment: 2023-01-01 to 2023-06-30
        # Worked: Jan, Feb, Mar, didn't work Apr, worked May, Jun

        worked_months = {(2023, 1), (2023, 2), (2023, 3), (2023, 5), (2023, 6)}

        def did_work_in_month(year: int, month: int) -> bool:
            return (year, month) in worked_months

        result = compute_seniority_method_a(
            prior_months=24,
            employment_start=date(2023, 1, 1),
            employment_end=date(2023, 6, 30),
            did_work_in_month=did_work_in_month,
        )

        # Verify monthly series
        assert len(result.monthly) == 6

        # January
        jan = result.monthly[0]
        assert jan.month == (2023, 1)
        assert jan.worked is True
        assert jan.at_defendant_cumulative == 1
        assert jan.total_industry_cumulative == 25

        # February
        feb = result.monthly[1]
        assert feb.month == (2023, 2)
        assert feb.worked is True
        assert feb.at_defendant_cumulative == 2
        assert feb.total_industry_cumulative == 26

        # March
        mar = result.monthly[2]
        assert mar.month == (2023, 3)
        assert mar.worked is True
        assert mar.at_defendant_cumulative == 3
        assert mar.total_industry_cumulative == 27

        # April (gap)
        apr = result.monthly[3]
        assert apr.month == (2023, 4)
        assert apr.worked is False
        assert apr.at_defendant_cumulative == 3  # stays flat
        assert apr.total_industry_cumulative == 27  # stays flat

        # May
        may = result.monthly[4]
        assert may.month == (2023, 5)
        assert may.worked is True
        assert may.at_defendant_cumulative == 4
        assert may.total_industry_cumulative == 28

        # June
        jun = result.monthly[5]
        assert jun.month == (2023, 6)
        assert jun.worked is True
        assert jun.at_defendant_cumulative == 5
        assert jun.total_industry_cumulative == 29

        # Verify getSeniority at April
        apr_seniority = get_seniority_at_date(result.monthly, date(2023, 4, 15))
        assert apr_seniority["at_defendant_months"] == 3
        assert apr_seniority["total_industry_months"] == 27

    def test_12_cumulative_series_with_employment_gap(self):
        """Test 12: Cumulative series with employment gap."""
        # Prior: 10 months
        # Period 1: 2023-01-01 to 2023-03-31
        # Period 2: 2023-06-01 to 2023-08-31
        # Gap months: April, May

        worked_months = {
            (2023, 1), (2023, 2), (2023, 3),
            (2023, 6), (2023, 7), (2023, 8),
        }

        def did_work_in_month(year: int, month: int) -> bool:
            return (year, month) in worked_months

        result = compute_seniority_method_a(
            prior_months=10,
            employment_start=date(2023, 1, 1),
            employment_end=date(2023, 8, 31),
            did_work_in_month=did_work_in_month,
        )

        assert len(result.monthly) == 8

        # Check gap months
        apr = result.monthly[3]
        assert apr.month == (2023, 4)
        assert apr.worked is False
        assert apr.at_defendant_cumulative == 3
        assert apr.total_industry_cumulative == 13

        may = result.monthly[4]
        assert may.month == (2023, 5)
        assert may.worked is False
        assert may.at_defendant_cumulative == 3
        assert may.total_industry_cumulative == 13

        # Check post-gap
        jun = result.monthly[5]
        assert jun.month == (2023, 6)
        assert jun.worked is True
        assert jun.at_defendant_cumulative == 4
        assert jun.total_industry_cumulative == 14

        # Final totals
        aug = result.monthly[7]
        assert aug.at_defendant_cumulative == 6
        assert aug.total_industry_cumulative == 16


class TestAntiPatterns:
    """Test anti-patterns from the skill doc."""

    def test_no_calendar_duration_counting(self):
        """DO NOT count calendar duration instead of actual work months.

        3 years with 6 months of gaps = 30 months, not 36.
        """
        # Employment span: 36 months, but 6 months of gaps
        gap_months = {
            (2021, 3), (2021, 4), (2021, 5),
            (2022, 7), (2022, 8), (2022, 9),
        }

        def did_work_in_month(year: int, month: int) -> bool:
            return (year, month) not in gap_months

        result = compute_seniority_method_a(
            prior_months=0,
            employment_start=date(2020, 1, 1),
            employment_end=date(2022, 12, 31),
            did_work_in_month=did_work_in_month,
        )

        # 36 - 6 = 30 work months
        assert result.totals.at_defendant_months == 30
        assert result.totals.at_defendant_months != 36  # anti-pattern

    def test_months_stored_as_integers(self):
        """DO NOT store seniority only as years. Store months as integer."""
        result = compute_seniority_method_b(
            total_industry_months=99,
            at_defendant_months=54,
        )

        # Months must be integers
        assert isinstance(result.totals.total_industry_months, int)
        assert isinstance(result.totals.at_defendant_months, int)

    def test_defendant_not_equal_to_total(self):
        """DO NOT assume seniority at defendant equals total industry seniority."""
        result = compute_seniority_method_b(
            total_industry_months=99,
            at_defendant_months=54,
        )

        # They should be different
        assert result.totals.at_defendant_months != result.totals.total_industry_months
