---
name: weaver
description: |
  The Weaver (המארג) module for the Claims Wizard (אשף התביעות).
  Weaves 3 input axes (employment periods, work patterns, salary tiers)
  into effective periods + daily records.
  Use this skill whenever working on cross-referencing input axes,
  generating effective periods, creating daily records, detecting
  employment gaps, or computing total employment summary.
  ALWAYS read this skill before touching any period-combining or daily-record code.
---

# המארג — The Weaver

## CRITICAL WARNINGS

1. **המארג הוא היסוד של כל המערכת.** כל מודול אחר (OT, שכר, ותק, חגים, היקף משרה) מניח ש-effective_periods ו-daily_records קיימים ותקינים. שגיאה כאן = שגיאה בכל מקום.
2. **שלושה צירי קלט חייבים לכסות את כל ימי ההעסקה.** כל יום בתוך employment_period חייב להיות מכוסה גם ע"י work_pattern וגם ע"י salary_tier. יום לא מכוסה = שגיאת ולידציה, לא ניחוש.
3. **המארג לא ממציא נתונים.** אם יש פער בכיסוי — עוצרים ומדווחים למשתמש. לא ממלאים ערכי ברירת מחדל.
4. **תקופות אטומיות = צירוף ייחודי אחד.** כל effective_period מייצגת טווח ימים עם **אותו** employment_period + work_pattern + salary_tier. שינוי בכל ציר = תקופה חדשה.
5. **daily_records נוצרות לכל יום — גם ימים שלא עבד בהם.** כל יום קלנדרי בתוך employment_period מקבל רשומה. ימים שלא עבד בהם מסומנים `is_work_day: false`.
6. **daily_records כוללות shift_templates.** כל יום עבודה מקבל את תבניות המשמרות הספציפיות שלו מהדפוס. ה-OT pipeline צורך אותן.
7. **המארג לא טוען שעות שבת ולא מחשב day_segments.** זו אחריות OT stage 3.5. המארג שם `is_rest_day` קלנדרי (boolean) בלבד.
8. **המארג מחשב Duration (ערכים מספריים).** days, months_decimal, years_decimal וכו' — חישוב מתמטי מ-start/end, המארג אחראי. שדה `display` (מחרוזת עברית) נוצר בפאזה 4 ע"י פורמטר Duration.
9. **ימי פער (בין employment_periods) לא מופיעים ב-daily_records.** רק ימים שבתוך employment_period.

---

## Conceptual Model

```
┌─────────────────────────────────────────────────────┐
│  SSOT.input                                         │
│                                                     │
│  ציר 1: employment_periods  ──┐                     │
│  [────EP1────]  [────EP2────] │                     │
│                               │                     │
│  ציר 2: work_patterns  ──────┤                     │
│  [──WP1──]  [────WP2────]    │                     │
│                               │                     │
│  ציר 3: salary_tiers  ───────┘                     │
│  [───ST1───]  [──ST2──]                             │
│                                                     │
│  + rest_day                                         │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│  שלב 1: ולידציה                                      │
│  - בדיקת טווחים תקינים                               │
│  - בדיקת חפיפות פנימיות בתוך ציר                     │
│  - בדיקת כיסוי מלא חוצה צירים                        │
│  - איסוף שגיאות                                      │
└──────────────────┬───────────────────────────────────┘
                   │ ✓ valid
                   ▼
┌──────────────────────────────────────────────────────┐
│  שלב 2: Sweep Line                                   │
│  - איסוף כל נקודות הגבול מכל הצירים                   │
│  - מיון כרונולוגי                                     │
│  - חיתוך לתקופות אטומיות                              │
│  - מיזוג רצופים עם אותו צירוף (בתוך אותה EP)         │
│  - כל אטום = (employment, pattern, salary) ייחודי     │
└──────────────────┬───────────────────────────────────┘
                   │ List<EffectivePeriod>
                   ▼
┌──────────────────────────────────────────────────────┐
│  שלב 3: פירוט יומי                                    │
│  - לכל effective_period → רשומה לכל יום               │
│  - is_work_day מדפוס העבודה                           │
│  - is_rest_day מיום המנוחה (boolean קלנדרי)           │
│  - shift_templates + break_templates מהדפוס           │
│  - ימים שלא עובד בהם: is_work_day=false, templates=[] │
└──────────────────┬───────────────────────────────────┘
                   │ List<DailyRecord>
                   ▼
┌──────────────────────────────────────────────────────┐
│  שלב 4: פערים וסיכום                                  │
│  - זיהוי פערי העסקה בין employment_periods            │
│  - חישוב total_employment                             │
│  - חישוב Duration (מספרי) לכל תקופה/פער/סיכום         │
│  - שדה display נוצר בפאזה 4 (פורמטר)                   │
└──────────────────────────────────────────────────────┘
```

---

## מבנה קוד

המארג הוא **מודול ארכיטקטוני אחד** עם נקודת כניסה אחת ונקודת יציאה אחת. אבל **בקוד** הוא מורכב מ-4 מנועים עצמאיים + מנוע מתכלל:

```
weaver/
├── orchestrator.py          # מנוע מתכלל — נקודת כניסה יחידה
│                            # קורא ל-4 המנועים בסדר, מחזיר תוצאה או שגיאות
├── validator.py             # מנוע 1 — ולידציה (שלב 1)
├── sweep.py                 # מנוע 2 — sweep line + מיזוג (שלב 2)
├── daily_records.py         # מנוע 3 — פירוט יומי (שלב 3)
├── gaps.py                  # מנוע 4 — פערים + סיכום (שלב 4)
└── tests/
    ├── test_validator.py    # unit tests לכל מנוע בנפרד
    ├── test_sweep.py
    ├── test_daily_records.py
    ├── test_gaps.py
    └── test_orchestrator.py # integration tests
```

**עקרון:** כל מנוע הוא פונקציה טהורה (pure function) — מקבל קלט, מחזיר פלט, ללא side effects. רק ה-orchestrator כותב ל-SSOT. כל מנוע ניתן לבדיקה ב-unit test עצמאי.

```python
# orchestrator.py — pseudocode
def run_weaver(employment_periods, work_patterns, salary_tiers, rest_day) -> WeaverResult:
    errors = validate(employment_periods, work_patterns, salary_tiers)
    if errors:
        return WeaverResult(success=False, errors=errors)

    atoms = sweep(employment_periods, work_patterns, salary_tiers)
    effective_periods = build_effective_periods(atoms, work_patterns, salary_tiers)
    daily_records = generate_daily_records(effective_periods, rest_day)
    gaps = detect_gaps(employment_periods)
    total = compute_total(employment_periods, gaps)

    return WeaverResult(
        success=True,
        effective_periods=effective_periods,
        daily_records=daily_records,
        employment_gaps=gaps,
        total_employment=total
    )
```

---

## שלב 1: ולידציה

### 1.1 ולידציה פנימית לכל ציר

לכל ציר בנפרד (employment_periods, work_patterns, salary_tiers):

```
function validateAxis(axis_items, axis_name):
  errors = []

  // בדיקה 1: טווחים תקינים
  for item in axis_items:
    if item.start > item.end:
      errors.append({
        type: "invalid_range",
        axis: axis_name,
        item: item.id,
        start: item.start,
        end: item.end
      })

  // בדיקה 2: אין חפיפות בתוך הציר
  sorted = sort(axis_items, by: start)
  for i in 1..sorted.length-1:
    if sorted[i].start <= sorted[i-1].end:
      errors.append({
        type: "overlap_within_axis",
        axis: axis_name,
        item_a: sorted[i-1].id,
        item_b: sorted[i].id,
        overlap_start: sorted[i].start,
        overlap_end: min(sorted[i-1].end, sorted[i].end)
      })

  return errors
```

### 1.2 ולידציה חוצת צירים — בדיקת כיסוי

כל יום שנמצא בתוך employment_period חייב להיות מכוסה **גם** ע"י work_pattern **וגם** ע"י salary_tier.

```
function validateCoverage(employment_periods, work_patterns, salary_tiers):
  errors = []

  // ממירים כל ציר לאינטרוולים ממויינים
  // סורקים ליניארית — O(n) על מספר התקופות, לא על ימים
  for ep in employment_periods:
    uncovered_wp = findUncoveredRanges(ep.start, ep.end, work_patterns)
    for range in uncovered_wp:
      errors.append({
        type: "uncovered_range",
        axis: "work_patterns",
        employment_period: ep.id,
        gap_start: range.start,
        gap_end: range.end
      })

    uncovered_st = findUncoveredRanges(ep.start, ep.end, salary_tiers)
    for range in uncovered_st:
      errors.append({
        type: "uncovered_range",
        axis: "salary_tiers",
        employment_period: ep.id,
        gap_start: range.start,
        gap_end: range.end
      })

  return errors
```

### 1.3 תגובה לשגיאות ולידציה

```
if errors is not empty:
  // עצור. אל תמשיך לשלב 2.
  // החזר את רשימת השגיאות ל-UI.
  // המשתמש חייב לתקן את הקלט לפני שאפשר לחשב.
  return { success: false, errors: errors }
```

**אין fallback. אין ערכי ברירת מחדל. אין "נשתמש בדפוס האחרון שהיה".**

---

## שלב 2: Sweep Line — יצירת תקופות אטומיות

### 2.1 איסוף נקודות גבול

```
function collectBoundaries(employment_periods, work_patterns, salary_tiers):
  boundaries = Set<date>()

  for ep in employment_periods:
    boundaries.add(ep.start)
    boundaries.add(ep.end + 1 day)    // exclusive end

  for wp in work_patterns:
    boundaries.add(wp.start)
    boundaries.add(wp.end + 1 day)

  for st in salary_tiers:
    boundaries.add(st.start)
    boundaries.add(st.end + 1 day)

  return sort(boundaries)
```

**למה `end + 1`?** כי הטווחים הם inclusive (`start` עד `end` כולל). נקודת הגבול היא היום הראשון שלא שייך לתקופה.

### 2.2 יצירת אטומים

```
function createAtomicPeriods(boundaries, employment_periods, work_patterns, salary_tiers):
  atoms = []
  sorted_boundaries = sort(boundaries)

  for i in 0..sorted_boundaries.length - 2:
    atom_start = sorted_boundaries[i]
    atom_end = sorted_boundaries[i + 1] - 1 day   // inclusive end

    // מי פעיל בטווח הזה?
    ep = employment_periods.find(ep => ep.start <= atom_start AND ep.end >= atom_end)
    if ep is null:
      continue    // לא בתקופת העסקה — דילוג (פער או מחוץ לתקופה)

    wp = work_patterns.find(wp => wp.start <= atom_start AND wp.end >= atom_end)
    st = salary_tiers.find(st => st.start <= atom_start AND st.end >= atom_end)

    // הולידציה בשלב 1 מבטיחה ש-wp ו-st קיימים
    assert wp is not null AND st is not null

    atoms.append({
      start: atom_start,
      end: atom_end,
      employment_period_id: ep.id,
      work_pattern_id: wp.id,
      salary_tier_id: st.id
    })

  return atoms
```

### 2.3 מיזוג אטומים רצופים עם אותו צירוף

```
function mergeConsecutiveAtoms(atoms):
  if atoms is empty: return []
  merged = [atoms[0]]

  for i in 1..atoms.length - 1:
    current = atoms[i]
    last = merged.last()

    same_combo = (
      current.employment_period_id == last.employment_period_id AND
      current.work_pattern_id == last.work_pattern_id AND
      current.salary_tier_id == last.salary_tier_id
    )
    consecutive = (current.start == last.end + 1 day)

    if same_combo AND consecutive:
      last.end = current.end    // הרחב
    else:
      merged.append(current)

  return merged
```

**חשוב:** מיזוג רק בתוך **אותה** employment_period. תקופות העסקה שונות = תקופות אפקטיביות נפרדות, גם אם הצירוף (WP, ST) זהה. הפרדה בין תקופות העסקה היא מידע משפטי חשוב.

### 2.4 בניית effective_periods

```
function buildEffectivePeriods(merged_atoms, work_patterns, salary_tiers):
  result = []

  for i, atom in enumerate(merged_atoms):
    wp = work_patterns.find(wp => wp.id == atom.work_pattern_id)
    st = salary_tiers.find(st => st.id == atom.salary_tier_id)

    result.append({
      id: "EP" + (i + 1),
      start: atom.start,
      end: atom.end,
      duration: computeDuration(atom.start, atom.end),  // מספרי (display נוצר בפאזה 4)
      employment_period_id: atom.employment_period_id,
      work_pattern_id: atom.work_pattern_id,
      salary_tier_id: atom.salary_tier_id,

      // Denormalized (from axes)
      pattern_work_days: wp.work_days,
      // תבניות משמרות — 3 מצבים (ראה סעיף 3.4):
      pattern_default_shifts: wp.default_shifts,       // מצב א (ברירת מחדל)
      pattern_default_breaks: wp.default_breaks,       // מצב א (ברירת מחדל)
      pattern_per_day: wp.per_day,                     // מצב ב (לפי יום בשבוע) — null אם לא רלוונטי
      pattern_daily_overrides: wp.daily_overrides,     // מצב ג (לפי תאריך) — null אם לא רלוונטי
      salary_amount: st.amount,
      salary_type: st.type,
      salary_net_or_gross: st.net_or_gross
    })

  return result
```

---

## שלב 3: פירוט יומי — Daily Records

### 3.1 יצירת רשומה לכל יום

לכל יום קלנדרי בתוך effective_period — **גם ימים שלא עבד בהם**.

```
function generateDailyRecords(effective_periods, rest_day):
  records = []

  for ep in effective_periods:
    for day in range(ep.start, ep.end):    // inclusive
      dow = dayOfWeek(day)                  // 0=ראשון..6=שבת
      is_rest = isRestDay(dow, rest_day)
      is_work = isWorkDay(dow, ep, day, is_rest)

      // shift_templates — מהדפוס, ליום הספציפי הזה
      if is_work:
        templates = getShiftTemplatesForDay(ep, day, dow)
        break_templates = getBreakTemplatesForDay(ep, day, dow)
      else:
        templates = []
        break_templates = []

      records.append({
        date: day,
        effective_period_id: ep.id,
        day_of_week: dow,
        is_work_day: is_work,
        is_rest_day: is_rest,

        // תבניות משמרות (OT pipeline צורך)
        shift_templates: templates,
        break_templates: break_templates,

        // day_segments — null, ימולא ע"י OT stage 3.5
        day_segments: null
      })

  return records
```

### 3.2 פונקציות עזר

```
REST_DAY_MAP = {
  "saturday": 6,    // שבת
  "friday": 5,      // שישי
  "sunday": 0       // ראשון
}

function isRestDay(day_of_week, rest_day):
  return day_of_week == REST_DAY_MAP[rest_day]

function isWorkDay(day_of_week, effective_period, day, is_rest_day):
  // יום מנוחה גובר — גם אם הדפוס כולל אותו
  if is_rest_day:
    return false
  return day_of_week in effective_period.pattern_work_days
```

**הערה חשובה:** `is_work_day` מתייחס לדפוס הרגיל בלבד — "האם ביום הזה של השבוע העובד אמור לעבוד?". זה **לא** מביא בחשבון חגים, חופשות, מחלה, או היעדרויות. אלה מטופלים בזכויות הספציפיות (חגים, חופשה) ולא ברמת ה-daily_record.

### 3.3 תבניות משמרות — גמישות מלאה

```
function getShiftTemplatesForDay(ep, day, day_of_week):
  // work_pattern כולל shifts — תבניות משמרות.
  // התבנית יכולה להיות:
  //   א. אחידה לכל ימי הדפוס (מצב פשוט)
  //   ב. שונה ליום בשבוע ספציפי
  //   ג. שונה ליום קלנדרי ספציפי (מצב מתקדם)
  //
  // ה-schema של work_patterns צריך לתמוך בכל הגמישות הזו.
  // המארג פשוט שולף את התבנית הנכונה ליום הנתון.
  //
  // ראה סעיף "גמישות דפוסי עבודה" למטה.

  wp = getWorkPattern(ep.work_pattern_id)
  return wp.getShiftsForDay(day, day_of_week)
```

```
function getBreakTemplatesForDay(ep, day, day_of_week):
  wp = getWorkPattern(ep.work_pattern_id)
  return wp.getBreaksForDay(day, day_of_week)
```

### 3.4 גמישות דפוסי עבודה

הקלט של work_patterns צריך לתמוך בשלושה מצבים:

**מצב א — דפוס אחיד:** shifts/breaks זהים לכל ימי העבודה.
```
{
  work_days: [0,1,2,3,4],
  shifts: [{start: "07:00", end: "16:00"}],
  breaks: [{start: "12:00", end: "12:30"}]
}
```

**מצב ב — דפוס לפי יום בשבוע:** shifts/breaks שונים ליום ספציפי.
```
{
  work_days: [0,1,2,3,4],
  per_day: {
    0: { shifts: [{start: "07:00", end: "16:00"}] },    // ראשון
    4: { shifts: [{start: "07:00", end: "13:00"}] }     // חמישי קצר
  },
  default: { shifts: [{start: "07:00", end: "16:00"}] } // שאר הימים
}
```

**מצב ג — דפוס לפי תאריך קלנדרי:** טווח קלט מקסימלי — כל יום עם דפוס ייחודי.
```
{
  daily_overrides: {
    "2024-03-15": { shifts: [{start: "06:00", end: "14:00"}] },
    "2024-03-16": { shifts: [{start: "14:00", end: "22:00"}] }
  }
}
```

**סדר עדיפויות:** daily_override > per_day > default.

המארג לא מפרש את הדפוס — רק שולף ממנו תבניות. ה-schema של work_patterns צריך לתמוך בכל שלושת המצבים, ופונקציית `getShiftsForDay` מתעדפת לפי הסדר.

---

## שלב 4: פערים וסיכום

### 4.1 זיהוי פערי העסקה

פער = רווח בין employment_periods. **לא** בין effective_periods.

```
function detectEmploymentGaps(employment_periods):
  gaps = []
  sorted = sort(employment_periods, by: start)

  for i in 1..sorted.length - 1:
    prev_end = sorted[i - 1].end
    curr_start = sorted[i].start
    gap_start = prev_end + 1 day

    if gap_start < curr_start:
      gaps.append({
        start: gap_start,
        end: curr_start - 1 day,
        duration: computeDuration(gap_start, curr_start - 1 day),  // מספרי
        before_period_id: sorted[i - 1].id,
        after_period_id: sorted[i].id
      })

  return gaps
```

### 4.2 סיכום תקופת העסקה

```
function computeTotalEmployment(employment_periods, gaps):
  sorted = sort(employment_periods, by: start)

  return {
    first_day: sorted[0].start,
    last_day: sorted.last().end,
    total_duration: computeDuration(sorted[0].start, sorted.last().end),
    worked_duration: sumDurations(employment_periods),    // סכום Duration של כל תקופה
    gap_duration: sumDurations(gaps),                     // סכום Duration של כל פער
    periods_count: sorted.length,
    gaps_count: gaps.length
  }
```

---

## סדר הכתיבה ל-SSOT

המארג כותב ל-SSOT בסדר הזה, בקריאה אחת:

```
1. SSOT.effective_periods  ← שלב 2 (כולל Duration מספרי)
2. SSOT.daily_records      ← שלב 3
3. SSOT.employment_gaps    ← שלב 4 (כולל Duration מספרי)
4. SSOT.total_employment   ← שלב 4 (כולל Duration מספרי)
```

**שדות `display` ב-Duration נוצרים בפאזה 4 (פורמטר) — המארג כותב רק ערכים מספריים.**

**שום מודול אחר לא כותב לשדות 1-4.** המארג הוא הבעלים הבלעדי.
**day_segments ב-daily_records נכתב ע"י OT stage 3.5** — זהו השדה היחיד ב-daily_records שמודול אחר כותב.

---

## SSOT Data Structures

### daily_records (full schema)

```
SSOT.daily_records: List<{
  date: date                             // תאריך קלנדרי
  effective_period_id: string            // → effective_periods[].id
  day_of_week: integer                   // 0=ראשון..6=שבת
  is_work_day: boolean                   // מדפוס עבודה (לא מביא בחשבון חגים)
  is_rest_day: boolean                   // יום המנוחה — boolean קלנדרי

  // תבניות משמרות (המארג כותב, OT stage 1 צורך)
  shift_templates: List<{               // ריק אם !is_work_day
    start_time: time                     // 07:00
    end_time: time                       // 16:00
  }>
  break_templates: List<{               // ריק אם !is_work_day
    start_time: time
    end_time: time
  }>

  // day_segments — OT stage 3.5 כותב (null עד שרץ)
  day_segments: List<{
    start: time                          // 00:00
    end: time                            // 17:30
    type: "regular" | "eve_of_rest" | "rest"
  }>?                                    // null = טרם חושב
}>
```

### effective_periods, employment_gaps, total_employment

ללא שינוי מה-SSOT skill הקיים. **Duration (ערכים מספריים) מחושב ע"י המארג. שדה `display` נוצר בפאזה 4 (פורמטר Duration).**

---

## דוגמה מלאה

### קלט

```
employment_periods:
  EMP_A: 2023-01-01 → 2023-12-31
  EMP_B: 2024-03-01 → 2024-12-31

work_patterns:
  WP1: 2023-01-01 → 2024-06-30  (א'–ה' 07:00–16:00, הפסקה 12:00–12:30)
  WP2: 2024-07-01 → 2024-12-31  (א'–ה' 08:00–17:00, הפסקה 12:00–12:30)

salary_tiers:
  ST1: 2023-01-01 → 2023-08-31  (₪40/שעה ברוטו)
  ST2: 2023-09-01 → 2024-12-31  (₪45/שעה ברוטו)

rest_day: saturday
```

### שלב 2 — Sweep Line

נקודות גבול:
```
2023-01-01, 2023-09-01, 2024-01-01, 2024-03-01, 2024-07-01, 2025-01-01
```

אטומים (אחרי סינון ימים שלא בהעסקה):
```
[2023-01-01 → 2023-08-31]  EMP_A + WP1 + ST1
[2023-09-01 → 2023-12-31]  EMP_A + WP1 + ST2
[2024-03-01 → 2024-06-30]  EMP_B + WP1 + ST2
[2024-07-01 → 2024-12-31]  EMP_B + WP2 + ST2
```

מיזוג: EP3 ו-EP4 הם employment_period שונה (EMP_B) אבל גם אם היו באותה EMP, WP שונה = לא ממזגים. → 4 effective periods.

### שלב 3 — Daily Records (מדגם)

```
2023-01-01 (ראשון): EP1, is_work=true,  is_rest=false, shifts=[{07:00-16:00}], breaks=[{12:00-12:30}]
2023-01-06 (שישי):  EP1, is_work=false, is_rest=false, shifts=[], breaks=[]
2023-01-07 (שבת):   EP1, is_work=false, is_rest=true,  shifts=[], breaks=[]
...
2024-01-15 (שני):   — לא קיים (פער בהעסקה, אין daily_record)
...
2024-03-01 (שישי):  EP3, is_work=false, is_rest=false, shifts=[], breaks=[]
2024-03-03 (ראשון): EP3, is_work=true,  is_rest=false, shifts=[{07:00-16:00}], breaks=[{12:00-12:30}]
```

### שלב 4 — פערים וסיכום

```
employment_gaps:
  GAP1: 2024-01-01 → 2024-02-29  (בין EMP_A ל-EMP_B)

total_employment:
  first_day: 2023-01-01
  last_day: 2024-12-31
  periods_count: 2
  gaps_count: 1
```

---

## Edge Cases

### 1. שינוי שכר באמצע חודש
```
ST1 מסתיים 15.6, ST2 מתחיל 16.6
→ שתי effective_periods באותו חודש
→ daily_records: 1-15 מצביעות ל-EP עם ST1, 16-30 ל-EP עם ST2
→ salary conversion יטפל ביחסיות (ראה סקיל salary-conversion)
```

### 2. שינוי דפוס עבודה באמצע שבוע
```
WP1 מסתיים ביום שלישי 18.6, WP2 מתחיל ברביעי 19.6
→ effective_period חדשה מ-19.6
→ daily_records: א'-ג' מ-EP ישנה (עם shift_templates של WP1), ד'-ו' מ-EP חדשה (WP2)
→ OT pipeline יטפל בשבוע המפוצל (שבוע חלקי — ראה סקיל OT)
```

### 3. Employment periods צמודות ללא פער
```
EMP_A: 2023-01-01 → 2023-06-30
EMP_B: 2023-07-01 → 2023-12-31
→ אין פער (EMP_B.start = EMP_A.end + 1)
→ employment_gaps = []
→ effective_periods נפרדות (employment_period_id שונה) — גם אם WP ו-ST זהים
```

### 4. דפוס עבודה שכולל יום מנוחה
```
work_days: [0,1,2,3,4,5,6]  (א'-שבת)
rest_day: saturday
→ שבת: is_work_day=false (יום מנוחה גובר), is_rest_day=true, shift_templates=[]
→ אזהרה (warning, לא error): "דפוס עבודה WP1 כולל את יום המנוחה (שבת)"
```

### 5. תקופת העסקה של יום אחד
```
EMP: 2024-03-15 → 2024-03-15
→ effective_period אחת של יום אחד
→ daily_record אחת
→ תקין לחלוטין
```

### 6. דפוס שונה לכל יום בשבוע
```
WP1: per_day = {
  0: {shifts: [{06:00-14:00}]},    // ראשון
  1: {shifts: [{14:00-22:00}]},    // שני
  2: {shifts: [{06:00-14:00}]},    // שלישי
  3: {shifts: [{14:00-22:00}]},    // רביעי
  4: {shifts: [{06:00-12:00}]}     // חמישי
}
→ כל daily_record מקבל shift_templates ייחודיות ליום שלו
→ אפס אובדן מידע — הדפוס "מתפרק" ברמת היום
```

### 7. דפוס עם שתי משמרות ביום
```
WP1: shifts = [{06:00-14:00}, {16:00-22:00}]
→ daily_record.shift_templates = [{06:00-14:00}, {16:00-22:00}]
→ OT stage 1 יבדוק gap (2h ≤ 3h) → shift אחת עם break
```

### 8. ימי לא-עבודה ב-daily_records
```
2024-03-08 (שישי, לא עובד בדפוס 5 ימים):
→ is_work_day=false, is_rest_day=false, shift_templates=[], break_templates=[]
→ הרשומה קיימת! (OT, ותק, חגים צריכים אותה)

2024-03-09 (שבת, יום מנוחה):
→ is_work_day=false, is_rest_day=true, shift_templates=[], break_templates=[]
→ הרשומה קיימת!
```

---

## Relationship to Other Skills

### → OT Pipeline
- **Stage 1:** צורך `shift_templates` + `break_templates` מ-daily_records. ממיר תבניות למשמרות קונקרטיות (datetime) בהקשר של תאריך ספציפי.
- **Stage 3.5 (חדש):** כותב `day_segments` ל-daily_records אחרי טעינת שעות שבת.
- **Stage 4:** קורא `day_segments` כדי לקבוע אם משמרת היא ערב מנוחה (≥2h חפיפה).

### → פורמטר Duration (פאזה 4)
- קורא `Duration` מ-effective_periods, employment_gaps, total_employment.
- ממלא שדה `display` (מחרוזת עברית).
- פונקציית עזר — לא מודול עצמאי.

### → ותק (Seniority)
- צורך daily_records: "עבד לפחות יום אחד בחודש?" → בודק `is_work_day`.
- לא צריך shift_templates, day_segments, או שום דבר מורכב.

### → חגים (Holidays)
- צורך daily_records: "האם העובד מועסק ביום החג?" → בודק אם daily_record קיים לתאריך.
- צורך `is_rest_day` (boolean) לצורך סינון חג שחל ביום מנוחה.
- **day_segments לא משפיעים על חגים** — חגים הם קלנדריים (יום שלם).

### → אגרגטור (③, פאזה 1)
- צורך shifts (מ-OT pipeline) → מסכם לכל (effective_period × month): work_days, shifts, regular_hours, ot_hours.
- כותב שדות שעות ל-period_month_records.
- **חייב לרוץ אחרי OT pipeline ולפני המרת שכר.**

### → המרת שכר (Salary Conversion)
- צורך effective_periods (salary data) + period_month_records (שדות שעות מאגרגטור).
- לא קורא daily_records ישירות.

### → היקף משרה (Job Scope)
- צורך period_month_records (total_regular_hours מאגרגטור).
- לא קורא daily_records ישירות.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** ממלאים ברירות מחדל ליום לא מכוסה. אם salary_tier חסר ליום — שגיאת ולידציה.
2. **DO NOT** ממזגים effective_periods מ-employment_periods שונות. תקופת העסקה שונה = תקופה אפקטיבית נפרדת תמיד.
3. **DO NOT** מחשבים effective_periods יום-יום. ה-sweep line עובד על גבולות בלבד — O(n) תקופות, לא O(n) ימים. רק שלב 3 סורק יום-יום.
4. **DO NOT** שמים לוגיקת חגים ב-daily_records. `is_work_day` = דפוס שבועי בלבד. חגים = סקיל holidays.
5. **DO NOT** משמיטים daily_records לימים שלא עבד בהם (בתוך employment_period). שבתות, ימי חופש בדפוס, וכו' — כולם צריכים רשומה.
6. **DO NOT** מייצרים daily_records לימי פער (בין employment_periods). פער = לא מועסק = אין רשומה.
7. **DO NOT** מניחים שצירים ממויינים. תמיד למיין לפני עיבוד.
8. **DO NOT** טוענים שעות שבת או מחשבים day_segments. זו אחריות OT stage 3.5.
9. **DO NOT** משאירים Duration ריק. המארג מחשב ערכים מספריים (days, months_decimal, years_decimal). שדה `display` נוצר בפאזה 4.
10. **DO NOT** מניחים דפוס אחיד לכל ימי השבוע. work_pattern יכול להכיל per_day ו-daily_overrides.
