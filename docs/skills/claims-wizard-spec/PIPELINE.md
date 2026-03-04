# סדר הרצה מלא — מתזמר הצינור

> **חובה:** קרא סקיל זה במלואו לפני כל עבודה על הפרויקט.
> לא לכתוב קוד, לא ליצור קבצים, לא להתחיל משימה — לפני שקראת את הסקיל הרלוונטי.
> מסמך זה הוא חלק מהמפרט המלא:
> - `claims-wizard-spec/SKILL.md` — נהלים ומוסכמות
> - `claims-wizard-spec/PIPELINE.md` ← אתה כאן
> - `claims-wizard-spec/ARCHITECTURE.md` — ארכיטקטורה
> - מבנה נתונים: `ssot/SKILL.md`

## מטרה

מסמך זה מגדיר את סדר ההרצה המדויק של כל מודולי המערכת, מקלט גולמי ועד SSOT מלא מוכן לתצוגה. פונקציה אחת (`run_full_pipeline`) מתזמרת את הכל.

---

## עקרונות

1. **סדר קבוע, אפס הסתעפויות.** הצינור רץ תמיד באותו סדר. אין "אם יש שכר חודשי תעשה X".
2. **כל מודול מקבל פרמטרים, לא ניגש ל-SSOT.** רק המתזמר קורא מ-SSOT וכותב אליו. המודולים הם פונקציות טהורות.
3. **כישלון ולידציה במארג = עצירה.** שאר השגיאות לא אמורות לקרות אם הקלט תקין.
4. **ותק מקבילי ל-OT.** אין תלות ביניהם. בקוד סינכרוני הסדר לא משנה, אבל אין לבנות תלות.
5. **המרת שכר והיקף משרה — מקביליים.** שניהם תלויים באגרגטור, לא אחד בשני.
6. **כל זכויות פאזה 2 מקביליות.** אין תלות בין זכות לזכות.

---

## שרטוט תלויות

```
SSOT.input
    │
    ├─→ ⓪ מתרגם הדפוסים
    │       │
    │       ▼
    ├─→ ① מארג ←── employment_periods, salary_tiers, rest_day
    │       │
    │       ├─→ ② OT stages 1–7 ←── rest_day, district, shabbat_times, ot_config
    │       │       │
    │       │       ▼
    │       │   ③ אגרגטור
    │       │       │
    │       │       ├─→ ④ המרת שכר ←── minimum_wage
    │       │       │
    │       │       └─→ ⑤ב היקף משרה ←── job_scope_config
    │       │
    │       └─→ ⑤א ותק ענפי ←── seniority_input, industry
    │                           (מקבילי ל-②, אין תלות)
    │
    ▼
[ SSOT מלא אחרי פאזה 1 ]
    │
    ├─→ שעות נוספות (stage 8) ←── right_toggles
    ├─→ דמי חגים ←── holiday_dates, rest_day
    ├─→ (חופשה — טרם הוגדר)
    ├─→ (פיצויים — טרם הוגדר)
    ├─→ (פנסיה — טרם הוגדר)
    ├─→ (הבראה — טרם הוגדר)
    ├─→ (נסיעות — טרם הוגדר)
    └─→ (השלמת שכר — טרם הוגדר)
    │
    ▼
[ rights_results ]
    │
    ├─→ ① התיישנות ←── limitation_config, filing_date
    │       │
    ├─→ ② ניכויים ←── deductions_input
    │       │
    └─→ ③ סיכום תביעה
    │
    ▼
[ פורמטר Duration — ממלא display בכל אובייקט Duration ]
    │
    ▼
  SSOT מוכן לתצוגה
```

---

## סדר ההרצה המפורט

### פאזה 0 — קלט

כבר קיים ב-`SSOT.input`. אין מה להריץ. המתזמר קורא ממנו.

---

### פאזה 1 — עיבוד ראשוני

#### שלב ⓪: מתרגם הדפוסים

```
קלט:
  SSOT.input.work_patterns

פלט:
  work_patterns_resolved — רשימת דפוסים בפורמט רמה א
  (default_shifts, default_breaks, per_day, daily_overrides)

לוגיקה:
  לכל דפוס ב-work_patterns:
    אם רמה א (שבועי פשוט) → העתק כמו שהוא
    אם רמה ב (מחזורי) → פריסת המחזור על ציר הזמן → רמה א
    אם רמה ג (סטטיסטי) → ייצור מחזור סינתטי → פריסה → רמה א
  
  התוצאה: רשימה של work_patterns שכולם בפורמט רמה א.
  המארג לא יודע שהיה תרגום.

שגיאות:
  דפוס לא תקין → שגיאה עם ציון הדפוס הבעייתי.
  עצירה: כן — בלי דפוסים תקינים המארג לא יכול לרוץ.

סקיל: /mnt/skills/user/pattern-translator/SKILL.md
```

#### שלב ①: מארג

```
קלט:
  SSOT.input.employment_periods
  work_patterns_resolved (מ-⓪)
  SSOT.input.salary_tiers
  SSOT.input.rest_day

פלט → SSOT:
  effective_periods
  daily_records
  employment_gaps
  total_employment

לוגיקה:
  שלב 1: ולידציה — כיסוי מלא חובה
  שלב 2: sweep line → תקופות אטומיות → מיזוג רצופים
  שלב 3: פירוט יומי (shift_templates, break_templates לכל יום)
  שלב 4: פערים + סיכום תקופת העסקה + Duration מספרי

שגיאות:
  ולידציה נכשלה → רשימת שגיאות מפורטת.
  עצירה: כן — בלי תקופות אפקטיביות שום דבר לא יכול לרוץ.

סקיל: /mnt/skills/user/weaver/SKILL.md
```

#### שלב ②: ספירת שעות (OT stages 1–7)

```
קלט:
  SSOT.daily_records (מ-①)
  SSOT.input.rest_day
  SSOT.input.district
  static_data.shabbat_times (CSV למחוז)
  settings.ot_config

פלט → SSOT:
  shifts — רשימת משמרות עם שעות + דרגות + חלון מנוחה (בלי ₪)
  weeks — רשימת שבועות עם week_type + OT שבועי + חלון מנוחה

לוגיקה:
  Stage 1: הרכבת משמרות מ-shift_templates (פער ≤3h = משמרת אחת)
  Stage 2: שיוך משמרת ליום ושבוע (majority rule)
  Stage 3: סיווג שבוע (5/6 ימים)
  Stage 3.5: כתיבת day_segments ל-daily_records (regular/eve_of_rest/rest)
  Stage 4: קביעת סף יומי למשמרת (7/8/8.4)
  Stage 5: OT יומי (tier 1 = 2 שעות ראשונות, tier 2 = השאר)
  Stage 6: OT שבועי (מעל 42 regular → ייחוס כרונולוגי)
  Stage 7: מיקום חלון מנוחה 36h (אופטימיזציה)

שגיאות:
  לא צפויות — הקלט כבר עבר ולידציה במארג.

סקיל: /mnt/skills/user/overtime-calculation/SKILL.md
```

#### שלב ⑤א: ותק ענפי (מקבילי ל-②)

```
קלט:
  SSOT.daily_records (מ-①)
  SSOT.input.seniority_input
  SSOT.input.industry

פלט → SSOT:
  seniority_monthly — סדרה חודשית מצטברת
  seniority_totals — סיכומי ותק

לוגיקה:
  לפי שיטת הקלט (א/ב/ג):
    א: ותק קודם + ספירת חודשי עבודה מ-daily_records
    ב: הזנה ידנית → כתיבה ישירה
    ג: חילוץ מ-PDF מת"ש → ספירה
  כל חודש: worked = עבד לפחות יום אחד? (בינארי)

תלויות: רק ① (מארג). לא תלוי ב-② (OT), לא ב-③ (אגרגטור).

סקיל: /mnt/skills/user/seniority/SKILL.md
```

#### שלב ③: אגרגציה

```
קלט:
  SSOT.shifts (מ-②)
  SSOT.effective_periods (מ-①)
  SSOT.daily_records (מ-①)

פלט → SSOT:
  period_month_records — שדות שעות בלבד:
    work_days_count, shifts_count
    total_regular_hours, total_ot_hours
    avg_regular_hours_per_day, avg_regular_hours_per_shift
  month_aggregates — שדות שעות בלבד:
    total_regular_hours, total_ot_hours
    total_work_days, total_shifts

לוגיקה:
  לכל (effective_period × חודש קלנדרי):
    סכום shifts באותה תקופה ובאותו חודש
    חישוב ממוצעים
  לכל חודש קלנדרי:
    סכום מכל ה-period_month_records באותו חודש

הערה: האגרגטור לא ממציא מידע. הוא רק מסכם.
       period_month_records = ברמת תקופה×חודש
       month_aggregates = ברמת חודש (חוצה תקופות)

טרם הוגדר כסקיל עצמאי. הלוגיקה מפוזרת ב:
  - /mnt/skills/user/ssot/SKILL.md (מבנה נתונים, שכבות 3-4)
  - /mnt/skills/user/salary-conversion/SKILL.md (צורך period_month_records)
  - /mnt/skills/user/job-scope/SKILL.md (צורך month_aggregates)
```

#### שלב ④: המרת שכר

```
קלט:
  SSOT.period_month_records (שדות שעות מ-③)
  SSOT.effective_periods (מדרגות שכר מ-①)
  static_data.minimum_wage (CSV)

פלט → SSOT:
  period_month_records — שדות שכר נוספים:
    salary_gross_amount, minimum_wage_value, minimum_applied, minimum_gap
    effective_amount, salary_hourly, salary_daily, salary_monthly

לוגיקה:
  לכל רשומה ב-period_month_records:
    1. נרמול לברוטו (נטו × 1.12 אם צריך)
    2. בדיקת מינימום (lookup לפי חודש, השוואה לפי סוג הקלט)
    3. המרה לכל הסוגים דרך שעתי כציר

סקיל: /mnt/skills/user/salary-conversion/SKILL.md
```

#### שלב ⑤ב: היקף משרה

```
קלט:
  SSOT.month_aggregates (total_regular_hours מ-③)
  settings.full_time_hours_base (ברירת מחדל 182)

פלט → SSOT:
  month_aggregates — שדות job_scope:
    full_time_hours_base, raw_scope, job_scope (מוגבל ל-1.0)

לוגיקה:
  לכל חודש: job_scope = min(total_regular_hours / base, 1.0)

סקיל: /mnt/skills/user/job-scope/SKILL.md
```

---

### פאזה 2 — חישוב זכויות

כל הזכויות מקביליות. אין תלות בין זכות לזכות.

#### שעות נוספות (OT stage 8 — תמחור)

```
קלט:
  SSOT.shifts (מ-②, שעות + דרגות + חלון מנוחה)
  SSOT.period_month_records.salary_hourly (מ-④)
  SSOT.input.right_toggles.overtime

פלט → SSOT:
  shifts — ממלא claim_amount + pricing_breakdown בכל משמרת
  rights_results.overtime — סיכומים חודשיים + סה"כ

לוגיקה:
  לכל משמרת, לכל שעה: tier × rest × salary_hourly → סכום
  סכום התביעה = ההפרש בלבד (25%/50%/75%/100%, לא 125%/150%...)
  טוגל "מעביד שילם פרמיית מנוחה" → מפחית את חלק המנוחה

סקיל: /mnt/skills/user/overtime-calculation/SKILL.md (חלק stage 8)
```

#### דמי חגים

```
קלט:
  SSOT.weeks (מ-②)
  SSOT.daily_records (מ-①)
  SSOT.effective_periods (מ-①)
  SSOT.period_month_records.salary_daily (מ-④)
  static_data.holiday_dates (CSV)
  SSOT.input.rest_day

פלט → SSOT:
  rights_results.holidays

לוגיקה:
  לכל שנה קלנדרית:
    בדיקת סף 1/10
    לכל חג: week_type של השבוע הספציפי, סינון (מנוחה, ערב מנוחה ב-5 ימים)
    ערך יום = salary_daily מ-period_month_records ליום החג

סקיל: /mnt/skills/user/holidays/SKILL.md
```

#### זכויות מוגדרות

##### דמי הבראה
סקיל: docs/skills/recreation/SKILL.md

קלט: employment_periods, seniority_totals.prior_seniority_months, month_aggregates, industry
פלט: rights_results.recreation

**חשוב:** מודול זה חייב לרוץ לפני פיצויי פיטורין בפאזה 2.
הסיבה: ענף ניקיון — פיצויי פיטורין כוללים רכיב הבראה שנתי שמחושב כאן.
זוהי תלות מכוונת, לא טעות. אל תשנה את הסדר.

##### פיצויי פיטורין
סקיל: docs/skills/severance/SKILL.md

קלט: termination_reason, industry, period_month_records, month_aggregates,
      effective_periods, total_employment_months, actual_deposits, shifts,
      rights_results.recreation (לענף ניקיון בלבד — חובה שיחושב קודם)
פלט: rights_results.severance

#### זכויות נוספות (טרם הוגדרו)

חופשה, פנסיה, נסיעות, השלמת שכר — טרם הוגדרו.
כשיוגדרו, כל זכות:
  1. תקבל סקיל ייעודי
  2. תקרא מ-SSOT (period_month_records, daily_records, seniority, מאגרים סטטיים)
  3. תכתוב ל-rights_results.{right_id}
  4. תרוץ בפאזה 2, בסדר שיוגדר בסקיל שלה

---

### פאזה 3 — פוסט-פרוססינג

סדר חובה. כל שלב תלוי בקודמו.

#### שלב ①: התיישנות

```
קלט:
  SSOT.rights_results (מפאזה 2)
  settings.limitation_config
  SSOT.input.filing_date

פלט → SSOT:
  limitation_results — חלונות + תוצאות לכל זכות + נתוני ציר זמן

לוגיקה:
  חישוב חלון אפקטיבי (עם הקפאות) לכל סוג התיישנות
  סינון תוצאות: מה בתוך החלון, מה בחוץ
  חודשים חצויים: שבר עשרוני

סקיל: /mnt/skills/user/limitation/SKILL.md
```

#### שלב ②: ניכויי הפרשות

```
קלט:
  SSOT.limitation_results (מ-①)
  SSOT.input.deductions_input

פלט → SSOT:
  deduction_results — לכל זכות: calculated, deduction, net, show

לוגיקה:
  לכל זכות: net = calculated - deduction
  ניכוי ≥ חישוב → אזהרה, הזכות לא מוצגת
  ניכוי = 0 → שורת ניכוי לא מוצגת

סקיל: /mnt/skills/user/employer-deductions/SKILL.md
```

#### שלב ③: סיכום תביעה

```
קלט:
  SSOT.limitation_results (מ-①)
  SSOT.deduction_results (מ-②)
  SSOT.total_employment (מפאזה 1)
  SSOT.input.personal_details
  SSOT.input.defendant_details
  SSOT.input.filing_date

פלט → SSOT:
  claim_summary — סיכום סופי:
    total_before_limitation, total_after_limitation, total_after_deductions
    per_right: רשימה עם כל הסכומים לכל זכות
    employment_summary: שמות, תאריכים

לוגיקה:
  אגרגציה בלבד. אפס חישובים חדשים.

סקיל: מוגדר ב-/mnt/skills/user/ssot/SKILL.md (שכבה 7)
```

---

### פאזה 4 — פורמוט תצוגה

#### פורמטר Duration

```
קלט:
  SSOT (כל אובייקט Duration שיש בו ערכים מספריים אבל display ריק)

פלט → SSOT:
  ממלא שדה display בכל אובייקט Duration:
    effective_periods[].duration.display
    employment_gaps[].duration.display
    total_employment.total_duration.display
    total_employment.worked_duration.display
    total_employment.gap_duration.display
    limitation_results.*.duration.display
    claim_summary.employment_summary.*_display

לוגיקה:
  מספר ימים → "X שנים, Y חודשים ו-Z ימים"
  פונקציית עזר טהורה. אפס לוגיקה עסקית.

סקיל: מוגדר ב-/mnt/skills/user/ssot/SKILL.md (פאזה 4)
```

---

## טיפול בשגיאות

```
כלל: שגיאה = עצירה + דיווח. לא ממשיכים עם נתונים חלקיים.

מתרגם הדפוסים:
  דפוס לא תקין → עצירה לפני המארג

מארג (ולידציה):
  כיסוי חסר / חפיפות / טווח לא תקין → עצירה. רשימת שגיאות ל-UI.

שאר המודולים:
  לא אמורות להיות שגיאות אם הקלט עבר ולידציה.
  אם בכל זאת קורה → עטיפה ב-PipelineError עם ציון הפאזה והמודול.

מבנה שגיאה:
  PipelineError {
    phase: "weaver" | "ot_pipeline" | "salary_conversion" | ...
    module: string
    errors: List<{
      type: string          // "uncovered_range", "invalid_range", ...
      message: string       // הודעה בעברית ל-UI
      details: object       // פרטים טכניים
    }>
  }

תגובת ה-UI:
  שגיאת ולידציה → מציג שגיאות, מבקש תיקון
  שגיאה פנימית → מציג "שגיאה בחישוב, פנה לתמיכה" + לוג טכני
```

---

## סיכום: מי קורא למי

```
run_full_pipeline
  ├── pattern_translator.translate()
  ├── weaver.run()                    → כותב 4 שדות ל-SSOT
  ├── ot_pipeline.run_stages_1_7()    → כותב 2 שדות ל-SSOT
  ├── seniority.compute()             → כותב 2 שדות ל-SSOT
  ├── aggregator.run()                → כותב 2 שדות ל-SSOT
  ├── salary_conversion.run()         → משלים שדות ב-period_month_records
  ├── job_scope.run()                 → משלים שדות ב-month_aggregates
  ├── ot_pipeline.run_stage_8()       → משלים שדות ב-shifts + כותב rights_results
  ├── holidays.compute()              → כותב rights_results
  ├── (זכויות נוספות — עתידי)
  ├── limitation.compute()            → כותב limitation_results
  ├── deductions.compute()            → כותב deduction_results
  ├── summary.compute()               → כותב claim_summary
  └── duration_formatter.fill_all()   → משלים display בכל Duration
```
