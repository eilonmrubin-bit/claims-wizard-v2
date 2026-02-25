---
name: ssot
description: |
  SSOT (Single Source of Truth) schema for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on data structures, adding fields to the SSOT,
  creating new modules that read/write to the SSOT, or debugging data flow issues.
  ALWAYS read this skill before touching any SSOT-related code or adding new rights.
---

# SSOT Schema — אשף התביעות

## עקרונות

1. **מקור אמת יחיד.** כל מודול כותב לכאן וקורא מכאן.
2. **קובץ .case = קלט בלבד (שכבה 0).** שכבות 1–7 מחושבות מחדש בכל לחיצת "חשב".
3. **לא זורקים מידע.** כל שביב מידע ביניים נשמר — לתצוגה, לדיבוג, לביקורת.
4. **דיוק יומי בכל מקום, דיוק לדקה במשמרות.**
5. **3 שכבות אגרגציה:** יום/משמרת → תקופה×חודש → חודש.
6. **אפס חישובים בפרונטאנד.** כל ערך נגזר (duration, אחוז, display string) מחושב ב-backend ונשמר ב-SSOT. פורמטר Duration (פאזה 4) יוצר display strings.

---

## Duration — טיפוס משותף

כל מקום שיש תקופה עם start/end מקבל גם אובייקט duration מחושב.
**ערכים מספריים** (days, months_decimal וכו') — מחושבים ע"י המודול שיוצר את התקופה (למשל: המארג עבור effective_periods).
**שדה display** (מחרוזת עברית) — נוצר בפאזה 4 ע"י פורמטר Duration.

```
Duration {
  days: integer              // 410
  months_decimal: decimal    // 13.67
  years_decimal: decimal     // 1.139
  months_whole: integer      // 13
  days_remainder: integer    // 20
  years_whole: integer       // 1
  months_remainder: integer  // 1
  display: string            // "שנה, חודש ו-20 יום"
}
```

ה-display מוכן לתצוגה בעברית. הפרונטאנד לא מחשב כלום — רק מציג.

---

## שכבה 0 — קלט (נשמר לקובץ .case)

```
SSOT.input {

  // ═══ מטא-דאטא ═══
  case_metadata: {
    case_name: string                    // שם התיק (חופשי)
    created_at: datetime                 // תאריך יצירת התיק
    notes: string?                       // הערות חופשיות
  }

  // ═══ פרטים אישיים (רשות חוץ משנת לידה) ═══
  personal_details: {
    id_number: string?                   // ת"ז — רשות
    first_name: string?                  // שם פרטי — רשות
    last_name: string?                   // שם משפחה — רשות
    birth_year: integer                  // שנת לידה — חובה (זכויות תלויות גיל)
  }

  // ═══ פרטי מעביד/נתבע (רשות — לתצוגה ולייצוא) ═══
  defendant_details: {
    name: string?                        // שם המעביד / החברה
    id_number: string?                   // ח.פ. / ע.מ.
    address: string?                     // כתובת
    notes: string?                       // הערות
  }

  // ═══ ציר 1: תקופות העסקה ═══
  employment_periods: List<{
    id: string                           // מזהה ייחודי
    start: date                          // תאריך התחלה
    end: date                            // תאריך סיום
    duration: Duration                   // מחושב (מספרי; display בפאזה 4)
  }>

  // ═══ ציר 2: דפוסי עבודה ═══
  work_patterns: List<{
    id: string
    start: date                          // תחילת תוקף
    end: date                            // סיום תוקף
    duration: Duration                   // מחושב (מספרי; display בפאזה 4)
    work_days: List<integer>             // ימים בשבוע (0=ראשון..6=שבת)

    // תבניות משמרות — 3 מצבים (סדר עדיפויות: daily_overrides > per_day > default):
    default_shifts: List<{               // מצב א — אחיד לכל ימי העבודה
      start_time: time
      end_time: time
    }>
    default_breaks: List<{               // הפסקות ברירת מחדל
      start_time: time
      end_time: time
    }>
    per_day: Map<integer, {              // מצב ב — לפי יום בשבוע (null אם לא רלוונטי)
      shifts: List<{start_time, end_time}>
      breaks: List<{start_time, end_time}>?
    }>?
    daily_overrides: Map<date, {         // מצב ג — לפי תאריך קלנדרי (null אם לא רלוונטי)
      shifts: List<{start_time, end_time}>
      breaks: List<{start_time, end_time}>?
    }>?
  }>

  // ═══ ציר 3: מדרגות שכר ═══
  salary_tiers: List<{
    id: string
    start: date
    end: date
    duration: Duration                   // מחושב (מספרי; display בפאזה 4)
    amount: decimal                      // סכום
    type: "hourly" | "daily" | "monthly" | "per_shift"
    net_or_gross: "net" | "gross"
  }>

  // ═══ קלט פשוט (לא ציר) ═══
  rest_day: "saturday" | "friday" | "sunday"
  district: "jerusalem" | "tel_aviv" | "haifa" | "south" | "galil"
  industry: string                       // ענף עבודה
  filing_date: date                      // תאריך הגשת תביעה

  // ═══ קלט ותק ═══
  seniority_input: {
    method: "prior_plus_pattern" | "total_plus_pattern" | "matash_pdf"
    prior_months: integer?               // שיטה א — ותק קודם (לפני הנתבע)
    total_industry_months: integer?      // שיטה ב — סה"כ ותק ענפי כולל
    matash_file: binary?                 // שיטה ג
  }

  // ═══ טוגלים לזכויות ═══
  right_toggles: Map<string, Map<string, boolean>>
  // דוגמה:
  // {
  //   "overtime": {
  //     "employer_paid_rest_premium": false,    // השבתה
  //     "employer_paid_base_salary": false       // השבתה
  //   },
  //   "salary_completion": {
  //     "molon_enabled": true                    // הפעלה
  //   }
  // }

  // ═══ ניכויי הפרשות מעסיק ═══
  deductions_input: Map<string, decimal>
  // דוגמה: { "pension": 15000, "severance": 22000 }

  // ═══ קלט ייחודי לזכויות ═══
  right_specific_inputs: Map<string, Map<string, any>>
  // דוגמה:
  // {
  //   "travel": { "distance_over_40km": true },
  //   "other_right": { "custom_field": "value" }
  // }
}
```

---

## שכבה 1 — מצליב תקופות (המארג)

```
// ═══ תקופות אפקטיביות (המארג יוצר, כולל Duration מספרי) ═══
SSOT.effective_periods: List<{
  id: string                             // מזהה ייחודי (e.g., "EP1", "EP2")
  start: date
  end: date
  duration: Duration                     // מחושב ע"י המארג (display בפאזה 4)
  employment_period_id: string           // → input.employment_periods[].id
  work_pattern_id: string                // → input.work_patterns[].id
  salary_tier_id: string                 // → input.salary_tiers[].id

  // שדות שנאספים מהצירים (denormalized)
  pattern_work_days: List<integer>       // ימי עבודה בשבוע
  pattern_default_shifts: List<{start_time, end_time}>   // ברירת מחדל
  pattern_default_breaks: List<{start_time, end_time}>   // ברירת מחדל
  pattern_per_day: Map<integer, {shifts, breaks?}>?      // לפי יום (null אם לא רלוונטי)
  pattern_daily_overrides: Map<date, {shifts, breaks?}>? // לפי תאריך (null אם לא רלוונטי)
  salary_amount: decimal
  salary_type: "hourly" | "daily" | "monthly" | "per_shift"
  salary_net_or_gross: "net" | "gross"
}>

// ═══ פערים בהעסקה (המארג יוצר, כולל Duration מספרי) ═══
SSOT.employment_gaps: List<{
  start: date                            // יום ראשון שלא מועסק
  end: date                              // יום אחרון שלא מועסק
  duration: Duration                     // מחושב ע"י המארג (display בפאזה 4)
  before_period_id: string               // תקופה שלפני הפער
  after_period_id: string                // תקופה שאחרי הפער
}>

// ═══ סיכום תקופת העסקה (המארג יוצר, כולל Duration מספרי) ═══
SSOT.total_employment: {
  first_day: date                        // יום ראשון של תקופה ראשונה
  last_day: date                         // יום אחרון של תקופה אחרונה
  total_duration: Duration               // מתחילה ראשונה עד סוף אחרונה (כולל פערים)
  worked_duration: Duration              // סה"כ ימי העסקה בפועל (בניכוי פערים)
  gap_duration: Duration                 // סה"כ ימי פער
  periods_count: integer                 // מספר תקופות
  gaps_count: integer                    // מספר פערים
}
```

---

## שכבה 2 — רשומות יומיות + משמרות

**כותבים:**
- `daily_records` ← המארג (①). שדה `day_segments` נכתב בנפרד ע"י OT stage 3.5.
- `shifts` ← OT pipeline (② stages 1–7, שעות בלבד. stage 8 pricing ממלא claim_amount בפאזה 2).
- `weeks` ← OT pipeline (② stage 3, מועשר ב-stages 6–7).

### daily_records

```
SSOT.daily_records: List<{
  date: date                             // תאריך קלנדרי
  effective_period_id: string            // → effective_periods[].id
  day_of_week: integer                   // 0=ראשון..6=שבת
  is_work_day: boolean                   // מדפוס עבודה בלבד (לא מביא בחשבון חגים/היעדרויות)
  is_rest_day: boolean                   // יום המנוחה — boolean קלנדרי (rest_day == day_of_week)

  // ═══ תבניות משמרות (המארג כותב, OT stage 1 צורך) ═══
  shift_templates: List<{               // ריק אם !is_work_day
    start_time: time                     // 07:00
    end_time: time                       // 16:00
  }>
  break_templates: List<{               // ריק אם !is_work_day
    start_time: time
    end_time: time
  }>

  // ═══ day_segments (OT stage 3.5 כותב, null עד שרץ) ═══
  day_segments: List<{
    start: time                          // 00:00
    end: time                            // 17:30
    type: "regular" | "eve_of_rest" | "rest"
  }>?                                    // null = טרם חושב
}>
```

### shifts (מ-OT stages 1–7, שעות בלבד)

```
SSOT.shifts: List<{

  // ═══ זיהוי ═══
  id: string                             // מזהה ייחודי
  date: date                             // תאריך היום שאליו שויכה המשמרת
  shift_index: integer                   // אינדקס המשמרת ביום (0, 1, 2...)
  effective_period_id: string            // → effective_periods[].id

  // ═══ Stage 1 — הרכבה ═══
  start: datetime                        // תחילת הסגמנט הראשון
  end: datetime                          // סוף הסגמנט האחרון
  segments: List<{                       // חלקי עבודה בפועל
    start: datetime
    end: datetime
  }>
  breaks: List<{                         // הפסקות
    start: datetime
    end: datetime
  }>
  net_hours: decimal                     // סה"כ שעות עבודה (ללא הפסקות)

  // ═══ Stage 2 — שיוך ═══
  assigned_day: date                     // היום שאליו שויכה (majority rule)
  assigned_week: string                  // (year, week_number) → weeks[].id

  // ═══ Stage 4 — סף ═══
  threshold: decimal                     // 7.0 | 8.0 | 8.4
  threshold_reason: string               // "5day" | "6day" | "eve_rest" | "night" | "eve_rest+night"

  // ═══ Stage 5 — OT יומי ═══
  regular_hours: decimal                 // שעות רגילות (Tier 0) — אחרי stages 5+6
  ot_tier1_hours: decimal                // שעות נוספות 125% — אחרי stage 6
  ot_tier2_hours: decimal                // שעות נוספות 150% — אחרי stage 6
  daily_ot_hours: decimal                // סה"כ OT יומי מ-stage 5
  weekly_ot_hours: decimal               // OT שבועי שנוסף ב-stage 6

  // ═══ Stage 7 — חלון מנוחה ═══
  rest_window_regular_hours: decimal     // שעות רגילות בתוך חלון מנוחה
  rest_window_ot_tier1_hours: decimal    // שעות tier1 בתוך חלון מנוחה
  rest_window_ot_tier2_hours: decimal    // שעות tier2 בתוך חלון מנוחה
  non_rest_regular_hours: decimal        // שעות רגילות מחוץ לחלון
  non_rest_ot_tier1_hours: decimal       // שעות tier1 מחוץ לחלון
  non_rest_ot_tier2_hours: decimal       // שעות tier2 מחוץ לחלון

  // ═══ Stage 8 — pricing (ממולא בשלב זכויות, לא בעיבוד) ═══
  claim_amount: decimal?                 // סה"כ ₪ לתביעה — null עד שרץ pricing
  pricing_breakdown: List<{              // פירוט לכל חלק במשמרת
    hours: decimal
    tier: 0 | 1 | 2
    in_rest: boolean
    rate_multiplier: decimal             // 1.00 / 1.25 / 1.50 / 1.75 / 2.00
    claim_multiplier: decimal            // 0.00 / 0.25 / 0.50 / 0.75 / 1.00
    hourly_wage: decimal                 // מ-period_month_records
    claim_amount: decimal                // hours × claim_multiplier × hourly_wage
  }>?
}>
```

### weeks (מ-OT stage 3, מועשר ב-stages 6–7)

```
SSOT.weeks: List<{
  id: string                             // e.g., "2024-W15"
  year: integer
  week_number: integer
  start_date: date                       // ראשון של השבוע
  end_date: date                         // שבת של השבוע

  // ═══ Stage 3 — סיווג ═══
  distinct_work_days: integer            // מספר ימי עבודה שונים
  week_type: 5 | 6                       // סוג שבוע

  // ═══ Stage 6 — OT שבועי ═══
  total_regular_hours: decimal           // סה"כ regular hours בשבוע (לפני weekly OT)
  weekly_ot_hours: decimal               // שעות שהפכו ל-OT שבועי
  weekly_threshold: decimal              // תמיד 42

  // ═══ Stage 7 — חלון מנוחה ═══
  rest_window_start: datetime?           // תחילת חלון 36h
  rest_window_end: datetime?             // סוף חלון 36h
  rest_window_work_hours: decimal        // שעות עבודה בתוך החלון (מינימיזציה)

  // ═══ שבוע חלקי ═══
  is_partial: boolean
  partial_reason: "employment_start" | "employment_end" | "gap_start" | "gap_end" | null
  partial_detail: string?                // e.g., "T2 started 2024-02-01 (Thursday)"
}>
```

---

## שכבה 3 — רשומות תקופה×חודש (אגרגטור ③ + המרת שכר ④)

```
SSOT.period_month_records: List<{
  effective_period_id: string            // → effective_periods[].id
  month: (integer, integer)              // (year, month)

  // ═══ שעות — אגרגטור (③) כותב ═══
  work_days_count: integer               // ימי עבודה בתקופה זו בחודש זה
  shifts_count: integer                  // מספר משמרות
  total_regular_hours: decimal           // סה"כ regular hours
  total_ot_hours: decimal                // סה"כ OT hours
  avg_regular_hours_per_day: decimal     // regular ÷ work_days
  avg_regular_hours_per_shift: decimal   // regular ÷ shifts

  // ═══ שכר גולמי — המרת שכר (④) כותבת ═══
  salary_input_amount: decimal           // הסכום שהוזן
  salary_input_type: "hourly" | "daily" | "monthly" | "per_shift"
  salary_input_net_or_gross: "net" | "gross"
  salary_gross_amount: decimal           // אחרי נטו→ברוטו (×1.12 אם נטו)

  // ═══ בדיקת מינימום — המרת שכר (④) כותבת ═══
  minimum_wage_value: decimal            // ערך המינימום לסוג ההשוואה (lookup לפי חודש!)
  minimum_wage_type: string              // "hourly" | "daily" | "monthly"
  minimum_applied: boolean               // האם הושלם למינימום?
  minimum_gap: decimal                   // הפרש (0 אם לא הושלם)
  effective_amount: decimal              // סכום אפקטיבי (אחרי מינימום, בסוג הקלט)

  // ═══ שכר מעובד — המרת שכר (④) כותבת ═══
  salary_hourly: decimal                 // שעתי (pivot)
  salary_daily: decimal                  // יומי
  salary_monthly: decimal                // חודשי
}>
```

---

## שכבה 4 — אגרגציות חודשיות (היקף משרה ⑤ + ותק ⑤)

### month_aggregates

```
SSOT.month_aggregates: List<{
  month: (integer, integer)              // (year, month)

  // ═══ שעות — אגרגטור (③) כותב (סיכום מכל period_month_records באותו חודש) ═══
  total_regular_hours: decimal           // סה"כ regular hours מכל התקופות
  total_ot_hours: decimal                // סה"כ OT
  total_work_days: integer               // סה"כ ימי עבודה
  total_shifts: integer                  // סה"כ משמרות

  // ═══ היקף משרה — מודול היקף משרה (⑤) כותב ═══
  full_time_hours_base: decimal          // מהגדרות (ברירת מחדל 182)
  raw_scope: decimal                     // total_regular_hours ÷ full_time_hours_base
  job_scope: decimal                     // min(raw_scope, 1.0)
}>
```

### seniority_monthly

```
SSOT.seniority_monthly: List<{
  month: (integer, integer)              // (year, month)
  worked: boolean                        // עבד לפחות יום אחד בחודש?
  at_defendant_cumulative: integer       // חודשי ותק מצטברים אצל נתבע
  at_defendant_years_cumulative: decimal // at_defendant_cumulative ÷ 12
  total_industry_cumulative: integer     // prior + at_defendant_cumulative
  total_industry_years_cumulative: decimal // total_industry_cumulative ÷ 12
}>

SSOT.seniority_totals: {
  input_method: "prior_plus_pattern" | "total_plus_pattern" | "matash_pdf"
  prior_seniority_months: integer        // חודשי ותק לפני הנתבע
  at_defendant_months: integer           // סה"כ חודשי ותק אצל נתבע
  at_defendant_years: decimal
  total_industry_months: integer         // סה"כ ותק ענפי
  total_industry_years: decimal

  // שיטה ג — רשומות מת"ש (לתצוגה וביקורת)
  matash_records: List<{
    employer_name: string
    start_date: date
    end_date: date
    duration: Duration                   // מחושב
    industry: string
    is_defendant: boolean
    is_relevant_industry: boolean
    months_counted: integer
  }>?
}
```

---

## שכבה 5 — תוצאות זכויות (פאזה 2)

### rights_results

```
SSOT.rights_results: {

  // ═══ שעות נוספות (pricing — stage 8) ═══
  overtime: {
    // claim_amount + pricing_breakdown כבר ב-shifts[]
    // כאן רק אגרגציות
    total_claim: decimal                 // סה"כ ₪
    monthly_breakdown: List<{
      month: (integer, integer)
      claim_amount: decimal
      regular_hours: decimal
      ot_hours: decimal
      shifts_count: integer
    }>
  }

  // ═══ דמי חגים ═══
  holidays: {
    per_year: List<{
      year: integer
      met_threshold: boolean
      employment_days_in_year: integer
      holidays: List<{
        name: string                     // "ראש השנה א'"
        hebrew_date: string              // "א' תשרי"
        gregorian_date: date
        employed_on_date: boolean
        day_of_week: string
        week_type: 5 | 6                 // של השבוע הספציפי של החג!
        is_rest_day: boolean
        is_eve_of_rest: boolean          // output מחושב לתצוגה (day_of_week == eve_of_rest(rest_day))
        excluded: boolean
        exclude_reason: string?
        entitled: boolean
        day_value: decimal?              // salary_daily מ-period_month_records ליום החג
        claim_amount: decimal?
      }>
      election_day_entitled: boolean
      total_entitled_days: integer
      total_claim: decimal
    }>
    grand_total_days: integer
    grand_total_claim: decimal
  }

  // ═══ חופשה ═══
  vacation: null                         // טרם הוגדר

  // ═══ פיצויי פיטורין ═══
  severance: null                        // טרם הוגדר

  // ═══ פנסיה ═══
  pension: null                          // טרם הוגדר

  // ═══ הבראה ═══
  recreation: null                       // טרם הוגדר

  // ═══ השלמת שכר ═══
  salary_completion: null                // טרם הוגדר

  // ═══ דמי נסיעות ═══
  travel: null                           // טרם הוגדר
  // הערה: שינוי תעריף נסיעות (מהמאגר) = גבול תקופה בפירוט הזכות.
  // הזכות שולפת travel_allowance לפי חודש ומקבצת חודשים רצופים עם אותו תעריף.

  // ═══ זכויות נוספות ═══
  // הוספת זכות חדשה:
  // 1. הוסף null placeholder כאן (e.g., "new_right: null")
  // 2. הגדר את הלוגיקה בסקיל ייעודי
  // 3. הוסף right_limitation_mapping ב-settings.json
  // 4. הזכות קוראת מ-SSOT (period_month_records, daily_records, seniority, מאגרים סטטיים)
  //    וכותבת לכאן. פורמט חופשי — כל זכות מגדירה את ה-schema שלה.
  // 5. זכות שתלויה בנתון מסד (כמו תעריף נסיעות/ערך הבראה): lookup לפי חודש,
  //    קיבוץ חודשים רצופים עם אותו ערך ל"תקופות תצוגה".
}
```

---

## שכבה 6 — התיישנות (פאזה 3 — פוסט-פרוססינג)

```
SSOT.limitation_results: {

  // ═══ חלונות לכל סוג התיישנות ═══
  windows: List<{
    type_id: string                      // "general", "vacation"
    type_name: string                    // "התיישנות כללית", "התיישנות חופשה"
    base_window_start: date              // ללא הקפאות
    effective_window_start: date         // עם הקפאות
    freeze_periods_applied: List<{       // הקפאות שהשפיעו
      name: string
      start_date: date
      end_date: date
      days: integer
      duration: Duration                 // מחושב
    }>
  }>

  // ═══ תוצאות לכל זכות ═══
  per_right: Map<string, {
    limitation_type_id: string           // סוג ההתיישנות שחל
    full_amount: decimal                 // סכום מלא לפני התיישנות
    claimable_amount: decimal            // סכום אחרי סינון
    excluded_amount: decimal             // סכום שהתיישן
    claimable_duration: Duration         // מ-effective_window_start עד filing_date
    excluded_duration: Duration?         // מתחילת עבודה עד effective_window_start (אם רלוונטי)
    partial_months: List<{               // חודשים חצויים
      month: (integer, integer)
      full_amount: decimal
      fraction: decimal                  // e.g., 18/30
      claimable_amount: decimal
    }>?
  }>

  // ═══ נתוני תצוגה — ציר זמן ═══
  timeline_data: {
    employment_start: date
    employment_end: date
    filing_date: date
    limitation_windows: List<{
      type_id: string
      type_name: string
      base_window_start: date
      effective_window_start: date
      claimable_duration: Duration       // effective_window_start → filing_date
    }>
    freeze_periods: List<{
      name: string
      start_date: date
      end_date: date
      duration: Duration                 // מחושב
    }>
    work_periods: List<{
      start_date: date
      end_date: date
      duration: Duration                 // מחושב
    }>
    summary: {
      total_employment_days: integer
      claimable_days_general: integer
      excluded_days_general: integer
      total_freeze_days: integer
    }
  }
}
```

---

## שכבה 7 — ניכויים + סיכום (פאזה 3 — פוסט-פרוססינג)

```
SSOT.deduction_results: Map<string, {
  right_id: string
  calculated_amount: decimal             // מ-limitation (אחרי התיישנות)
  deduction_amount: decimal              // מ-input.deductions_input
  net_amount: decimal                    // calculated - deduction
  show_deduction: boolean                // deduction > 0?
  show_right: boolean                    // net > 0?
  warning: boolean                       // deduction ≥ calculated?
}>

// ═══ סיכום תביעה סופי (מוכן לתצוגה) ═══
SSOT.claim_summary: {
  total_before_limitation: decimal       // סה"כ כל הזכויות לפני התיישנות
  total_after_limitation: decimal        // סה"כ אחרי סינון התיישנות
  total_after_deductions: decimal        // סה"כ סופי אחרי ניכויים

  per_right: List<{
    right_id: string                     // e.g., "overtime"
    name: string                         // "שעות נוספות"
    full_amount: decimal                 // לפני התיישנות
    after_limitation: decimal            // אחרי התיישנות
    after_deductions: decimal            // אחרי ניכויים
    deduction_amount: decimal            // סכום הניכוי
    show: boolean                        // net > 0?
    limitation_type: string              // "general" | "vacation"
    limitation_excluded: decimal         // סכום שהתיישן
  }>

  employment_summary: {                  // מוכן לתצוגה (display מפורמטר Duration, פאזה 4)
    worker_name: string?                 // שם פרטי + משפחה (או null)
    defendant_name: string?              // שם המעביד (או null)
    total_duration_display: string       // "3 שנים, 4 חודשים ו-12 יום"
    worked_duration_display: string      // "3 שנים ו-2 חודשים"
    filing_date: date
    filing_date_display: string          // "19.2.2026"
  }
}
```

---

## שאילתות נפוצות — איך מגיעים למידע

### "מה המצב ביום 15.3.2024?"

```
daily = SSOT.daily_records[date=2024-03-15]
  → effective_period_id: "EP3"
  → is_work_day: true, is_rest_day: false
  → shift_templates: [{start_time: 07:00, end_time: 16:15}]
  → day_segments: [{00:00–17:30, "regular"}, {17:30–24:00, "eve_of_rest"}]  // אם שישי
  // day_segments = null אם OT pipeline טרם רץ

shifts = SSOT.shifts[date=2024-03-15]
  → [{id: "S001", start: 07:00, end: 16:15, net_hours: 8.75,
      regular_hours: 8.0, ot_tier1: 0.75, threshold: 8.0, ...}]

ep = SSOT.effective_periods[id="EP3"]
  → pattern: א'–ו' 06:00–14:00, salary: ₪42 שעתי

pmr = SSOT.period_month_records[ep="EP3", month=(2024,3)]
  → salary_hourly: 42.00, salary_daily: 336.00, minimum_applied: false

ma = SSOT.month_aggregates[month=(2024,3)]
  → job_scope: 0.923, total_regular_hours: 168

sen = SSOT.seniority_monthly[month=(2024,3)]
  → at_defendant_cumulative: 14, total_industry_years: 3.5
```

### "כמה שעות נוספות בינואר 2024?"

```
shifts = SSOT.shifts.filter(s => s.date.month == (2024,1))
  → sum(s.ot_tier1_hours + s.ot_tier2_hours)

// או מ-rights_results:
SSOT.rights_results.overtime.monthly_breakdown[(2024,1)]
  → { ot_hours: 24.5, claim_amount: 1225.00 }
```

### "מה הותק ב-15.6.2024?"

```
sen = SSOT.seniority_monthly.last(s => s.month <= (2024,6))
  → at_defendant_years_cumulative: 2.5, total_industry_years: 4.5
```

### "מה השכר השעתי ביום שבו חל חג הפסח 2024?"

```
holiday_date = 2024-04-23  // מקובץ סטטי
ep = SSOT.effective_periods.find(ep => ep.start <= holiday_date <= ep.end)
pmr = SSOT.period_month_records[ep.id, (2024,4)]
  → salary_hourly: 39.20, salary_daily: 313.60
```

---

## אנטי-פטרנים — טעויות שכבר נעשו

1. **week_type "דומיננטי" שנתי.** טעות: להשתמש ב-week_type הנפוץ ביותר בשנה לכל החגים. נכון: week_type של השבוע הספציפי של כל חג בנפרד.

2. **day_value אחיד לכל חגי השנה.** טעות: שכר יומי אחד לכל השנה. נכון: salary_daily מ-period_month_records לתאריך הספציפי של כל חג (כי שכר יכול להשתנות באמצע שנה).

3. **המצאת נוסחאות לזכויות לא מוגדרות.** טעות: לנחש איך מחושבת חופשה/פיצויים/פנסיה. נכון: לרשום "טרם הוגדר" ולשאול.

4. **stage 8 (pricing) בתוך צינור OT.** טעות: להריץ pricing ביחד עם stages 1–7. נכון: pricing תלוי בשכר שעתי שמחושב אחרי stages 1–7 → חייב לרוץ בזכויות.

5. **monthly_records בלבד לשכר.** טעות: רשומה חודשית אחת — לא מכסה שינוי שכר באמצע חודש. נכון: period_month_records (תקופה × חודש) — שתי רשומות לאותו חודש אם השכר השתנה.

6. **חישובים בפרונטאנד.** טעות: לשלוח start+end ולחשב duration ב-JS. נכון: Duration מספרי מחושב ע"י המארג, display strings נוצרים בפאזה 4 (פורמטר) — הפרונטאנד רק מציג.

7. **is_eve_of_rest כ-boolean סטטי ב-daily_records.** טעות: לשמור boolean "ערב מנוחה?" ברמת היום. נכון: OT stage 3.5 כותב `day_segments` עם סוגי קטעים (regular/eve_of_rest/rest). OT stage 4 קובע לכל *משמרת* אם היא ערב מנוחה לפי כלל ≥2h חפיפה. משמרת בוקר בערב שבת ≠ משמרת לילה בערב שבת — ה-boolean לא תופס את זה.

8. **shift_templates חסרות ב-daily_records.** טעות: לשמור רק is_work_day בלי את הדפוס. נכון: המארג כותב shift_templates + break_templates לכל יום. OT stage 1 צורך אותן כדי ליצור משמרות קונקרטיות (datetime).

---

## מבנה הקובץ .case

```
{
  "version": "1.0",
  "input": { ... },                      // SSOT.input בלבד — מקור אמת
  "cache": {                             // אופטימיזציה — אפשר למחוק בכל רגע
    "settings_hash": "a3f8c2...",        // hash של settings.json בזמן החישוב
    "computed_at": "2025-02-19T14:30:00",// מתי חושב
    "ssot": { ... }                      // העתק מלא של שכבות 1–7
  }
}
```

### מחזור חיים

```
פותח תיק:
  → קורא .case מדיסק
  → cache קיים + settings_hash תואם?
    כן → SSOT = input + cache.ssot, מציג מיד
    לא → SSOT = input בלבד, שכבות 1-7 ריקות
       → מציג "תוצאות לא עדכניות — יש לחשב מחדש"

לוחץ "חשב":
  → מריץ צינור מלא מ-input + settings → SSOT מלא בזיכרון
  → שומר input + cache חדש (עם hash נוכחי) לקובץ

הגדרות השתנו (settings.json):
  → hash משתנה → בפתיחה הבאה cache לא תואם → דורש חישוב מחדש

שמירה אוטומטית (כל X זמן + ביציאה):
  → כותבת input + cache (אם קיים) לדיסק

שמירה בלחיצת "חשב":
  → כותבת input + cache חדש לדיסק
```

### עקרון: ה-cache הוא לא מקור מידע

- שום מודול חישוב לא קורא מה-cache
- ה-cache משרת רק את התצוגה (פתיחה מיידית בלי המתנה)
- מחיקת cache = תקין. פשוט צריך לחשב מחדש
- ה-cache הוא העתק מלא של SSOT שכבות 1–7 — לא תקציר, לא חלקי

## מבנה settings.json

```
{
  "ot_config": {
    "weekly_cap": 42,
    "threshold_5day": 8.4,
    "threshold_6day": 8.0,
    "threshold_eve_rest": 7.0,
    "threshold_night": 7.0,
    "tier1_max_hours": 2
  },
  "full_time_hours_base": 182,
  "limitation_config": {
    "limitation_types": [
      { "id": "general", "name": "התיישנות כללית", "window_years": 7 },
      { "id": "vacation", "name": "התיישנות חופשה", "window_calc": "3_plus_current" }
    ],
    "freeze_periods": [
      { "id": "war_2023", "name": "הקפאת מלחמת התקומה", "start_date": "2023-10-07", "end_date": "2024-04-06", "days": 183 }
    ],
    "right_limitation_mapping": {
      "overtime": "general",
      "holidays": "general",
      "vacation": "vacation",
      "severance": "general",
      "pension": "general",
      "recreation": "general",
      "salary_completion": "general",
      "travel": "general"
    }
  }
}
```
