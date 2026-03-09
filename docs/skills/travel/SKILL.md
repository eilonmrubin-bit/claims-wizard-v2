---
name: travel
description: |
  Israeli labor law travel allowance (דמי נסיעות) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on travel allowance calculation, industry-specific rates,
  distance-based tiers (construction), or lodging pattern computation.
  ALWAYS read this skill before touching any travel-related code.
  For LodgingInput structure and VisitGroup definition, see meal-allowance/SKILL.md §3.
---

# דמי נסיעות — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent legal rules.** All rates, thresholds, and rules come from this skill only.
2. **The unit of travel entitlement is the work day, not the shift.** Multiple shifts on the same calendar day = 1 travel day.
3. **Lodging workers get travel only for departure/return days.** Intermediate lodging days are NOT travel days — they are אש"ל days.
4. **Industry rates override the base rate.** Construction workers never use 22.6 ₪ — they always use at least 26.4 ₪.
5. **Do not compute אש"ל here.** אש"ל is a fully separate right.
6. **Rates are time-varying.** Always look up travel_allowance.csv by effective date, never hardcode.
7. **LodgingInput uses VisitGroups.** The old cycle/full_lodging/daily_return structure is gone. See meal-allowance/SKILL.md §3.
8. **The travel formula floor is 2 × visits, NOT 0.** Every visit has departure + return = minimum 2 travel days.

---

## Conceptual Model

```
For each work week W (weekly lodging pattern):
  work_days(W) = distinct calendar dates with ≥1 shift in week W
  travel_days(W) = max(2 × visits, work_days(W) + visits - nights)
  travel_value(W) = travel_days(W) × daily_rate(week.start_date)

For each calendar month M (monthly lodging pattern):
  work_days(M) = distinct calendar dates in M with ≥1 shift  ← by date, not week attribution
  travel_days(M) = max(2 × visits, work_days(M) + visits - nights)
  travel_value(M) = travel_days(M) × daily_rate(M.start)

grand_total_travel_days = Σ travel_days
grand_total_value       = Σ travel_value
```

---

## Step 1 — Determine Daily Rate

Look up travel_allowance/{industry}.csv by effective_date <= period_start_date.

### Industry Rates

| Industry     | Distance condition       | Daily rate         |
|--------------|--------------------------|--------------------|
| general      | (none)                   | from CSV — 22.6 ₪  |
| construction | < 40 km home to site     | 26.4 ₪             |
| construction | ≥ 40 km home to site     | 39.6 ₪             |
| cleaning     | (none)                   | same as general    |
| agriculture  | (none)                   | same as general    |

Construction floor is always 26.4 ₪. Distance only determines if the 39.6 ₪ tier applies.

Rate source:
- general/cleaning/agriculture: data/travel_allowance/general.csv
- construction <40km: data/travel_allowance/construction_base.csv
- construction ≥40km: data/travel_allowance/construction_far.csv

---

## Step 2 — SSOT Input Fields

```
travel_distance_km: decimal | null
  // Construction only. <40 → base rate, ≥40 → far rate.

lodging_input: LodgingInput | null
  // See meal-allowance/SKILL.md §3 for full LodgingInput / LodgingPeriod / VisitGroup schema.
  // null = no lodging, all work days are travel days.
```

UI rules:
- travel_distance_km and lodging_input are shown only when industry = "construction".
- Radio for distance: "מתחת 40 ק"מ" (stores 0) / "40 ק"מ ומעלה" (stores 40).

---

## Step 3 — Work Days

Source: top-level SSOT.shifts (or SSOT.daily_records).

```python
# For weekly pattern: per week W
work_days(W) = len({ shift.assigned_day
                     for shift in all_shifts
                     if shift.assigned_day >= W.start and shift.assigned_day <= W.end })

# For monthly pattern: per month M — MUST use calendar dates, not week attribution
work_days(M) = len({ shift.assigned_day
                     for shift in all_shifts
                     if shift.assigned_day.month == M.month
                     and shift.assigned_day.year == M.year })
```

---

## Step 4 — Derived Lodging Totals

For the active LodgingPeriod P covering the current week/month:

```python
def total_nights(p: LodgingPeriod) -> int:
    return sum(vg.nights_per_visit * vg.count for vg in p.visit_groups)

def total_visits(p: LodgingPeriod) -> int:
    return sum(vg.count for vg in p.visit_groups)
```

---

## Step 5 — Travel Days

```python
def compute_travel_days(work_days: int, lodging_period: LodgingPeriod | None) -> int:
    if lodging_period is None or lodging_period.pattern_type == "none":
        return work_days

    n = total_nights(lodging_period)
    v = total_visits(lodging_period)

    # Floor: every visit has departure + return = 2 travel days minimum
    return max(2 * v, work_days + v - n)
```

### Formula derivation

Each visit: worker departs (1 travel day), spends N nights, returns (1 travel day) = 2 travel days.
Non-visit work days: 1 travel day each.
Total non-visit work days = work_days - nights - visits (can be negative when lodging is dense).
Net = 2×visits + max(0, work_days - nights - visits) = max(2×visits, work_days + visits - nights).

### Verification table

| work_days | visits | nights | travel_days              |
|-----------|--------|--------|--------------------------|
| 5         | 0      | 0      | 5                        |
| 5         | 1      | 4      | max(2, 2) = 2            |
| 4         | 1      | 1      | max(2, 4) = 4            |
| 4         | 2      | 2      | max(4, 4) = 4            |
| 5         | 2      | 4      | max(4, 3) = 4            |
| 23        | 7      | 20     | max(14, 10) = 14         |
| 20        | 7      | 20     | max(14, 7) = 14          |
| 1         | 1      | 0      | max(2, 2) = 2 — edge     |

---

## Step 6 — Weekly Travel Value

```python
daily_rate = get_travel_rate(industry, travel_distance_km, period_start_date)
travel_value = travel_days × daily_rate
```

---

## Step 7 — Monthly Aggregation

For weekly pattern: aggregate week values to month by week.start_date.month.
For monthly pattern: compute directly at month level (Step 5 runs per month).

```python
for each calendar month M:
    month_travel_days = Σ travel_days for the period/weeks in M
    month_value       = Σ travel_value for the period/weeks in M
```

---

## Step 8 — Totals

```python
grand_total_travel_days = Σ month_travel_days
grand_total_value       = Σ month_value
claim_before_deductions = grand_total_value
```

No waiting period. Limitation: general — 7 years.

---

## SSOT Output Schema

```
travel: {
  industry: string
  daily_rate: decimal
  distance_km: decimal | null
  distance_tier: "standard" | "far" | null
  has_lodging: bool
  lodging_periods_count: int

  weekly_detail: List<{
    week_start: date
    week_end: date
    effective_period_id: string
    work_days: int
    week_pattern: "no_lodging" | "lodging"
    travel_days: int
    daily_rate: decimal
    week_travel_value: decimal
  }>

  monthly_breakdown: List<{
    month: (int, int)
    travel_days: int
    claim_amount: decimal
  }>

  grand_total_travel_days: decimal
  grand_total_value: decimal
  claim_before_deductions: decimal
}
```

---

## Pipeline Integration

Phase 2, parallel to other rights.

```python
def compute_travel(
    industry: str,
    travel_distance_km: Decimal | None,
    lodging_input: LodgingInput | None,
    all_shifts: list[Shift],
    weeks: list[Week],
    get_travel_rate: Callable[[str, Decimal | None, date], Decimal],
    right_enabled: bool,
) -> TravelResult:
    ...
```

---

## Anti-Patterns

1. **DO NOT use 22.6 for construction workers.** Floor is 26.4.
2. **DO NOT give travel for lodging days.** Only departure and return days.
3. **DO NOT use max(0, ...) as the formula floor.** Use max(2 × visits, ...).
4. **DO NOT hardcode rates.** Always look up from CSV.
5. **DO NOT compute אש"ל here.**
6. **DO NOT count monthly work_days by week attribution.** Use calendar dates.
7. **DO NOT apply limitation here.** The limitation module handles it.
8. **DO NOT use old cycle/full_lodging/daily_return structure.** Use VisitGroups.
9. **DO NOT use monthly lodging pattern_type with cyclic work patterns.**
   Cross-month visits cause double-counting. Cyclic work patterns must
   use weekly lodging only — enforced by frontend validation.

---

## Edge Cases

1. **No lodging:** travel_days = work_days for all weeks.
2. **Dense lodging (visits × nights > work_days):** formula gives negative intermediate value — floor kicks in: travel_days = 2 × visits.
3. **Single work day in a lodging week:** work_days=1, visits=1, nights=0 → max(2, 2) = 2.
4. **Rate change mid-employment:** each week/month uses rate at its start_date.
5. **Non-construction with lodging_input set:** ignore lodging_input, treat as no lodging. Log warning.
6. **right_toggles["travel"] = false:** return empty result, grand_total_value = 0.

---

## Test Cases

### Case 1 — General, no lodging

```
industry: general, employment: 2024-01-01–2024-03-31, 5 days/week
travel_days/week = 5, grand_total ≈ 65 × 22.6 = 1,469 ₪
```

### Case 2 — Construction <40km, no lodging

```
industry: construction, distance: 15km, 5 days/week, January 2024
~4 weeks × 5 × 26.4 = 528 ₪
```

### Case 3 — Construction, monthly lodging, dense pattern

```
industry: construction, distance: 25km
lodging: monthly, visit_groups: [{nights:14, count:1}, {nights:1, count:6}]
total_nights=20, total_visits=7

January 2023 (23 work days): max(14, 23+7-20) = max(14, 10) = 14 travel days
February 2023 (20 work days): max(14, 20+7-20) = max(14, 7) = 14 travel days
```

### Case 4 — Formula: sparse lodging (old formula still correct)

```
weekly, visit_groups: [{nights:4, count:1}]
work_days=5: max(2, 5+1-4) = max(2, 2) = 2
```

### Case 5 — Formula: daily return visitors

```
weekly, visit_groups: [{nights:1, count:2}]
total_nights=2, total_visits=2
work_days=5: max(4, 5+2-2) = max(4, 5) = 5
```
