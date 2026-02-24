---
name: pattern-translator
description: |
  Pattern Translator (מתרגם הדפוסים) module for the Claims Wizard (אשף התביעות).
  Translates user-entered work patterns (simple weekly, cyclic, or statistical)
  into concrete daily records with shift templates.
  Use this skill whenever working on pattern input, pattern-to-daily-record conversion,
  synthetic shift generation, or night shift placement optimization.
  ALWAYS read this skill before touching any pattern translation code.
---

# מתרגם הדפוסים — Pattern Translator

## CRITICAL WARNINGS

1. **מתרגם הדפוסים יושב בין הקלט לבין המארג.** הוא מקבל דפוס עבודה מהמשתמש ומייצר רשומות יומיות עם תבניות משמרות. המארג והשאר לא יודעים איך הדפוס הוזן — הם רואים רק את הפלט.
2. **כל שבוע מתחיל ביום ראשון.** בכל שלוש הרמות, שבוע = ראשון 00:00 עד שבת 24:00.
3. **ברמה ג — תמיד מספרים שלמים בשבוע בודד.** שברים מתורגמים למחזור שבועי. לא קיים "חצי משמרת" בשבוע אחד.
4. **משמרות יום לא זזות.** רק משמרות לילה ניתנות למיקום. ימים רגילים, ערב מנוחה ויום מנוחה — מיקומם קבוע לפי סוגם.
5. **מתרגם הדפוסים אינו מחשב שעות נוספות.** הוא רק מייצר תבניות. מעבד המשמרות אחראי על כל החישובים.
6. **ברמה ג — משמרת לילה משויכת ליום הקלנדרי שבו רוב שעותיה.** לכן משמרת 22:00-05:00 משויכת ליום שאחרי. זה משפיע על אלגוריתם המיקום.

---

## מיקום בצינור

```
קלט המשתמש
    │
    ▼
┌─────────────────────────────┐
│  מתרגם הדפוסים              │
│                             │
│  רמה א → פריסה ישירה       │
│  רמה ב → פריסת מחזור       │
│  רמה ג → ייצור מחזור       │
│           סינתטי + פריסה   │
└──────────────┬──────────────┘
               │ work_patterns (רמה א format)
               ▼
┌─────────────────────────────┐
│  המארג                      │
│  (sweep line, effective     │
│   periods, daily records)   │
└──────────────┬──────────────┘
               │
               ▼
         מעבד המשמרות
```

**עיקרון:** מתרגם הדפוסים מייצר `work_patterns` בפורמט של רמה א (ימי עבודה + תבניות משמרות ליום). המארג ומעבד המשמרות לא יודעים מאיזו רמה הגיע הדפוס.

---

## רמה א — דפוס שבועי פשוט

### קלט

```
PatternLevel_A {
  id: string                             // מזהה ייחודי (תואם SSOT.input.work_patterns[].id)
  type: "weekly_simple"
  start: date                          // תחילת תוקף
  end: date                            // סיום תוקף
  duration: Duration                   // מחושב (מספרי; display בפאזה 4)
  work_days: List<integer>             // ימים בשבוע (0=ראשון..6=שבת)

  // תבניות משמרות — 3 מצבים (סדר עדיפויות: daily_overrides > per_day > default):
  default_shifts: List<{
    start_time: time                   // 07:00
    end_time: time                     // 16:00
  }>
  default_breaks: List<{
    start_time: time                   // 12:00
    end_time: time                     // 12:30
  }>
  per_day: Map<integer, {              // לפי יום בשבוע (null אם לא רלוונטי)
    shifts: List<{start_time, end_time}>
    breaks: List<{start_time, end_time}>?
  }>?
  daily_overrides: Map<date, {         // לפי תאריך קלנדרי (null אם לא רלוונטי)
    shifts: List<{start_time, end_time}>
    breaks: List<{start_time, end_time}>?
  }>?
}
```

### אלגוריתם

פריסה ישירה על לוח שנה:

```
function translateLevelA(pattern, rest_day):
  for each day in range(pattern.start, pattern.end):
    dow = dayOfWeek(day)              // 0=ראשון..6=שבת
    is_rest = (dow == rest_day_number)

    if is_rest:
      → is_work_day=false, shifts=[], breaks=[]
    else if dow in pattern.work_days:
      → is_work_day=true
      // סדר עדיפויות: daily_overrides > per_day > default
      → shifts = daily_overrides[day].shifts
                ?? per_day[dow].shifts
                ?? default_shifts
      → breaks = daily_overrides[day].breaks
                ?? per_day[dow].breaks
                ?? default_breaks
    else:
      → is_work_day=false, shifts=[], breaks=[]
```

**פשוט.** כל יום בודק: מה היום בשבוע? האם הוא ברשימה? אם כן — שם תבנית משמרת.

---

## רמה ב — דפוס מחזורי

### קלט

```
PatternLevel_B {
  type: "cyclic"
  start: date
  end: date
  cycle: List<PatternLevel_A>         // רשימת דפוסי רמה א, כל אחד = שבוע אחד
                                       // cycle[0] = שבוע 1, cycle[1] = שבוע 2, ...
  cycle_length: integer                // מספר שבועות במחזור (= cycle.length)
}
```

### אלגוריתם

```
function translateLevelB(pattern, rest_day):
  cycle_length = pattern.cycle.length
  period_start_week = weekNumber(pattern.start)

  for each day in range(pattern.start, pattern.end):
    weeks_since_start = weeksBetween(pattern.start, day)
    cycle_index = weeks_since_start % cycle_length
    weekly_pattern = pattern.cycle[cycle_index]

    // מכאן — בדיוק כמו רמה א
    dow = dayOfWeek(day)
    apply weekly_pattern rules for this dow
```

**עקרון:** סופר שבועות מתחילת התקופה, מחליט איפה במחזור, ומפעיל את הדפוס השבועי המתאים.

### מחזור שנקטע

אם התקופה לא מתחלקת שווה באורך המחזור — המחזור פשוט נקטע. תקופה של 10 שבועות עם מחזור 3 = 3 מחזורים שלמים + שבוע 1 בלבד.

---

## רמה ג — דפוס סטטיסטי

### קלט

```
PatternLevel_C {
  type: "statistical"
  start: date
  end: date

  day_types: List<{
    type_id: "regular" | "eve_of_rest" | "rest_day" | "night"
    count: decimal                     // מספר ימים (יכול להיות שבר)
    count_period: "weekly" | "monthly" // שבועי או חודשי
    hours: decimal                     // שעות עבודה ביום
  }>

  night_placement: "employer_favor" | "employee_favor" | "average"
}
```

### סוגי ימים מוכרים

**הערה חשובה:** `type_id` כאן הוא **סוג יום עבודה** (קלט מתרגם הדפוסים) — לא לבלבל עם `day_segments.type` ב-SSOT שהוא **סוג קטע ביממה** (`"regular" | "eve_of_rest" | "rest"`). סוג יום עבודה קובע מיקום ושעות; `day_segments` נכתב על ידי מעבד המשמרות שלב 3.5.

| סוג | מזהה | ימים אפשריים בשבוע | חלק ביממה | שעת התחלה ברירת מחדל |
|-----|-------|---------------------|-----------|---------------------|
| רגיל | `regular` | א-ה | יום | 07:00 + שעות |
| ערב מנוחה | `eve_of_rest` | יום לפני יום המנוחה | יום (קצר) | 07:00 + שעות |
| יום מנוחה | `rest_day` | יום המנוחה | יום | 07:00 + שעות |
| לילה | `night` | א-שבת | לילה | 22:00 + שעות |

### גזירת שעות אוטומטית

המשתמש מזין רק מספר שעות. המערכת גוזרת שעת התחלה, סיום, והפסקות:

```
function deriveShiftTemplate(type_id, hours):
  if type_id == "regular":
    start = 07:00
    if hours > 6:
      break_start = 12:00
      break_end = 12:30
      end = start + hours + 0:30     // מוסיף זמן הפסקה
    else:
      no break
      end = start + hours
    return {shifts: [{start, end}], breaks: [{break_start, break_end}]?}

  if type_id == "eve_of_rest":
    start = 07:00
    end = start + hours               // בדרך כלל קצר, ללא הפסקה
    return {shifts: [{start, end}], breaks: []}

  if type_id == "rest_day":
    start = 07:00
    if hours > 6:
      break like regular
    else:
      no break
    return {shifts: [{start, end}], breaks: ...}

  if type_id == "night":
    start = 22:00
    end = 22:00 + hours              // חוצה חצות → למשל 22:00-05:00
    return {shifts: [{start, end}], breaks: []}
```

**הערה:** הפסקה ניתנת רק ביום עבודה של יותר מ-6 שעות (חוק). ברירת המחדל: 30 דקות, 12:00-12:30.

---

### אלגוריתם רמה ג — שלב אחר שלב

#### שלב 1: נרמול לשבועי

אם הקלט חודשי — מחלקים ב-4.33 (ממוצע שבועות בחודש):

```
function normalizeToWeekly(count, count_period):
  if count_period == "weekly":
    return count
  if count_period == "monthly":
    return count / 4.33
```

דוגמה: 13 לילות בחודש → 13 / 4.33 = 3.0 לשבוע.

#### שלב 2: חישוב אורך מחזור

מוצאים את המחזור הקצר ביותר שבו כל השברים מתאפסים:

```
function computeCycleLength(weekly_counts):
  // weekly_counts = [4.0, 0.5, 0.0, 1.5]  (regular, eve, rest, night)
  // מוצאים LCD של כל המכנים
  fractions = extractFractions(weekly_counts)
  // 0.5 = 1/2, 1.5 = 3/2 → מכנה 2
  cycle_length = LCM of all denominators
  return cycle_length
```

דוגמאות:
- 0.5 לשבוע → מחזור 2 שבועות
- 0.33 לשבוע → מחזור 3 שבועות
- 2.3 לשבוע → 23/10 → מחזור 10 שבועות
- 4.0 לשבוע → מחזור 1 שבוע (מספר שלם)

**מגבלת מחזור:** אם המחזור יוצא ארוך מדי (למשל 100 שבועות), יש לעגל את הקלט ולהציג אזהרה למשתמש. מגבלה מוצעת: 52 שבועות (שנה).

#### שלב 3: חלוקת ימים לשבועות במחזור

לכל סוג יום, מחלקים את הסכום הכולל במחזור לשבועות בודדים:

```
function distributeToWeeks(weekly_avg, cycle_length):
  total_in_cycle = round(weekly_avg * cycle_length)  // מספר שלם
  base_per_week = floor(total_in_cycle / cycle_length)
  remainder = total_in_cycle - (base_per_week * cycle_length)

  weeks = []
  for i in 0..cycle_length-1:
    if i < remainder:
      weeks[i] = base_per_week + 1   // שבועות עם יום נוסף
    else:
      weeks[i] = base_per_week

  // פיזור שווה: שבועות עם יום נוסף מפוזרים שווה במחזור
  weeks = spreadEvenly(weeks, remainder, cycle_length)
  return weeks
```

דוגמה: 1.5 לילות לשבוע, מחזור 2:
- סה"כ = 3 לילות ב-2 שבועות
- base = 1, remainder = 1
- שבוע 1: 2 לילות, שבוע 2: 1 לילה

דוגמה: 2.3 לילות לשבוע, מחזור 10:
- סה"כ = 23 לילות ב-10 שבועות
- base = 2, remainder = 3
- 7 שבועות × 2 לילות + 3 שבועות × 3 לילות = 23
- השבועות עם 3 לילות מפוזרים: שבועות 3, 6, 9 (שווה ככל שאפשר)

#### שלב 4: שיבוץ ימי יום בשבוע

ימי יום (רגיל, ערב מנוחה, יום מנוחה) משובצים לפי כללים קבועים:

```
function placeDayShifts(week, rest_day):
  // שלב 4א: ימי מנוחה — תמיד ביום המנוחה
  if week.rest_day_count > 0:
    place rest_day shift on rest_day (e.g., Saturday)

  // שלב 4ב: ערב מנוחה — תמיד ביום שלפני המנוחה
  if week.eve_of_rest_count > 0:
    place eve_of_rest shift on eve_of_rest_day (e.g., Friday)

  // שלב 4ג: ימים רגילים — מראשון עד חמישי, מתמלאים מתחילת השבוע
  remaining_regular = week.regular_count
  for dow in [0,1,2,3,4]:  // ראשון עד חמישי
    if remaining_regular > 0:
      place regular shift on dow
      remaining_regular -= 1
```

**הערה:** ימי יום לעולם לא זזים. 4 ימים רגילים = ראשון עד רביעי, תמיד.

#### שלב 5: שיבוץ משמרות לילה

כאן נכנס הטוגל של טובת מעביד/עובד/ממוצע:

```
function placeNightShifts(week, night_count, placement_mode, rest_day, shabbat_times):
  available_nights = getAllNights(week)  // 7 לילות אפשריים (מוצ"ש עד שישי לילה)

  // סינון: לא לזלוג לתוך יום המנוחה
  // משמרת לילה 22:00-05:00 בליל שישי → רוב השעות בשבת → משויכת לשבת
  // אם יום המנוחה = שבת ואין עבודה בשבת → לא לשים לילה בליל שישי
  available_nights = filterNoRestDayOverflow(available_nights, rest_day)

  if placement_mode == "employer_favor":
    // שיבוץ לפני ימים שכבר יש בהם משמרת יום
    // ככה הלילה משויכת לאותו יום → פחות ימי עבודה נפרדים
    // + ממזער חפיפה עם חלון מנוחה
    scored_nights = []
    for night in available_nights:
      next_day = night + 1 day        // היום שאליו הלילה תשויך (רוב השעות)
      has_day_shift = week.hasShift(next_day)
      overlap_with_rest_window = estimateRestWindowOverlap(night, shabbat_times)
      score = prioritize(has_day_shift=true, low_overlap)
      scored_nights.append((night, score))

    selected = selectBest(scored_nights, night_count)

  if placement_mode == "employee_favor":
    // שיבוץ לפני ימים ריקים
    // ככה הלילה משויכת ליום נפרד → יותר ימי עבודה
    scored_nights = []
    for night in available_nights:
      next_day = night + 1 day
      has_day_shift = week.hasShift(next_day)
      score = prioritize(has_day_shift=false)
      scored_nights.append((night, score))

    selected = selectBest(scored_nights, night_count)

  if placement_mode == "average":
    // חצי מהלילות בטובת מעביד, חצי בטובת עובד
    employer_count = floor(night_count / 2)
    employee_count = night_count - employer_count
    selected = placeNightShifts(week, employer_count, "employer_favor", ...)
             + placeNightShifts(week, employee_count, "employee_favor", ...)

  return selected
```

**כלל "לא לזלוג למנוחה":**
- משמרת לילה 22:00-05:00: 3 שעות ביום הנוכחי, 5 שעות ביום הבא
- הרוב ביום הבא → משויכת ליום הבא
- אם היום הבא = יום מנוחה ואין עבודה ביום מנוחה → אסור לשבץ כאן
- אם **יש** עבודה ביום מנוחה (סוג rest_day בקלט) → מותר

#### שלב 6: הפיכה לדפוס רמה ב

אחרי שלבים 1-5 יש לנו מחזור שבועי מלא עם כל המשמרות משובצות. זה בדיוק דפוס מחזורי מרמה ב:

```
function levelCToLevelB(statistical_input, rest_day, shabbat_times):
  weekly_counts = normalizeToWeekly(statistical_input)
  cycle_length = computeCycleLength(weekly_counts)
  week_distributions = distributeToWeeks(weekly_counts, cycle_length)

  cycle = []
  for week_index in 0..cycle_length-1:
    week = createEmptyWeek()
    placeDayShifts(week, week_distributions[week_index], rest_day)
    placeNightShifts(week, week_distributions[week_index].night,
                     statistical_input.night_placement, rest_day, shabbat_times)
    cycle.append(weekToPatternLevelA(week))

  return PatternLevel_B {
    type: "cyclic",
    start: statistical_input.start,
    end: statistical_input.end,
    cycle: cycle,
    cycle_length: cycle_length
  }
```

**עיקרון:** רמה ג מתורגמת תמיד לרמה ב, שמתורגמת לרמה א על לוח השנה. שכבת תרגום אחת על גבי השנייה.

---

## ולידציה

### ולידציה ברמה א

```
- start <= end
- work_days ⊆ {0,1,2,3,4,5,6}
- כל shift: start_time < end_time (או חוצה חצות)
- per_day keys ⊆ work_days
```

### ולידציה ברמה ב

```
- כל השבועות במחזור עוברים ולידציה של רמה א
- cycle_length >= 1
- cycle_length == cycle.length
```

### ולידציה ברמה ג

```
- לפחות סוג יום אחד עם count > 0
- סה"כ ימים בשבוע <= 7
- סה"כ ימי ערב מנוחה <= 1 (רק יום אחד לפני מנוחה בשבוע)
- סה"כ ימי מנוחה <= 1 (רק יום מנוחה אחד בשבוע)
- hours > 0 לכל סוג עם count > 0
- אורך מחזור מחושב <= 52 (שבועות)
- night_placement ∈ {"employer_favor", "employee_favor", "average"}
- משמרות לילה: hours <= 12 (מקסימום סביר)
- משמרות יום: hours <= 14 (מקסימום סביר)
```

---

## SSOT Integration

מתרגם הדפוסים כותב ל-`SSOT.input.work_patterns`. הפלט תמיד בפורמט של רמה א — כלומר `id` + `work_days` + `default_shifts` + `default_breaks` + `per_day` + `daily_overrides`. זהה לחלוטין למבנה `work_patterns` הקיים ב-SSOT.

ברמה ב וג, הפורמט הפנימי (מחזורי/סטטיסטי) נשמר **גם** ב-`SSOT.input.pattern_source` לצורך:
- עריכה חוזרת (המשתמש פותח את הדפוס ורואה את מה שהזין)
- תצוגה ("דפוס סטטיסטי: 18 ימים רגילים + 2.3 ימי שישי")
- ביקורת (שקיפות — מאיפה הגיעו הרשומות היומיות)

**הערה:** `pattern_source` הוא שדה חדש שצריך להוסיף ל-SSOT שכבה 0 (input). הוא לא משפיע על שום מודול אחר — רק מתרגם הדפוסים קורא וכותב אליו.

```
SSOT.input.pattern_source: List<{
  id: string                           // תואם work_patterns[].id
  type: "weekly_simple" | "cyclic" | "statistical"
  start: date
  end: date

  // רמה א בלבד:
  level_a_data: PatternLevel_A?

  // רמה ב בלבד:
  level_b_data: PatternLevel_B?

  // רמה ג בלבד:
  level_c_data: PatternLevel_C?

  // תמיד מאוכלס — התוצאה אחרי תרגום:
  translated_pattern: PatternLevel_A   // מה שנכתב ל-work_patterns
}>
```

---

## Edge Cases

### 1. שברים שלא מתאפסים יפה

קלט: 1.7 לילות בשבוע → 17/10 → מחזור 10 שבועות. 7 שבועות × 2, 3 שבועות × 1 = 17 ✓

### 2. מחזור ארוך מדי

קלט: 1.37 לילות → 137/100 → מחזור 100. עובר מגבלת 52.
→ עיגול: 1.37 → 1.4 → מחזור 5. הצגת אזהרה: "ערך עוגל מ-1.37 ל-1.4"

### 3. סה"כ ימים > 7

קלט: 5 רגיל + 1 ערב מנוחה + 1 מנוחה + 1 לילה = 8.
→ שגיאת ולידציה: "סה"כ ימים בשבוע (8) חורג מ-7"

### 4. משמרת לילה בליל שישי ואין עבודה בשבת

rest_day = שבת, לא הוזנו ימי מנוחה.
משמרת 22:00-05:00 בליל שישי → משויכת לשבת → אסור (זולג למנוחה).
→ הלילה הזה לא זמין לשיבוץ.

### 5. משמרת לילה בליל שישי ויש עבודה בשבת

rest_day = שבת, הוזנו ימי מנוחה (rest_day_count > 0).
→ מותר לשבץ לילה בליל שישי (שבת כבר יום עבודה).

### 6. רמה ב — תקופה קצרה ממחזור

תקופה של 2 שבועות, מחזור של 5 שבועות.
→ תקין. רצים שבועות 1 ו-2 בלבד.

### 7. רמה ג — רק לילות, בלי ימי יום

קלט: 0 רגיל, 0 ערב מנוחה, 0 מנוחה, 3 לילות בשבוע.
→ תקין. מעבד המשמרות יחשב לפי הלילות בלבד.

### 8. רמה ג — קלט חודשי עם שברים

קלט: 13.5 לילות בחודש → 13.5 / 4.33 = 3.118... → עיגול ל-3.1 → מחזור 10.
→ סה"כ 31 לילות ב-10 שבועות.

### 9. חודש ראשון/אחרון חלקי

תקופה שמתחילה באמצע שבוע → השבוע הראשון הוא חלקי.
→ הדפוס חל רגיל, אבל ימים שלפני תחילת התקופה לא מקבלים רשומות (המארג אחראי על זה, לא המתרגם).

### 10. טובת עובד — אין מקום ללילה ללא זליגה למנוחה

כל הימים הריקים הם יום שישי בלבד, ולילה בליל חמישי → משויכת לשישי (ערב מנוחה, לא מנוחה) → מותר.
אבל אם היום הריק היחיד הוא שבת ולילה בליל שישי → זולג → fallback לטובת מעביד עם אזהרה.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** מזיזים משמרות יום. רק משמרות לילה ניתנות למיקום אופטימלי.
2. **DO NOT** מייצרים חצי משמרת בשבוע אחד. שברים מתורגמים למחזור עם מספרים שלמים.
3. **DO NOT** מניחים שבוע מתחיל ביום אחר מראשון.
4. **DO NOT** גוזרים שעות נוספות. מתרגם הדפוסים רק מייצר תבניות — מעבד המשמרות מחשב.
5. **DO NOT** מניחים שמשמרת לילה משויכת ליום שבו התחילה. היא משויכת ליום שבו רוב שעותיה.
6. **DO NOT** שוכחים לשמור את הקלט הגולמי (`pattern_source`). המשתמש צריך לראות מה הזין כשהוא פותח את הדפוס.
7. **DO NOT** מאפשרים מחזור ארוך מ-52 שבועות. עיגול + אזהרה.
8. **DO NOT** שמים לילה בליל שישי כש-rest_day=שבת ואין עבודה בשבת.
9. **DO NOT** מערבבים קלט חודשי ושבועי בתוך אותו דפוס. כל סוג יום באותו דפוס חייב להיות באותה יחידת זמן.
10. **DO NOT** מתייחסים למתרגם כחלק מהמארג. הוא מודול נפרד שרץ לפניו.
