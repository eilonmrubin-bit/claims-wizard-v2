---
name: salary-conversion
description: |
  Salary conversion and minimum wage enforcement module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on converting raw salary input to processed salary types,
  minimum wage comparison, or salary completion (השלמת שכר) logic.
  ALWAYS read this skill before touching any salary conversion code.
---

# המרת שכר — Israeli Labor Law

## CRITICAL WARNINGS

1. **All conversions go through hourly.** Hourly is the pivot. Convert input → hourly first, then hourly → other types.
2. **"Regular hours" come from the SSOT, not recalculated.** Every conversion uses regular hours (Tier 0) as determined by the overtime pipeline.
3. **Minimum wage comparison uses the same salary type as the input.** Input is hourly → compare to hourly minimum. Input is daily → compare to daily minimum. Input is monthly → compare to monthly minimum. Input is per-shift → compare to **daily** minimum (per-shift has no legal minimum of its own).
4. **Net → Gross is always ×1.12.** No tax brackets, no exceptions.
5. **Never invent minimum wage values.** Use the historical table. If a date is not covered, ASK.

---

## Conceptual Model

```
┌─────────────────────────────────┐
│  User Input (per tier/period)   │
│  - amount (₪)                   │
│  - type: hourly/daily/monthly/  │
│          per-shift              │
│  - net_or_gross: net | gross    │
│  - period: start_date, end_date│
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Step 1: Gross Normalization    │
│  If net → amount × 1.12        │
│  If gross → amount as-is       │
└──────────────┬──────────────────┘
               │ gross amount in input type
               ▼
┌─────────────────────────────────┐
│  Step 2: Minimum Wage Check     │
│  Compare gross to minimum wage  │
│  of the SAME type as input      │
│  (per-shift → daily minimum)    │
│  If below → flag + use minimum  │
└──────────────┬──────────────────┘
               │ effective amount (may be minimum)
               ▼
┌─────────────────────────────────┐
│  Step 3: Convert to All Types   │
│  input → hourly (pivot)         │
│  hourly → daily                 │
│  hourly → monthly               │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  SSOT Storage                   │
│  Per period per month:          │
│  hourly, daily, monthly,        │
│  minimum_applied flag,          │
│  minimum_gap amount             │
└─────────────────────────────────┘
```

---

## Step 1: Gross Normalization

```
if input.net_or_gross == "net":
  gross = input.amount × 1.12
else:
  gross = input.amount
```

---

## Step 2: Minimum Wage Check

Compare the gross amount to the minimum wage of the **same type as input**:

| Input Type | Compare To |
|------------|------------|
| שעתי (hourly) | שכר מינימום שעתי |
| יומי (daily) | שכר מינימום יומי — `daily_5day` או `daily_6day` לפי `week_type` מה-SSOT |
| חודשי (monthly) | שכר מינימום חודשי |
| לפי משמרת (per-shift) | שכר מינימום יומי — `daily_5day` או `daily_6day` לפי `week_type` מה-SSOT |

The minimum wage value is looked up by date from the historical table (see below).

```
minimum = getMinimumWage(date, comparison_type, week_type)
// comparison_type derived from input_type (per-shift → daily)
// week_type needed only for daily comparison: selects daily_5day or daily_6day

if gross < minimum:
  effective = minimum
  minimum_applied = true
  minimum_gap = minimum - gross    // for salary completion right (השלמת שכר)
else:
  effective = gross
  minimum_applied = false
  minimum_gap = 0
```

---

## Step 3: Conversion to All Types

All conversions use **regular hours data from the SSOT**. The overtime pipeline (stages 1–6) writes each shift's regular hours (Tier 0) to the SSOT. The salary conversion module aggregates this data per month:

- **avg_regular_hours_per_day**: total regular hours in month ÷ number of work days in month
- **avg_regular_hours_per_month**: sum of `regular_hours` across all shifts in the month
- **avg_regular_hours_per_shift**: total regular hours in month ÷ number of shifts in month (for per-shift input)

**DO NOT** recalculate regular hours independently. Read them from the SSOT.

### From Hourly (שעתי):

```
hourly = effective
daily = hourly × avg_regular_hours_per_day
monthly = hourly × avg_regular_hours_per_month
```

### From Daily (יומי):

```
hourly = effective / avg_regular_hours_per_day
daily = effective
monthly = hourly × avg_regular_hours_per_month
```

### From Monthly (חודשי):

```
hourly = effective / avg_regular_hours_per_month
monthly = effective
daily = hourly × avg_regular_hours_per_day
```

### From Per-Shift (לפי משמרת):

```
hourly = effective / avg_regular_hours_per_shift
daily = hourly × avg_regular_hours_per_day
monthly = hourly × avg_regular_hours_per_month
```

**Note:** Per-shift is input-only. The system converts FROM it but never TO it.

---

## Per-Month Calculation

Conversions are calculated **per calendar month separately**, because:
- Regular hours per month vary (different number of work days per month)
- Minimum wage may change mid-period (rate changes on a specific date)

For a tier spanning Jan–Jun, the system produces 6 separate monthly records, each with its own hourly/daily/monthly values.

---

## SSOT Data Structure

```
SalaryData {
  tiers: List<{
    period_start: date
    period_end: date
    input_type: "hourly" | "daily" | "monthly" | "per_shift"
    input_net_or_gross: "net" | "gross"
    input_amount: decimal               // raw user input
    gross_amount: decimal               // after net→gross if applicable
    
    monthly_records: List<{
      month: (year, month)
      
      // Regular hours (written by overtime pipeline)
      avg_regular_hours_per_day: decimal
      avg_regular_hours_per_month: decimal
      avg_regular_hours_per_shift: decimal?   // only if input is per-shift
      
      // Minimum wage check
      minimum_wage_value: decimal        // the minimum for comparison type
      minimum_wage_type: string          // which minimum was compared (hourly / daily_5day / daily_6day / monthly)
      minimum_applied: boolean
      minimum_gap: decimal               // 0 if not applied
      
      // Effective salary (after minimum enforcement)
      effective_amount: decimal           // in input type
      
      // All conversions
      hourly: decimal
      daily: decimal
      monthly: decimal
    }>
  }>
}
```

---

## Minimum Wage Historical Table

The system must maintain a table of minimum wage values by effective date.
The table must be easy to update when new rates are legislated.

```
data/minimum_wage.csv

effective_date,hourly,daily_5day,daily_6day,monthly
2018-04-01,29.12,244.62,212.00,5300.00
2023-04-01,30.61,257.16,222.87,5571.75
2024-04-01,32.30,271.38,235.20,5880.02
2025-04-01,34.32,288.35,249.90,6247.67
```

**Lookup:** For a given date, find the row with the latest `effective_date` that is ≤ the target date. For daily comparison, use `daily_5day` or `daily_6day` based on the `week_type` from the SSOT for that month.

**Update:** When minimum wage changes, add a new row. No code changes needed.

---

## Display

### Per tier, show the conversion process:

```
תקופה: 01/2024 - 06/2024
סוג שכר: חודשי (נטו)
שכר מוזן: ₪4,800
שכר ברוטו: ₪5,376 (×1.12)
שכר מינימום חודשי: ₪5,571.75
⚠ שכר נמוך ממינימום — הושלם ל-₪5,571.75
הפרש להשלמה: ₪195.75

שכר שעתי: ₪30.61
שכר יומי: ₪244.90
שכר חודשי: ₪5,571.75
```

### When no minimum applied:

```
תקופה: 07/2024 - 12/2024
סוג שכר: שעתי (ברוטו)
שכר מוזן: ₪45.00

שכר שעתי: ₪45.00
שכר יומי: ₪378.00
שכר חודשי: ₪8,190.00
```

(No minimum row, no flag.)

---

## Edge Cases

1. **Minimum wage changes mid-tier** — the tier is split into monthly records. Each month uses the minimum wage effective for that month's date.

2. **Per-shift input, varying shift lengths** — average regular hours per shift is aggregated from shift data in the SSOT per month. If shifts are inconsistent, the average captures this.

3. **Net input below minimum even after ×1.12** — the system applies minimum AFTER gross normalization. So: net ₪4,800 → gross ₪5,376 → still below ₪5,571.75 → use ₪5,571.75.

4. **Input type changes between tiers** — each tier is independent. Tier 1 can be monthly, tier 2 can be hourly. Conversions are per-tier.

5. **Zero salary** — valid input (e.g., unpaid period). Minimum wage still applies if the worker was employed. Flag and use minimum.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** hardcode 186 hours/month or 22 days/month. Use regular hours aggregated from the SSOT per month.
2. **DO NOT** convert directly between non-hourly types (e.g., daily→monthly without going through hourly). Hourly is always the pivot.
3. **DO NOT** compare per-shift input to hourly minimum. Use daily minimum for per-shift.
4. **DO NOT** apply minimum wage before gross normalization. Net→gross first, then minimum check.
5. **DO NOT** hardcode minimum wage values. Use the historical table.
6. **DO NOT** use a single conversion for an entire tier. Calculate per month separately.
