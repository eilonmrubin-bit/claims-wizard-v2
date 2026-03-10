---
name: meal-allowance
description: |
  Israeli labor law meal/lodging allowance (אש"ל) module for the Claims Wizard (אשף התביעות).
  Also defines the new shared LodgingInput structure that replaces the old cycle-based
  lodging input used in the travel module.
  Use this skill whenever working on אש"ל calculation, lodging period input,
  or the updated travel formula that depends on lodging visits.
  ALWAYS read this skill before touching any אש"ל or lodging-related code.
---

# אש"ל (Meal & Lodging Allowance) — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent legal rules.** All rates, thresholds, and rules come from this skill only.
2. **אש"ל is per night, not per day.** The unit of entitlement is a lodging night.
3. **Construction industry only.** Other industries have no אש"ל entitlement (for now).
4. **This skill also redefines LodgingInput.** The old cycle-based LodgingInput in the travel
   skill is replaced by the period-based structure defined here. The travel module must be
   updated to use the new structure.
5. **Limitation: general — 7 years.** Same as most rights.
6. **Do not track lodging days inside the travel module.** The אש"ל module is the sole owner
   of lodging-day accounting.
7. **The unit of visit counting is VisitGroup.** Do not reduce lodging to a single
   nights_per_unit / visits_per_unit pair — multiple visit groups per period are allowed.

---

## 1. Entitlement Rules

- **Who:** Construction workers only (`industry = "construction"`).
- **What:** A daily allowance for each night spent sleeping on site (away from home).
- **Rate:** Per night (not per work day).
- **Waiting period:** None. Entitlement from first night on site.
- **Limitation:** General — 7 years. `right_limitation_mapping.meal_allowance = "general"`.
- **Employer deductions:** Yes — employer may have paid partial or full meal allowance
  in advance. Handled via `deductions_input.meal_allowance`.

---

## 2. Rates

| Effective date | Rate per night |
|----------------|---------------|
| 1948-01-01     | 124.20 ₪      |
| 2017-06-01     | 143.50 ₪      |

Static data file: `data/meal_allowance/construction.csv`

```csv
effective_date,nightly_amount
1948-01-01,124.20
2017-06-01,143.50
```

Rate lookup: `get_meal_allowance_rate(date) → Decimal`
Use the rate effective at the **first day of the lodging period** within each month.
If rate changes mid-month, split that month into two segments.

---

## 3. LodgingInput Structure

This structure is used by both the אש"ל module and the travel module.

### VisitGroup

A **VisitGroup** describes one recurring visit pattern within a lodging period:
how many nights each visit lasts, and how many such visits occur per week or per month.

```python
@dataclass
class VisitGroup:
    id: str
    nights_per_visit: int              # how many nights each visit in this group lasts (>= 1)
    count: int                         # how many such visits per week or per month (>= 1)
    # nights contributed by this group = nights_per_visit x count
    # travel days contributed by this group = count x 2 (departure + return per visit)
```

### LodgingPeriod

```python
@dataclass
class LodgingPeriod:
    id: str
    start: date                        # inclusive
    end: date                          # inclusive
    snap_to: str | None                # "employment_period" | "work_pattern" | None
    snap_ref_id: str | None            # id of the snapped EP or WP, if any

    pattern_type: str                  # "none" | "weekly" | "monthly"
    # "none"    -> no lodging in this period; visit_groups must be empty
    # "weekly"  -> visit_groups define visits per week
    # "monthly" -> visit_groups define visits per month

    cycle_weeks: int = 1               # relevant only when pattern_type == "weekly"
    # cycle_weeks = 1 (default): standard weekly pattern — formula applied per week.
    # cycle_weeks = N (N > 1): multi-week cycle — formula applied once per block of
    #   N consecutive work weeks, then distributed proportionally.
    # Ignored when pattern_type == "monthly".
    # Example: 2-weeks-on/2-weeks-off pattern → cycle_weeks=2, nights=10 per block.

    visit_groups: list[VisitGroup]     # empty if pattern_type == "none"
    # Derived totals (computed, not stored):
    #   total_nights_per_unit = sum(vg.nights_per_visit * vg.count)
    #   total_visits_per_unit = sum(vg.count)
    # Constraint: total_nights_per_unit >= total_visits_per_unit >= 1
```

**Note on cycle_weeks:** When `cycle_weeks > 1`, the travel formula is applied to the
entire block of `cycle_weeks` work weeks at once. The meal allowance (אש"ל) logic is
**not affected** — nights are still counted directly from `visit_groups` and pro-rated
to calendar months. Only the travel module uses `cycle_weeks`.

### LodgingInput

```python
@dataclass
class LodgingInput:
    periods: list[LodgingPeriod]
    # Empty list = no lodging at all.
    # Periods must not overlap. Gaps between periods = no lodging.
    # Periods do not need to cover the full employment span.
```

**SSOT change:** `lodging_input: LodgingInput | None` in `SSOTInput` uses this structure.

---

## 4. UI / Lodging Input UX

The lodging input UI is a **standalone section** in the form, **separate from the travel
section**. It is shown only when `industry = "construction"`.

### Section header: "לינה באתר"

Contains:
- A list of lodging periods (initially empty).
- An "הוסף תקופת לינה" button.

### Per Lodging Period

Each period card contains:

**Row 1 — תאריכים:**
- DatePicker start / end.
- [SNAP] dropdown: snap to any employment period or work pattern (fills dates automatically).

**Row 2 — דפוס לינה (Radio):**
- שבועי | חודשי | ללא לינה

**Row 3+ — VisitGroups (shown only when pattern_type is "weekly" or "monthly"):**

Each VisitGroup row:
  [ X  לילות לביקור ] x [ Y  ביקורים ל{שבוע/חודש} ]   [delete]

Below all groups:
  [ + הוסף סוג ביקור ]
  סה"כ: Z לילות, W ביקורים ל{שבוע/חודש}

**Helper formula display** (below the groups):
  ימי נסיעה = ימי עבודה + W - Z
where W = total_visits_per_unit, Z = total_nights_per_unit.

**Delete period** button (top-right of card).

### Example display

```
תקופת לינה 1: 01.01.2019 - 30.06.2021  [SNAP]                    [delete]
  דפוס: * שבועי  o חודשי  o ללא לינה
  [ 4 לילות לביקור ] x [ 1 ביקורים לשבוע ]   [delete]
  [ + הוסף סוג ביקור ]
  סה"כ: 4 לילות, 1 ביקור לשבוע
  ימי נסיעה = ימי עבודה + 1 - 4

תקופת לינה 2: 01.07.2021 - 31.12.2024  [SNAP]                    [delete]
  דפוס: o שבועי  * חודשי  o ללא לינה
  [ 14 לילות לביקור ] x [ 1 ביקורים לחודש ]   [delete]
  [  1 לילה  לביקור ] x [ 6 ביקורים לחודש ]   [delete]
  [ + הוסף סוג ביקור ]
  סה"כ: 20 לילות, 7 ביקורים לחודש
  ימי נסיעה = ימי עבודה + 7 - 20
```

**Validation:**
- Each VisitGroup: nights_per_visit >= 1, count >= 1.
- At least 1 VisitGroup required when pattern_type != "none".
- No overlapping lodging periods.
- Periods within employment span.

---

## 5. אש"ל Calculation

### Derived totals per LodgingPeriod

```python
def total_nights(p: LodgingPeriod) -> int:
    return sum(vg.nights_per_visit * vg.count for vg in p.visit_groups)

def total_visits(p: LodgingPeriod) -> int:
    return sum(vg.count for vg in p.visit_groups)
```

### Step 1 — Enumerate lodging nights per month

For each LodgingPeriod P where pattern_type != "none":

```python
nights_per_unit = total_nights(P)   # per week or per month, depending on pattern_type

for each calendar month M that overlaps with P:
    month_start = max(P.start, first_day_of(M))
    month_end   = min(P.end,   last_day_of(M))
    days_in_clip = (month_end - month_start).days + 1

    if P.pattern_type == "monthly":
        days_in_full_month = last_day_of(M).day
        nights_this_month = nights_per_unit * (days_in_clip / days_in_full_month)

    elif P.pattern_type == "weekly":
        # weeks_in_clip is decimal: each Mon-Sun week weighted by fraction of 7 days in clip
        weeks_in_clip = count_fractional_weeks(month_start, month_end)
        nights_this_month = nights_per_unit * weeks_in_clip
```

### Step 2 — Rate lookup

Look up nightly_amount from data/meal_allowance/construction.csv by effective_date <= month_start.

If rate changes within the month (2017-06-01 falls mid-month):
Split the month into two segments at the rate-change date, compute each separately.

### Step 3 — Monthly value

```python
month_meal_value = nights_this_month x nightly_rate
```

### Step 4 — Totals

```python
grand_total_nights  = sum(nights_this_month for all months)
grand_total_value   = sum(month_meal_value for all months)
claim_before_deductions = grand_total_value
```

---

## 6. Updated Travel Formula

**Key formula:** `travel_days = max(2 × total_visits, work_days + total_visits - total_nights)`

Derivation:
- Each visit generates exactly 2 travel days (departure + return), regardless of how many nights.
- Non-visit work days each generate 1 travel day.
- When there are non-lodging work days: travel = 2×v + (work_days - nights - visits) = work_days + visits - nights
- When lodging is dense (work_days <= nights + visits): all work days are inside visits,
  so the minimum is 2 travel days per visit = 2 × visits.
- Combined: max(2 × visits, work_days + visits - nights)

**ANTI-PATTERN:** DO NOT use `max(0, work_days + visits - nights)`. Zero is wrong —
every visit has a departure AND a return, so the floor is 2 × visits, not 0.

### Weekly pattern — compute per work week

```python
for each work week W:
    active = find_active_lodging_period(W.start, W.end, lodging_input)

    if active is None or active.pattern_type == "none":
        travel_days = work_days(W)
    else:
        n = total_nights(active)
        v = total_visits(active)
        travel_days = max(2 * v, work_days(W) + v - n)
```

### Monthly pattern — compute per calendar month

```python
for each calendar month M:
    active = find_active_lodging_period(M, lodging_input)

    # CRITICAL: count work days by calendar date, NOT by week attribution.
    # A work day belongs to month M if its calendar date falls within M,
    # regardless of which week it belongs to in the OT pipeline.
    work_days_M = count of distinct calendar dates d where:
                    d.month == M.month and d.year == M.year
                    and d has at least one work shift

    if active is None or active.pattern_type == "none":
        travel_days_M = work_days_M
    else:
        n = total_nights(active)
        v = total_visits(active)
        travel_days_M = max(2 * v, work_days_M + v - n)
```

**Anti-pattern:** DO NOT count work_days for monthly pattern by summing
`work_days(W)` for weeks whose `start_date` falls in M. This double-counts or
misses days at month boundaries. Always count by calendar date.

**Verification table:**

| work_days | total_visits | total_nights | travel_days         |
|-----------|-------------|--------------|---------------------|
| 5         | 0           | 0            | 5                   |
| 5         | 1           | 4            | max(2, 2) = 2       |
| 4         | 1           | 1            | max(2, 4) = 4       |
| 4         | 2           | 2            | max(4, 4) = 4       |
| 5         | 2           | 4            | max(4, 3) = 4       |
| 23        | 7           | 20           | max(14, 10) = 14    |
| 20        | 7           | 20           | max(14, 7) = 14     |

---

## 7. SSOT Input Changes

No additional changes beyond the LodgingInput structure in §3. The field in SSOTInput:

```python
lodging_input: LodgingInput | None = None
```

---

## 8. SSOT Output Schema

Add to SSOT.rights_results:

```
meal_allowance: {
  entitled: bool
  not_entitled_reason: str | null      # "not_construction" | "no_lodging_input" | "disabled"
  industry: str

  monthly_breakdown: List<{
    month: (int, int)                  # (year, month)
    nights: decimal
    nightly_rate: decimal
    claim_amount: decimal
  }>

  grand_total_nights: decimal
  grand_total_value: decimal
  claim_before_deductions: decimal
}
```

---

## 9. Static Data

File: data/meal_allowance/construction.csv (already created — no changes needed).

settings.json (already updated — no changes needed).

---

## 10. Pipeline Integration

No changes needed — module signature and pipeline wiring are unchanged from original implementation.

---

## 11. Anti-Patterns

1. **DO NOT compute אש"ל for non-construction workers.**
2. **DO NOT give אש"ל per work day.** The unit is per night.
3. **DO NOT reduce multiple VisitGroups to a single pair before computing.**
   Always sum: total_nights = sum(vg.nights_per_visit x vg.count), total_visits = sum(vg.count).
4. **DO NOT hardcode rates.** Always look up from CSV.
5. **DO NOT apply limitation inside this module.**
6. **DO NOT round nights before the final monthly total.**
7. **DO NOT place the lodging UI inside the travel section.** It is a standalone section.
8. **DO NOT store total_nights / total_visits in the dataclass.** Always compute on the fly.
9. **DO NOT count monthly work_days by week attribution (week.start_date).** For monthly
   lodging pattern, count work days by calendar date. A day belongs to a month if its
   date falls within that month — period. Week attribution is for weekly pattern only.
10. **DO NOT combine monthly lodging pattern with cyclic work pattern.**
   Monthly lodging assumes visits are contained within calendar months.
   For cyclic work patterns, always use weekly lodging — visits align
   naturally with work weeks in the cycle.

---

## 12. Edge Cases

1. **Lodging period spans rate change (2017-06-01):** Split June 2017 into two segments.
2. **Partial month at employment boundary:** Pro-rate using fractional weeks / days.
3. **VisitGroup with count = 0:** Invalid — reject in validation; skip in module.
4. **Lodging period extends beyond employment end:** Clip to employment end.
5. **pattern_type = "none" with non-empty visit_groups:** Ignore visit_groups.
6. **Non-construction industry, lodging_input set:** Return not_entitled, log warning.
7. **right_toggles["meal_allowance"] = false:** Return empty result, grand_total_value = 0.
8. **Multiple VisitGroups:**
   [{nights_per_visit:14, count:1}, {nights_per_visit:1, count:6}]
   -> total_nights=20, total_visits=7
   -> travel_days = work_days + 7 - 20

---

## 13. Test Cases

### Case 1 — Weekly, single visit group, full year 2024

```
employment: 2024-01-01 - 2024-12-31
lodging: weekly, visit_groups: [{nights_per_visit:4, count:1}]
total_nights=4, total_visits=1, rate=143.5

grand_total_nights ~= 208
grand_total_value  ~= 29,848
travel_days/week = work_days + 1 - 4
```

### Case 2 — Rate change mid-employment

```
employment: 2017-01-01 - 2017-12-31
lodging: weekly, visit_groups: [{nights_per_visit:4, count:1}]

Jan-May 2017 (~21 weeks): 21 x 4 x 124.2 = 10,432.8
Jun-Dec 2017 (~31 weeks): 31 x 4 x 143.5 = 17,794
Total ~= 28,226.8
```

### Case 3 — Monthly, multiple visit groups

```
employment: 2023-01-01 - 2023-12-31
lodging: monthly, visit_groups: [
  {nights_per_visit:14, count:1},
  {nights_per_visit:1,  count:6},
]
total_nights=20, total_visits=7, rate=143.5

meal_allowance: 12 x 20 x 143.5 = 34,440
travel (work_days=22/month): 22 + 7 - 20 = 9 travel days/month
```

### Case 4 — Travel formula, single group

```
weekly, visit_groups: [{nights_per_visit:4, count:1}]
work_days=5: travel = 5 + 1 - 4 = 2
```

### Case 5 — Travel formula, two groups same size

```
weekly, visit_groups: [{nights_per_visit:2, count:2}]
total_nights=4, total_visits=2
work_days=5: travel = 5 + 2 - 4 = 3
```
