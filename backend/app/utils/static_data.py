"""Static data loading utilities.

Loads CSV files and settings.json once at startup.
All data is cached in memory - no file access during calculation.

See docs/skills/static-data/SKILL.md for schemas.
"""

import csv
import json
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from typing import Any


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class ShabbatTimes:
    """Shabbat times for a specific week."""
    date: date  # Friday of that week
    candles: time  # Candle lighting time
    havdalah: time  # Havdalah time


@dataclass
class HolidayDate:
    """Holiday date entry."""
    year: int
    holiday_id: str
    hebrew_date: str
    gregorian_date: date


@dataclass
class MinimumWage:
    """Minimum wage entry."""
    effective_date: date
    hourly: Decimal
    daily_5day: Decimal
    daily_6day: Decimal
    monthly: Decimal


@dataclass
class RecreationDayValue:
    """Recreation day value entry."""
    industry: str
    effective_date: date
    value: Decimal


@dataclass
class RecreationDays:
    """Recreation days by industry and seniority."""
    industry: str
    min_years: int
    max_years: int
    days_per_year: int


@dataclass
class TravelAllowance:
    """Travel allowance entry."""
    effective_date: date
    daily_amount: Decimal


@dataclass
class OTConfig:
    """Overtime configuration."""
    weekly_cap: Decimal = Decimal("42")
    threshold_5day: Decimal = Decimal("8.4")
    threshold_6day: Decimal = Decimal("8")
    threshold_eve_rest: Decimal = Decimal("7")
    threshold_night: Decimal = Decimal("7")
    tier1_max_hours: Decimal = Decimal("2")


@dataclass
class LimitationType:
    """Limitation type definition."""
    id: str
    name: str
    window_years: int | None = None
    window_calc: str | None = None


@dataclass
class FreezePeriod:
    """Limitation freeze period."""
    id: str
    name: str
    start_date: date
    end_date: date
    days: int


@dataclass
class LimitationConfig:
    """Limitation configuration."""
    limitation_types: list[LimitationType]
    freeze_periods: list[FreezePeriod]
    right_limitation_mapping: dict[str, str]


@dataclass
class Settings:
    """System settings from settings.json."""
    ot_config: OTConfig
    full_time_hours_base: Decimal
    limitation_config: LimitationConfig


# =============================================================================
# Helper functions
# =============================================================================

def parse_date(date_str: str) -> date:
    """Parse ISO 8601 date string."""
    return date.fromisoformat(date_str)


def parse_time(time_str: str) -> time:
    """Parse HH:MM time string."""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def lookup_by_date(
    table: list[dict[str, Any]],
    target_date: date,
    date_field: str = "effective_date"
) -> dict[str, Any]:
    """Find the row with effective_date <= target_date, largest.

    Args:
        table: List of dicts with date field
        target_date: Date to look up
        date_field: Name of the date field

    Returns:
        Matching row

    Raises:
        ValueError: If no row found for date
    """
    candidates = [row for row in table if row[date_field] <= target_date]
    if not candidates:
        raise ValueError(f"No data for date {target_date}")
    return max(candidates, key=lambda r: r[date_field])


# =============================================================================
# Loading functions
# =============================================================================

class StaticDataLoader:
    """Loads and caches all static data."""

    def __init__(self, data_dir: Path | None = None, settings_path: Path | None = None):
        """Initialize loader with paths.

        Args:
            data_dir: Path to data/ directory (default: backend/data)
            settings_path: Path to settings.json (default: backend/settings.json)
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        if settings_path is None:
            settings_path = Path(__file__).parent.parent.parent / "settings.json"

        self.data_dir = data_dir
        self.settings_path = settings_path

        # Cached data
        self._shabbat_times: dict[str, list[ShabbatTimes]] = {}
        self._holiday_dates: list[HolidayDate] = []
        self._minimum_wage: list[MinimumWage] = []
        self._recreation_day_value: list[RecreationDayValue] = []
        self._recreation_days: list[RecreationDays] = []
        self._travel_allowance: dict[str, list[TravelAllowance]] = {}
        self._settings: Settings | None = None

        self._loaded = False

    def load_all(self) -> None:
        """Load all static data files into memory."""
        if self._loaded:
            return

        self._load_settings()
        self._load_minimum_wage()
        self._load_recreation_day_value()
        self._load_recreation_days()
        self._load_travel_allowance()
        # Holiday dates and shabbat times are generated - load if exist
        self._load_holiday_dates()
        self._load_shabbat_times()

        self._loaded = True

    def _load_settings(self) -> None:
        """Load settings.json."""
        if not self.settings_path.exists():
            # Use defaults
            self._settings = Settings(
                ot_config=OTConfig(),
                full_time_hours_base=Decimal("182"),
                limitation_config=LimitationConfig(
                    limitation_types=[],
                    freeze_periods=[],
                    right_limitation_mapping={},
                ),
            )
            return

        with open(self.settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ot_cfg = data.get("ot_config", {})
        lim_cfg = data.get("limitation_config", {})

        limitation_types = [
            LimitationType(
                id=lt["id"],
                name=lt["name"],
                window_years=lt.get("window_years"),
                window_calc=lt.get("window_calc"),
            )
            for lt in lim_cfg.get("limitation_types", [])
        ]

        freeze_periods = [
            FreezePeriod(
                id=fp["id"],
                name=fp["name"],
                start_date=parse_date(fp["start_date"]),
                end_date=parse_date(fp["end_date"]),
                days=fp["days"],
            )
            for fp in lim_cfg.get("freeze_periods", [])
        ]

        self._settings = Settings(
            ot_config=OTConfig(
                weekly_cap=Decimal(str(ot_cfg.get("weekly_cap", 42))),
                threshold_5day=Decimal(str(ot_cfg.get("threshold_5day", 8.4))),
                threshold_6day=Decimal(str(ot_cfg.get("threshold_6day", 8))),
                threshold_eve_rest=Decimal(str(ot_cfg.get("threshold_eve_rest", 7))),
                threshold_night=Decimal(str(ot_cfg.get("threshold_night", 7))),
                tier1_max_hours=Decimal(str(ot_cfg.get("tier1_max_hours", 2))),
            ),
            full_time_hours_base=Decimal(str(data.get("full_time_hours_base", 182))),
            limitation_config=LimitationConfig(
                limitation_types=limitation_types,
                freeze_periods=freeze_periods,
                right_limitation_mapping=lim_cfg.get("right_limitation_mapping", {}),
            ),
        )

    def _load_csv(self, path: Path) -> list[dict[str, str]]:
        """Load CSV file as list of dicts."""
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _load_minimum_wage(self) -> None:
        """Load minimum_wage.csv."""
        path = self.data_dir / "minimum_wage.csv"
        rows = self._load_csv(path)
        self._minimum_wage = [
            MinimumWage(
                effective_date=parse_date(row["effective_date"]),
                hourly=Decimal(row["hourly"]),
                daily_5day=Decimal(row["daily_5day"]),
                daily_6day=Decimal(row["daily_6day"]),
                monthly=Decimal(row["monthly"]),
            )
            for row in rows
        ]

    def _load_recreation_day_value(self) -> None:
        """Load recreation_day_value.csv."""
        path = self.data_dir / "recreation_day_value.csv"
        rows = self._load_csv(path)
        self._recreation_day_value = [
            RecreationDayValue(
                industry=row["industry"],
                effective_date=parse_date(row["effective_date"]),
                value=Decimal(row["value"]),
            )
            for row in rows
        ]

    def _load_recreation_days(self) -> None:
        """Load recreation_days.csv."""
        path = self.data_dir / "recreation_days.csv"
        rows = self._load_csv(path)
        self._recreation_days = [
            RecreationDays(
                industry=row["industry"],
                min_years=int(row["min_years"]),
                max_years=int(row["max_years"]),
                days_per_year=int(row["days_per_year"]),
            )
            for row in rows
        ]

    def _load_travel_allowance(self) -> None:
        """Load travel_allowance/*.csv files."""
        travel_dir = self.data_dir / "travel_allowance"
        if not travel_dir.exists():
            return
        for csv_file in travel_dir.glob("*.csv"):
            industry = csv_file.stem
            rows = self._load_csv(csv_file)
            self._travel_allowance[industry] = [
                TravelAllowance(
                    effective_date=parse_date(row["effective_date"]),
                    daily_amount=Decimal(row["daily_amount"]),
                )
                for row in rows
            ]

    def _load_holiday_dates(self) -> None:
        """Load holiday_dates.csv."""
        path = self.data_dir / "holiday_dates.csv"
        rows = self._load_csv(path)
        self._holiday_dates = [
            HolidayDate(
                year=int(row["year"]),
                holiday_id=row["holiday_id"],
                hebrew_date=row["hebrew_date"],
                gregorian_date=parse_date(row["gregorian_date"]),
            )
            for row in rows
        ]

    def _load_shabbat_times(self) -> None:
        """Load shabbat_times/*.csv files."""
        shabbat_dir = self.data_dir / "shabbat_times"
        if not shabbat_dir.exists():
            return
        for csv_file in shabbat_dir.glob("*.csv"):
            district = csv_file.stem
            rows = self._load_csv(csv_file)
            self._shabbat_times[district] = [
                ShabbatTimes(
                    date=parse_date(row["date"]),
                    candles=parse_time(row["candles"]),
                    havdalah=parse_time(row["havdalah"]),
                )
                for row in rows
            ]

    # =========================================================================
    # Public accessors
    # =========================================================================

    @property
    def settings(self) -> Settings:
        """Get system settings."""
        if not self._loaded:
            self.load_all()
        assert self._settings is not None
        return self._settings

    def get_shabbat_times(self, friday_date: date, district: str) -> ShabbatTimes:
        """Get shabbat times for a specific Friday and district.

        Args:
            friday_date: The Friday of the week
            district: District identifier (jerusalem, tel_aviv, etc.)

        Returns:
            ShabbatTimes for that week

        Raises:
            ValueError: If no data for that date/district
        """
        if not self._loaded:
            self.load_all()

        if district not in self._shabbat_times:
            raise ValueError(f"No shabbat times for district: {district}")

        times = self._shabbat_times[district]
        for st in times:
            if st.date == friday_date:
                return st

        raise ValueError(f"No shabbat times for date {friday_date} in {district}")

    def get_holiday_dates(self, year: int) -> list[HolidayDate]:
        """Get all holidays for a specific year.

        Args:
            year: Gregorian year

        Returns:
            List of 9 holidays for that year

        Raises:
            ValueError: If no data for that year
        """
        if not self._loaded:
            self.load_all()

        holidays = [h for h in self._holiday_dates if h.year == year]
        if not holidays:
            raise ValueError(f"No holiday data for year {year}")
        return holidays

    def get_minimum_wage(self, month: tuple[int, int]) -> MinimumWage:
        """Get minimum wage for a specific month.

        Args:
            month: (year, month) tuple

        Returns:
            MinimumWage effective for that month

        Raises:
            ValueError: If no data for that date
        """
        if not self._loaded:
            self.load_all()

        target = date(month[0], month[1], 1)
        table = [{"effective_date": mw.effective_date, "data": mw} for mw in self._minimum_wage]
        row = lookup_by_date(table, target)
        return row["data"]

    def get_recreation_day_value(self, target_date: date, industry: str = "general") -> tuple[Decimal, date]:
        """Get recreation day value for a specific date and industry.

        Args:
            target_date: Date to look up
            industry: Industry identifier (default: general)

        Returns:
            Tuple of (value in NIS, effective_date used)

        Raises:
            ValueError: If no data for that date/industry
        """
        if not self._loaded:
            self.load_all()

        # Filter by industry, fall back to general if not found
        industry_rows = [rv for rv in self._recreation_day_value if rv.industry == industry]
        if not industry_rows:
            industry_rows = [rv for rv in self._recreation_day_value if rv.industry == "general"]

        if not industry_rows:
            raise ValueError(f"No recreation day value data for industry: {industry}")

        table = [{"effective_date": rv.effective_date, "data": rv} for rv in industry_rows]
        row = lookup_by_date(table, target_date)
        return row["data"].value, row["data"].effective_date

    def get_all_recreation_day_value_dates(self, industry: str = "general") -> list[date]:
        """Get all effective dates for recreation day value for an industry.

        Args:
            industry: Industry identifier (default: general)

        Returns:
            Sorted list of all effective dates for the industry
        """
        if not self._loaded:
            self.load_all()

        # Filter by industry, fall back to general if not found
        industry_rows = [rv for rv in self._recreation_day_value if rv.industry == industry]
        if not industry_rows:
            industry_rows = [rv for rv in self._recreation_day_value if rv.industry == "general"]

        dates = sorted(set(rv.effective_date for rv in industry_rows))
        return dates

    def get_recreation_days(self, industry: str, seniority_years: int) -> int:
        """Get recreation days per year for industry and seniority.

        Args:
            industry: Industry identifier
            seniority_years: Seniority in whole years

        Returns:
            Number of recreation days per year

        Raises:
            ValueError: If no matching entry
        """
        if not self._loaded:
            self.load_all()

        for rd in self._recreation_days:
            if rd.industry == industry and rd.min_years <= seniority_years <= rd.max_years:
                return rd.days_per_year

        # Fall back to general
        for rd in self._recreation_days:
            if rd.industry == "general" and rd.min_years <= seniority_years <= rd.max_years:
                return rd.days_per_year

        raise ValueError(f"No recreation days data for industry={industry}, seniority={seniority_years}")

    def get_travel_allowance(self, target_date: date, industry: str = "general") -> Decimal:
        """Get daily travel allowance for a date and industry.

        Args:
            target_date: Date to look up
            industry: Industry identifier (default: general)

        Returns:
            Daily amount in NIS

        Raises:
            ValueError: If no data for that date/industry
        """
        if not self._loaded:
            self.load_all()

        if industry not in self._travel_allowance:
            industry = "general"

        if industry not in self._travel_allowance:
            raise ValueError(f"No travel allowance data for industry: {industry}")

        table = [{"effective_date": ta.effective_date, "data": ta} for ta in self._travel_allowance[industry]]
        row = lookup_by_date(table, target_date)
        return row["data"].daily_amount

    def get_travel_rate(
        self,
        industry: str,
        distance_km: Decimal | None,
        target_date: date
    ) -> Decimal:
        """Get travel rate based on industry and distance (for construction).

        Args:
            industry: Industry identifier
            distance_km: Distance in km (for construction only)
            target_date: Date to look up rate

        Returns:
            Daily travel rate in NIS

        Construction workers:
            - distance_km < 40 or None: construction_base rate (26.4)
            - distance_km >= 40: construction_far rate (39.6)

        Other industries: general rate (22.6)
        """
        if not self._loaded:
            self.load_all()

        if industry == "construction":
            if distance_km is not None and distance_km >= 40:
                csv_key = "construction_far"
            else:
                csv_key = "construction_base"
        else:
            csv_key = "general"

        if csv_key not in self._travel_allowance:
            csv_key = "general"

        if csv_key not in self._travel_allowance:
            raise ValueError(f"No travel allowance data for: {csv_key}")

        table = [{"effective_date": ta.effective_date, "data": ta} for ta in self._travel_allowance[csv_key]]
        row = lookup_by_date(table, target_date)
        return row["data"].daily_amount


# Global instance
_loader: StaticDataLoader | None = None


def get_static_data() -> StaticDataLoader:
    """Get the global static data loader instance."""
    global _loader
    if _loader is None:
        _loader = StaticDataLoader()
        _loader.load_all()
    return _loader
