---
name: pension
description: |
  Israeli labor law pension contributions (פנסיה) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on pension calculation, industry-specific pension rates,
  or monthly pension value computation.
  ALWAYS read this skill before touching any pension-related code.
---

# פנסיה — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent legal rules.** This module computes pension based only on the rules described here.
2. **Calculation is per calendar month.** Each month is computed independently.
3. **Salary basis is `salary_monthly` from `period_month_records`.** NOT from salary tiers directly. The salary_monthly already reflects gross effective salary after minimum wage enforcement.
4. **Job scope from `month_aggregates`.** Apply per-month job scope exactly as stored.
5. **Construction rate changes on 2018-07-01.** Before July 2018 (exclusive): 6.0%. From July 2018 (inclusive): 7.1%.
6. **Partial months are handled automatically.** `salary_monthly` and `job_scope` already reflect partial months. No extra proration needed.
7. **Deduction is a single total amount.** No per-month breakdown.

---

## Conceptual Model

```
For each calendar month M covered by employment:

  salary_monthly_M = sum of salary_monthly across all period_month_records for month M
  job_scope_M      = month_aggregates[M].job_scope
  rate_M           = pension_rate(industry, M)

  pension_M = salary_monthly_M × rate_M × job_scope_M

grand_total = Σ pension_M
```

---

## §Pension Rates by Industry

| Industry     | Effective From    | Rate  |
|--------------|-------------------|-------|
| general      | always            | 6.5%  |
| agriculture  | always            | 6.5%  |
| cleaning     | always            | 7.5%  |
| construction | before 2018-07-01 | 6.0%  |
| construction | from 2018-07-01   | 7.1%  |

**Lookup rule:** For month M, use the rate with the latest `effective_date ≤ month_start`.

```python
PENSION_RATES: dict[str, list[tuple[date, Decimal]]] = {
    "general":      [(date(1900,1,1), Decimal("0.065"))],
    "agriculture":  [(date(1900,1,1), Decimal("0.065"))],
    "cleaning":     [(date(1900,1,1), Decimal("0.075"))],
    "construction": [
        (date(1900,1,1), Decimal("0.060")),
        (date(2018,7,1), Decimal("0.071")),
    ],
}
```

---

## §Salary Basis

Use `salary_monthly` from `period_month_records`:

```
salary_monthly = hourly × full_time_hours_base (182)
```

This is **NOT** adjusted for actual hours worked — that is handled via `job_scope`.

When multiple effective periods overlap a single calendar month (salary change mid-month), sum their `salary_monthly` values — each PMR already represents only its proportional slice.

---

## §Job Scope

From `month_aggregates[month].job_scope`. Decimal fraction (e.g., 0.85 = 85% scope).

---

## §Limitation

Pension uses **`limitation_type_id = "general"`** (7-year window).

Filter: a month is claimable if `effective_window_start ≤ month_start ≤ filing_date`.

---

## §Deduction

`deductions_input["pension"]` — single total amount representing employer contributions already paid.

---

## §SSOT Schema

```python
@dataclass
class PensionMonthData:
    month: tuple[int, int] = (0, 0)
    month_start: date | None = None
    salary_monthly: Decimal = Decimal("0")
    job_scope: Decimal = Decimal("0")
    pension_rate: Decimal = Decimal("0")
    month_value: Decimal = Decimal("0")      # salary_monthly × rate × job_scope

@dataclass
class PensionResult:
    entitled: bool = True
    industry: str = ""
    months: list[PensionMonthData] = field(default_factory=list)
    grand_total_value: Decimal = Decimal("0")
```

---

## §Pipeline Integration

- **Phase 2** — after `compute_vacation()`
- **Phase 3** — limitation: filter months by `effective_window_start ≤ month_start ≤ filing_date`
- **Phase 3** — deduction: `deductions_input.get("pension", 0)`
- **settings.json** — `right_limitation_mapping["pension"] = "general"` (already present)

---

## §Frontend

- Toggle in "זכויות נתבעות" — default ON
- Deduction field: "הפרשות פנסיה ששולמו"
- `PensionBreakdown` component:
  - Header: grand_total_value, claimable_amount, industry, rate
  - Table grouped by year with collapse
  - Columns: חודש | שיעור | שכר חודשי | היקף משרה | שווי
  - Limitation panel (same pattern as recreation)

---

## §Test Cases

### Case 1 — General, 3 years, 10,000₪/month gross, full time
- 36 months × (10,000 × 0.065 × 1.0) = **23,400₪**

### Case 2 — Construction, 2015-01-01 to 2024-12-31, 45₪/h
- Jan 2015 – Jun 2018 (42 months): 8,190 × 0.060 × 1.0 = 491.40₪ × 42 = **20,638.80₪**
- Jul 2018 – Dec 2024 (78 months): 8,190 × 0.071 × 1.0 = 581.49₪ × 78 = **45,356.22₪**
- Grand total = **65,995.02₪**

### Case 3 — Toggle disabled → entitled=False, grand_total=0

### Case 4 — Cleaning, job_scope=0.5, salary_monthly=6,000₪
- 6,000 × 0.075 × 0.5 = **225₪**

---

## §Anti-Patterns (DO NOT DO)

1. **DO NOT** compute from hourly × hours worked. Use `salary_monthly` from PMR.
2. **DO NOT** apply single rate for all construction months. Rate is per month.
3. **DO NOT** prorate partial months manually. PMR handles this.
4. **DO NOT** hardcode rates inline without the PENSION_RATES table.
