---
name: travel
description: |
  Israeli labor law travel allowance (דמי נסיעות) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on travel allowance calculation, industry-specific rates,
  distance-based tiers (construction), or lodging pattern computation.
  ALWAYS read this skill before touching any travel-related code.
---

# דמי נסיעות — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent legal rules.** All rates, thresholds, and rules come from this skill only.
2. **The unit of travel entitlement is the work day, not the shift.** Multiple shifts on the same calendar day = 1 travel day.
3. **Lodging workers get travel only for departure/return days.** Intermediate lodging days are NOT travel days — they are אש"ל days (a separate future right).
4. **Industry rates override the base rate.** Construction workers never use 22.6 ₪ — they always use at least 26.4 ₪.
5. **The lodging cycle is the unit of computation.** Never compute travel days daily — always accumulate to week level first, then apply lodging pattern.
6. **Do not compute אש"ל here.** Lodging days are not tracked by this module. אש"ל is a fully separate right with no dependency on this module.
7. **Rates are time-varying.** Always look up `travel_allowance.csv` by effective date, not hardcode.

---

## Conceptual Model

```
For each work week W:
  work_days(W) = count of calendar days with ≥1 shift in week W
  travel_days(W) = split(work_days, lodging_pattern, week_position_in_cycle)

  travel_value(W) = travel_days(W) × daily_rate_at(week.start_date)

grand_total_travel_days = Σ travel_days(W)
grand_total_value       = Σ travel_value(W)
```

---

## Step 1 — Determine Daily Rate

Look up `travel_allowance/{industry}.csv` by `effective_date ≤ week.start_date`.

### Industry Rates

| Industry | Distance condition | Daily rate |
|----------|-------------------|------------|
| `general` | (none) | from CSV — currently 22.6 ₪ |
| `construction` | < 40 km from home to site | 26.4 ₪ |
| `construction` | ≥ 40 km from home to site | 26.4 × 1.5 = **39.6 ₪** |
| `cleaning` | (none) | same as `general` — 22.6 ₪ |
| `agriculture` | (none) | same as `general` — 22.6 ₪ |

**Construction rule:** 26.4 ₪ is the floor for all construction workers, regardless of distance. Distance input is only needed to determine whether the higher 39.6 ₪ tier applies.

**Rate source:** `data/travel_allowance/{industry}.csv` where `industry` ∈ `{general, construction}`.
- All industries that don't have their own CSV file fall back to `general.csv`.
- Construction has its own CSV: `construction_base.csv` (26.4 tier) and `construction_far.csv` (39.6 tier).
- Which construction CSV to use is determined by `travel_distance_km` input (see Step 2).

---

## Step 2 — New SSOT Input Fields

Add to `SSOT.input`:

```
// ═══ דמי נסיעות ═══
travel_distance_km: decimal | null
  // Construction only. One-way distance from worker's home to work site in km.
  // null for non-construction industries (distance is irrelevant).
  // Determines which construction rate applies: <40 → 26.4, ≥40 → 39.6

lodging_input: LodgingInput | null
  // null if no overnight stays (worker returns home every day).
  // Relevant for construction workers who sleep on site during the work week.
```

```
LodgingInput {
  has_lodging: bool
  // If true, worker sleeps on site for some or all of the work week.
  // If false, all fields below are irrelevant.

  cycle_weeks: int                    // 1, 2, 3, or 4
  // Length of the repeating lodging cycle in weeks.
  // Example: cycle_weeks=4 means a pattern that repeats every 4 weeks.

  cycle: List<{
    week_in_cycle: int               // 1-based index within the cycle (1 ≤ week_in_cycle ≤ cycle_weeks)
    pattern: "full_lodging" | "daily_return"
    // full_lodging: worker sleeps on site all week, returns home once at end of week.
    //   → 2 travel days for that week (departure + return), rest are lodging/אש"ל days.
    // daily_return: worker returns home every working day.
    //   → all work_days are travel days, 0 lodging days.
  }>
}
```

**UI rules:**
- `has_lodging` checkbox is shown **only** when `industry = "construction"`.
- `travel_distance_km` input is shown **only** when `industry = "construction"`.
- When `has_lodging = false` or `lodging_input = null`: all work days are travel days.
- When `has_lodging = true`:
  - Show cycle builder: select cycle length (1/2/3/4 weeks), then for each week select `full_lodging` / `daily_return`.
  - The cycle builder resembles the training fund tier UI — a compact list of week slots.

**Common examples:**
- Weekly return (most common): `cycle_weeks=1`, `cycle=[{week_in_cycle:1, pattern:"full_lodging"}]`
- Daily return: `cycle_weeks=1`, `cycle=[{week_in_cycle:1, pattern:"daily_return"}]` (same as `has_lodging=false`)
- 3 weeks lodging + 1 week daily: `cycle_weeks=4`, `cycle=[{1:"full_lodging"},{2:"full_lodging"},{3:"full_lodging"},{4:"daily_return"}]`
- Alternating: `cycle_weeks=2`, `cycle=[{1:"full_lodging"},{2:"daily_return"}]`

---

## Step 3 — Work Days per Week

Source: `SSOT.ot_results.weeks[]` — the list of `Week` objects produced by the OT pipeline.

For each week W:
```python
work_days(W) = len({ shift.assigned_day
                     for shift in W.shifts
                     if shift is not a rest day })
```

Alternatively, count distinct calendar dates with at least one actual work shift.

**Important:** Use only weeks where `work_days(W) > 0`. Skip empty weeks entirely.

---

## Step 4 — Determine Week Position in Lodging Cycle

For workers with `has_lodging = true`:

```python
# Assign each work week a cycle position.
# Cycle resets at the start of each employment period.

work_weeks = [W for W in ssot.ot_results.weeks if work_days(W) > 0]

for i, week in enumerate(work_weeks):
    cycle_position = (i % cycle_weeks) + 1   # 1-based
    week_pattern = cycle[cycle_position].pattern
```

**Gap handling:** Employment gaps reset the cycle. When a new employment period starts, the cycle index restarts from 1.

---

## Step 5 — Travel Days per Week

```python
def compute_week_travel(work_days: int, week_pattern: str) -> int:
    """Returns travel_days for the week."""

    if week_pattern == "daily_return":
        return work_days

    if week_pattern == "full_lodging":
        if work_days == 0:
            return 0
        if work_days == 1:
            # Only one day worked — departure or return, not both.
            return 1
        # Standard lodging week: 2 travel days (departure + return).
        return 2
```

---

## Step 6 — Weekly Travel Value

```python
daily_rate = get_travel_rate(industry, travel_distance_km, week.start_date)
week_travel_value = travel_days × daily_rate
```

---

## Step 7 — Monthly Aggregation

After computing per-week values, aggregate to month level for the limitation module and UI display:

```python
for each calendar month M:
  month_travel_days = Σ travel_days(W)  for W whose start_date.month == M
  month_value       = Σ week_travel_value(W) for W in M
```

**Week attribution:** A week belongs to the month of its `start_date` (Monday). This matches the OT pipeline convention.

---

## Step 8 — Totals

```python
grand_total_travel_days = Σ month_travel_days
grand_total_value       = Σ month_value
claim_before_deductions = grand_total_value
```

No waiting period. Travel allowance accrues from the first work day.

**Limitation:** General — 7 years. `right_limitation_mapping.travel = "general"`.

---

## SSOT Output Schema

Add to `SSOT.rights_results`:

```
travel: {
  // ═══ Configuration ═══
  industry: string
  daily_rate: decimal                  // effective rate used (22.6 / 26.4 / 39.6)
  distance_km: decimal | null          // from input, construction only
  distance_tier: "standard" | "far" | null  // construction: <40 → standard, ≥40 → far

  // ═══ Lodging Summary ═══
  has_lodging: bool
  lodging_cycle_weeks: int | null
  lodging_cycle: list<{ week_in_cycle: int, pattern: string }> | null

  // ═══ Weekly Detail ═══
  weekly_detail: List<{
    week_start: date
    week_end: date
    effective_period_id: string
    work_days: int
    cycle_position: int | null          // 1-based position within lodging cycle, null if no lodging
    week_pattern: "full_lodging" | "daily_return" | "no_lodging"
    travel_days: int
    daily_rate: decimal
    week_travel_value: decimal
  }>

  // ═══ Monthly Breakdown (for limitation module) ═══
  monthly_breakdown: List<{
    month: (int, int)                   // (year, month)
    travel_days: int
    claim_amount: decimal
  }>

  // ═══ Totals ═══
  grand_total_travel_days: decimal
  grand_total_value: decimal
  claim_before_deductions: decimal      // = grand_total_value
}
```

---

## Static Data — Required Updates

### New files in `data/travel_allowance/`

The existing `general.csv` remains. Add:

```
data/travel_allowance/
├── general.csv               # exists — base rate (22.6)
├── construction_base.csv     # NEW — construction <40km (26.4)
└── construction_far.csv      # NEW — construction ≥40km (39.6)
```

**`construction_base.csv`:**
```csv
effective_date,daily_amount
2025-02-01,26.40
```

**`construction_far.csv`:**
```csv
effective_date,daily_amount
2025-02-01,39.60
```

**Rate lookup function:**
```python
def get_travel_rate(industry: str, distance_km: Decimal | None, date: date) -> Decimal:
    if industry == "construction":
        if distance_km is not None and distance_km >= 40:
            return lookup_csv("construction_far", date)
        else:
            return lookup_csv("construction_base", date)
    else:
        return lookup_csv("general", date)
```

### `settings.json` Addition

```json
"travel_config": {
  "industries": {
    "construction": {
      "name": "בניין",
      "requires_distance_input": true,
      "distance_threshold_km": 40,
      "rate_csv_standard": "construction_base",
      "rate_csv_far": "construction_far"
    },
    "general": {
      "name": "כללי",
      "requires_distance_input": false,
      "rate_csv": "general"
    },
    "cleaning": {
      "name": "ניקיון",
      "requires_distance_input": false,
      "rate_csv": "general"
    },
    "agriculture": {
      "name": "חקלאות",
      "requires_distance_input": false,
      "rate_csv": "general"
    }
  }
}
```

Update `limitation_config.right_limitation_mapping`:
```json
"travel": "general"
```

---

## Pipeline Integration

### Position in Pipeline

Phase 2, parallel to other rights. No dependencies on other Phase 2 rights.

### Inputs from SSOT

```
Reads:
  SSOT.input.industry
  SSOT.input.travel_distance_km          // new field
  SSOT.input.lodging_input               // new field
  SSOT.input.right_toggles["travel"]     // skip if false
  SSOT.ot_results.weeks                  // week list with shift data
  data/travel_allowance/*.csv
  settings.travel_config
```

### Output

```
Writes:
  SSOT.rights_results.travel
```

### Module Signature

```python
def compute_travel(
    industry: str,
    travel_distance_km: Decimal | None,
    lodging_input: LodgingInput | None,
    weeks: list[Week],
    get_travel_rate: Callable[[str, Decimal | None, date], Decimal],
    right_enabled: bool,
) -> TravelResult:
    ...
```

---

## Anti-Patterns

1. **DO NOT use 22.6 for construction workers.** Construction floor is 26.4.
2. **DO NOT give travel allowance for lodging days.** Only departure and return days are travel days.
3. **DO NOT compute per calendar day.** Work at week level, then aggregate.
4. **DO NOT hardcode rates.** Always look up from CSV by effective date.
5. **DO NOT compute אש"ל here.** אש"ל is a fully separate right — this module has no connection to it.
6. **DO NOT reset the lodging cycle on calendar month boundaries.** Cycle resets only on employment period boundaries (gaps).
7. **DO NOT count a week with 0 work days as a cycle week.** Skip empty weeks when tracking cycle position.
8. **DO NOT apply limitation here.** The limitation module handles it via `monthly_breakdown`.
9. **DO NOT give 2 travel days for a 1-day work week in lodging mode.** 1 day worked = 1 travel day.
10. **DO NOT invent rates for new industries.** If an industry is not in `travel_config`, use `general`.

---

## Edge Cases

1. **No lodging, any industry:** All work days are travel days.

2. **Construction, lodging, partial week at employment start:**
   Example: employment starts Wednesday, worker goes straight to site, works Wed+Thu, returns Friday.
   → `work_days = 3`, `week_pattern = "full_lodging"` → `travel_days = 2`.

3. **Construction, lodging, partial week at employment end:**
   Same logic: count actual work days, apply formula.

4. **Single-day work week in lodging mode:**
   `work_days = 1` → `travel_days = 1`.
   Rationale: worker either departed or returned, not both.

5. **Gap between employment periods:**
   Cycle position resets at the start of the next employment period. The week immediately after a gap starts at `cycle_position = 1`.

6. **Non-construction industry with `lodging_input` set:**
   Ignore `lodging_input`. Treat as no lodging. Only construction lodging is defined.
   Log a warning if `lodging_input.has_lodging = true` for a non-construction worker — this is a data entry error.

7. **Construction worker, distance exactly 40 km:**
   `distance_km >= 40` → far tier applies. Rate = 39.6 ₪.

8. **Rate changes mid-employment:**
   Each week uses the rate in effect at `week.start_date`. If a rate change falls mid-week, it applies from the next week.

9. **`right_toggles["travel"] = false`:**
   Return an empty result with `grand_total_value = 0`. Do not compute.

10. **Cycle length = 1, pattern = "daily_return":**
    Equivalent to `has_lodging = false`. All work days are travel days.

---

## Test Cases

### Case 1 — General worker, no lodging, 3 months

```
industry: "general"
employment: 2024-01-01 – 2024-03-31
work pattern: 5 days/week (Mon–Fri)
lodging: none
daily_rate: 22.6 ₪

~13 work weeks × 5 work_days × 22.6 = ~1,469 ₪

Expected:
  travel_days per week = 5
  grand_total_travel_days ≈ 65
  grand_total_value ≈ 65 × 22.6 = 1,469 ₪
```

### Case 2 — Construction, <40km, no lodging

```
industry: "construction"
travel_distance_km: 15
lodging: none
daily_rate: 26.4 ₪
employment: 2024-01-01 – 2024-01-31
work pattern: 5 days/week

~4 work weeks × 5 work_days × 26.4 = ~528 ₪
```

### Case 3 — Construction, ≥40km, no lodging

```
industry: "construction"
travel_distance_km: 60
lodging: none
daily_rate: 39.6 ₪
employment: 2024-01-01 – 2024-01-31
work pattern: 5 days/week

~4 work weeks × 5 × 39.6 = ~792 ₪
```

### Case 4 — Construction, weekly lodging (most common case)

```
industry: "construction"
travel_distance_km: 30
lodging: has_lodging=true, cycle_weeks=1,
         cycle=[{week_in_cycle:1, pattern:"full_lodging"}]
daily_rate: 26.4 ₪
employment: 2024-01-01 – 2024-03-31
work pattern: 5 days/week (Mon–Fri)

Per week: work_days=5, pattern=full_lodging
  → travel_days=2

~13 weeks:
  grand_total_travel_days = 26
  grand_total_value = 26 × 26.4 = 686.4 ₪
```

### Case 5 — Construction, mixed cycle (3 weeks lodging + 1 week daily)

```
lodging: cycle_weeks=4,
  cycle=[{1:"full_lodging"},{2:"full_lodging"},{3:"full_lodging"},{4:"daily_return"}]
work_days/week: 5
daily_rate: 26.4

Per 4-week cycle:
  Weeks 1,2,3 (full_lodging): 2 travel_days each = 6 travel days
  Week 4 (daily_return): 5 travel_days = 5 travel days
  Total per cycle: 11 travel_days

3 full cycles (12 weeks) + 1 remaining week:
  → to be computed per week with exact cycle position
```

### Case 6 — Partial week, employment starts mid-week (lodging mode)

```
industry: "construction", travel_distance_km: 20
lodging: cycle_weeks=1, cycle=[{1:"full_lodging"}]
employment start: 2024-01-03 (Wednesday)
first week: work_days=3 (Wed, Thu, Fri)

Partial week at start:
  week_pattern = "full_lodging", work_days = 3
  → travel_days = 2
```

### Case 7 — Anti-pattern: single work day in lodging week

```
lodging: full_lodging
work_days = 1 (holiday week, only 1 day worked)

→ travel_days = 1 (NOT 2)
```

### Case 8 — Cycle resets after employment gap

```
Employment period 1: Jan–Mar 2023 (cycle_weeks=4, patterns: L,L,L,D)
Gap: Apr–May 2023
Employment period 2: Jun–Sep 2023

Period 2 week 1 → cycle_position = 1 (resets)
Period 2 week 2 → cycle_position = 2
...
```
