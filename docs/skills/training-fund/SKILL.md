---
name: training-fund
description: |
  Israeli labor law training fund (קרן השתלמות) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on training fund calculation, industry-specific contribution
  rates, seniority-based tiers (construction), or custom contract overrides.
  ALWAYS read this skill before touching any training-fund-related code.
---

# קרן השתלמות — Israeli Labor Law

## CRITICAL WARNINGS

1. **The right is contractual, not statutory.** No collective agreement or extension order = no right. Do not compute for industries not listed here.
2. **Only the employer portion is claimed.** The employee portion was deducted from wages in real time — it is not part of the claim.
3. **Construction tiers depend on industry seniority.** Use `SSOT.seniority.industry_seniority_years` from the seniority module.
4. **Agriculture (regular workers) — excluded.** Regular agricultural workers have no personal training fund right under the extension order. Do not compute.
5. **Salary base varies by industry.** Do not hardcode. See salary base rules below.
6. **Custom contract overrides industry defaults.** If the user provides custom tiers, they take precedence over industry config.
7. **Cleaning includes recreation pay in the base.** Until recreation module exists, flag as pending and compute on salary_monthly only.

---

## Covered Industries

| Industry | Right Source | Notes |
|----------|-------------|-------|
| `construction` | Extension order — בניין | Tiers by industry seniority |
| `cleaning` | Extension order — ניקיון | Includes recreation in base |
| `general` | Personal contract | User-defined rates |
| `agriculture` | **Not eligible** | Regular workers — no personal right |

---

## New SSOT Input Fields

Add to `SSOT.input`:

```
training_fund_tiers: List<{
  seniority_type: "industry" | "employer"   // ותק ענפי או ותק אצל מעסיק
  from_months: integer                       // גבול תחתון כולל בחודשים
  to_months: integer | null                  // גבול עליון לא-כולל. null = ללא הגבלה
  employer_rate: decimal
}>?
```

This field is **optional**. If provided, it overrides the industry default rates when the worker's seniority falls within the specified range. If not provided, the system uses industry defaults from `settings.training_fund_config`.

**Seniority types:**
- `"industry"` — uses total industry seniority (`SSOT.seniority.total_industry_years_cumulative`)
- `"employer"` — uses seniority at the specific employer (`SSOT.seniority.at_defendant_years_cumulative`)

**Open-ended tiers:** Set `to_months: null` to create a tier that applies from `from_months` onwards indefinitely.

**UI label:** "מדרגות קרן השתלמות לפי חוזה אישי"

The `deductions_input["training_fund"]` field already exists — this is the actual total employer deposits made. Used for computing the claim shortfall.

---

## Salary Base Rules

The salary base for computing required contributions varies by industry:

### Construction
```
salary_base = salary_monthly from PMR
```
The user is responsible for entering the correct salary base in the PMR. Per case law, the base is the higher of: (a) the tariff wage specified in the extension order, or (b) the actual agreed wage. Since the system does not track the tariff wage separately, the user must enter the correct (higher) value as `salary_monthly`.

### Cleaning
```
salary_base = salary_computed + monthly_recreation_value
```
- `salary_computed` = "השכר המחושב לפי סעיף 2 לצו ההרחבה" — this is the actual computed monthly wage per the extension order, not any higher wage in practice. In the system this corresponds to `salary_monthly` from the PMR, since the user enters the relevant wage base.
- `monthly_recreation_value` = from recreation module (future dependency)
- Until recreation module exists: `recreation_pending = true`, base = `salary_monthly` only
- **Note:** unlike construction, there is no "higher of tariff vs actual" rule in cleaning. The base is the computed wage per the order only.

### General
```
salary_base = salary_monthly from PMR
```

---

## Industry Configuration

```
TRAINING_FUND_INDUSTRY_CONFIG = {
  "construction": {
    "name": "בניין",
    "tiers_by_seniority": [
      {
        "role": "foreman",             // מנהל עבודה (certified)
        "min_seniority_years": 0,
        "employer_rate": 0.075,
        "employee_rate": 0.025
      },
      {
        "role": "worker",
        "min_seniority_years": 0,
        "max_seniority_years": 3,
        "employer_rate": 0.0,          // not eligible
        "employee_rate": 0.0
      },
      {
        "role": "worker",
        "min_seniority_years": 3,
        "max_seniority_years": 6,
        "employer_rate": 0.025,
        "employee_rate": 0.01
      },
      {
        "role": "worker",
        "min_seniority_years": 6,
        "employer_rate": 0.05,
        "employee_rate": 0.025
      }
    ]
  },
  "cleaning": {
    "name": "ניקיון",
    "employer_rate": 0.075,
    "employee_rate": 0.025,
    "min_months": 0
  },
  "general": {
    "name": "כללי",
    "employer_rate": null,             // must come from custom tiers
    "employee_rate": null,
    "min_months": 0
  }
}
```

Store in `settings.json` under `training_fund_config.industries`.

**Note on construction foreman:** The system does not track foreman status separately. If the worker is a certified foreman, the user must select this via a dedicated input field (`is_construction_foreman: boolean`). Add to `SSOT.input`.

---

## Determining Applicable Rate Per Month

For each calendar month of employment:

### Construction (non-foreman)
```
function get_construction_rate(month, ssot):
  seniority_years = ssot.seniority.industry_seniority_at(month)

  if seniority_years < 3:
    return { employer_rate: 0.0, employee_rate: 0.0, eligible: false }
  elif seniority_years < 6:
    return { employer_rate: 0.025, employee_rate: 0.01, eligible: true }
  else:
    return { employer_rate: 0.05, employee_rate: 0.025, eligible: true }
```

### Construction (foreman)
```
employer_rate: 0.075, employee_rate: 0.025, eligible: true (from day 1)
```

### Custom tiers override
```
function get_rate_for_month(month, seniority_years, custom_tiers, industry_defaults):
  // Check if a custom tier covers this seniority level
  seniority_months = seniority_years * 12
  for tier in custom_tiers:
    if tier.seniority_type matches the seniority being checked:
      if seniority_months >= tier.from_months:
        if tier.to_months is null or seniority_months < tier.to_months:
          return { employer_rate: tier.employer_rate, eligible: true }

  // Fall back to industry defaults
  return industry_defaults.get_rate(month)
```

### Split months

A **split month** occurs when a rate transition falls mid-month. Two cases:

1. **Seniority threshold crossing (construction)** — the day the worker crosses 3 or 6 years of industry seniority falls inside a calendar month.
2. **Custom tier seniority boundary** — a `training_fund_tier.from_months` or `to_months` threshold is crossed mid-month based on the worker's seniority progression.

In both cases, compute the month proportionally:

```
days_total = number of days in calendar month

// Segment A: days before the transition
days_A = transition_day - first_day_of_month   // exclusive
rate_A = rate applicable before transition

// Segment B: days from the transition onward
days_B = days_total - days_A
rate_B = rate applicable from transition

month_required = salary_base × job_scope ×
  ( (days_A / days_total) × employer_rate_A
  + (days_B / days_total) × employer_rate_B )
```

Store both segments in `monthly_detail[month].segments` (see SSOT structure below).

**More than two transitions in one month** — rare in practice, but apply the same logic iteratively: split into N segments, each weighted by its days.

---

## Computation

### Required Employer Contributions

Per calendar month:
```
month_required = salary_base × employer_rate × job_scope
```

- `salary_base` = per industry rules above
- `employer_rate` = from applicable tier for that month
- `job_scope` = `SSOT.month_aggregates[month].job_scope`
- If `eligible == false` for this month → `month_required = 0`

Total:
```
required_total = sum(month_required for all work months)
```

### Claim

```
claim_before_deductions = required_total
```

The actual deposits (`deductions_input["training_fund"]`) are **not** subtracted here. They are passed to the standard post-processing deductions module (פאזה 3, שלב ②), which handles them uniformly alongside all other rights. The training fund module returns `required_total` as the pre-deduction claim.

### Limitation
General limitation: 7 years.
`right_limitation_mapping.training_fund = "general"`

---

## SSOT Data Structure

### rights_results.training_fund

```
TrainingFundData {
  // ═══ Eligibility ═══
  eligible: boolean
  ineligible_reason: string?             // "ענף חקלאות — אין זכות אישית", etc.

  // ═══ Configuration ═══
  industry: string
  is_construction_foreman: boolean       // construction only
  used_custom_tiers: boolean             // true if custom tiers overrode defaults

  // ═══ Cleaning Recreation ═══
  recreation_pending: boolean            // true until recreation module built

  // ═══ Monthly Detail ═══
  monthly_detail: List<{
    month: (integer, integer)
    effective_period_id: string
    salary_base: decimal                 // salary_monthly [+ recreation if cleaning]
    recreation_component: decimal        // 0 if not cleaning or pending
    job_scope: decimal
    eligible_this_month: boolean         // false if construction < 3yr seniority (all segments)
    seniority_years: decimal?            // construction only — at start of month
    tier_source: "industry" | "custom"
    month_required: decimal              // total for month (sum of segments)
    is_split_month: boolean              // true if rate transition mid-month
    segments: List<{                     // always 1 entry; 2+ if split month
      days: integer
      days_total: integer
      employer_rate: decimal
      eligible: boolean
      tier_source: "industry" | "custom"
      segment_required: decimal          // salary_base × hours_weight × (days/days_total) × employer_rate
    }>
  }>

  // ═══ Totals ═══
  required_total: decimal
  actual_deposits: decimal               // from deductions_input["training_fund"] — display only
  claim_before_deductions: decimal       // = required_total (deduction handled in post-processing)

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
  SSOT.input.industry
  SSOT.input.is_construction_foreman
  SSOT.input.training_fund_tiers          // optional custom tiers
  SSOT.input.deductions_input["training_fund"]
  SSOT.effective_periods
  SSOT.period_month_records
  SSOT.month_aggregates
  SSOT.seniority                          // construction — seniority per month
  SSOT.rights_results.recreation          // cleaning — recreation base (future)
  settings.training_fund_config
```

### Output

```
Writes:
  SSOT.rights_results.training_fund
```

---

## settings.json Addition

```json
{
  "training_fund_config": {
    "industries": {
      "construction": {
        "name": "בניין",
        "tiers_by_seniority": [
          { "role": "foreman", "min_seniority_years": 0,
            "employer_rate": 0.075, "employee_rate": 0.025 },
          { "role": "worker", "min_seniority_years": 0,
            "max_seniority_years": 3,
            "employer_rate": 0.0, "employee_rate": 0.0 },
          { "role": "worker", "min_seniority_years": 3,
            "max_seniority_years": 6,
            "employer_rate": 0.025, "employee_rate": 0.01 },
          { "role": "worker", "min_seniority_years": 6,
            "employer_rate": 0.05, "employee_rate": 0.025 }
        ]
      },
      "cleaning": {
        "name": "ניקיון",
        "employer_rate": 0.075,
        "employee_rate": 0.025,
        "min_months": 0
      },
      "general": {
        "name": "כללי",
        "employer_rate": null,
        "employee_rate": null,
        "min_months": 0
      }
    }
  }
}
```

Update `right_limitation_mapping`:
```json
"training_fund": "general"
```

---

## Edge Cases

1. **Agriculture — regular workers.** Return `eligible: false`, `ineligible_reason: "ענף חקלאות — אין זכות אישית לעובד רגיל"`. No calculation.

2. **Construction worker, seniority < 3 years.** Not eligible for that month. `month_required = 0`. Once 3-year threshold is crossed, entitlement begins from that month forward (not retroactive).

3. **Construction worker crossing 3-year or 6-year threshold mid-employment.** Rate changes from the month the threshold is crossed. The crossing month is a **split month** — compute proportionally (see Split months above). Prior months retain the lower rate.

4. **Custom tiers partially covering the employment period.** Months not covered by custom tiers fall back to industry defaults. If the tier boundary falls mid-month, that month is a **split month**.

5. **Custom tiers with 0 rates.** Valid — means no entitlement for that period (e.g. during trial period per personal contract).

6. **Actual deposits exceed required.** Post-processing deductions module handles this — it will result in net = 0. No negative claim.

7. **Cleaning — recreation pending.** Compute on `salary_monthly` only. Flag `recreation_pending = true`. Module recalculates when recreation module is built.

8. **General industry — no custom tiers provided.** `eligible: false`, `ineligible_reason: "לא הוזנו מדרגות קרן השתלמות"`.

9. **Job scope < 1.0.** Applied to `month_required`. Job scope already reflects partial months naturally (same logic as severance).

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** claim the employee portion. Only employer contributions are claimed.
2. **DO NOT** compute for agriculture regular workers. No personal right.
3. **DO NOT** hardcode rates. Everything from industry config or custom tiers.
4. **DO NOT** apply general limitation to construction/cleaning paths — limitation module handles this via `monthly_breakdown`. Just mark `"general"` in the mapping.
5. **DO NOT** use `partial_fraction` in the monthly calculation. Job scope absorbs partial months.
6. **DO NOT** assume foreman status. Require explicit `is_construction_foreman` input.
7. **DO NOT** make construction entitlement retroactive when crossing 3/6 year threshold. Forward only.
8. **DO NOT** compute general industry without custom tiers. It is not a default.
9. **DO NOT** apply a single rate to an entire month when a threshold or tier boundary crosses mid-month. Use proportional day-based calculation (split month logic).
10. **DO NOT** use date-based tier matching. Tiers are always seniority-based (`from_months`, `to_months`).

---

## Test Fixtures

### Fixture 1: Construction worker, 3–6 year seniority tier

```
Input:
  industry: "construction"
  is_construction_foreman: false
  employment: 2020-01-01 to 2023-06-30
  industry_seniority at start: 2.5 years (crosses 3yr threshold in Jul 2020)
  salary_monthly: 10,000
  job_scope: 1.0
  actual_deposits: 0

Expected:
  Months Jan–Jun 2020: seniority < 3yr → eligible_this_month = false, amount = 0
  Months Jul 2020–Jun 2023: seniority >= 3yr, < 6yr → employer_rate = 2.5%
  Eligible months: 36
  required_total = 10,000 × 0.025 × 36 = 9,000
  claim_before_deductions = 9,000
```

### Fixture 2: Construction foreman

```
Input:
  industry: "construction"
  is_construction_foreman: true
  employment: 2022-01-01 to 2023-12-31 (24 months)
  salary_monthly: 12,000
  job_scope: 1.0
  actual_deposits: 10,000

Expected:
  employer_rate = 7.5% (from day 1)
  required_total = 12,000 × 0.075 × 24 = 21,600
  claim_before_deductions = 21,600
  // actual_deposits = 10,000 → handled by deductions module → net = 11,600
```

### Fixture 3: Cleaning

```
Input:
  industry: "cleaning"
  employment: 2022-01-01 to 2023-12-31 (24 months)
  salary_monthly: 6,000
  job_scope: 1.0
  actual_deposits: 5,000
  recreation_pending: true

Expected:
  salary_base = 6,000 (recreation pending)
  required_total = 6,000 × 0.075 × 24 = 10,800
  claim_before_deductions = 10,800
  // actual_deposits = 5,000 → handled by deductions module → net = 5,800
  recreation_pending = true (note: amount will increase when recreation module built)
```

### Fixture 4: Custom tiers override

```
Input:
  industry: "construction"
  is_construction_foreman: false
  employment: 2021-01-01 to 2023-12-31 (36 months)
  salary_monthly: 10,000
  job_scope: 1.0
  actual_deposits: 0
  training_fund_tiers: [
    { seniority_type: "industry", from_months: 0, to_months: null,
      employer_rate: 0.075 }
  ]

Expected:
  Custom tier applies from day 1 (from_months=0) with no upper limit (to_months=null)
  → employer_rate = 7.5% for all months
  required_total = 10,000 × 0.075 × 36 = 27,000
  claim_before_deductions = 27,000
```

### Fixture 5: Agriculture — ineligible

```
Input:
  industry: "agriculture"

Expected:
  eligible: false
  ineligible_reason: "ענף חקלאות — אין זכות אישית לעובד רגיל"
  No calculation.
```

### Fixture 6: General without custom tiers — ineligible

```
Input:
  industry: "general"
  training_fund_tiers: null

Expected:
  eligible: false
  ineligible_reason: "לא הוזנו מדרגות קרן השתלמות"
```

### Fixture 7: Construction worker — split month at 3-year threshold

```
Input:
  industry: "construction"
  is_construction_foreman: false
  employment: 2020-03-15 to 2023-06-30
  industry_seniority at 2020-03-15: 2 years 11 months
  → 3-year threshold reached on: 2020-04-15
  salary_monthly: 10,000
  job_scope: 1.0
  actual_deposits: 0

Explanation:
  April 2020 is a split month (30 days):
    Segment A: 2020-04-01 to 2020-04-14 → 14 days → rate = 0% (seniority < 3yr)
    Segment B: 2020-04-15 to 2020-04-30 → 16 days → rate = 2.5%

  April 2020 month_required:
    = 10,000 × 1.0 × ((14/30) × 0.0 + (16/30) × 0.025)
    = 10,000 × (0 + 0.01333...)
    = 133.33

  All months before April 2020 (Mar 2020): eligible_this_month = false, amount = 0
  All months May 2020 onward: employer_rate = 2.5%, amount = 10,000 × 0.025 = 250/month

Expected for April 2020:
  is_split_month: true
  segments:
    { days: 14, days_total: 30, employer_rate: 0.0, eligible: false, segment_required: 0 }
    { days: 16, days_total: 30, employer_rate: 0.025, eligible: true, segment_required: 133.33 }
  month_required: 133.33
```

### Fixture 8: Custom tier — split month at seniority threshold

```
Input:
  industry: "general"
  employment: 2022-01-01 to 2022-12-31 (12 months)
  salary_monthly: 8,000
  job_scope: 1.0
  actual_deposits: 0
  prior_industry_seniority: 2.5 months
  training_fund_tiers: [
    { seniority_type: "industry", from_months: 3, to_months: null,
      employer_rate: 0.075 }
  ]

Explanation:
  Seniority progression: Jan starts at 2.5 months, ends at 3.5 months
  January 2022: seniority crosses 3-month threshold mid-month → split month (31 days):
    Segment A: before threshold → rate = 0% (seniority < 3 months, no tier matches)
    Segment B: after threshold → rate = 7.5%
    month_required = partial amount based on days after threshold
  Feb–Dec 2022: full tier coverage, 11 months × 8,000 × 0.075 = 6,600

Expected:
  January 2022 is_split_month: true
  January 2022 month_required: partial amount (< 600)
  required_total: partial + 6,600
  claim_before_deductions: same as required_total
```
