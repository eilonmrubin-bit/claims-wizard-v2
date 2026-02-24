---
name: static-data
description: |
  Static data files and system settings for the Claims Wizard (אשף התביעות).
  Defines the exact schema for every CSV file, the settings.json structure,
  and the generation scripts for computed data (shabbat times, holiday dates).
  ALWAYS read this skill before creating, editing, or loading any static data file.
  This skill does NOT replace module-specific skills — it complements them.
  For shabbat_times calculation details, see overtime-calculation skill §7.3–7.5.
  For holiday eligibility logic, see holidays skill.
  For minimum wage comparison logic, see salary-conversion skill.
---

# נתונים סטטיים והגדרות — Static Data & Settings

> **חובה:** קרא סקיל זה לפני כל עבודה על קבצי נתונים סטטיים או settings.json.

## עקרונות

1. **כל קובץ סטטי הוא טבלת lookup.** שורה = ערכים שתקפים מתאריך מסוים. שליפה: "תן לי את השורה עם effective_date ≤ תאריך המבוקש, הגדולה ביותר".
2. **קבצים סטטיים הם read-only בזמן ריצה.** הם נוצרים בפיתוח (ידנית או בסקריפט) ונשלחים עם המערכת.
3. **אין לוגיקה עסקית בקבצים.** הקובץ מכיל נתון גולמי. הזכות/המודול שצורך אותו מחליט מה לעשות איתו.
4. **פורמט אחיד.** כל CSV: UTF-8, כותרת בשורה ראשונה, ללא BOM, שדות לא עטופים במרכאות אלא אם מכילים פסיק.
5. **תאריכים ב-ISO 8601.** `YYYY-MM-DD` בכל מקום.
6. **שעות ב-`HH:MM`.** 24 שעות, local time (`Asia/Jerusalem`).

---

## מבנה תיקיות

```
backend/
├── data/
│   ├── shabbat_times/           # קובץ לעיר מייצגת — נוצר בסקריפט
│   │   ├── jerusalem.csv
│   │   ├── tel_aviv.csv
│   │   ├── haifa.csv
│   │   ├── beer_sheva.csv
│   │   └── nof_hagalil.csv
│   ├── holiday_dates.csv        # 9 חגים × 200 שנה — נוצר בסקריפט
│   ├── minimum_wage.csv         # שכר מינימום היסטורי — ידני
│   ├── recreation_day_value.csv # ערך ₪ ליום הבראה — ידני
│   ├── recreation_days.csv      # ימי הבראה לפי ענף + ותק — ידני
│   └── travel_allowance/        # דמי נסיעות — קובץ לכל ענף, ידני
│       └── general.csv
├── settings.json                # הגדרות מערכת
└── scripts/
    ├── generate_shabbat_times.py
    └── generate_holiday_dates.py
```

---

## 1. shabbat_times — זמני שבת

### מיקום

```
data/shabbat_times/{district}.csv
```

קובץ נפרד לכל עיר מייצגת: `jerusalem.csv`, `tel_aviv.csv`, `haifa.csv`, `beer_sheva.csv`, `nof_hagalil.csv`.

### סכמה

```csv
date,candles,havdalah
2024-01-05,16:13,17:28
2024-01-12,16:19,17:34
```

| עמודה | סוג | תיאור |
|-------|------|-------|
| `date` | date | תאריך יום שישי של אותו שבוע (ISO 8601) |
| `candles` | time | שעת הדלקת נרות (HH:MM, local) |
| `havdalah` | time | שעת הבדלה (HH:MM, local) |

### כללים

- שורה אחת לכל שבת. `date` = יום שישי.
- טווח: 1948-01-01 עד 2148-12-31.
- ~10,400 שורות לקובץ. 5 קבצים. ~2.5MB סה"כ.
- ממויין לפי `date` בסדר עולה.

### מחוזות

| מפתח | שם עברי | עיר מייצגת | קו רוחב | קו אורך | b (דקות) |
|-------|---------|------------|----------|----------|----------|
| `jerusalem` | ירושלים | ירושלים | 31.7683 | 35.2137 | 40 |
| `tel_aviv` | תל אביב | תל אביב-יפו | 32.0853 | 34.7818 | 18 |
| `haifa` | חיפה | חיפה | 32.7940 | 34.9896 | 30 |
| `beer_sheva` | באר שבע | באר שבע | 31.2530 | 34.7915 | 18 |
| `nof_hagalil` | נוף הגליל | נוף הגליל | 32.7070 | 35.3273 | 18 |

- `b` = דקות הדלקת נרות לפני שקיעה (מנהג הלכתי).
- הבדלה = צאת הכוכבים (שמש 8.5° מתחת לאופק).
- אזור זמן: `Asia/Jerusalem`.

### שימוש בצרכן

הצרכן מזהה את יום השישי של השבוע הרלוונטי, שולף את השורה המתאימה לפי `date` מקובץ המחוז. מקבל `candles` ו-`havdalah`. אם יום השישי לא קיים בטבלה — שגיאה.

### גישה בקוד

```python
def get_shabbat_times(date: date, district: str) -> ShabbatTimes:
    """מחזיר candles + havdalah לשבת הקרובה ביותר ל-date."""
```

### סקריפט ייצור

```
scripts/generate_shabbat_times.py
```

- משתמש בספריית חישוב אסטרונומי (astral / ephem / skyfield) או שואב מ-Hebcal API.
- פרמטרים: קואורדינטות + b + timezone מטבלת המחוזות.
- אימות: מדגם ~50 תאריכים מאומת מול מקור חיצוני.

**לפירוט מלא:** ראה סקיל overtime-calculation, סעיפים 7.3–7.5.

---

## 2. holiday_dates — תאריכי חגים

### מיקום

```
data/holiday_dates.csv
```

### סכמה

```csv
year,holiday_id,hebrew_date,gregorian_date
2024,rosh_hashana_1,א' תשרי,2024-10-03
2024,rosh_hashana_2,ב' תשרי,2024-10-04
2024,yom_kippur,י' תשרי,2024-10-12
```

| עמודה | סוג | תיאור |
|-------|------|-------|
| `year` | integer | שנה לועזית |
| `holiday_id` | string | מזהה חג (ראה טבלה) |
| `hebrew_date` | string | תאריך עברי לתצוגה |
| `gregorian_date` | date | תאריך לועזי (ISO 8601) — יום החג, לא הערב |

### רשימת חגים

| holiday_id | שם | תאריך עברי |
|------------|-----|------------|
| `rosh_hashana_1` | ראש השנה א' | א' תשרי |
| `rosh_hashana_2` | ראש השנה ב' | ב' תשרי |
| `yom_kippur` | יום כיפור | י' תשרי |
| `sukkot` | סוכות | ט"ו תשרי |
| `hoshana_raba` | הושענא רבה | כ"א תשרי |
| `pesach` | פסח | ט"ו ניסן |
| `pesach_7` | שביעי של פסח | כ"א ניסן |
| `yom_haatzmaut` | יום העצמאות | ה' אייר |
| `shavuot` | שבועות | ו' סיוון |

### כללים

- 9 חגים × 200 שנה = 1,800 שורות.
- טווח: 1948–2148.
- ממויין לפי `year, gregorian_date`.
- יום העצמאות יכול לזוז (הימנעות מסמיכות שבת) — הסקריפט משתמש בתאריך הרשמי.
- `gregorian_date` הוא **יום החג הקלנדרי**, לא הערב שלפניו.

### שימוש בצרכן

הצרכן שולף שורות לפי `year` ו/או `gregorian_date`. מקבל רשימת 9 חגים עם תאריכים לועזיים. אם השנה לא קיימת בטבלה — שגיאה.

### גישה בקוד

```python
def get_holiday_dates(year: int) -> list[HolidayDate]:
    """מחזיר 9 חגים עם תאריכים לועזיים לשנה נתונה."""
```

### סקריפט ייצור

```
scripts/generate_holiday_dates.py
```

- משתמש בספריית לוח עברי (pyluach / hdate / hebcal).
- מטפל בשנים מעוברות (אדר שני).
- אימות: מדגם תאריכים ידועים מאומת מול מקור חיצוני.

**לפירוט מלא:** ראה סקיל holidays, סעיף Hebrew Calendar.

---

## 3. minimum_wage — שכר מינימום

### מיקום

```
data/minimum_wage.csv
```

### סכמה

```csv
effective_date,hourly,daily_5day,daily_6day,monthly
2018-04-01,29.12,244.62,212.00,5300.00
2023-04-01,30.61,257.16,222.87,5571.75
2024-04-01,32.30,271.38,235.20,5880.02
2025-04-01,34.32,288.35,249.90,6247.67
```

| עמודה | סוג | תיאור |
|-------|------|-------|
| `effective_date` | date | תאריך תחילת תוקף |
| `hourly` | decimal | שכר מינימום לשעה (₪) |
| `daily_5day` | decimal | שכר מינימום ליום — שבוע 5 ימים (₪) |
| `daily_6day` | decimal | שכר מינימום ליום — שבוע 6 ימים (₪) |
| `monthly` | decimal | שכר מינימום לחודש (₪) |

### כללים

- ממויין לפי `effective_date` בסדר עולה.
- שורה תקפה מ-`effective_date` עד יום לפני ה-`effective_date` של השורה הבאה.
- **lookup**: לחודש נתון, מחפשים את השורה עם `effective_date ≤ first_of_month`, הגדולה ביותר.
- שדה `daily_5day` / `daily_6day`: שכר יומי תלוי בסוג שבוע (5/6 ימים). סוג השבוע נקבע ע"י ה-week_type מ-SSOT.
- מתחיל מ-2018. שורות חדשות מתווספות ידנית כשהשכר משתנה.

### שימוש בצרכן

הצרכן שולף את השורה עם `effective_date ≤ first_of_month` הגדולה ביותר. מקבל שכר שעתי, יומי (5/6 ימים), וחודשי. סוג השבוע (5/6) נקבע ע"י ה-`week_type` מ-SSOT.

### גישה בקוד

```python
def get_minimum_wage(month: tuple[int, int]) -> MinimumWage:
    """מחזיר שכר מינימום (hourly, daily_5, daily_6, monthly) לחודש נתון."""
```

**לפירוט לוגיקת השוואה:** ראה סקיל salary-conversion.

---

## 4. recreation_day_value — ערך יום הבראה

### מיקום

```
data/recreation_day_value.csv
```

### סכמה

```csv
effective_date,value
2018-07-01,378.00
2023-07-01,418.00
```

| עמודה | סוג | תיאור |
|-------|------|-------|
| `effective_date` | date | תאריך תחילת תוקף |
| `value` | decimal | ערך יום הבראה (₪) — מגזר פרטי |

### כללים

- ממויין לפי `effective_date` בסדר עולה.
- lookup זהה לשאר הטבלאות: `effective_date ≤ תאריך מבוקש`.
- ערך אחד — מגזר פרטי בלבד.
- שורות חדשות מתווספות ידנית כשהערך משתנה.

### שימוש בצרכן

הצרכן שולף את השורה עם `effective_date ≤ תאריך מבוקש` הגדולה ביותר. מקבל ערך ₪ ליום הבראה.

### גישה בקוד

```python
def get_recreation_day_value(date: date) -> Decimal:
    """מחזיר ערך ₪ ליום הבראה לתאריך נתון."""
```

---

## 5. recreation_days — ימי הבראה לפי ענף וותק

### מיקום

```
data/recreation_days.csv
```

### סכמה

```csv
industry,min_years,max_years,days_per_year
general,1,1,5
general,2,3,6
general,4,10,7
general,11,15,8
general,16,19,9
general,20,999,10
construction,1,3,6
construction,4,10,8
construction,11,15,9
construction,16,19,10
construction,20,24,11
construction,25,999,12
cleaning,1,3,7
cleaning,4,10,9
cleaning,11,15,10
cleaning,16,19,11
cleaning,20,24,12
cleaning,25,999,13
```

| עמודה | סוג | תיאור |
|-------|------|-------|
| `industry` | string | מזהה ענף |
| `min_years` | integer | ותק מינימלי (שנים, כולל) |
| `max_years` | integer | ותק מקסימלי (שנים, כולל). 999 = ללא הגבלה |
| `days_per_year` | integer | ימי הבראה לשנה |

### ענפים מוגדרים

| מזהה | שם עברי | הערות |
|------|---------|-------|
| `general` | כללי | ברירת מחדל — כל ענף שאין לו טבלה ייעודית |
| `construction` | בניין | צו הרחבה ענף הבניין |
| `cleaning` | ניקיון | צו הרחבה ענף הניקיון |

### כללים

- ממויין לפי `industry, min_years`.
- ותק בשנים שלמות (הזכות אחראית על המרה מחודשים לשנים).
- `max_years=999` = "ואילך".
- כל ענף חייב לכסות את הטווח 1–999 ללא פערים וללא חפיפות.
- **הטבלה מכילה רק את הנתון הגולמי.** התניות ענפיות (גיל, סוג שבוע, תוספות מיוחדות) — זו לוגיקה של הזכות, לא של הטבלה. הזכות שולפת מכאן את הבסיס ומשלבת עם נתונים מה-SSOT.
- **להוספת ענף חדש:** הוספת שורות לקובץ עם `industry` חדש. אין צורך בשינוי קוד — רק הוספת נתונים.

### שימוש בצרכן

הצרכן שולף את השורה לפי `industry` + ותק בשנים שלמות (כך ש-`min_years ≤ ותק ≤ max_years`). מקבל מספר ימי הבראה לשנה.

### גישה בקוד

```python
def get_recreation_days(industry: str, seniority_years: int) -> int:
    """מחזיר מספר ימי הבראה לשנה לפי ענף וותק."""
```

---

## 6. דמי נסיעות — travel_allowance

### מיקום

```
data/travel_allowance/
├── general.csv
└── {industry}.csv      # קבצים נוספים לפי ענף בעתיד
```

### החלטת עיצוב

בניגוד לשאר הטבלאות הסטטיות, לדמי נסיעות **אין פורמט אחיד בין ענפים**. הסיבה: ענפים שונים מחשבים נסיעות לפי קריטריונים שונים לחלוטין — הענף הכללי מגדיר סכום יומי קבוע, ענפים אחרים עשויים להגדיר סכומים לפי מרחק, אזור מגורים, או קריטריונים אחרים. לכן:

- כל ענף מקבל **קובץ נפרד** עם סכמה משלו.
- הזכות (כשתיבנה) אחראית לדעת לקרוא את הפורמט של כל ענף.
- הסקיל הזה מתעד את הסכמה של כל ענף בנפרד.

### ענף כללי — general.csv

```csv
effective_date,daily_amount
2025-02-01,22.60
```

| עמודה | סוג | תיאור |
|-------|------|-------|
| `effective_date` | date | תאריך תחילת תוקף |
| `daily_amount` | decimal | סכום יומי (₪) |

שליפה: לפי עקרון הלוקאפ הכללי (`effective_date ≤ תאריך מבוקש`).

### הוספת ענף חדש

1. צור קובץ בשם `{industry}.csv` בתיקייה.
2. תעד את הסכמה שלו כאן (עמודות, כללים, דוגמה).
3. עדכן את הזכות כך שתדע לקרוא את הפורמט החדש.

### שימוש בצרכן

הצרכן מזהה את הענף, טוען את הקובץ המתאים, ושולף לפי הסכמה הייחודית לאותו ענף. ענף כללי — שליפה לפי תאריך, מקבל סכום יומי.

---

## 7. settings.json — הגדרות מערכת

### מיקום

```
backend/settings.json
```

### סכמה מלאה

```json
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
      {
        "id": "general",
        "name": "התיישנות כללית",
        "window_years": 7
      },
      {
        "id": "vacation",
        "name": "התיישנות חופשה",
        "window_calc": "3_plus_current"
      }
    ],
    "freeze_periods": [
      {
        "id": "war_2023",
        "name": "הקפאת מלחמת התקומה",
        "start_date": "2023-10-07",
        "end_date": "2024-04-06",
        "days": 183
      }
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

### פירוט שדות

#### ot_config

| שדה | סוג | ברירת מחדל | תיאור |
|-----|------|-----------|-------|
| `weekly_cap` | decimal | 42 | סף שבועי לשעות רגילות |
| `threshold_5day` | decimal | 8.4 | סף יומי בשבוע 5 ימים |
| `threshold_6day` | decimal | 8.0 | סף יומי בשבוע 6 ימים |
| `threshold_eve_rest` | decimal | 7.0 | סף ערב מנוחה |
| `threshold_night` | decimal | 7.0 | סף משמרת לילה |
| `tier1_max_hours` | decimal | 2 | שעות מקסימום ב-Tier 1 |

#### full_time_hours_base

| סוג | ברירת מחדל | תיאור |
|------|-----------|-------|
| decimal | 182 | בסיס שעות למשרה מלאה — להיקף משרה |

#### limitation_config

**limitation_types** — רשימת סוגי התיישנות:

| שדה | סוג | תיאור |
|-----|------|-------|
| `id` | string | מזהה ייחודי |
| `name` | string | שם בעברית לתצוגה |
| `window_years` | integer? | חלון בשנים (להתיישנות כללית) |
| `window_calc` | string? | שיטת חישוב מיוחדת (להתיישנות חופשה) |

**freeze_periods** — הקפאות התיישנות:

| שדה | סוג | תיאור |
|-----|------|-------|
| `id` | string | מזהה ייחודי |
| `name` | string | שם בעברית |
| `start_date` | date | תאריך תחילה (ISO 8601) |
| `end_date` | date | תאריך סיום (ISO 8601) |
| `days` | integer | מספר ימים (מחושב, לנוחות) |

**right_limitation_mapping** — שיוך זכות לסוג התיישנות:

```
Map<right_id, limitation_type_id>
```

כל זכות מוגדרת חייבת שיוך. זכויות ללא שיוך = שגיאת ולידציה.

### כללים

- **הגדרות מערכת, לא הגדרות תיק.** settings.json זהה לכל התיקים. שינוי כאן משפיע על כל החישובים.
- **hash.** ה-cache ב-.case כולל hash של settings.json. שינוי = חישוב מחדש.
- **configurable, לא hardcoded.** כל ערך ב-settings.json ניתן לשינוי. המערכת לא מניחה ערכים קבועים.
- **הוספת סוג התיישנות:** הוספת אובייקט ל-`limitation_types` + שיוך ב-`right_limitation_mapping`. אין צורך בשינוי קוד (אלא אם ה-`window_calc` דורש לוגיקה חדשה).
- **הוספת הקפאה:** הוספת אובייקט ל-`freeze_periods`.

---

## פונקציית lookup כללית

כל טבלה עם `effective_date` משתמשת באותה לוגיקה:

```python
def lookup_by_date(table: list[dict], target_date: date, date_field: str = "effective_date") -> dict:
    """
    מחזיר את השורה עם effective_date ≤ target_date, הגדולה ביותר.
    אם אין שורה כזו — שגיאה (תאריך לפני תחילת הטבלה).
    """
    candidates = [row for row in table if row[date_field] <= target_date]
    if not candidates:
        raise ValueError(f"No data for date {target_date}")
    return max(candidates, key=lambda r: r[date_field])
```

אם אין שורה כזו (תאריך לפני תחילת הטבלה) — שגיאה, לא ניחוש.

---

## הוספת טבלה סטטית חדשה

כשזכות חדשה צריכה מאגר סטטי:

1. **צור קובץ CSV** ב-`data/` עם כותרת ועמודות מתאימות.
2. **הוסף את הסכמה** לסקיל זה (פורמט, עמודות, כללים, שימוש בצרכן, גישה בקוד).
3. **כתוב פונקציית גישה** ב-`utils/static_data.py`.
4. **אם הקובץ נוצר בסקריפט** — הוסף סקריפט ל-`scripts/` ותעד כאן.
5. **אם הקובץ ידני** — הוסף את הנתונים ואמת.

פורמט מומלץ לטבלת lookup כרונולוגית:
```csv
effective_date,field1,field2,...
```

פורמט מומלץ לטבלת lookup לפי קטגוריה + טווח:
```csv
category,min_value,max_value,result_field,...
```

---

## אנטי-פטרנים

1. **לא טוענים CSV בזמן חישוב.** כל הנתונים נטענים פעם אחת בעליית המערכת ונשמרים ב-cache בזיכרון.
2. **לא כותבים לקבצי CSV בזמן ריצה.** הם read-only.
3. **לא ממציאים ערכים.** אם תאריך לא מכוסה — שגיאה, לא ניחוש.
4. **לא שמים לוגיקה בטבלה.** הטבלה = נתון. הלוגיקה = בזכות/במודול.
5. **לא hardcoding ערכי settings.** כל מודול קורא מ-settings.json, לא משתמש בקבועים.
