---
name: overtime-calculation
description: |
  Israeli labor law overtime calculation engine for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on overtime (שעות נוספות) calculation logic, 
  shift classification, weekly/daily threshold computation, rest-window (חלון מנוחה) 
  placement, or overtime pricing. This is the most complex calculation in the system.
  ALWAYS read this skill before touching any overtime-related code.
---

# Overtime Calculation — Israeli Labor Law

## CRITICAL WARNINGS

1. **NO ROUNDING. EVER.** All hours are decimal (e.g., 7.5, 8.4). Never round up or down.
2. **No "lazy" shortcuts.** The algorithm must handle ANY shift pattern, not just common ones. If it only works on golden-test cases, it is BROKEN.
3. **Overtime is per-SHIFT, not per-day.** The law says "daily" but means per-shift. A worker can have multiple shifts in one calendar day.
4. **The claim amount is the DIFFERENCE only.** Overtime section claims 25%/50%/75%/100% — NOT 125%/150%/175%/200%. Base pay (100%) belongs in the salary completion (השלמת שכר) section.
5. **Every right is toggleable.** The user can mark any right as "paid by employer" to exclude it from the claim.
6. **ALL THRESHOLDS MUST BE CONFIGURABLE.** Never hardcode threshold values. Store them in a configuration object with sensible defaults. The user must be able to override any threshold from the UI.

```
OTConfig {
  weekly_cap: 42              // סף שבועי — ברירת מחדל 42
  threshold_5day: 8.4         // סף יומי בשבוע 5 ימים
  threshold_6day: 8.0         // סף יומי בשבוע 6 ימים
  threshold_eve_rest: 7.0     // סף ערב מנוחה
  threshold_night: 7.0        // סף משמרת לילה
  tier1_max_hours: 2          // שעות מקסימום ב-Tier 1 לפני מעבר ל-Tier 2
}
```
All calculation logic reads from this config object, never from inline constants.

---

## Conceptual Model

Overtime calculation is a **pipeline** with distinct stages. Each stage has clear inputs and outputs. **Never collapse stages together** — that's what caused the previous project to fail.

```
Raw Work Entries
       │
       ▼
┌─────────────────┐
│ 1. SHIFT        │  Group raw entries into shifts
│    ASSEMBLY     │  (break ≤ 3h = same shift)
└────────┬────────┘
         │ List<Shift>
         ▼
┌─────────────────┐
│ 2. SHIFT        │  Assign each shift to a calendar day & week
│    ASSIGNMENT   │  (majority rule, tie → earlier)
└────────┬────────┘
         │ List<AssignedShift>
         ▼
┌─────────────────┐
│ 3. WEEK         │  Determine week type (5/6) per week
│    CLASSIFICATION│  Count distinct work days in the week
└────────┬────────┘
         │ List<ClassifiedWeek>
         ▼
┌─────────────────┐
│ 4. THRESHOLD    │  For each shift: determine applicable daily threshold
│    RESOLUTION   │  (8.4 / 8 / 7 based on week type + exceptions)
└────────┬────────┘
         │ List<ShiftWithThreshold>
         ▼
┌─────────────────┐
│ 5. DAILY OT     │  Per shift: hours beyond threshold → OT tiers
│    DETECTION    │  Tier 1 = first 2 OT hours, Tier 2 = remaining
└────────┬────────┘
         │ List<ShiftWithDailyOT>
         ▼
┌─────────────────┐
│ 6. WEEKLY OT    │  Per week: sum regular hours, if > 42 →
│    DETECTION    │  assign weekly OT to shifts chronologically
└────────┬────────┘
         │ List<ShiftWithAllOT>
         ▼
┌─────────────────┐
│ 7. REST WINDOW  │  Per week: compute 36h rest window placement
│    PLACEMENT    │  (optimization: minimize work hours in window)
└────────┬────────┘
         │ List<ShiftWithRestWindow>
         │
═════════╪═══════════════════════════════════════════════
  STAGES │ 1-7 → run in INPUT PROCESSING (step 2)
  OUTPUT │ → writes shifts + weeks to SSOT (hours only, no ₪)
         │
  STAGE  │ 8 → runs in RIGHTS CALCULATION (step 4)
  REASON │ → needs salary_hourly from salary conversion (step 3)
═════════╪═══════════════════════════════════════════════
         │
         │ + salary_hourly from SSOT.period_month_records
         ▼
┌─────────────────┐
│ 8. PRICING      │  Per shift-hour: combine OT tier (0/1/2) ×
│                 │  day type (regular/rest) → rate
│                 │  Then subtract base (100%) → claim amount
└─────────────────┘
```

### Why the split?

Stages 1–7 produce `regular_hours` and `week_type` which are consumed by:
- **Salary conversion** (needs regular_hours per month to compute salary_hourly)
- **Job scope** (needs regular_hours per month)
- **Holidays** (needs week_type per week)

Stage 8 needs `salary_hourly` which only exists after salary conversion runs. The dependency chain is: stages 1–7 → salary conversion → stage 8. Stages 1–7 cannot be deferred.

---

## Stage Details

### Stage 1: Shift Assembly

**Input:** Raw work entries (start_time, end_time per work segment, plus break definitions from work pattern)

**Rules:**
- A shift = continuous work minus breaks
- If gap between two work segments ≤ 3 hours → they are ONE shift with a break
- If gap > 3 hours → two separate shifts
- Shift net hours = total time minus break time (breaks are not worked hours)

**Output:** `List<Shift>` where each Shift has:
- `segments: List<{start: datetime, end: datetime}>` (the actual work parts)
- `breaks: List<{start: datetime, end: datetime}>`
- `net_hours: decimal` (total worked time, no rounding)
- `start: datetime` (start of first segment)
- `end: datetime` (end of last segment)

### Stage 2: Shift Assignment (Day & Week)

**Input:** `List<Shift>`

**Rules for day assignment:**
- A shift belongs to the calendar day (00:00–24:00) in which the MAJORITY of its net hours fall
- Tie → assign to the EARLIER day
- Calendar day = midnight to midnight

**Rules for week assignment:**
- Same majority rule applied to weeks
- Week = Sunday 00:00 to Saturday 24:00
- Tie → assign to EARLIER week

**Output:** `List<AssignedShift>` — each shift now has `assigned_day: date` and `assigned_week: (year, week_number)`

### Stage 3: Week Classification

**Input:** `List<AssignedShift>` grouped by week

**Rules:**
- Count the number of DISTINCT `assigned_day` values in the week that have at least one shift
- If distinct work days > 5 → week type = "6" (six-day week)
- If distinct work days ≤ 5 → week type = "5" (five-day week)

**Output:** Each week tagged with `week_type: 5 | 6`

### Stage 4: Threshold Resolution

**Input:** Each `AssignedShift` with its week's `week_type`

**Base thresholds:**
| Week Type | Daily (Shift) Threshold |
|-----------|------------------------|
| 5         | 8.4 hours              |
| 6         | 8.0 hours              |

**Weekly threshold:** Always 42 hours (regardless of week type)

**Exception 1 — Eve of Rest (ערב מנוחה):**
- Threshold = **7.0 hours** (always)
- Definition: The 24-hour period BEFORE the start of the rest day
- For Saturday rest: 24 hours before candle lighting (כניסת שבת)
  - Candle lighting time varies by DATE and DISTRICT (מחוז)
  - The system must have a lookup table: `(date, district) → candle_lighting_time`
  - Eve of rest starts 24 hours before candle lighting
- For Friday/Sunday rest: the calendar day before (simple 00:00–24:00)
- A shift is classified as "eve of rest" if its `assigned_day` falls within the eve-of-rest window

**Exception 2 — Night Shift (משמרת לילה):**
- Threshold = **7.0 hours** (always)
- Definition: A shift where ≥ 2 hours fall within the 22:00–06:00 window
- Count actual hours of the shift (including across midnight) that overlap with any 22:00–06:00 band

**Combined exceptions:** If a shift qualifies as BOTH eve-of-rest AND night shift → threshold is still 7.0 (no further reduction, no stacking)

**Output:** Each shift now has `threshold: decimal` (7.0, 8.0, or 8.4)

### Stage 5: Daily (Per-Shift) Overtime Detection

**Input:** Each shift with `net_hours` and `threshold`

**Rules:**
- If `net_hours <= threshold` → all hours are regular (Tier 0)
- If `net_hours > threshold`:
  - Hours up to threshold → Tier 0 (regular)
  - Next 2 hours → Tier 1 (first overtime tier)
  - Remaining hours → Tier 2 (second overtime tier)

**Example:** Shift of 11h, threshold 8.0:
- 8.0h Tier 0, 2.0h Tier 1, 1.0h Tier 2

**Output:** Each shift annotated with:
- `regular_hours: decimal`
- `ot_tier1_hours: decimal`
- `ot_tier2_hours: decimal`
- `daily_ot_total: decimal` (tier1 + tier2)

### Stage 6: Weekly Overtime Detection

**Input:** All shifts in a week, already annotated with daily OT

**Rules:**
1. Sum all `regular_hours` (Tier 0 only!) across all shifts in the week
2. If sum ≤ 42 → no weekly overtime
3. If sum > 42 → the excess = weekly overtime hours
4. These weekly OT hours are **attributed to the shifts where they were worked**, in **chronological order** (by shift start time)

**CRITICAL — UNIFIED TIER ASSIGNMENT:**
After attributing weekly OT to shifts, each shift has a total OT count = daily OT + weekly OT.
Tier assignment happens **ONCE per shift** on the combined total:
- First 2 OT hours (from any source) → Tier 1
- All remaining OT hours → Tier 2
- **Maximum 2 hours Tier 1 per shift. No exceptions. No separate counting.**

**CRITICAL:** Weekly OT only applies to hours that were NOT already counted as daily OT. The weekly threshold is a "safety net" that catches hours that escaped daily detection.

**Example:** 6 shifts × 8h in week type "6" (threshold 8.0):
- Daily OT per shift: 0 (8h ≤ 8.0)
- Weekly regular total: 48h
- Weekly OT: 48 - 42 = 6h
- Attribution: shifts 1-5 contribute 8h regular each (40h), shift 6 contributes 2h regular (reaching 42), then 6h weekly OT
- Shift 6 total OT: 6h → 2h Tier 1 + 4h Tier 2

**Detailed attribution algorithm:**
1. Sort shifts by start time (chronological)
2. Walk through shifts, accumulating regular hours
3. When accumulated regular > 42, the current shift is the "crossover" shift
4. In the crossover shift: some hours are regular (up to reaching 42 total), rest are weekly OT
5. All subsequent shifts: ALL their regular hours become weekly OT
6. **Per shift: combine daily_ot + weekly_ot → total_ot. First 2h = Tier 1, rest = Tier 2.**

**Output:** Each shift now has:
- `regular_hours: decimal` (may have decreased from stage 5)
- `total_ot_hours: decimal` (daily + weekly combined)
- `ot_tier1_hours: decimal` (first 2 of total_ot, max 2)
- `ot_tier2_hours: decimal` (remainder)

### Stage 7: Rest Window Placement

> **הערה ארכיטקטונית:** שלב 7 מתועד כאן בתוך סקיל שעות נוספות כי זו הזכות העיקרית
> שמשתמשת בו. אבל בקוד — חלון המנוחה צריך להיות **שירות נפרד** (RestDayWindowService)
> כי גם השלמת שכר מולן משתמשת בו. ארכיטקטורת הקוד:
> ```
> ShabbatTimesService (שכבה תחתונה — שליפת זמנים)
>     ↓
> RestDayWindowService (שכבה אמצעית — אופטימיזציית חלון)
>     ↓
> OvertimeCalculator + MulanCalculator (שכבה עליונה — צרכנים)
> ```
> שני הסקיל הנפרדים (זמני שבת, חלון מנוחה) מתועדים כאן לנוחות.
> בקוד — מודולים נפרדים עם ממשק ברור.

**Input:** All shifts in a week + rest day definition + district

**Output:** Per week: `rest_window: {start: datetime, end: datetime}`

#### 7.1 Legal Basis

חוק שעות עבודה ומנוחה, תשי"א-1951, סעיף 7:
המנוחה השבועית חייבת להיות לפחות 36 שעות רצופות, ולעובד יהודי חייבת לכלול את השבת.

**חשוב:** חישוב זה חל **רק על שבתות**. חגים לא נכנסים לחישוב חלון המנוחה
ולא לשעות נוספות. חגים מטופלים בזכות נפרדת ("דמי חגים").

#### 7.2 Four Rules (סדר עדיפויות)

החלון חייב לקיים את כל ארבעת הכללים, בסדר עדיפות יורד:

1. **בדיוק 36 שעות** — לא 35:59, לא 36:01
2. **כיסוי מלא של השבת** — מהדלקת נרות (יום שישי) ועד הבדלה (מוצאי שבת). אף חלק מהשבת לא נשאר מחוץ לחלון
3. **רציפות** — בלוק אחד ללא הפסקות
4. **מינימום שעות עבודה בתעריף מנוחה** — מיקום החלון על ציר הזמן כך שיכלול כמה שפחות שעות עבודה בפועל מחוץ לשבת עצמה

#### 7.3 Shabbat Times — Data Source

הגדרת "שבת" בחוק הישראלי עוקבת אחרי **ההגדרה ההלכתית**:
- **כניסה:** הדלקת נרות — מספר דקות קבוע לפני השקיעה, לפי מנהג המקום
- **יציאה:** הבדלה / צאת הכוכבים — שלושה כוכבים קטנים (שמש 8.5 מעלות מתחת לאופק)

**מקור נתונים: קבצים סטטיים מחושבים מראש**

במקום קריאת API בזמן ריצה, המערכת משתמשת בקבצי נתונים סטטיים שמכילים
זמני כניסת שבת (הדלקת נרות) ויציאת שבת (הבדלה) לכל שבוע, לכל מחוז,
בטווח 1948–2148.

**מבנה הקבצים:**
```
data/shabbat_times/
├── jerusalem.csv
├── tel_aviv.csv
├── haifa.csv
├── south.csv
└── galil.csv
```

**פורמט כל קובץ (CSV):**
```
date,candles,havdalah
2024-01-05,16:13,17:28
2024-01-12,16:19,17:34
...
```

- `date`: תאריך יום שישי (הגרגוריאני) של אותו שבוע
- `candles`: שעת הדלקת נרות (local time, `HH:MM`)
- `havdalah`: שעת הבדלה (local time, `HH:MM`)

**ייצור הקבצים:** סקריפט חד-פעמי (`scripts/generate_shabbat_times.py`) שמחשב
את הזמנים באמצעות ספריית חישוב אסטרונומי (או שואב מ-Hebcal API) ושומר לקבצים.
הסקריפט רץ פעם אחת בפיתוח, לא בזמן ריצה.

**פרמטרי הייצור:** הסקריפט צריך את אותם פרמטרים שהיו נשלחים ל-API:
- קואורדינטות למחוז (ראה 7.4)
- ערך `b` (דקות הדלקת נרות לפני שקיעה, לפי מחוז)
- אזור זמן: `Asia/Jerusalem`
- שיטת חישוב הבדלה: צאת הכוכבים (8.5 מעלות)

**אימות:** לאחר הייצור, מדגם אקראי של ~50 תאריכים מאומת מול Hebcal API
כ-sanity check.

**יתרונות:**
- אפס תלות בשירות חיצוני בזמן ריצה
- אפס latency (lookup ישיר במקום ~20 שניות לתקופה של 3 שנים)
- דטרמיניסטי — אותו קלט תמיד נותן אותה תוצאה
- עובד offline
- נפח: ~10,400 שורות × 5 מחוזות ≈ 2.5MB סה"כ (זניח)

**גישה בקוד:**
```
function getShabbatTimes(date, district) → { candles: datetime, havdalah: datetime }
```
טוען את הקובץ הרלוונטי למחוז, מוצא את השורה לפי תאריך שישי הקרוב ביותר.

#### 7.4 District Configuration (מחוזות)

| מפתח | מחוז | קו רוחב | קו אורך | b (דקות) |
|-------|------|----------|----------|----------|
| `jerusalem` | ירושלים | 31.7683 | 35.2137 | 40 |
| `tel_aviv` | תל אביב-יפו | 32.0853 | 34.7818 | 18 |
| `haifa` | חיפה | 32.7940 | 34.9896 | 30 |
| `south` | באר שבע | 31.2530 | 34.7915 | 18 |
| `galil` | נוף הגליל | 32.7070 | 35.3273 | 18 |

שלושת ערכי ה-b (40, 30, 18) הם מנהגים הלכתיים מבוססים.
ירושלים מקבלת את הדלקת הנרות המוקדמת ביותר (40 דקות לפני שקיעה).

**הערה:** הפער בפועל בין המחוזות הוא דקות בודדות ברוב המקרים, אבל
הקפדה על הזמנים הנכונים חיונית לעמידה בדרישות החוק.

#### 7.5 Optimization Algorithm (אלגוריתם אופטימיזציה)

**מודל:**
```
ציר זמן (שישי → שבת → ראשון):

     שישי בוקר   שישי ערב   שבת בוקר   שבת ערב   ראשון בוקר
     ──────────┬─────────────────────┬──────────────
               │       שבת           │
               │ (נרות → הבדלה)      │
     ──────────┴─────────────────────┴──────────────
     
     ◄─לפני──►│                     │◄───אחרי────►
     (ריפוד)   │    חובה לכלול       │  (ריפוד)
     
     לפני + משך_שבת + אחרי = 36
```

**בעיית אופטימיזציה:**
- משתנה: `before` (שעות ריפוד לפני שבת)
- `after = padding_total - before`
- `window_start = shabbat_start - before`
- `window_end = shabbat_end + after`
- **מטרה:** מזער `work_in_padding = work_hours_in(window_start, shabbat_start) + work_hours_in(shabbat_end, window_end)`

**שיטה — נקודות שבירה (Breakpoints):**

פונקציית המטרה היא **ליניארית למקוטעין** — היא משנה שיפוע רק בנקודות שבהן
מתחילה או נגמרת משמרת. לכן מספיק לבדוק רק את הנקודות הללו:

1. `before = 0` (כל הריפוד אחרי)
2. `before = padding_total` (כל הריפוד לפני)
3. לכל משמרת שנגמרת לפני כניסת שבת: `before = (shabbat_start - entry.end)` ו-`before = (shabbat_start - entry.start)`
4. לכל משמרת שמתחילה אחרי יציאת שבת: `before = padding_total - (entry.start - shabbat_end)` ו-`before = padding_total - (entry.end - shabbat_end)`
5. סנן: רק ערכים בטווח `[0, padding_total]`

**חישוב לכל נקודה:** סכום שעות עבודה שחופפות עם אזורי הריפוד.
**בחר:** הנקודה עם הסכום המינימלי. שוויון → העדף ריפוד אחרי (שרירותי אך עקבי).

**מספר איטרציות:** מקסימום `2 + 4 × מספר_משמרות_סוף_שבוע`. בפועל 2-10.

#### 7.6 Hour Classification

לאחר קביעת החלון, כל שעת עבודה מסווגת:
- שעה שנופלת **בתוך** `[window_start, window_end]` → תעריף יום מנוחה
- שעה שנופלת **מחוץ** → תעריף רגיל

משמרת שחוצה את גבול החלון **מפוצלת** — חלק בתעריף מנוחה, חלק בתעריף רגיל.
דירוג השעות הנוספות (tier) נקבע על פי **כלל המשמרת** ולא משתנה בגבול החלון.

#### 7.7 Data Loading

הנתונים נטענים מקובץ CSV סטטי (ראה 7.3). בתחילת החישוב, טען את כל
השורות הרלוונטיות לטווח התאריכים של תקופת ההעסקה למילון ב-memory:

```
shabbat_cache = loadShabbatTimes(district, start_date, end_date)
// Returns Map<friday_date, {candles: datetime, havdalah: datetime}>
```

כל קריאה ל-`getShabbatTimes(date, district)` מגיעה מה-cache. אין I/O בזמן חישוב.

#### 7.8 Seasonal Variation

משך השבת יציב יחסית (~25 שעות) כל השנה, כי גם כניסה וגם יציאה זזות יחד.
הריפוד תמיד בסביבות 10-11 שעות.

| עונה | דוגמה (תל אביב) | נרות | הבדלה | ריפוד |
|------|-----------------|------|-------|-------|
| חורף (ינואר) | 16:37 | 17:42 | ~10:55 |
| קיץ (יוני) | 19:30 | 20:30 | ~11:00 |

### Stage 8: Pricing

**⚠ ARCHITECTURE NOTE:** Stage 8 runs in the **Rights Calculation phase**, NOT in the Input Processing phase with stages 1–7. This is because pricing requires `salary_hourly` from the salary conversion module, which in turn requires `regular_hours` from stages 1–7. The dependency chain is: stages 1-7 → salary conversion → stage 8 (pricing).

**Input:** Each shift with OT tiers + rest window + salary_hourly (from SSOT period_month_records)

**Rate table:**

| OT Tier | Regular Day | Rest Window |
|---------|-------------|-------------|
| Tier 0  | 100%        | 150%        |
| Tier 1  | 125%        | 175%        |
| Tier 2  | 150%        | 200%        |

**Per-hour pricing for cross-boundary shifts:**
- For each hour (or fraction) in a shift, determine if it falls inside or outside the rest window
- Apply the rate based on BOTH its tier AND its rest/regular status
- A single shift can have hours at multiple different rates

**Claim calculation:**
- The overtime CLAIM is only the DIFFERENCE from base pay:

| OT Tier | Regular Day Claim | Rest Window Claim |
|---------|-------------------|-------------------|
| Tier 0  | 0% (no claim)     | 50%               |
| Tier 1  | 25%               | 75%               |
| Tier 2  | 50%               | 100%              |

**Toggle: "Employer paid rest premium"** — If ON:
- Rest window Tier 0 claim = 0% (instead of 50%)
- Rest window Tier 1 claim = 25% (instead of 75%)
- Rest window Tier 2 claim = 50% (instead of 100%)
- (Essentially: only the OT bonus, not the rest premium)

**Toggle: "Employer paid base salary"** — If OFF:
- Base salary gap goes to "salary completion" (השלמת שכר מולן) section, not here

---

## Input Data Requirements

The overtime engine requires:
1. **Work pattern** (דפוס עבודה): defines typical shifts, breaks, work days
2. **Employment periods**: date ranges with potentially different work patterns/wages
3. **Rest day**: which day is the worker's rest day (Saturday / Friday / Sunday / other)
4. **District** (מחוז): for candle lighting time lookup (only relevant if rest day = Saturday)
5. **Hourly wage per period**: from SSOT `period_month_records.salary_hourly` (available only at stage 8, after salary conversion)
6. **Toggles**: which components the employer already paid (from SSOT `right_toggles.overtime`)

---

## Edge Cases to Handle

1. **Shift crossing midnight** → belongs to the day with majority of hours
2. **Shift crossing week boundary (Sat 24:00)** → belongs to week with majority of hours
3. **Shift crossing INTO rest window** → split pricing: hours outside = regular rates, hours inside = rest rates. OT tier stays the same across the entire shift.
4. **Shift crossing OUT OF rest window** → same as above
5. **Worker with zero shifts in a week** → skip week entirely
6. **Very short shift (e.g., 0.5h)** → still counts, still accumulates toward weekly total
7. **Multiple shifts in one calendar day** → each is independent for daily OT, all count toward weekly total
8. **Eve of rest AND night shift** → threshold = 7, no stacking
9. **Week with mixed 5/6 threshold** → NOT POSSIBLE. Week type is determined once per week. All shifts in that week use the same base threshold (though exceptions may override for specific shifts).
10. **Holiday (חג)** → **לא מטופל בשעות נוספות.** חגים מטופלים בזכות נפרדת ("דמי חגים"). אין להם חלון מנוחה ואין להם תעריפי יום מנוחה בחישוב שעות נוספות. רק שבתות.
11. **Partial week (שבוע חלקי)** → Employment starts, ends, or has a gap mid-week. The weekly OT threshold (42) still applies as-is — fewer shifts simply means less chance of reaching it. No special rules. The week must be annotated with partial status for display:

```
WeekRecord {
  ...existing fields...
  is_partial: boolean
  partial_reason: "employment_start" | "employment_end" | "gap_start" | "gap_end" | null
  partial_detail: string    // e.g., "T2 started 2024-02-01 (Thursday)"
}
```

12. **Rest window crossing week boundary (חלון מנוחה חוצה שבוע)** → The 36-hour rest window is anchored to the rest day, not to the week. When the window extends beyond the week boundary (into the next or previous week), shifts from the adjacent week must be considered:

    **For optimization:** When computing optimal window placement for week A, include shifts from:
    - The last day of the previous week (e.g., Friday shifts from week A-1 if rest=Saturday)
    - The first day of the next week (e.g., Sunday shifts from week A+1 if rest=Saturday)

    **For classification:** After all windows are placed, classify ALL shifts against the rest window of their adjacent week if the window extends across the boundary:
    - A Sunday shift in week B may fall partially in the rest window of week A
    - A Friday shift in week A may fall partially in the rest window of week A-1
    - A shift can be affected by at most ONE rest window (its own week's or the adjacent week's)
    - If a shift is already classified with rest hours by its own week's window, do not overwrite

    **Implementation in `place_rest_windows`:**
    1. First pass: compute all windows (optimization) considering adjacent shifts
    2. Second pass: classify shifts — for each shift, check both its own week's window AND the adjacent week's window

    **Example:** rest_day=Saturday, Havdalah 17:32 → window ends Sunday ~04:30. A Sunday shift starting 02:00 has ~2.5h inside the previous week's rest window. Without cross-week handling, these hours are priced at regular rates instead of rest rates (150%+).

---

## Testing Strategy

### Unit Tests per Stage
Each pipeline stage must be independently testable with known inputs → expected outputs.

### Integration Test Cases

**Case 1: Simple week, no OT**
- 5 shifts × 8h, week type 5 (threshold 8.4)
- Expected: 40h regular, 0h OT, 0h weekly OT

**Case 2: Daily OT only**
- 5 shifts × 10h, week type 5 (threshold 8.4)
- Expected per shift: 8.4h regular, 1.6h tier1, 0h tier2
- Weekly regular: 42h → 0h weekly OT

**Case 3: Weekly OT only**
- 6 shifts × 8h, week type 6 (threshold 8.0)
- Expected: 0h daily OT per shift, 48h - 42h = 6h weekly OT
- Attribution: distributed across last shift(s)

**Case 4: Mixed daily + weekly OT**
- 6 shifts × 10h, week type 6 (threshold 8.0)
- Daily OT per shift: 2h tier1, 0h tier2
- Regular hours per shift: 8h → weekly total regular = 48h → 6h weekly OT
- Total OT: 12h daily + 6h weekly = 18h

**Case 5: Night shift threshold**
- Shift 20:00–05:00 (9h, 4h in 22:00–06:00 band ≥ 2h → night shift)
- Threshold = 7.0 → 7h regular, 2h tier1

**Case 6: Eve-of-rest threshold**
- Friday shift when Shabbat candle lighting is 16:30
- Eve of rest starts 24h before = Thursday 16:30
- Friday shift starts 07:00 → inside eve-of-rest window → threshold 7.0

**Case 7: Rest window cross-boundary**
- Shift 14:00–22:00, rest window starts at 16:30
- 2.5h regular-day rates, 5.5h rest-day rates
- OT tier determined by total shift hours vs threshold

**Case 8: Weekly OT across multiple shifts**
- Week: 5 shifts of 9h + 1 shift of 4h
- Daily OT: first 5 shifts have 1h tier1 each (threshold 8 in week 6)
- Regular: 5×8 + 4 = 44h → 2h weekly OT in last shift
- Last shift (4h): 2h regular (reaching 42 total) + 2h weekly OT tier1

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** calculate overtime as `total_weekly_hours - 42`. This ignores the per-shift structure entirely.
2. **DO NOT** hardcode candle lighting times. They change every week and vary by district. Use the static data files (see 7.3).
3. **DO NOT** treat daily and weekly OT as interchangeable. They are detected separately, attributed separately.
4. **DO NOT** assume shifts are always within one calendar day.
5. **DO NOT** round hours at any intermediate step.
6. **DO NOT** collapse the pipeline stages — each must be a separate, testable function.
7. **DO NOT** optimize for common cases at the expense of edge cases. A shift of 0.3 hours at 23:50 on Saturday night crossing into Sunday is a valid input.
8. **DO NOT** use "golden test" driven development where the algorithm is reverse-engineered from expected outputs. Build the algorithm from RULES, then verify with tests.

---

## Reference: Rate Calculation Formulas

```
hourly_wage = SSOT.period_month_records[shift.effective_period_id, shift.month].salary_hourly
employer_paid_rest_premium = SSOT.right_toggles["overtime"]["employer_paid_rest"]

For each hour in a shift:
  tier = 0 | 1 | 2  (from stages 5-6)
  in_rest = true | false  (from stage 7)
  
  if not in_rest:
    rate_multiplier = {0: 1.00, 1: 1.25, 2: 1.50}[tier]
  else:
    rate_multiplier = {0: 1.50, 1: 1.75, 2: 2.00}[tier]
  
  # What goes in the overtime CLAIM section:
  if employer_paid_rest_premium:
    claim_multiplier = {0: 0.00, 1: 0.25, 2: 0.50}[tier]  # same for rest and regular
  else:
    if not in_rest:
      claim_multiplier = {0: 0.00, 1: 0.25, 2: 0.50}[tier]
    else:
      claim_multiplier = {0: 0.50, 1: 0.75, 2: 1.00}[tier]
  
  claim_amount = hourly_wage × claim_multiplier × hours_at_this_rate
```
