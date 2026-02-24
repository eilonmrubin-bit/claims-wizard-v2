---
name: aggregator
description: |
  Aggregator (אגרגטור) module for the Claims Wizard (אשף התביעות).
  Aggregates individual shifts (from OT pipeline) into period×month summaries
  and monthly totals. Use this skill whenever working on period_month_records,
  month_aggregates, or any code that summarizes shift-level data to monthly level.
  ALWAYS read this skill before touching any aggregation code.
---

# אגרגטור — סיכום משמרות לרמה חודשית

## אזהרות קריטיות

1. **האגרגטור לא ממציא מידע.** הוא מקבץ ומסכם בלבד. אין לוגיקה עסקית, אין כללים משפטיים.
2. **ממוצעים נפרדים לכל תקופה × חודש.** אם השכר השתנה באמצע חודש — שתי רשומות נפרדות, כל אחת עם הממוצעים שלה. לעולם לא לערבב שעות משתי תקופות לחישוב ממוצע אחד.
3. **ספירת ימי עבודה — מהמשמרות, לא מהרשומות היומיות.** is_work_day ברשומה היומית הוא הדפוס התיאורטי. ימי עבודה בפועל = ימים שבהם יש לפחות משמרת אחת.
4. **אפס עיגול.** כל הערכים עשרוניים. לא מעגלים בשום שלב ביניים.
5. **חלוקה באפס — לא קורה.** אם אין משמרות בתקופה × חודש, אין רשומה. אבל אם בכל זאת מגיעים לחלוקה באפס — הממוצע הוא 0.

---

## מיקום בצינור

```
② OT stages 1–7
       │
       │ shifts (משמרות מעובדות עם שעות + דרגות)
       ▼
┌─────────────────────────┐
│  ③ אגרגטור              │
│                         │
│  קיבוץ 1: תקופה × חודש │ → period_month_records (שדות שעות)
│  קיבוץ 2: חודש          │ → month_aggregates (שדות שעות)
└─────────────────────────┘
       │
       ├──→ ④ המרת שכר (צורכת period_month_records)
       └──→ ⑤ב היקף משרה (צורך month_aggregates)
```

---

## קלט

```
shifts — רשימת משמרות מצינור OT. כל משמרת כוללת:
  effective_period_id   → לאיזו תקופה אטומית שייכת
  assigned_day          → באיזה יום קלנדרי
  regular_hours         → שעות רגילות (דרגה 0, אחרי שלבים 5+6)
  ot_tier1_hours        → שעות נוספות 125%
  ot_tier2_hours        → שעות נוספות 150%

effective_periods — רשימת תקופות אטומיות (לצורך מיפוי תקופה → חודשים)
```

---

## פלט

### קיבוץ 1: period_month_records (שדות שעות)

רשומה אחת לכל (תקופה אטומית × חודש קלנדרי) שבה יש לפחות משמרת אחת.

```
period_month_records: List<{
  effective_period_id: string
  month: (year, month)

  work_days_count: integer              // ימים שונים שבהם יש לפחות משמרת אחת
  shifts_count: integer                 // מספר משמרות
  total_regular_hours: decimal          // סך שעות רגילות
  total_ot_hours: decimal               // סך שעות נוספות (tier1 + tier2)
  avg_regular_hours_per_day: decimal    // total_regular_hours / work_days_count
  avg_regular_hours_per_shift: decimal  // total_regular_hours / shifts_count
}>
```

### קיבוץ 2: month_aggregates (שדות שעות)

רשומה אחת לכל חודש קלנדרי שבו יש לפחות משמרת אחת. סיכום חוצה תקופות.

```
month_aggregates: List<{
  month: (year, month)

  total_regular_hours: decimal          // סך שעות רגילות מכל התקופות
  total_ot_hours: decimal               // סך שעות נוספות מכל התקופות
  total_work_days: integer              // סך ימי עבודה מכל התקופות
  total_shifts: integer                 // סך משמרות מכל התקופות
}>
```

---

## אלגוריתם

### קיבוץ 1 — תקופה × חודש

```
function aggregateByPeriodMonth(shifts):
  buckets = Map<(effective_period_id, year, month), List<shift>>

  // שלב 1: קיבוץ
  for shift in shifts:
    key = (shift.effective_period_id, shift.assigned_day.year, shift.assigned_day.month)
    buckets[key].append(shift)

  // שלב 2: סיכום
  result = []
  for (ep_id, year, month), bucket_shifts in buckets:
    work_days = countDistinct(s.assigned_day for s in bucket_shifts)
    shifts_count = len(bucket_shifts)
    total_regular = sum(s.regular_hours for s in bucket_shifts)
    total_ot = sum(s.ot_tier1_hours + s.ot_tier2_hours for s in bucket_shifts)

    result.append({
      effective_period_id: ep_id,
      month: (year, month),
      work_days_count: work_days,
      shifts_count: shifts_count,
      total_regular_hours: total_regular,
      total_ot_hours: total_ot,
      avg_regular_hours_per_day: total_regular / work_days,
      avg_regular_hours_per_shift: total_regular / shifts_count,
    })

  return result
```

### קיבוץ 2 — חודש

```
function aggregateByMonth(period_month_records):
  buckets = Map<(year, month), List<pmr>>

  for pmr in period_month_records:
    buckets[pmr.month].append(pmr)

  result = []
  for (year, month), pmrs in buckets:
    result.append({
      month: (year, month),
      total_regular_hours: sum(p.total_regular_hours for p in pmrs),
      total_ot_hours: sum(p.total_ot_hours for p in pmrs),
      total_work_days: sum(p.work_days_count for p in pmrs),
      total_shifts: sum(p.shifts_count for p in pmrs),
    })

  return result
```

### נקודת כניסה

```
function runAggregator(shifts, effective_periods):
  pmr = aggregateByPeriodMonth(shifts)
  ma = aggregateByMonth(pmr)
  return AggregatorResult(period_month_records=pmr, month_aggregates=ma)
```

---

## מקרי קצה

### 1. חודש מפוצל בין שתי תקופות אטומיות

```
תקופה א: 01.03 – 15.03 (שכר 40 ש"ח)
תקופה ב: 16.03 – 31.03 (שכר 45 ש"ח)

→ שתי רשומות ב-period_month_records לחודש מרץ:
  (תקופה א, מרץ): 11 ימי עבודה, 88 שעות רגילות, ממוצע 8 שעות ליום
  (תקופה ב, מרץ): 11 ימי עבודה, 88 שעות רגילות, ממוצע 8 שעות ליום

→ רשומה אחת ב-month_aggregates:
  (מרץ): 22 ימי עבודה, 176 שעות רגילות

המרת שכר תשתמש ברשומות הנפרדות.
היקף משרה ישתמש בסיכום.
```

### 2. תקופה שמתחילה באמצע חודש

```
תקופת העסקה מתחילה ב-20 לחודש.

→ period_month_records: 8 ימי עבודה בחודש הראשון (במקום ~22)
→ הממוצעים מחושבים מהנתונים שיש — לא "מנרמלים" לחודש מלא
→ המרת שכר תקבל ממוצע שעות ליום תקין,
   כי גם 8 ימים × ממוצע = סך שעות נכון
```

### 3. כמה משמרות ביום אחד

```
יום עם שתי משמרות: 06:00-14:00 ו-16:00-22:00

→ work_days_count = 1 (יום אחד, שתי משמרות)
→ shifts_count = 2
→ total_regular_hours = סכום regular_hours משתי המשמרות
→ avg_regular_hours_per_day = סך שעות / 1
→ avg_regular_hours_per_shift = סך שעות / 2
```

### 4. חודש ללא משמרות

```
חודש שבו העובד מועסק אבל אין משמרות (לא עבד בפועל).

→ אין רשומה ב-period_month_records לחודש הזה
→ אין רשומה ב-month_aggregates לחודש הזה
→ המרת שכר: אין מה להמיר (אין שעות)
→ היקף משרה: 0 שעות / 182 = 0% (רשומה עם job_scope = 0)
```

### 5. משמרת ששויכה ליום בחודש אחר

```
משמרת שהתחילה ב-31.03 בלילה ורוב שעותיה ב-01.04.
צינור OT שייך אותה ל-01.04 (כלל הרוב).

→ המשמרת נספרת באפריל, לא במרץ
→ האגרגטור משתמש ב-assigned_day, לא בתאריך ההתחלה
```

---

## מה האגרגטור לא עושה

- **לא ממלא שדות שכר.** זו אחריות המרת שכר (④).
- **לא ממלא שדות היקף משרה.** זו אחריות מודול היקף משרה (⑤ב).
- **לא מחשב שעות נוספות.** זו אחריות צינור OT (②).
- **לא יוצר רשומות לחודשים ריקים.** אם אין משמרות — אין רשומה. מודול היקף משרה אחראי לטפל בזה.
- **לא מגע ברשומות היומיות.** הוא קורא רק מ-shifts.

---

## יחס לסקילים אחרים

```
← צורך מ:
  shifts (צינור OT, שלבים 1-7)
  effective_periods (מארג)

→ נצרך ע"י:
  המרת שכר — period_month_records (שדות שעות)
  היקף משרה — month_aggregates (שדות שעות)
```

---

## אנטי-פטרנים

1. **לא לערבב תקופות בממוצע.** אם בחודש יש שתי תקופות, כל אחת מקבלת ממוצע בנפרד. ממוצע משותף יתן מספר חסר משמעות להמרת שכר.
2. **לא לספור ימי עבודה מ-daily_records.** is_work_day הוא הדפוס התיאורטי. ימי עבודה בפועל = ימים שבהם יש משמרת ב-shifts.
3. **לא ליצור רשומות לחודשים ריקים.** אין משמרות = אין רשומה.
4. **לא לעגל.** כל הערכים עשרוניים, בלי עיגול.
5. **לא להשתמש ב-shift.date.** להשתמש ב-shift.assigned_day (שיוך לפי כלל הרוב מצינור OT).
