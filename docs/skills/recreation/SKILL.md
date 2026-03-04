---
name: recreation
description: |
  Israeli labor law recreation pay (דמי הבראה) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on recreation pay calculation, entitlement per employment year,
  waiting period logic, or industry-specific recreation tables.
  ALWAYS read this skill before touching any recreation-related code.
---

# דמי הבראה — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent legal rules.** This module computes recreation based only on the rules described here.
2. **Calculation is per employment year, not per calendar year.** Each 12-month period from employment start is a separate "employment year".
3. **Waiting period of 1 full year.** If total employment < 1 year → zero entitlement. After completing 1 year, the employee becomes entitled retroactively for year 1 as well.
4. **Industry tables differ.** Never mix up tables between industries.
5. **Partial last year entitles to a partial amount.** Prorated by the fraction of the year completed.
6. **Job scope is applied per employment year.** Average job scope for that year, not overall average.

---

## Conceptual Model

```
For each employment year Y (Y=1, 2, 3, ...):
  seniority = floor(industry_seniority_at_start_of_year_Y)
  days      = table_lookup(industry, seniority)
  scope     = average_job_scope_during_year_Y
  fraction  = 1.0 (full year) or partial_fraction (last year)
  day_value = table_lookup(recreation_day_value, industry, year_end_Y)
  entitled  = days × scope × fraction × day_value

grand_total_days  = Σ (days × scope × fraction)
grand_total_value = Σ entitled
```

---

## Step 1 — Waiting Period

- If total employment duration < 1 complete year → `entitled = False`, result = 0.
- If total employment duration ≥ 1 year → `entitled = True`.
  - All employment years (including year 1) are included in the calculation.
  - Year 1 entitlement is NOT forfeited — it accrues retroactively from day 1 of employment.

---

## Step 2 — Employment Years

Define employment years from the **employment start date**:
- Year 1: [start, start + 1 year)
- Year 2: [start + 1 year, start + 2 years)
- ...
- Year N: [start + (N−1) years, min(end, start + N years))

The last year may be partial (fraction < 1.0).

`partial_fraction = whole_months_in_partial_year / 12`

"Whole months" = same definition as in the seniority module: a month counts only if fully completed from the day-of-month of employment start. See seniority skill for exact month-counting logic.

---

## Step 3 — Seniority per Year

For employment year Y:
- `seniority_at_start_of_year_Y = floor(industry_seniority_at_employment_start) + (Y − 1)`

Industry seniority at employment start = `SSOT.seniority_result.total_seniority_years` (from the seniority module, resolved at employment start date).

**Note:** For full employment years the seniority is an integer. For the partial last year, the seniority used is the integer at the start of that year (same formula, floored).

---

## Step 4 — Table Lookup

Look up `recreation_days.csv` by `industry` + `seniority_years`.

Returns `days_per_year` = the base day entitlement for a full year at full scope.

If `industry` not found in the table → fall back to `general`.

---

## Step 5 — Scope

For each employment year Y:
- Compute `avg_scope_year_Y` = weighted average of `job_scope_pct` across all `period_month_records` that fall within year Y.
- If year Y spans multiple employment periods (gap case) → compute scope only over days where actually employed.

Source: `SSOT.aggregated_results.period_month_records[].job_scope_pct`

---

## Step 6 — Day Value

For each employment year Y:
- `day_value_Y` = lookup `recreation_day_value.csv` by `industry` + `year_end` of year Y.
- Each year gets its own day value — the one in effect at the end of that employment year.

The CSV must be restructured to include `industry` as a dimension (see Static Data section).

---

## Step 7 — Per-Year Calculation

```python
for year Y:
  base_days   = get_recreation_days(industry, seniority_at_start_of_Y)
  fraction    = 1.0 if full year else partial_fraction
  scope       = avg_scope_year_Y
  day_value   = get_recreation_day_value(industry, year_end_of_Y)
  year_days   = base_days * fraction * scope       # decimal, no rounding
  year_value  = year_days * day_value              # decimal, no rounding
```

---

## Step 8 — Totals

```python
grand_total_days  = Σ year_days      # sum of all employment years
grand_total_value = Σ year_value     # sum of all employment years
```

Round to 2 decimal places only in final display.

---

## Industry Tables

### ענף כללי — `general`

| ותק (שנים שלמות) | ימים לשנה |
|-------------------|-----------|
| 1                 | 5         |
| 2–3               | 6         |
| 4–10              | 7         |
| 11–15             | 8         |
| 16–19             | 9         |
| 20+               | 10        |

### ענף בניין — `construction`

| ותק (שנים שלמות) | ימים לשנה |
|-------------------|-----------|
| 1–2               | 6         |
| 3–4               | 8         |
| 5–10              | 9         |
| 11–15             | 10        |
| 16–19             | 11        |
| 20+               | 12        |

### ענף חקלאות — `agriculture`

| ותק (שנים שלמות) | ימים לשנה |
|-------------------|-----------|
| 1–7               | 7         |
| 8                 | 8         |
| 9                 | 9         |
| 10+               | 10        |

### ענף ניקיון — `cleaning`

| ותק (שנים שלמות) | ימים לשנה |
|-------------------|-----------|
| 1–3               | 7         |
| 4–10              | 9         |
| 11–15             | 10        |
| 16–19             | 11        |
| 20–24             | 12        |
| 25+               | 13        |

---

## SSOT Output Schema

Add to `SSOT.rights_results`:

```
recreation: {
  entitled: boolean                      // האם עמד בתקופת המתנה (שנה)
  not_entitled_reason: string?           // אם entitled=False, הסיבה

  industry: string                       // "general" | "construction" | "agriculture" | "cleaning"

  years: List<{
    year_number: integer                 // 1, 2, 3, ...
    year_start: date
    year_end: date
    is_partial: boolean
    partial_fraction: decimal?           // 0 < x < 1, null אם full year. = whole_months / 12
    seniority_years: integer             // הותק בתחילת שנה זו
    base_days: decimal                   // ימי הבראה לפי טבלה (מספר שלם)
    avg_scope: decimal                   // אחוז משרה ממוצע
    day_value: decimal                   // ערך יום הבראה לשנה זו (₪), לפי industry + year_end
    day_value_effective_date: date       // תאריך effective_date שנשלף
    entitled_days: decimal               // base_days × partial_fraction × avg_scope
    entitled_value: decimal              // entitled_days × day_value
  }>

  grand_total_days: decimal              // סה"כ ימים (לא מעוגל)
  grand_total_value: decimal             // סה"כ שווי (₪, מעוגל בתצוגה בלבד)
}
```

---

## Static Data — Required Updates

### 1. `recreation_days.csv` — תיקונים נדרשים

הטבלה הקיימת שגויה בשני מקומות:

**בניין — שגוי בקובץ הנוכחי:**
```
# שורות לא נכונות (צריך להסיר):
construction,1,3,6
construction,4,10,8
construction,20,24,11
construction,25,999,12

# שורות נכונות (צריך להוסיף):
construction,1,2,6
construction,3,4,8
construction,5,10,9
construction,11,15,10
construction,16,19,11
construction,20,999,12
```

**חקלאות — חסרה לחלוטין (צריך להוסיף):**
```
agriculture,1,7,7
agriculture,8,8,8
agriculture,9,9,9
agriculture,10,999,10
```

### 2. `recreation_day_value.csv` — נדרש שינוי סכמה

הקובץ הנוכחי לא כולל ממד ענף — יש לשנות את הסכמה:

```csv
industry,effective_date,value
general,2018-07-01,378.00
general,2023-07-01,418.00
construction,...,...
agriculture,...,...
cleaning,...,...
```

**תוכן מלא נכון של הקובץ:**

```csv
industry,effective_date,value
general,2018-07-01,378.00
general,2023-07-01,418.00
construction,2018-07-01,378.00
construction,2023-07-01,418.00
agriculture,2018-07-01,378.00
agriculture,2023-07-01,418.00
cleaning,2018-07-01,423.00
```

הערות:
- כללי, בניין, חקלאות — ערך זהה בכל תקופה.
- ניקיון — ערך קבוע 423₪ לאורך כל התקופה (שורה אחת).
- Lookup: לפי `industry` + `effective_date ≤ year_end`.

---

## Input Requirements

המודול קורא מ-SSOT:
- `SSOT.input.employment_periods` — תאריכי העסקה
- `SSOT.seniority_result.total_seniority_years` — ותק ענפי כולל
- `SSOT.aggregated_results.period_month_records[].job_scope_pct` — היקף משרה חודשי
- `SSOT.input.industry` — ענף העובד (כבר קיים ב-SSOT)
- `data/recreation_days.csv`
- `data/recreation_day_value.csv`

---

## הערת סדר pipeline

מודול זה חייב לרוץ **לפני** `compute_severance` בפאזה 2.
ענף ניקיון: פיצויי פיטורין צורכים את `rights_results.recreation.years[].entitled_value`
לחישוב רכיב ההבראה בפיצויים. ראה: docs/skills/severance/SKILL.md §Cleaning Additions.

---

## Anti-Patterns

1. **לא מחשבים לפי שנה קלנדרית.** תמיד לפי שנת עסקה (12 חודשים מתאריך תחילת העסקה).
2. **לא מחשבים ותק בשנים עשרוניות לצורך lookup.** הותק לטבלה הוא תמיד מספר שלם (floor).
3. **לא מחשבים שנה חלקית בימים.** שנה חלקית = חודשים שלמים / 12 (ברזולוציה חודשית, כמו ותק).
4. **לא משתמשים בערך יום אחד לכל החישוב.** כל שנת עסקה מקבלת day_value משלה לפי industry + year_end.
5. **לא מניחים ענף ברירת מחדל בשקט.** אם הענף לא בטבלה — נופלים ל-general ומתעדים זאת.
6. **לא מעגלים בשלבי ביניים.** עיגול רק בתצוגה הסופית.

---

## Test Cases

### מקרה 1 — ותיק אחד מלא, ענף כללי, 3 שנים

```
employment: 01.01.2021 – 01.01.2024 (3 שנים מלאות)
industry: general
seniority at start: 0
scope: 1.0 כל התקופה
day_value: 418.00

year 1: seniority=0 → days=5, fraction=1.0, scope=1.0 → 5 ימים
year 2: seniority=1 → days=5, fraction=1.0, scope=1.0 → 5 ימים
year 3: seniority=2 → days=6, fraction=1.0, scope=1.0 → 6 ימים

grand_total_days  = 16.0
grand_total_value = 16.0 × 418 = 6,688.00 ₪
```

### מקרה 2 — פחות משנה → לא זכאי

```
employment: 01.01.2024 – 01.06.2024 (5 חודשים)
entitled = False
grand_total_days  = 0
grand_total_value = 0
```

### מקרה 3 — שנה וחצי (שנה ראשונה מלאה + 6 חודשים)

```
employment: 01.01.2023 – 01.07.2024 (18 חודשים)
industry: general
seniority at start: 0
scope: 1.0
day_value: 418.00

year 1: seniority=0 → days=5, fraction=1.0, scope=1.0 → 5 ימים
year 2: seniority=1 → days=5, fraction=6/12=0.5, scope=1.0 → 2.5 ימים

grand_total_days  = 7.5
grand_total_value = 7.5 × 418 = 3,135.00 ₪
```

### מקרה 4 — ותק ענפי קיים, ענף בניין

```
employment: 01.01.2022 – 01.01.2024 (2 שנים)
industry: construction
seniority at start: 5 (5 שנות ותק ענפי לפני תחילת עסקה)
scope: 0.5

year 1: seniority=5 → days=9 (5 נמצא בטווח 5–10), fraction=1.0, scope=0.5 → 4.5 ימים
year 2: seniority=6 → days=9, fraction=1.0, scope=0.5 → 4.5 ימים

grand_total_days  = 9.0
grand_total_value = 9.0 × 418 = 3,762.00 ₪
```

### מקרה 5 — אנטי-פטרן: בדיוק שנה אחת (גבול תקופת המתנה)

```
employment: 01.01.2023 – 01.01.2024 (365 ימים מלאים — שנה אחת בדיוק)
entitled = True  (השלים שנה, לא פחות)

year 1: שנה מלאה → fraction = 1.0
```
