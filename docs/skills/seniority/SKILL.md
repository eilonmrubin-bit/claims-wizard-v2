---
name: seniority
description: |
  Israeli labor law industry seniority (ותק ענפי) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on seniority calculation, seniority-dependent rights,
  or מת"ש (employment registry) PDF extraction.
  ALWAYS read this skill before touching any seniority-related code.
---

# ותק ענפי — Israeli Labor Law

## CRITICAL WARNINGS

1. **Seniority is counted in ACTUAL WORK MONTHS, not calendar duration.** A month the worker worked in = 1. A month the worker did not work in = 0. Binary per month, no fractions at the month level.
2. **Seniority is INDUSTRY seniority (ותק ענפי), not employer seniority.** It accumulates across all employers in the same industry.
3. **Express seniority as years with a decimal fraction.** 5 years and 6 months = 5.5. The fraction represents months (each month = 1/12 of a year).
4. **Never invent seniority rules for specific rights.** Each right defines how it uses seniority. This module only COMPUTES seniority — it does not decide what to do with it.
5. **SSOT must store both total industry seniority AND seniority at the defendant.** Both values are needed by different rights and display components.

---

## Conceptual Model

Seniority is an **input-processing module** — computed once from input data, stored in the SSOT, and consumed by rights on demand.

```
┌──────────────────────────────────┐
│  Input Sources                   │
│  (one of three methods)          │
│                                  │
│  א: Prior seniority + work      │
│     pattern calculation          │
│  ב: Manual total entry           │
│  ג: מת"ש PDF extraction          │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Seniority Module                │
│                                  │
│  Computes:                       │
│  - Total industry seniority      │
│  - Seniority at defendant        │
│  Stores both in SSOT             │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  SSOT (Single Source of Truth)   │
│                                  │
│  seniority: {                    │
│    total_industry_months: int    │
│    at_defendant_months: int      │
│    total_industry_years: decimal │
│    at_defendant_years: decimal   │
│  }                               │
└──────────────┬───────────────────┘
               │ queried by rights as needed
               ▼
         Rights Calculations
```

### How Rights Use Seniority

Each right that depends on seniority calls the SSOT to get the relevant value. The seniority module exposes:

```
getSeniority(as_of_date?: date) → {
  total_industry_months: int
  total_industry_years: decimal    // months / 12
  at_defendant_months: int
  at_defendant_years: decimal      // months / 12
}
```

If `as_of_date` is provided, the function finds the matching entry in the `monthly` series (the last month ≤ as_of_date) and returns its cumulative values. If omitted, returns the final totals (last entry in series).

---

## Input Methods

### Method א: Prior Seniority + Work Pattern Calculation

The user provides:
1. **Prior industry seniority** (ותק ענפי לפני תחילת העבודה אצל הנתבע): integer, in months
2. The system calculates seniority at the defendant from the **work pattern data**

**Calculation from work pattern:**
- The work pattern system provides, for any given day, whether the worker worked that day
- For each calendar month in the employment period: if the worker worked at least 1 day in that month → count as 1 month of seniority
- Sum all counted months → seniority at defendant (in months)
- Total industry seniority = prior seniority + seniority at defendant

**SSOT output:**
```
{
  total_industry_months: prior + counted_at_defendant,
  at_defendant_months: counted_at_defendant,
  total_industry_years: total_industry_months / 12,
  at_defendant_years: at_defendant_months / 12
}
```

### Method ב: Manual Total Entry

The user directly enters:
1. **Total industry seniority** (ותק ענפי כולל): in months or years+months
2. **Seniority at defendant** (ותק אצל הנתבע): in months or years+months

No calculation needed — values go directly to SSOT.

### Method ג: מת"ש PDF Extraction

The user uploads a מת"ש (מרשם תעסוקתי) PDF from ביטוח לאומי. The system extracts seniority data.

**Extraction pipeline:**

```
┌─────────────────┐
│  מת"ש PDF       │
└────────┬────────┘
         │ parse/OCR
         ▼
┌─────────────────────────────────────┐
│  1. Extract employment records      │
│     (employer, dates, industry)     │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  2. Filter by industry              │
│     Keep only records matching      │
│     the user-specified industry     │
│     (user input from claim setup)   │
└────────┬────────────────────────────┘
         │ filtered records
         ▼
┌─────────────────────────────────────┐
│  3. Count work months               │
│     Per record: each calendar month │
│     with any work → 1 month         │
│     Deduplicate overlapping months  │
│     across employers                │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  4. Separate defendant vs. total    │
│     - Identify defendant's records  │
│     - at_defendant = months from    │
│       defendant's records only      │
│     - total_industry = months from  │
│       ALL filtered records          │
└─────────────────────────────────────┘
```

**Step 1 — Parse employment records:**
- Extract from the מת"ש: employer name, employment start date, employment end date, industry classification
- The מת"ש may contain multiple employers across different industries and time periods

**Step 2 — Filter by industry:**
- The user specifies the relevant industry (ענף) as part of the claim setup input
- Keep only employment records whose industry matches
- Discard records from other industries
- Present filtered results to user for confirmation (the user may need to manually include/exclude borderline records)

**Step 3 — Count work months:**
- For each filtered record: generate the set of calendar months (year+month) the worker was employed
- Union all month-sets across all filtered records (deduplication — if two employers overlap in the same month, count it once)
- Total industry months = size of the union set

**Step 4 — Separate defendant vs. total:**
- Identify which records belong to the defendant (by employer name matching or user confirmation)
- at_defendant_months = count of months from defendant's records only
- total_industry_months = count from all filtered records
- Both values go to SSOT

**User confirmation points:**
- After step 2: "These records were identified as [industry]. Please confirm or adjust."
- After step 4: "These records were identified as belonging to [defendant]. Please confirm."

---

## SSOT Data Structure

```
SeniorityData {
  input_method: "prior_plus_pattern" | "manual" | "matash_pdf"
  
  // Final totals (derived from last entry in monthly series)
  total_industry_months: integer      // total months worked in the industry
  total_industry_years: decimal       // total_industry_months / 12
  
  at_defendant_months: integer        // months worked at the defendant specifically
  at_defendant_years: decimal         // at_defendant_months / 12
  
  prior_seniority_months: integer     // only for method א: months before defendant
  
  // Cumulative monthly series — one entry per calendar month in defendant's employment range
  monthly: List<{
    month: (year, month)
    worked: boolean                           // did the worker work at least 1 day this month?
    at_defendant_cumulative: integer          // cumulative work months at defendant up to this month
    at_defendant_years_cumulative: decimal    // at_defendant_cumulative / 12
    total_industry_cumulative: integer        // prior + at_defendant_cumulative
    total_industry_years_cumulative: decimal  // total_industry_cumulative / 12
  }>
  
  // For display and audit trail (method ג):
  matash_records?: List<{
    employer_name: string
    start_date: date
    end_date: date
    industry: string
    is_defendant: boolean
    is_relevant_industry: boolean
    months_counted: integer
  }>
}
```

---

## Month Counting Logic

```
function countWorkMonths(periods: List<{start_date, end_date}>): integer {
  month_set = Set<(year, month)>()
  
  for period in periods:
    cursor = first_day_of_month(period.start_date)
    end = last_day_of_month(period.end_date)
    
    while cursor <= end:
      month_set.add((cursor.year, cursor.month))
      cursor = first_day_of_next_month(cursor)
  
  return month_set.size
}
```

For method א (work pattern based):
```
function countWorkMonthsFromPattern(employment_start, employment_end, workPattern): integer {
  month_set = Set<(year, month)>()
  
  for each calendar_month in range(employment_start, employment_end):
    for each day in calendar_month:
      if workPattern.didWork(day):
        month_set.add((day.year, day.month))
        break  // one work day is enough, move to next month
  
  return month_set.size
}
```

### Cumulative Monthly Series Generation

After counting work months, generate the cumulative series for the SSOT:

```
function generateMonthlySeries(employment_start, employment_end, work_month_set, prior_months):
  series = []
  defendant_cumulative = 0
  
  for each calendar_month in range(employment_start, employment_end):
    worked = (calendar_month.year, calendar_month.month) in work_month_set
    
    if worked:
      defendant_cumulative += 1
    
    industry_cumulative = prior_months + defendant_cumulative
    
    series.append({
      month: (calendar_month.year, calendar_month.month),
      worked: worked,
      at_defendant_cumulative: defendant_cumulative,
      at_defendant_years_cumulative: defendant_cumulative / 12,
      total_industry_cumulative: industry_cumulative,
      total_industry_years_cumulative: industry_cumulative / 12,
    })
  
  return series
```

**Notes:**
- The series includes EVERY calendar month in the employment range, including months the worker didn't work (gaps). These have `worked: false` and the cumulative values stay flat.
- For method ב (manual entry): the series still covers every month, but `worked` is derived from the work pattern (if available) or defaults to true for all months.
- For method ג (מת"ש): `prior_months` is derived from the total industry count minus the defendant count, and the series covers only the defendant employment range.

---

## Display

Seniority should be displayed in the claim summary as:

- **ותק ענפי כולל:** X שנים (Y חודשים)
- **ותק אצל הנתבע:** X שנים (Y חודשים)
- If method ג was used: expandable table showing all מת"ש records with industry filter and defendant identification

---

## Edge Cases

1. **Worker employed at two industry employers simultaneously** — each overlapping calendar month counts once (deduplication via month-set).

2. **Employment gap of several months** — gap months are simply not in the month-set. Seniority does not accumulate during gaps.

3. **Worker started mid-month** — that month still counts as 1 (binary: any work = 1).

4. **Worker ended mid-month** — same: that partial month counts as 1.

5. **Prior seniority + defendant overlap** — if the user enters prior seniority of 24 months and the defendant employment is 36 months, total = 60 months. The prior seniority is taken as-is (the user is responsible for its accuracy).

6. **מת"ש has no records for the specified industry** — warn the user. Suggest checking the industry classification or switching to manual entry.

7. **Zero seniority** — valid. A worker with no prior industry experience who just started has 0 or near-0 seniority.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** count calendar duration instead of actual work months. 3 years of employment with 6 months of gaps = 30 months, not 36.
2. **DO NOT** apply seniority rules for specific rights inside this module. This module computes seniority. Rights consume it.
3. **DO NOT** store seniority only as years. Store months (integer) as the source of truth; derive years (decimal) from it.
4. **DO NOT** assume seniority at defendant equals total industry seniority. They are different values.
5. **DO NOT** double-count overlapping employment months across employers.
6. **DO NOT** invent industry classification rules. The user specifies the industry; the module filters by it.
