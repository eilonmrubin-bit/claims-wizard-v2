---
name: job-scope
description: |
  Job scope (היקף משרה) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on job scope calculation or any right
  that depends on job scope percentage.
  ALWAYS read this skill before touching any job-scope-related code.
---

# היקף משרה — Israeli Labor Law

## CRITICAL WARNINGS

1. **היקף משרה = regular hours in month ÷ full_time_hours_base.** Default: 182. Configurable in system settings (not per-claim UI) to accommodate legislative changes.
2. **Maximum is 100%.** If the calculation yields more than 1.0, cap at 1.0.
3. **Regular hours come from the SSOT** (written by the overtime pipeline). Do not recalculate.
4. **Calculated per calendar month separately.** Each month has its own scope value.

---

## Calculation

```
FULL_TIME_HOURS_BASE = settings.full_time_hours_base  // default: 182

function calculateJobScope(month) → decimal:
  regular_hours = SSOT.getMonthlyRegularHours(month)  // sum of Tier 0 hours
  scope = regular_hours / FULL_TIME_HOURS_BASE
  return min(scope, 1.0)
```

---

## SSOT Data Structure

```
JobScopeData {
  full_time_hours_base: decimal      // default 182, from system settings
  
  monthly_records: List<{
    month: (year, month)
    regular_hours: decimal       // from SSOT (overtime pipeline output)
    raw_scope: decimal           // regular_hours / full_time_hours_base
    effective_scope: decimal     // min(raw_scope, 1.0)
  }>
}
```

---

## Edge Cases

1. **Over full_time_hours_base regular hours in a month** — raw_scope > 1.0, effective_scope capped at 1.0.
2. **Zero hours in a month** — scope = 0. Valid (unpaid month, gap in employment).
3. **Partial month (start/end of employment)** — regular hours reflect only the days worked. Scope will naturally be lower.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** hardcode 182 inline. Read from system settings so it can be updated when legislation changes.
2. **DO NOT** recalculate regular hours. Read from SSOT.
3. **DO NOT** return scope greater than 1.0.
