---
name: holidays
description: |
  Israeli labor law holiday pay (דמי חגים) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on holiday pay calculation, Hebrew calendar date
  resolution, or holiday eligibility logic.
  ALWAYS read this skill before touching any holiday-related code.
---

# דמי חגים — Israeli Labor Law

## CRITICAL WARNINGS

1. **Never invent eligibility rules.** This module computes holiday pay entitlement based on the rules described here. Do not add conditions or exceptions not specified.
2. **Hebrew calendar static data is required.** The system must have a pre-computed file mapping Hebrew-date holidays to Gregorian calendar dates for every year from 1948 to 2148.
3. **Legally, the holiday is the Gregorian calendar day, not the eve.** Hebrew holidays start at sunset the day before, but for labor law purposes the holiday is the calendar day itself.
4. **Holiday pay is a monetary claim, not attendance tracking.** We calculate how many holiday days the worker was entitled to but did not receive pay for. The value of each day = one work day's pay (from SSOT).
5. **Seniority prerequisite is a ONE-TIME gate, not per-year.** The 3-month seniority requirement is checked once. After it is met, it never needs to be checked again. There is NO retroactive entitlement for holidays that fell before the eligibility date.

---

## Conceptual Model

```
┌─────────────────────────────────┐
│  Hebrew Calendar Sub-Module     │
│  Maps each holiday to its       │
│  Gregorian date per year        │
│  (1948–2148)                    │
└──────────────┬──────────────────┘
               │ holiday dates
               ▼
┌─────────────────────────────────┐
│  Seniority Gate (one-time)      │
│  Compute seniority_eligibility  │
│  _date from SSOT seniority      │
│  monthly series                 │
└──────────────┬──────────────────┘
               │ eligibility date
               ▼
┌─────────────────────────────────┐
│  Holiday Eligibility Engine     │
│                                 │
│  Per calendar year:             │
│  1. Filter holidays by          │
│     employment period AND       │
│     seniority eligibility date  │
│  2. Exclude holidays on rest    │
│     day / eve-of-rest (5-day)   │
│  3. Add election day            │
│  4. Count entitled days         │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  SSOT Storage                   │
│  Per calendar year:             │
│  - Entitled holidays (list)     │
│  - Excluded holidays (list      │
│    + reason)                    │
│  - Election day entitlement     │
│  - Total entitled days          │
│  - Day value (₪)               │
│  - Total claim (₪)             │
└─────────────────────────────────┘
```

---

## Holiday List

The 9 holidays eligible for pay:

| # | Holiday | Hebrew Date |
|---|---------|-------------|
| 1 | ראש השנה א' | א' תשרי |
| 2 | ראש השנה ב' | ב' תשרי |
| 3 | יום כיפור | י' תשרי |
| 4 | סוכות | ט"ו תשרי |
| 5 | הושענא רבה | כ"א תשרי |
| 6 | פסח (יום ראשון) | ט"ו ניסן |
| 7 | שביעי של פסח | כ"א ניסן |
| 8 | יום העצמאות | ה' אייר |
| 9 | שבועות | ו' סיוון |

Plus: **יום בחירה** — 1 additional entitled day per year (not tied to a specific date).

**Total maximum per year: 10 days** (9 holidays + 1 election day).

---

## Hebrew Calendar — Static Data File

### Approach

במקום חישוב בזמן ריצה, המערכת משתמשת בקובץ נתונים סטטי שמכיל את התאריכים
הלועזיים של כל 9 החגים לכל שנה בטווח 1948–2148.

**מבנה הקובץ:**
```
data/holiday_dates.csv
```

**פורמט:**
```
year,holiday_id,hebrew_date,gregorian_date
2024,rosh_hashana_1,א' תשרי,2024-10-03
2024,rosh_hashana_2,ב' תשרי,2024-10-04
2024,yom_kippur,י' תשרי,2024-10-12
2024,sukkot,ט"ו תשרי,2024-10-17
2024,hoshana_raba,כ"א תשרי,2024-10-23
2024,pesach,ט"ו ניסן,2024-04-23
2024,pesach_7,כ"א ניסן,2024-04-29
2024,yom_haatzmaut,ה' אייר,2024-05-14
2024,shavuot,ו' סיוון,2024-06-12
...
```

**ייצור הקובץ:** סקריפט חד-פעמי (`scripts/generate_holiday_dates.py`) שמשתמש
בספריית לוח עברי (e.g., `hebcal` for JS/TS, `pyluach` or `hdate` for Python)
לייצר את כל התאריכים פעם אחת. הסקריפט רץ בפיתוח בלבד.

**נפח:** 9 חגים × 200 שנה = 1,800 שורות. זניח.

**אימות:** לאחר הייצור, מדגם של תאריכים ידועים (ראה מבחן 10 בקובץ הבדיקות)
מאומת מול מקור חיצוני.

**גישה בקוד:**
```
function getHolidayDates(gregorian_year) → List<{holiday_id, name, hebrew_date, gregorian_date}>
```
טוען מהקובץ, מסנן לפי שנה.

**יום העצמאות:** יום העצמאות יכול לזוז כדי להימנע מסמיכות לשבת.
הסקריפט צריך לטפל בתאריך הרשמי (כפי שהספרייה מחזירה).
אם הספרייה לא מטפלת בזה, ה' אייר הוא ברירת המחדל.

### Constraints
- הקובץ חייב לכסות 1948–2148
- התאריך הלועזי הוא **יום החג הקלנדרי**, לא הערב שלפניו
- הלוח העברי כולל שנים מעוברות עם אדר שני — הסקריפט חייב לטפל בזה

---

## Seniority Prerequisite (תנאי ותק)

### Rule

A worker is entitled to holiday pay only after completing **3 months of seniority at the defendant** (`at_defendant_months >= 3` from SSOT seniority data). This is a **one-time gate**:

1. Find the first month in `SSOT.seniority.monthly` where `at_defendant_cumulative >= 3`.
2. The **seniority eligibility date** = the first day of the **following** calendar month.
3. Only holidays whose `gregorian_date >= seniority_eligibility_date` are eligible.
4. **No retroactive entitlement** — holidays that fell before the eligibility date are never entitled, even after the threshold is crossed.

### Computation

```
function computeSeniorityEligibilityDate():
  monthly_series = SSOT.seniority.monthly

  for entry in monthly_series:
    if entry.at_defendant_cumulative >= 3:
      // This month is the 3rd work month. Eligibility starts next month.
      eligibility_date = first_day_of_next_month(entry.month)
      return eligibility_date

  // Worker never reached 3 months — no holiday entitlement at all
  return null
```

### Example

Worker started January 15, 2024. Worked every month:
- Jan 2024: cumulative = 1
- Feb 2024: cumulative = 2
- Mar 2024: cumulative = 3 → **eligibility date = April 1, 2024**
- Holidays before April 1, 2024 → not entitled (e.g., Pesach on April 23 IS eligible; but if a holiday fell in February, it would NOT be)

Worker started January 15, 2024. Did NOT work in February:
- Jan 2024: cumulative = 1
- Feb 2024: cumulative = 1 (didn't work)
- Mar 2024: cumulative = 2
- Apr 2024: cumulative = 3 → **eligibility date = May 1, 2024**

### Election Day

The same seniority prerequisite applies to election day. Once the seniority gate is passed, the worker is entitled to 1 election day in **every calendar year** in which they were employed at least 1 day (i.e., at least one `daily_record` exists in that year). No further per-year threshold applies.

**CRITICAL:** The old 1/10-of-year threshold does NOT exist. It has been fully replaced by this one-time seniority gate.

---

## Eligibility Algorithm

### Per Calendar Year:

```
function calculateHolidayEntitlement(year, rest_day, seniority_eligibility_date):
  // All data read from SSOT

  // Step 0: Check seniority gate
  // If seniority_eligibility_date is null, the worker never reached 3 months — no entitlement
  if seniority_eligibility_date == null:
    return { entitled_days: 0, reason: "לא השלים 3 חודשי ותק אצל הנתבע" }

  // Step 1: Get holiday dates for this year
  holidays = getHolidayDates(year)  // 9 holidays with Gregorian dates

  // Step 2: Filter by employment period AND seniority eligibility
  // A holiday is "active" if:
  //   (a) the worker was employed on that date (daily_record exists)
  //   (b) the holiday date >= seniority_eligibility_date
  active_holidays = holidays.filter(h =>
    SSOT.daily_records.has(h.date) AND
    h.date >= seniority_eligibility_date
  )

  // Holidays where employed but before seniority eligibility:
  pre_seniority_holidays = holidays.filter(h =>
    SSOT.daily_records.has(h.date) AND
    h.date < seniority_eligibility_date
  )
  // These are stored for display with exclude_reason "טרם השלמת 3 חודשי ותק"

  // Step 3: Exclude based on rest day and week type
  for each holiday in active_holidays:
    day_of_week = holiday.date.dayOfWeek
    holiday_week_type = getWeekTypeForHoliday(holiday.date)  // per holiday!

    if day_of_week == rest_day:
      holiday.excluded = true
      holiday.exclude_reason = "חג שחל ביום המנוחה"

    else if holiday_week_type == 5 AND day_of_week == eve_of_rest(rest_day):
      holiday.excluded = true
      holiday.exclude_reason = "חג שחל בערב מנוחה (שבוע 5 ימים)"

    else:
      holiday.excluded = false

  entitled_holidays = active_holidays.filter(h => !h.excluded)

  // Step 4: Election day
  // Entitled if: (a) seniority gate passed, AND (b) at least 1 daily_record in this year
  employed_in_year = SSOT.daily_records.any(d => d.date.year == year)

  // Also check: was the seniority gate passed before the end of this year?
  // (If eligibility_date is in 2025, election day for 2024 is NOT entitled)
  election_day_entitled = employed_in_year AND
    seniority_eligibility_date <= last_day_of_year(year)

  // Step 5: Calculate per-holiday value
  // Each holiday gets its salary_daily from the period_month_record
  // of the effective_period active on that holiday's date
  for each holiday in entitled_holidays:
    ep = getEffectivePeriod(holiday.date)    // from SSOT
    pmr = SSOT.period_month_records[ep.id, holiday.date.month]
    holiday.day_value = pmr.salary_daily
    holiday.claim_amount = pmr.salary_daily

  // Step 5b: Election day value
  // Election day has no specific calendar date, so its value =
  // the HIGHEST salary_daily across all period_month_records in this year.
  // If there are multiple salary tiers in the same year, election day
  // is valued at the highest one (not chronologically dependent).
  if election_day_entitled:
    election_day_value = max(
      pmr.salary_daily
      for pmr in SSOT.period_month_records
      where pmr.month.year == year
    )

  // Step 6: Sum
  total_entitled_days = entitled_holidays.length + (1 if election_day_entitled)
  total_claim = sum(h.claim_amount for h in entitled_holidays)
               + (election_day_value if election_day_entitled else 0)

  return {
    year,
    seniority_eligibility_date,
    holidays: active_holidays + pre_seniority_holidays,  // all with status
    excluded_holidays,              // with reasons
    election_day_entitled,
    total_entitled_days,
    total_claim
  }
```

### Eve of Rest Resolution

```
function eve_of_rest(rest_day):
  // The calendar day before the rest day
  if rest_day == Saturday: return Friday
  if rest_day == Friday: return Thursday
  if rest_day == Sunday: return Saturday
```

---

## Week Type Source

The week type (5 or 6) is determined **per holiday individually** — look up the week_type of the specific calendar week in which the holiday falls. This value is stored in the SSOT `weeks` data (written by the overtime pipeline).

```
function getWeekTypeForHoliday(holiday_date):
  week_id = getCalendarWeek(holiday_date)   // e.g., 2024-W15
  week = SSOT.weeks[week_id]
  return week.week_type                      // 5 or 6
```

**CRITICAL:** Do NOT use a "dominant" or "average" week type for the year. Each holiday's eve-of-rest exclusion depends on the week type of **its own week**. A holiday in a 5-day week is excluded if it falls on eve-of-rest; the same holiday in a 6-day week would NOT be excluded.

---

## SSOT Data Structure

```
HolidayData {
  seniority_eligibility_date: date?        // first day eligible for holidays (null = never reached 3 months)

  per_year: List<{
    year: integer

    holidays: List<{
      name: string                      // "ראש השנה א'"
      hebrew_date: string               // "א' תשרי"
      gregorian_date: date              // resolved date
      employed_on_date: boolean         // was worker employed?
      before_seniority: boolean         // holiday fell before seniority_eligibility_date
      day_of_week: string               // "Sunday".."Saturday"
      week_type: integer?               // 5 or 6 — of THIS holiday's week (null if not employed)
      is_rest_day: boolean
      is_eve_of_rest: boolean
      excluded: boolean
      exclude_reason: string?           // "חג שחל ביום המנוחה" / "חג שחל בערב מנוחה (שבוע 5 ימים)" / "טרם השלמת 3 חודשי ותק" / "לא הועסק בתאריך החג"
      entitled: boolean                 // final: employed AND after seniority AND not excluded
      day_value: decimal?               // ₪ — salary_daily from period_month_records for this date
      claim_amount: decimal?            // = day_value if entitled, null if not
    }>

    election_day_entitled: boolean
    election_day_value: decimal?          // highest salary_daily in that year (if entitled)

    total_entitled_days: integer        // count of entitled holidays + election day
    total_claim: decimal                // sum of claim_amounts
  }>

  grand_total_days: integer
  grand_total_claim: decimal
}
```

**Every calendar year in the employment period must be stored**, even if entitled days = 0 (before seniority or no holidays fell on work days).

---

## Display

Per calendar year, show a table:

| חג | תאריך עברי | תאריך לועזי | יום בשבוע | זכאות | הערה |
|----|-----------|-------------|----------|-------|------|
| ראש השנה א' | א' תשרי | 2024-10-03 | Thursday | ✓ | |
| יום כיפור | י' תשרי | 2024-10-12 | Saturday | ✗ | חל ביום המנוחה |
| פסח | ט"ו ניסן | 2024-04-23 | Tuesday | ✗ | טרם השלמת 3 חודשי ותק |
| ... | | | | | |
| יום בחירה | — | — | — | ✓ | |
| **סה"כ** | | | | **8 ימים** | **₪X** |

Years where seniority was never reached show: "לא השלים 3 חודשי ותק אצל הנתבע — אין זכאות לדמי חגים"

---

## Edge Cases

1. **Holiday falls on Saturday AND rest day is Saturday** — excluded regardless of week type.

2. **Holiday falls on Friday, rest day is Saturday, week type 5** — excluded (Friday is eve of rest for Saturday rest day in 5-day week).

3. **Holiday falls on Friday, rest day is Saturday, week type 6** — entitled (in 6-day week, only rest day itself is excluded, not eve of rest).

4. **Holiday falls on Friday, rest day is Friday** — excluded (it IS the rest day).

5. **Seniority gate crossed mid-year** — worker started Jan 2024, eligibility date = April 1, 2024. Holidays in Jan–Mar 2024 are NOT entitled (no retroactivity). Holidays from April onward in 2024 ARE checked for entitlement normally.

6. **Worker never reached 3 months** — short employment (e.g., 2 months). No holiday entitlement at all, including no election day.

7. **Seniority gap delays eligibility** — worker started Jan 2024, did not work in Feb, Mar. Cumulative reaches 3 only in June 2024. Eligibility date = July 1, 2024. All holidays before July are not entitled.

8. **Election day in the first eligible year** — the seniority gate was crossed in April 2024. Election day for 2024 IS entitled (the worker was employed at least 1 day in 2024, and the gate was crossed within 2024).

9. **Election day in a year entirely before the seniority gate** — if employment started Dec 2023 and eligibility date = March 1, 2024, election day for 2023 is NOT entitled (gate was not yet passed in 2023).

10. **Two holidays on the same Gregorian date** — should not happen with the standard list, but if it does, count each separately.

11. **יום העצמאות moved** — the static data file should contain the official date. If the generation script handled it, the data is correct. Otherwise ה' אייר is the default.

12. **Leap year (Hebrew)** — the Hebrew calendar has leap years with an extra month (Adar II). This affects when Nisan holidays fall in the Gregorian calendar. The generation script must handle this correctly (the library does).

13. **Election day with multiple salary tiers in the same year** — worker earned ₪250/day in Jan–Jun and ₪300/day in Jul–Dec. Election day value = ₪300 (the highest). This is not tied to chronological order — even if the higher tier was earlier in the year, it would still be selected.

14. **Partial first year — started in October** — no 1/10 threshold check needed. The only question is whether the seniority gate was passed (3 months at defendant). If employment started Oct 1, eligibility date is Jan 1 of the following year. Holidays in Oct–Dec are NOT entitled. If the worker had prior months at defendant (unusual), that could accelerate the gate.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** hardcode Gregorian dates for holidays. They change every year. Use the static data file.
2. **DO NOT** calculate week type inside this module. Read it from SSOT.
3. **DO NOT** treat election day like a calendar holiday. It has no date — it's always 1 entitled day per eligible year. Its monetary value = the highest salary_daily from any period_month_record in that calendar year.
4. **DO NOT** skip years where entitlement is 0. Store and display them for transparency.
5. **DO NOT** confuse Hebrew day start (sunset) with legal day. The legal holiday = the Gregorian calendar day.
6. **DO NOT** assume rest day is always Saturday. It's a per-worker input.
7. **DO NOT** apply a 1/10-of-year threshold. This rule has been removed. The only prerequisite is 3 months seniority at defendant (one-time).
8. **DO NOT** grant retroactive holiday entitlement. Holidays that fell before the seniority eligibility date are never entitled, even after the gate is crossed.
9. **DO NOT** re-check the seniority gate per year. It is computed once and applies globally. Once the eligibility date is set, it is permanent.
