---
name: severance
description: |
  Israeli labor law severance pay (פיצויי פיטורין) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on severance pay calculation, termination reason handling,
  Section 14 determination, required employer contributions, or industry-specific severance rules.
  ALWAYS read this skill before touching any severance-related code.
---

# פיצויי פיטורין — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent legal rules.** This module computes severance based on the rules described here only.
2. **There are THREE computation paths,** determined by termination reason + Section 14 status. The Section 14 status is computed, not input.
3. **Section 14 determination is automatic.** The system compares required contributions vs. actual deposits. If actual ≥ required → Section 14 holds. If actual < required → Section 14 falls.
4. **"Fired/resigned_as_fired" and "resigned" are fundamentally different.** Different base salary reference, different limitation, different logic.
5. **Cleaning industry has additional components** (OT + recreation) that are the same value in ALL paths. Only the base component changes between paths.
6. **Rates vary by industry.** Do not hardcode any rate.

---

## New SSOT Input Fields

Add to `SSOT.input`:

```
termination_reason: "fired" | "resigned_as_fired" | "resigned"
```

Global field (one value per case).

**UI labels:**
- "fired" → "פוטר"
- "resigned_as_fired" → "התפטר בדין מפוטר"
- "resigned" → "התפטר"

**Note:** `deductions_input["severance"]` already exists — this is the actual amount the employer deposited to the severance fund. It is used both for Section 14 comparison AND as the deduction.

---

## Conceptual Model

```
┌─────────────────────────────────────────────────────┐
│ Step 1: Eligibility (12 months)                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Step 2: Compute TWO values (always, all paths):     │
│                                                     │
│  A. Full Severance (פיצויים מלאים)                  │
│     8.333% × last_salary × job_scope × months       │
│     + cleaning additions (OT + recreation)          │
│                                                     │
│  B. Required Contributions (הפרשות נדרשות)          │
│     contribution_rate% × actual_monthly_salary      │
│     × job_scope, per month                          │
│     + cleaning additions (OT + recreation)          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Step 3: Determine path by termination_reason        │
│                                                     │
│  ┌─────────────────────┐  ┌──────────────────────┐  │
│  │ fired /             │  │ resigned             │  │
│  │ resigned_as_fired   │  │                      │  │
│  └─────────┬───────────┘  └──────────┬───────────┘  │
│            │                         │              │
│            ▼                         ▼              │
│  ┌─────────────────────┐  ┌──────────────────────┐  │
│  │ Compare actual      │  │ PATH C              │  │
│  │ deposits vs.        │  │ claim =             │  │
│  │ required            │  │ required_contrib    │  │
│  │ contributions       │  │ − actual_deposits   │  │
│  └────┬──────────┬─────┘  │ (general limitation)│  │
│       │          │        └──────────────────────┘  │
│       ▼          ▼                                  │
│  ┌─────────┐ ┌──────────┐                           │
│  │ actual  │ │ actual   │                           │
│  │ >= req  │ │ < req    │                           │
│  │         │ │          │                           │
│  │ PATH A  │ │ PATH B   │                           │
│  │ s14     │ │ s14      │                           │
│  │ holds   │ │ falls    │                           │
│  └─────────┘ └──────────┘                           │
└─────────────────────────────────────────────────────┘

PATH A (s14 holds):
  claim = full_severance − required_contributions
  deposit goes to worker separately (not deducted)
  No limitation

PATH B (s14 falls):
  claim = full_severance − actual_deposits
  No limitation

PATH C (resigned):
  claim = required_contributions − actual_deposits
  General limitation (7 years)
```

---

## Industry Configuration

```
SEVERANCE_INDUSTRY_CONFIG = {
  "general": {
    "name": "כללי",
    "severance_rate": 0.08333,         // for full severance calc
    "contribution_rate": 0.06,         // required monthly contribution
    "ot_addition": false,
    "recreation_addition": false,
    "min_months": 12
  },
  "construction": {
    "name": "בניין",
    "severance_rate": 0.08333,
    "contribution_rate": 0.08333,
    "ot_addition": false,
    "recreation_addition": false,
    "min_months": 0
  },
  "cleaning": {
    "name": "נקיון",
    "severance_rate": 0.08333,
    "contribution_rate": 0.08333,
    "ot_addition": true,
    "ot_addition_rate": 0.06,
    "recreation_addition": true,
    "recreation_addition_rate": 0.08333,
    "min_months": 0
  },
  "agriculture": {
    "name": "חקלאות",
    "severance_rate": 0.08333,
    "contribution_rate": 0.06,
    "ot_addition": false,
    "recreation_addition": false,
    "min_months": 6
  }
}
```

Store in `settings.json` under `severance_config.industries`.

---

## Eligibility Gate — Minimum Employment Period

Worker must complete the minimum employment period defined for the industry:
- General: 12 months
- Construction: 0 (eligible from day one)
- Cleaning: 0 (eligible from day one)
- Agriculture: 6 months

Source: `SSOT.total_employment.worked_duration.months_decimal >= config.min_months`.

Once crossed → retroactive from day one. If not met → `eligible: false`, no calculation.
When `min_months = 0`, the gate is always passed.

---

## Sub-Computations (Always Computed)

These two values are always computed, regardless of path. The path determines how they are used.

### A. Full Severance (פיצויים מלאים)

#### Last Salary Determination

"Last salary" (`last_salary`) = monthly salary used as base for the **entire** full severance calculation.

**Rule:**
1. From the last 12 months, filter to **full months only** (`partial_fraction == 1.0`).
2. If no full months exist → fall back to all months in the last 12 months (full and partial alike).
3. Salary did NOT change across the filtered set → `salary_monthly` from the **last full month** in the filtered set.
4. Salary DID change across the filtered set → simple average of `salary_monthly` across the filtered set.

**"Last 12 months"** = 12 calendar months ending with last month of employment.
**"Full month"** = `partial_fraction == 1.0` (worker was employed for the entire calendar month). A month is partial if employment started or ended mid-month.
**"Salary changed"** = any difference in `salary_monthly` across PMRs in the filtered set.
**Multiple PMRs in same month** = each is a separate data point.

```
function determine_last_salary(period_month_records):
  all_pmrs = sorted by month descending
  last_month = all_pmrs[0].month
  twelve_months_ago = last_month - 11 months

  recent_pmrs = filter(pmr.month >= twelve_months_ago)

  full_pmrs = filter(pmr.partial_fraction == 1.0 for pmr in recent_pmrs)
  working_pmrs = full_pmrs if len(full_pmrs) > 0 else recent_pmrs

  salary_values = unique(pmr.salary_monthly for pmr in working_pmrs)
  last_full_pmr = working_pmrs sorted by month descending [0]

  if len(salary_values) == 1:
    return { last_salary: last_full_pmr.salary_monthly, method: "last_full_pmr", salary_changed: false }
  else:
    return { last_salary: avg(salary_values), method: "avg_12_months", salary_changed: true }
```

#### Base Component

Per calendar month of employment:

```
month_full_base = last_salary × severance_rate × month_job_scope
```

- `last_salary` = from above (one value)
- `severance_rate` = always 0.08333
- `month_job_scope` = `SSOT.month_aggregates[month].job_scope`
- No `partial_fraction` — job_scope already reflects partial months naturally (fewer hours worked = lower scope).

#### Cleaning OT Addition

Per calendar month (cleaning industry only):

```
month_full_ot = full_ot_monthly_pay × 0.06 × month_job_scope
```

- `full_ot_monthly_pay` = sum of `hours × rate_multiplier × hourly_wage` for all `pricing_breakdown` parts where `tier > 0`, across all shifts in this month. FULL pay (125%/150%/175%/200%), NOT differential.
- No `partial_fraction` — OT pay already reflects actual shifts.

#### Cleaning Recreation Addition

Per calendar month (cleaning industry only):

```
month_full_recreation = (annual_recreation_value / 12) × 0.08333 × month_job_scope
```

- `annual_recreation_value` = from recreation right module (future dependency).
- Until recreation module exists: `recreation_pending = true`, amount = 0.
- No `partial_fraction` — job_scope already reflects partial months.

#### Total Full Severance

```
full_severance = sum(month_full_base) + sum(month_full_ot) + sum(month_full_recreation)
```

---

### B. Required Contributions (הפרשות נדרשות)

#### Base Component

Per calendar month of employment:

```
month_required_base = salary_monthly × contribution_rate × month_job_scope
```

- `salary_monthly` = from `period_month_records[month].salary_monthly` — **actual** salary of that specific month (NOT last salary)
- `contribution_rate` = from industry config (6% or 8.333%)
- No `partial_fraction` — job_scope already reflects partial months naturally.

#### Cleaning OT Addition

**Same value** as in full severance:

```
month_required_ot = full_ot_monthly_pay × 0.06 × month_job_scope
```

#### Cleaning Recreation Addition

**Same value** as in full severance:

```
month_required_recreation = (annual_recreation_value / 12) × 0.08333 × month_job_scope
```

#### Total Required Contributions

```
required_contributions = sum(month_required_base) + sum(month_required_ot) + sum(month_required_recreation)
```

---

## Path Determination and Claim Calculation

### Input

```
actual_deposits = SSOT.input.deductions_input["severance"]  // user-entered total
```

### Logic

```
function determine_path_and_claim(termination_reason, full_severance, required_contributions, actual_deposits):

  if termination_reason == "resigned":
    // PATH C — Required contributions shortfall
    return {
      path: "contributions",
      section_14_status: null,
      claim_amount: required_contributions,  // gross (deductions module subtracts actual_deposits)
      limitation_type: "general"
    }

  // fired or resigned_as_fired
  if actual_deposits >= required_contributions:
    // PATH A — Section 14 holds
    return {
      path: "section_14_holds",
      section_14_status: "holds",
      claim_amount: full_severance - required_contributions,
      limitation_type: "none"
      // actual_deposits belong to worker separately — NOT deducted
    }
  else:
    // PATH B — Section 14 falls
    return {
      path: "section_14_falls",
      section_14_status: "falls",
      claim_amount: full_severance,  // gross (deductions module subtracts actual_deposits)
      limitation_type: "none"
    }
```

### Implications Per Path

**PATH A (Section 14 holds):**
- Claim = full_severance − required_contributions (the "top-up")
- General/agriculture: 2.333% gap → positive claim
- Construction/cleaning: 0% gap → claim = 0
- Fund money belongs to worker separately — NOT deducted from claim
- `deduction_override = 0`
- No limitation

**PATH B (Section 14 falls):**
- Claim = full_severance (full amount)
- Actual deposits deducted by deductions module (counted as "on account")
- `deduction_override = null` (normal deduction)
- No limitation

**PATH C (Resigned):**
- Claim = required_contributions (what should be in the fund)
- Actual deposits deducted by deductions module
- `deduction_override = null` (normal deduction)
- General limitation (7 years)

### Deductions Module Integration

The severance module communicates via `deduction_override`:

```
if path == "section_14_holds":
  deduction_override = 0      // deductions module must NOT subtract actual_deposits
else:
  deduction_override = null   // deductions module subtracts actual_deposits normally
```

---

## SSOT Data Structure

### rights_results.severance

```
SeveranceData {
  // ═══ Eligibility ═══
  eligible: boolean
  ineligible_reason: string?

  // ═══ Path & Status ═══
  termination_reason: "fired" | "resigned_as_fired" | "resigned"
  industry: string
  path: "section_14_holds" | "section_14_falls" | "contributions"
  section_14_status: "holds" | "falls" | null
  limitation_type: "none" | "general"

  // ═══ Rates ═══
  severance_rate: decimal               // 0.08333
  contribution_rate: decimal            // industry-dependent
  ot_addition_rate: decimal?            // 0.06 (cleaning only)
  recreation_addition_rate: decimal?    // 0.08333 (cleaning only)

  // ═══ Last Salary ═══
  last_salary_info: {
    last_salary: decimal
    method: "last_full_pmr" | "avg_12_months"
    salary_changed_in_last_year: boolean
    pmrs_used: List<{
      month: (integer, integer)
      salary_monthly: decimal
    }>
  }

  // ═══ Full Severance ═══
  full_severance: {
    base_total: decimal
    ot_total: decimal                   // 0 if not cleaning
    recreation_total: decimal           // 0 if not cleaning or pending
    recreation_pending: boolean
    grand_total: decimal

    base_monthly_detail: List<{
      month: (integer, integer)
      effective_period_id: string
      calendar_days_employed: integer   // display only — not used in calculation
      total_calendar_days: integer      // display only — not used in calculation
      partial_fraction: decimal         // display only — not used in calculation (job_scope absorbs this)
      job_scope: decimal
      salary_used: decimal              // last_salary (same every month)
      amount: decimal
    }>

    period_summaries: List<{
      effective_period_id: string
      start: date
      end: date
      months_count: integer             // count of calendar months in this period (including partial months)
      avg_job_scope: decimal
      subtotal: decimal
    }>
  }

  // ═══ Required Contributions ═══
  required_contributions: {
    base_total: decimal
    ot_total: decimal                   // same as full_severance.ot_total
    recreation_total: decimal           // same as full_severance.recreation_total
    grand_total: decimal

    base_monthly_detail: List<{
      month: (integer, integer)
      effective_period_id: string
      calendar_days_employed: integer   // display only — not used in calculation
      total_calendar_days: integer      // display only — not used in calculation
      partial_fraction: decimal         // display only — not used in calculation (job_scope absorbs this)
      job_scope: decimal
      salary_used: decimal              // actual salary_monthly of this month
      amount: decimal
    }>

    period_summaries: List<{
      effective_period_id: string
      start: date
      end: date
      months_count: integer             // count of calendar months in this period (including partial months)
      avg_job_scope: decimal
      avg_salary_monthly: decimal
      subtotal: decimal
    }>
  }

  // ═══ Cleaning Additions (shared) ═══
  ot_addition: {
    rate: decimal
    total: decimal
    monthly_detail: List<{
      month: (integer, integer)
      effective_period_id: string
      full_ot_monthly_pay: decimal
      job_scope: decimal
      amount: decimal
    }>
  }?

  recreation_addition: {
    rate: decimal
    total: decimal
    recreation_pending: boolean
    monthly_detail: List<{
      month: (integer, integer)
      annual_recreation_value: decimal
      monthly_value: decimal
      partial_fraction: decimal
      amount: decimal
    }>
  }?

  // ═══ Section 14 Comparison ═══
  section_14_comparison: {
    actual_deposits: decimal
    required_contributions_total: decimal
    difference: decimal                 // actual − required
    status: "holds" | "falls" | null
  }?

  // ═══ Final Claim ═══
  claim_before_deductions: decimal
  deduction_override: decimal?          // 0 for path A, null for B/C
  total_claim: decimal

  // ═══ Monthly Breakdown (for limitation module) ═══
  monthly_breakdown: List<{
    month: (integer, integer)
    claim_amount: decimal
  }>
}
```

---

## Pipeline Integration

### Position in Pipeline

Phase 2, parallel to other rights.

### Inputs from SSOT

```
Reads:
  SSOT.input.termination_reason
  SSOT.input.industry
  SSOT.input.deductions_input["severance"]
  SSOT.effective_periods
  SSOT.period_month_records
  SSOT.month_aggregates
  SSOT.total_employment
  SSOT.shifts[].pricing_breakdown        // cleaning OT
  SSOT.rights_results.recreation         // cleaning recreation (future)
  settings.severance_config
```

### Output

```
Writes:
  SSOT.rights_results.severance
```

### Limitation

- Paths A/B: `"none"`
- Path C: `"general"`
- `right_limitation_mapping.severance = "dynamic"`

---

## settings.json Addition

```json
{
  "severance_config": {
    "industries": {
      "general": {
        "name": "כללי",
        "severance_rate": 0.08333,
        "contribution_rate": 0.06,
        "ot_addition": false,
        "recreation_addition": false,
        "min_months": 12
      },
      "construction": {
        "name": "בניין",
        "severance_rate": 0.08333,
        "contribution_rate": 0.08333,
        "ot_addition": false,
        "recreation_addition": false,
        "min_months": 0
      },
      "cleaning": {
        "name": "נקיון",
        "severance_rate": 0.08333,
        "contribution_rate": 0.08333,
        "ot_addition": true,
        "ot_addition_rate": 0.06,
        "recreation_addition": true,
        "recreation_addition_rate": 0.08333,
        "min_months": 0
      },
      "agriculture": {
        "name": "חקלאות",
        "severance_rate": 0.08333,
        "contribution_rate": 0.06,
        "ot_addition": false,
        "recreation_addition": false,
        "min_months": 6
      }
    }
  }
}
```

Update `right_limitation_mapping`:
```json
"severance": "dynamic"
```

---

## Computation Pseudocode — Full Flow

```
function compute_severance(ssot, settings):

  industry = ssot.input.industry
  termination = ssot.input.termination_reason
  config = settings.severance_config.industries[industry]
  actual_deposits = ssot.input.deductions_input.get("severance", 0)

  // ═══ Eligibility ═══
  if ssot.total_employment.worked_duration.months_decimal < config.min_months:
    return SeveranceData(eligible=false, ineligible_reason="לא השלים את תקופת העבודה המינימלית")

  work_months = get_work_months(ssot)

  // ═══ Always compute both ═══

  // A. Full severance
  last_salary_info = determine_last_salary(ssot.period_month_records)
  last_salary = last_salary_info.last_salary

  full_base_monthly = []
  for wm in work_months:
    job_scope = ssot.month_aggregates[wm.month].job_scope
    amount = last_salary × config.severance_rate × job_scope
    full_base_monthly.append({ ..., salary_used: last_salary, amount })
  full_base_total = sum(amounts)

  // B. Required contributions
  req_base_monthly = []
  for wm in work_months:
    pmr = ssot.period_month_records[wm.ep_id, wm.month]
    job_scope = ssot.month_aggregates[wm.month].job_scope
    amount = pmr.salary_monthly × config.contribution_rate × job_scope
    req_base_monthly.append({ ..., salary_used: pmr.salary_monthly, amount })
  req_base_total = sum(amounts)

  // Cleaning additions (shared, same value in both)
  ot_total = 0
  ot_addition = null
  if config.ot_addition:
    ot_addition = compute_ot_addition(ssot, work_months, config.ot_addition_rate)
    ot_total = ot_addition.total

  recreation_total = 0
  recreation_addition = null
  if config.recreation_addition:
    recreation_addition = compute_recreation_addition(ssot, work_months, config.recreation_addition_rate)
    recreation_total = recreation_addition.total

  full_severance_total = full_base_total + ot_total + recreation_total
  required_contributions_total = req_base_total + ot_total + recreation_total

  // ═══ Path determination ═══
  if termination == "resigned":
    path = "contributions"
    section_14_status = null
    claim = required_contributions_total
    limitation_type = "general"
    deduction_override = null
    breakdown_source = req_base_monthly

  elif actual_deposits >= required_contributions_total:
    path = "section_14_holds"
    section_14_status = "holds"
    claim = full_severance_total - required_contributions_total
    limitation_type = "none"
    deduction_override = 0
    // breakdown = difference per month (for display; limitation irrelevant)
    breakdown_source = diff(full_base_monthly, req_base_monthly)

  else:
    path = "section_14_falls"
    section_14_status = "falls"
    claim = full_severance_total
    limitation_type = "none"
    deduction_override = null
    breakdown_source = full_base_monthly

  monthly_breakdown = build_monthly_breakdown(breakdown_source, ot_addition, recreation_addition)

  return SeveranceData(...)
```

### Helper: get_work_months

```
function get_work_months(ssot):
  result = []
  for ep in ssot.effective_periods:
    for month in each calendar month overlapping with ep:
      month_start = max(ep.start, first_day_of(month))
      month_end = min(ep.end, last_day_of(month))
      calendar_days = (month_end - month_start).days + 1
      total_days = days_in_month(month)
      result.append({
        month: month,
        ep_id: ep.id,
        calendar_days_employed: calendar_days,
        total_calendar_days: total_days,
        partial_fraction: calendar_days / total_days
      })
  return result
```

### Helper: compute_ot_addition

```
function compute_ot_addition(ssot, work_months, rate):
  monthly_detail = []
  for wm in work_months:
    job_scope = ssot.month_aggregates[wm.month].job_scope
    month_shifts = ssot.shifts.filter(s => s.date in wm)
    full_ot_pay = sum(
      part.hours × part.rate_multiplier × part.hourly_wage
      for shift in month_shifts
      for part in shift.pricing_breakdown
      if part.tier > 0
    )
    amount = full_ot_pay × rate × job_scope
    monthly_detail.append({ month: wm.month, full_ot_monthly_pay: full_ot_pay, job_scope, amount })
  return { rate, total: sum(amounts), monthly_detail }
```

---

## Edge Cases

1. **Employment shorter than minimum period.** Not eligible. Return early. Note: construction and cleaning have min_months=0, so this only applies to general (12) and agriculture (6).

2. **Salary changed in last year.** Simple average of salary_monthly across **full months** in last 12 months. Not weighted by days. Partial months (partial_fraction < 1.0) excluded from the average. If all months are partial → fall back to using all months.

3. **Multiple PMRs in same month.** Each is a separate data point for salary comparison and averaging.

4. **Gap in employment.** Gap months excluded. `get_work_months` only includes months with effective_period coverage.

5. **Partial first/last month.** Job scope naturally reflects partial months (fewer hours = lower scope). No separate `partial_fraction` multiplication needed.

6. **Job scope capped at 1.0.** From job_scope module.

7. **Construction/cleaning — Section 14 holds → claim ≈ 0.** Because `severance_rate ≈ contribution_rate`. Tiny rounding differences possible.

8. **General/agriculture — Section 14 holds → claim ≈ 2.333%.** The gap between 8.333% and 6%.

9. **Resigned_as_fired.** Identical to fired — Path A or B.

10. **Section 14 comparison includes cleaning additions.** OT/recreation are part of required contributions.

11. **Actual deposits > required contributions.** Section 14 holds. Overpayment stays in fund.

12. **Resigned with zero deposits.** claim = full required_contributions. General limitation.

13. **Recreation module not yet built.** `recreation_pending = true`, amounts = 0. Severance recalculates when module is built.

14. **Path A deduction override.** Deductions module MUST respect `deduction_override = 0` and NOT subtract deposits.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** hardcode any rate. Everything from industry config.
2. **DO NOT** use `claim_multiplier` for cleaning OT. Use `rate_multiplier` — FULL OT pay.
3. **DO NOT** deduct actual deposits in Path A. Fund belongs to worker separately.
4. **DO NOT** apply limitation to Paths A/B (fired/resigned_as_fired).
5. **DO NOT** use last_salary in required contributions calc. Each month uses its own salary_monthly.
6. **DO NOT** include partial months (partial_fraction < 1.0) in the last salary average, unless all months in the last 12 are partial (fallback).
7. **DO NOT** use the last PMR unconditionally as the "no change" result — use the last **full** PMR (or last overall if fallback).
6. **DO NOT** apply partial_fraction to OT addition. OT already reflects actual shifts.
7. **DO NOT** skip Section 14 comparison. It determines the path.
8. **DO NOT** treat Section 14 as user input. It is computed automatically.
9. **DO NOT** forget cleaning additions are identical in both full_severance and required_contributions.
10. **DO NOT** compute severance without termination_reason. Required input.

---

## Test Fixtures

### Fixture 1: General, fired, Section 14 holds

```
Input:
  termination_reason: "fired"
  industry: "general"
  employment: 2022-01-01 to 2023-12-31 (24 months)
  salary_monthly: 10,000 (constant)
  job_scope: 1.0
  actual_deposits: 15,000

Expected:
  full_severance = 10,000 × 0.08333 × 24 = 19,999.20
  required_contributions = 10,000 × 0.06 × 24 = 14,400.00
  actual (15,000) >= required (14,400) → PATH A (s14 holds)
  claim = 19,999.20 − 14,400.00 = 5,599.20
  deduction = 0 (fund → worker)
  limitation: none
```

### Fixture 2: General, fired, Section 14 falls

```
Input:
  termination_reason: "fired"
  industry: "general"
  employment: 2022-01-01 to 2023-12-31 (24 months)
  salary_monthly: 10,000 (constant)
  job_scope: 1.0
  actual_deposits: 8,000

Expected:
  full_severance = 19,999.20
  required_contributions = 14,400.00
  actual (8,000) < required (14,400) → PATH B (s14 falls)
  claim = 19,999.20
  deduction = 8,000
  net = 11,999.20
  limitation: none
```

### Fixture 3: General, resigned

```
Input:
  termination_reason: "resigned"
  industry: "general"
  employment: 2022-01-01 to 2023-12-31 (24 months)
  salary_monthly: 10,000 (constant)
  job_scope: 1.0
  actual_deposits: 8,000

Expected:
  required_contributions = 10,000 × 0.06 × 24 = 14,400.00
  claim = 14,400.00
  deduction = 8,000
  net = 6,400.00
  limitation: general
```

### Fixture 4: Construction, fired, Section 14 holds

```
Input:
  termination_reason: "fired"
  industry: "construction"
  employment: 2022-01-01 to 2023-12-31 (24 months)
  salary_monthly: 10,000
  job_scope: 1.0
  actual_deposits: 20,000

Expected:
  full_severance = 10,000 × 0.08333 × 24 = 19,999.20
  required_contributions = 10,000 × 0.08333 × 24 = 19,999.20
  actual (20,000) >= required (19,999.20) → PATH A (s14 holds)
  claim = 19,999.20 − 19,999.20 = 0
  No claim — fund covers everything
```

### Fixture 5: Cleaning, fired, with OT, Section 14 falls

```
Input:
  termination_reason: "fired"
  industry: "cleaning"
  employment: 2023-01-01 to 2023-12-31 (12 months)
  salary_monthly: 6,000
  job_scope: 1.0
  OT per month: full_ot_monthly_pay = 1,137.50
  actual_deposits: 5,000

Expected:
  full_base = 6,000 × 0.08333 × 12 = 5,999.76
  ot_addition = 1,137.50 × 0.06 × 12 = 819.00
  recreation = 0 (pending)
  full_severance = 6,818.76

  req_base = 6,000 × 0.08333 × 12 = 5,999.76
  required_contributions = 5,999.76 + 819.00 = 6,818.76

  actual (5,000) < required (6,818.76) → PATH B (s14 falls)
  claim = 6,818.76
  deduction = 5,000
  net = 1,818.76
```

### Fixture 6: Salary changed in last year

```
Input:
  termination_reason: "fired"
  industry: "general"
  employment: 2022-01-01 to 2024-06-30 (30 months)
  salary: 8,000 (months 1–18), 10,000 (months 19–30)
  job_scope: 1.0
  actual_deposits: 20,000

Expected:
  last 12 months: 2023-07 to 2024-06
  salary_monthly: 8,000 × 6 + 10,000 × 6
  last_salary = avg = 9,000
  full_severance = 9,000 × 0.08333 × 30 = 22,499.10
  required = (8,000 × 0.06 × 18) + (10,000 × 0.06 × 12) = 8,640 + 7,200 = 15,840
  actual (20,000) >= required (15,840) → PATH A
  claim = 22,499.10 − 15,840 = 6,659.10
```

### Fixture 7: Ineligible

```
Input:
  termination_reason: "fired"
  industry: "general"
  employment: 2024-01-01 to 2024-10-31 (10 months)

Expected:
  eligible: false
  ineligible_reason: "לא השלים את תקופת העבודה המינימלית"
```

### Fixture 9: Partial month excluded from last salary average

```
Input:
  termination_reason: "fired"
  industry: "general"
  employment: 2023-01-15 to 2024-06-30
  salary: 8,000 (Jan 2023–Jun 2023), 10,000 (Jul 2023–Jun 2024)
  job_scope: 1.0
  actual_deposits: 20,000

Last 12 months: 2023-07 to 2024-06
  2024-06: partial (ends 30 Jun = last day, but starts 01 Jun → full)
  2023-07: full, salary 10,000
  ... all months 2023-07 to 2024-05: full, salary 10,000
  2024-06: full, salary 10,000
  → all full months have salary 10,000 → no change
  last_salary = 10,000, method: "last_full_pmr"

Note: 2023-01 is partial (starts 15 Jan) but is outside the last-12-months window anyway.
```

### Fixture 10: Partial first month excluded from last salary average

```
Input:
  termination_reason: "fired"
  industry: "general"
  employment: 2023-06-15 to 2024-06-14
  salary: 8,000 throughout
  job_scope: 1.0
  actual_deposits: 5,000

Last 12 months: 2023-06 to 2024-06
  2023-06: partial (starts 15 Jun) → excluded
  2024-06: partial (ends 14 Jun) → excluded
  2023-07 to 2024-05: 11 full months, salary 8,000

  full_pmrs exist → use them
  salary_values = {8,000} → no change
  last_salary = 8,000 from last full month (2024-05)

Expected:
  last_salary = 8,000, method: "last_full_pmr"
```

### Fixture 11: All months partial — fallback to all

```
Input:
  termination_reason: "fired"
  industry: "construction"
  employment: 2024-01-15 to 2024-02-14
  salary: 10,000
  job_scope: 1.0
  actual_deposits: 1,500

Last 12 months: 2024-01 to 2024-02
  2024-01: partial (starts 15 Jan)
  2024-02: partial (ends 14 Feb)

  full_pmrs = [] → fallback to recent_pmrs (all)
  salary_values = {10,000} → no change
  last_salary = 10,000 from all_pmrs[0] (2024-02, partial), method: "last_full_pmr"
```

```
Input:
  termination_reason: "fired"
  industry: "construction"
  employment: 2024-01-01 to 2024-03-31 (3 months)
  salary_monthly: 10,000
  job_scope: 1.0
  actual_deposits: 2,500

Expected:
  eligible: true (min_months = 0)
  full_severance = 10,000 × 0.08333 × 3 = 2,499.90
  required_contributions = 10,000 × 0.08333 × 3 = 2,499.90
  actual (2,500) >= required (2,499.90) → PATH A
  claim = 0
```
