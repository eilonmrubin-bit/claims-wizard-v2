---
name: vacation
description: |
  Israeli labor law annual vacation (חופשה שנתית) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on vacation day calculation, partial year entitlement,
  daily salary averaging, or week-type-based table lookup.
  ALWAYS read this skill before touching any vacation-related code.
---

# חופשה שנתית — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent legal rules.** This module computes vacation based only on the rules described here.
2. **Calendar year, not employment year.** Each calendar year (Jan 1 – Dec 31) is a separate vacation year.
3. **Net days only for general industry.** The law tables show gross days — use the net (בפועל) column only.
4. **Week type is per week, not per year.** Within a mixed year (patterns change mid-year), split proportionally by number of weeks of each type.
5. **No waiting period.** Entitlement begins from day one of employment.
6. **Partial year → partial days.** Proportional to actual working days in the year divided by full-year working days.
7. **Seniority basis differs by industry.** General + agriculture: employer only. Construction + cleaning: industry (ותק ענפי).
8. **Construction age 55:** Split the year at the birthday — days before and after are computed with different tables.
9. **Daily salary = annual average.** For each calendar year, average the daily salary over all days worked in that year.

---

## Conceptual Model

```
For each calendar year Y covered by employment:

  1. Determine seniority_years_at_year_start (see §Seniority Basis)
  2. Determine week_type distribution for year Y (see §Week Type)
  3. Look up base_days per week type using seniority_years_at_year_start
     Construction only: if worker turns 55 during year Y → split year at birthday
  4. weighted_base_days = Σ (weight × base_days_for_type)
  5. partial_fraction = actual_work_days_in_year_Y / full_year_work_days
     (1.0 for full years within employment)
  6. entitled_days = weighted_base_days × partial_fraction
  7. avg_daily_salary = weighted average of salary_daily for all months in year Y
  8. year_value = entitled_days × avg_daily_salary
```

---

## §Seniority Basis

| Industry     | Seniority Source                       |
|--------------|----------------------------------------|
| general      | months at this employer only           |
| agriculture  | months at this employer only           |
| construction | total industry months (ותק ענפי)       |
| cleaning     | total industry months (ותק ענפי)       |

**Year rank calculation:**
```
seniority_months_at_jan1 = relevant_months_worked_before_this_calendar_year
seniority_years = floor(seniority_months_at_jan1 / 12) + 1
```

For the first calendar year of employment: seniority_months_at_jan1 = prior_seniority_months (for construction/cleaning) or 0 (for general/agriculture). So seniority_years = floor(prior/12) + 1.

For each subsequent year: add the months worked in all prior calendar years at this employer (general/agriculture) or total industry (construction/cleaning).

Gaps in employment: months not worked do not count toward seniority.

---

## §Week Type

Work days per week determine week type:
- **6-day week:** work_days includes day index 5 (Friday/שישי)
- **5-day week:** work_days does NOT include Friday

When patterns change mid-year, count ISO weeks:
```
weeks_6day = count of weeks in year Y where the active pattern is 6-day
weeks_5day = count of weeks in year Y where the active pattern is 5-day
total_weeks = weeks_6day + weeks_5day
weight_6 = weeks_6day / total_weeks
weight_5 = weeks_5day / total_weeks
weighted_base_days = weight_6 × days_6day + weight_5 × days_5day
```

For agriculture: single column (no week-type split), use `days_6day` value for both types.

---

## §Daily Salary

For each calendar year Y, compute a weighted average of `salary_daily` across all months
that overlap with employment in year Y:

```
avg_daily_salary_Y = Σ(salary_daily_month × work_days_in_month) / Σ(work_days_in_month)
```

Where:
- `salary_daily_month` = `period_month_records[month].salary_daily`
- `work_days_in_month` = number of actual work days in that month within the employment period

For a partial year, use only the months (and partial months at boundaries) that fall within employment.

---

## §Partial Year

A calendar year is **partial** if:
- Employment starts after Jan 1 (first year), OR
- Employment ends before Dec 31 (last year), OR
- A gap in employment exists within that year

```
partial_fraction = actual_work_days_in_year_Y / full_year_work_days_in_year_Y
```

`full_year_work_days_in_year_Y` = total work days that would be worked if employed all year under the applicable pattern(s).

If multiple employment periods fall in one calendar year, sum their actual work days for the numerator. The denominator is always the full year's work days.

---

## §Construction: Age 55 Split

**Birthday convention:** The system stores only `birth_year`. Use **January 1 of (birth_year + 55)** as the age-55 turning point. This must be clearly labeled in the UI.

When age_55_date falls within calendar year Y:
```
days_A = (age_55_date - year_start).days      # before turning 55
days_B = (year_end - age_55_date).days + 1    # from birthday onward
total_days = days_A + days_B

base_days_under55 = lookup(construction, seniority_years, week_type)
base_days_55plus  = lookup(construction_55plus, seniority_years, week_type)
                    # construction_55plus only applies to seniority_years >= 11
                    # if seniority_years < 11, use same as under-55

weighted_base_days = (days_A/total_days) × base_days_under55
                   + (days_B/total_days) × base_days_55plus
```

---

## §Entitlement Tables

### General (חוק חופשה שנתית תשי"א — ערכי נטו בלבד)

Seniority = years at this employer.

| ותק (שנים) | 6 ימים/שבוע | 5 ימים/שבוע |
|------------|------------|------------|
| 1–5        | 14         | 12         |
| 6          | 16         | 14         |
| 7          | 18         | 15         |
| 8          | 19         | 16         |
| 9          | 20         | 17         |
| 10         | 21         | 18         |
| 11         | 22         | 19         |
| 12         | 23         | 20         |
| 13+        | 24         | 20         |

### Construction (בנייה — ותק ענפי)

| ותק ענפי (שנים) | 6 ימים | 5 ימים |
|----------------|--------|--------|
| 1–2            | 12     | 10     |
| 3              | 13     | 11     |
| 4              | 16     | 14     |
| 5              | 18     | 15     |
| 6–7            | 19     | 17     |
| 8              | 19     | 17     |
| 9+             | 26     | 23     |

**גיל 55+ ו-seniority 11+** (מחליף את שורת 9+ עבור עובדים שעברו גיל 55):

| ותק ענפי (שנים) | 6 ימים | 5 ימים |
|----------------|--------|--------|
| 11+            | 28     | 24     |

### Agriculture (חקלאות — ללא תלות בסוג שבוע)

Seniority = years at this employer.

| ותק (שנים) | ימי חופשה |
|------------|-----------|
| 1–3        | 12        |
| 4–6        | 16        |
| 7–9        | 20        |
| 10         | 24        |
| 11+        | 26        |

### Cleaning (נקיון — ותק ענפי)

| ותק ענפי (שנים) | 6 ימים | 5 ימים |
|----------------|--------|--------|
| 1–2            | 12     | 10     |
| 3–4            | 13     | 11     |
| 5              | 15     | 13     |
| 6              | 20     | 18     |
| 7–8            | 21     | 19     |
| 9+             | 26     | 23     |

---

## §Limitation

Vacation uses **`limitation_type_id = "vacation"`**:
- Window start: `date(filing_date.year - 3, 1, 1)`
- Freeze periods apply (same mechanism as general limitation)
- A calendar year is claimable if: `vacation_window_start <= year_end <= filing_date`

See: `docs/skills/limitation/SKILL.md` §Vacation.

---

## §SSOT Schema

Add to `backend/app/ssot.py`:

```python
@dataclass
class VacationWeekTypeSegment:
    """A segment within a calendar year with uniform week type."""
    segment_start: date | None = None
    segment_end: date | None = None
    week_type: str = ""               # "five_day" | "six_day"
    weeks_count: Decimal = Decimal("0")
    weight: Decimal = Decimal("0")    # weeks_count / total_weeks_in_year
    base_days: int = 0                # days per table for this week type
    weighted_days: Decimal = Decimal("0")  # weight × base_days


@dataclass
class VacationYearData:
    """Vacation data for a single calendar year."""
    year: int = 0
    year_start: date | None = None    # Jan 1 or employment start (partial)
    year_end: date | None = None      # Dec 31 or employment end (partial)
    is_partial: bool = False
    partial_fraction: Decimal | None = None   # None if full year
    partial_description: str = ""     # e.g. "9 חודשים (אפריל–דצמבר)" for UI
    seniority_years: int = 0
    age_at_year_start: int | None = None      # construction only
    age_55_split: bool = False                # construction: turned 55 this year
    week_type_segments: list[VacationWeekTypeSegment] = field(default_factory=list)
    weighted_base_days: Decimal = Decimal("0")
    entitled_days: Decimal = Decimal("0")
    avg_daily_salary: Decimal = Decimal("0")
    year_value: Decimal = Decimal("0")


@dataclass
class VacationResult:
    """Annual vacation calculation result."""
    entitled: bool = True

    industry: str = ""
    seniority_basis: str = ""         # "employer" | "industry"

    years: list[VacationYearData] = field(default_factory=list)

    grand_total_days: Decimal = Decimal("0")
    grand_total_value: Decimal = Decimal("0")
```

Add to `RightsResults`:
```python
vacation: VacationResult | None = None
```

---

## §Static Data

The entitlement tables are embedded as constants in the module code (not CSV files — they are stable legal constants).

```python
# Format: (min_seniority_years, max_seniority_years_inclusive, days_6day, days_5day)
VACATION_DAYS_TABLES: dict[str, list[tuple[int, int, int, int]]] = {
    "general": [
        (1, 5, 14, 12), (6, 6, 16, 14), (7, 7, 18, 15),
        (8, 8, 19, 16), (9, 9, 20, 17), (10, 10, 21, 18),
        (11, 11, 22, 19), (12, 12, 23, 20), (13, 999, 24, 20),
    ],
    "construction": [
        (1, 2, 12, 10), (3, 3, 13, 11), (4, 4, 16, 14),
        (5, 5, 18, 15), (6, 7, 19, 17), (8, 8, 19, 17),
        (9, 999, 26, 23),
    ],
    "construction_55plus": [
        # Replaces "construction" rows for seniority >= 11 when worker is age 55+
        (11, 999, 28, 24),
    ],
    "agriculture": [
        (1, 3, 12, 12), (4, 6, 16, 16), (7, 9, 20, 20),
        (10, 10, 24, 24), (11, 999, 26, 26),
    ],
    "cleaning": [
        (1, 2, 12, 10), (3, 4, 13, 11), (5, 5, 15, 13),
        (6, 6, 20, 18), (7, 8, 21, 19), (9, 999, 26, 23),
    ],
}
```

---

## §Pipeline Integration

### Phase 2 — add after recreation

```python
from .modules.vacation import compute_vacation

if ssot.input.employment_periods and ssot.period_month_records:
    vacation_result = compute_vacation(
        employment_periods=ssot.input.employment_periods,
        work_patterns=ssot.input.work_patterns,
        period_month_records=ssot.period_month_records,
        industry=ssot.input.industry,
        seniority_totals=ssot.seniority_totals,
        birth_year=ssot.input.personal_details.birth_year,
        right_toggles=ssot.input.right_toggles,
    )
    ssot.rights_results.vacation = vacation_result
```

Vacation has no dependencies on other rights. It can run in any order within Phase 2.

### Phase 3 — limitation

```python
if ssot.rights_results.vacation:
    vac = ssot.rights_results.vacation
    full_amount = vac.grand_total_value

    # Compute vacation window start (3 + current year)
    vac_window_start = date(filing_date.year - 3, 1, 1)
    # Apply freeze adjustments using the existing vacation LimitationWindow
    # (computed earlier in Phase 3 Step 1 via compute_limitation_window)

    claimable_amount = Decimal("0")
    for year in vac.years:
        if year.year_end and vac_window_start <= year.year_end <= filing_date:
            claimable_amount += year.year_value

    excluded_amount = full_amount - claimable_amount
    claimable_dur, excluded_dur = compute_right_durations("vacation")
    per_right_results["vacation"] = RightLimitationResult(
        limitation_type_id="vacation",
        full_amount=full_amount,
        claimable_amount=claimable_amount,
        excluded_amount=excluded_amount,
        claimable_duration=claimable_dur,
        excluded_duration=excluded_dur,
    )
```

---

## §Frontend

### Right Toggle

Add `vacation` to the right_toggles input section (enabled by default).

### VacationBreakdown Component

Display in ResultsView after RecreationBreakdown:

**Header card stats:**
- סה"כ ימי חופשה
- סה"כ שווי (לפני התיישנות)
- סה"כ שווי (אחרי התיישנות)

**Per-year table — one row per calendar year:**

| שנה | חלקיות | ותק | בסיס ימים | ימים מזכים | שכר יומי ממוצע | שווי |
|-----|--------|-----|-----------|-----------|----------------|------|

- Partial years: show `Tag` with `"שנה חלקית"` + `partial_description` in a tooltip or sub-row
- Expandable row for years with mixed week type: show `VacationWeekTypeSegment` breakdown
- Expandable row for construction age-55 split years

---

## §Test Cases

### Case 1 — General, 5-day, 3 full years, limitation cuts year 1
- Employment: 2021-01-01 – 2023-12-31, prior=0, salary 10,000₪/month, filing 2025-01-01
- Vacation window: from 2022-01-01
- Expected:
  - Year 2021: seniority=1, base=12 days (5-day), full year → EXCLUDED (before 2022)
  - Year 2022: seniority=2, base=12 days → claimable
  - Year 2023: seniority=3, base=12 days → claimable

### Case 2 — Cleaning, partial first/last year, industry seniority 12m
- Employment: 2021-04-01 – 2023-09-30, prior=12m (1y), 5-day, salary 40₪/h
- Year 2021 (9 months Apr–Dec): seniority=floor(12/12)+1=2 → 10 days × 9/12 = 7.5 days
- Year 2022 (12 months): seniority=floor(21/12)+1=2 → 10 days × 1.0 = 10 days
- Year 2023 (9 months Jan–Sep): seniority=floor(33/12)+1=3 → 11 days × 9/12 = 8.25 days

### Case 3 — Construction, mixed week, age 55 in year 10
- Employment: 2015-01-01 – 2024-12-31, prior=24m (2y), birth_year=1969
- Age 55 turns on 2024-01-01 (Jan 1, 1969+55)
- Year 2024: seniority=floor((24+108)/12)+1 = floor(132/12)+1 = 11+1 = 12 years
  Wait: seniority at Jan 1 2024 = prior(24m) + months at defendant 2015-2023(108m) = 132m = 11 years → seniority_years = 12
  Age 55 on Jan 1 2024 → full year at 55+ → base = 28 (6-day) or 24 (5-day)

---

## §Anti-Patterns (DO NOT DO)

1. **DO NOT** use gross days for general industry. Net only.
2. **DO NOT** use employment anniversary year — always calendar year.
3. **DO NOT** apply industry seniority for general/agriculture.
4. **DO NOT** apply employer-only seniority for construction/cleaning.
5. **DO NOT** assume avg_daily_salary = monthly/22 — compute from actual days.
6. **DO NOT** use months for partial_fraction — use actual work days.
