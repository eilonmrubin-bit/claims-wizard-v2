---
name: limitation
description: |
  Israeli labor law limitation (התיישנות) engine for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on limitation (התיישנות) calculation,
  freeze periods (הקפאות התיישנות), vacation special limitation (התיישנות חופשה 3+שוטף),
  or filtering claim results by limitation windows.
  ALWAYS read this skill before touching any limitation-related code.
---

# התיישנות — Israeli Labor Law

## CRITICAL WARNINGS

1. **Calculate everything, filter at the end.** Rights are computed over the FULL employment period. The limitation engine is a POST-PROCESSING filter — it determines which results to INCLUDE in the final claim, not which periods to calculate.
2. **Freeze periods affect ALL limitation types.** Both the general 7-year limitation and the special vacation limitation (3+שוטף) are extended by freeze periods.
3. **NO HARDCODED FREEZE PERIODS.** The war freeze (7.10.2023–6.4.2024) is a default, but freeze periods must be configurable. The user can add/remove freeze periods from the UI.
4. **NO HARDCODED LIMITATION TYPES.** The system ships with two limitation types (general 7-year, vacation 3+שוטף). The architecture must support adding new limitation types in the future without code changes.
5. **The limitation window is per-RIGHT, not global.** Each right references a limitation type. Different rights may use different limitation windows.

---

## Conceptual Model

The limitation engine is NOT part of the calculation pipeline — it sits AFTER it.

```
┌──────────────────────────────────┐
│  Rights Calculation Pipeline     │
│  (overtime, vacation, severance, │
│   pension, recreation, etc.)     │
│                                  │
│  Computes over FULL employment   │
│  period, ignoring limitations    │
└──────────────┬───────────────────┘
               │ List<RightResult> (each with date/period attribution)
               ▼
┌──────────────────────────────────┐
│  Limitation Engine               │
│                                  │
│  1. Resolve limitation window    │
│     per limitation type          │
│  2. Filter/trim results          │
│     to limitation window         │
└──────────────┬───────────────────┘
               │ List<RightResult> (filtered)
               ▼
         Final Claim Output
```

---

## Configuration

```
LimitationConfig {
  filing_date: date                    // מועד הגשת התביעה — required input

  limitation_types: List<LimitationType> {
    id: string                         // e.g., "general", "vacation"
    name: string                       // e.g., "התיישנות כללית", "התיישנות חופשה"
    window_calc: WindowCalcMethod      // how to compute the base window
  }

  freeze_periods: List<FreezePeriod> {
    id: string                         // unique identifier
    name: string                       // e.g., "הקפאת מלחמת התקומה"
    start_date: date                   // inclusive
    end_date: date                     // inclusive
    days: integer                      // redundant but explicit (end - start + 1)
  }
}
```

### Limitation Types — Configurable Registry

The system maintains a **registry** of limitation types. Each type defines how to compute its base window from the filing date. New types can be added by the user without code changes.

**Adding a new limitation type requires:**
1. An ID and display name
2. A window calculation rule (how far back from filing date)
3. Assignment to one or more rights (each right references a limitation type by ID)

When a right is calculated, it looks up its limitation type from the registry. If the type doesn't exist, the system falls back to `general`.

#### Built-in Type: General (התיישנות כללית)
- **ID:** `general`
- **Rule:** 7 years back from `filing_date`
- **Base window start:** `filing_date - 7 years`
- **Used by:** All rights unless explicitly overridden

#### Built-in Type: Vacation (התיישנות חופשה)
- **ID:** `vacation`
- **Rule:** 3 + שוטף (3 שנים קלנדריות + השנה השוטפת בה הוגשה התביעה)
- **Base window start:** January 1st of (`filing_year - 3`)
- **Examples:**
  - Filing date: January 15, 2025 → window starts January 1, 2022 (3 שנים + ~15 ימים שוטפים)
  - Filing date: June 10, 2025 → window starts January 1, 2022 (3 שנים + ~161 ימים שוטפים)
  - Filing date: December 20, 2025 → window starts January 1, 2022 (3 שנים + ~355 ימים שוטפים)
- **Used by:** חופשה

#### Right-to-Limitation Mapping

| Right | Limitation Type |
|-------|----------------|
| חופשה (vacation) | vacation |
| כל שאר הזכויות | general |

This mapping is configurable. When a new limitation type is added, the user can assign it to any existing right from the UI.

### Freeze Periods — Configurable List

The system maintains an **editable list** of freeze periods. The user can:
- **Add** new freeze periods (name, start date, end date)
- **Remove** existing freeze periods (including the default war freeze)
- **Edit** existing freeze periods

All freeze periods apply to ALL limitation types equally.

#### Built-in Default:

**הקפאת מלחמת התקומה**
- **Start:** October 7, 2023
- **End:** April 6, 2024
- **Days:** 183

---

## Algorithm: Computing the Effective Limitation Window

### Core Concept

A freeze period **pauses** the limitation clock. The limitation period is defined in "active days" — days that are NOT frozen. To find the effective window start, we walk backwards from `filing_date`, counting only active (non-frozen) days, until we've accumulated enough active days to match the base limitation period.

### Optimized Algorithm (Single Pass)

```
function computeEffectiveWindow(filing_date, base_window_start, freeze_periods):
  merged = mergeAndSort(freeze_periods)  // merge overlapping, sort by start ascending

  active_needed = daysBetween(base_window_start, filing_date)

  // Walk backward from filing_date in chunks (between freeze periods)
  cursor = filing_date
  active_accumulated = 0

  // Process freeze periods from latest to earliest
  for freeze in reversed(merged):
    if freeze.end >= cursor:
      if freeze.start < cursor:
        // cursor is INSIDE this freeze — jump past it
        cursor = freeze.start - 1 day
      continue  // freeze is entirely after cursor, or we already jumped past it

    // Active gap: from (freeze.end + 1) to cursor
    gap_start = freeze.end + 1 day
    if gap_start > cursor:
      gap_days = 0
    else:
      gap_days = daysBetween(gap_start, cursor)

    if active_accumulated + gap_days >= active_needed:
      // Answer is within this gap
      remaining = active_needed - active_accumulated
      return cursor - remaining + 1 day

    active_accumulated += gap_days
    cursor = freeze.start - 1 day  // jump over the freeze

  // Final gap: from beginning of time to cursor
  remaining = active_needed - active_accumulated
  return cursor - remaining + 1 day
```

**Complexity:** O(F log F) where F = number of freeze periods (for merge+sort). The walk itself is O(F).

### Why This Works

Instead of day-by-day iteration, we process the timeline in chunks between freeze periods. Each chunk is a continuous block of "active" days. We accumulate active days going backward until we reach the required total. Freeze periods are simply skipped — the cursor jumps over them.

---

## Filtering Results

Once the effective limitation window is computed, results are filtered:

Each result item has an associated period (typically a month or a year).

**Rule:** Include a result if its period **overlaps** with the limitation window.

For a result attributed to period P:
- Include if `period_end >= effective_window_start AND period_start <= filing_date`

**Partial periods at the boundary:** If a period straddles the `effective_window_start`, the claimable amount is calculated as a **decimal fraction** of the full period amount. For example, if 18 days out of a 30-day month fall within the window, the claimable amount = full month amount × (18/30). The same applies to annual calculations — if a year is split by the limitation boundary, the claimable amount is the annual amount × the decimal fraction of the year within the window.

---

## Data Flow Integration

### Each Right Declares Its Limitation Type

```
RightDefinition {
  id: string              // e.g., "overtime", "vacation", "pension"
  name: string
  limitation_type: string // references LimitationConfig.limitation_types[].id
  // ... calculation logic
}
```

### Pipeline Integration Point

```
function applyLimitation(results: List<RightResult>, config: LimitationConfig): List<RightResult> {
  // Pre-compute effective windows for each limitation type
  windows = {}
  for type in config.limitation_types:
    base_start = type.window_calc(config.filing_date)
    windows[type.id] = computeEffectiveWindow(config.filing_date, base_start, config.freeze_periods)

  // Filter each result, tracking excluded amounts
  included = []
  excluded = []
  for r in results:
    window = windows[r.right.limitation_type]
    if r.period_end >= window.effective_start AND r.period_start <= config.filing_date:
      included.append(r)
    else:
      excluded.append(r)

  return { included, excluded }
}
```

---

## Results Display — Timeline Visualization

The limitation results must be displayed as an interactive **timeline** (ציר זמן) in the system UI (not in exports).

### Timeline Layout — Dual Bar Design

The display consists of **two parallel horizontal bars** (פסים צמודים):

**Bar 1 — Limitation (התיישנות):**
Shows the limitation window with its cutoff point and freeze periods.

**Bar 2 — Actual Employment (עבודה בפועל):**
Shows the periods where the worker actually worked. The worker may not have worked during the entire non-expired window (e.g., employment started after the effective window start, or there were gaps in employment).

```
RTL: ימין = ישן, שמאל = חדש

         הגשת תביעה          הקפאה            effective    base     תחילת עבודה
              │            ┌────────┐          window_start window     │
              ▼            │        │             │         │          ▼
Bar 1:   ├────────────────▓▓▓▓▓▓▓▓▓▓────────────┼─ ─ ─ ─ ─┼─────────┤
  התיישנות│    לא התיישן   ▓ הקפאה  ▓ לא התיישן  │ התיישן   │ התיישן  │
         │  (highlighted) ▓(marked)▓(highlighted)│(grayed)  │(grayed) │

Bar 2:   ├──────────────────────────────────────────────┼─────────────┤
  עבודה   │               עבודה בפועל                    │  לא עבד    │
         │              (highlighted)                   │ (grayed)   │
```

**Key observations:**
- The freeze period sits **inside** the non-expired zone (chronologically between filing date and effective window start). It does NOT separate expired from non-expired.
- The freeze **causes** the effective_window_start to be earlier than base_window_start. The gap between them shows the freeze's effect.
- The base_window_start marker (dashed line or subtle marker) shows where limitation would have fallen WITHOUT freezes.
- Bar 2 shows actual employment independently — the worker's employment period may be shorter than the limitation window.

### Required Elements

1. **Full span:** Both bars run from `filing_date` (left, most recent) to the earlier of `employment_start_date` or `effective_window_start` (right, earliest). RTL layout.

2. **Bar 1 — Limitation bar:**
   - **Claimable zone** (לא התיישן): from `filing_date` to `effective_window_start` — highlighted (colored, full opacity). This zone MAY contain freeze periods within it.
   - **Excluded zone** (התיישן): from `effective_window_start` to `employment_start` — grayed out, reduced opacity.
   - **Freeze periods:** Marked as distinct overlay blocks (hatched pattern / different color) at their **chronological position** on the timeline. They appear WITHIN the claimable zone. Tooltip shows freeze name and dates.
   - **Base vs. effective markers:** Two vertical lines — `base_window_start` (dashed, subtle) and `effective_window_start` (solid, prominent). The distance between them visually represents the total freeze extension.

3. **Bar 2 — Employment bar:**
   - **Worked periods:** Highlighted where worker actually worked.
   - **Non-work periods:** Grayed out (before employment start, gaps, after employment end).

4. **Per-limitation-type view:** If multiple limitation types are active (general + vacation), show a pair of bars per type so the user can see each cutoff independently.

### Display Data Structure

```
TimelineData {
  employment_start: date
  employment_end: date
  filing_date: date

  limitation_windows: List<{
    type_id: string               // "general", "vacation"
    type_name: string             // "התיישנות כללית", "התיישנות חופשה"
    base_window_start: date       // without freezes
    effective_window_start: date  // with freezes
  }>

  freeze_periods: List<{
    name: string
    start_date: date
    end_date: date
  }>

  work_periods: List<{            // actual employment periods
    start_date: date
    end_date: date
  }>

  summary: {
    total_employment_days: integer
    claimable_days_general: integer
    excluded_days_general: integer
    claimable_days_vacation: integer
    excluded_days_vacation: integer
    total_freeze_days: integer
  }
}
```

### Interaction

- Hovering over the excluded zone shows: "תקופה זו התיישנה — X חודשים, ₪Y הוחרגו מהתביעה"
- Hovering over a freeze period shows: "הקפאת [name] — [start] עד [end] ([days] ימים)"
- Hovering over the claimable zone shows: "תקופה תבעית — X חודשים"
- Hovering over the gap between base and effective markers shows: "הארכה בשל הקפאות — [days] ימים"

---

## Edge Cases

1. **Freeze period entirely BEFORE the base window** — no effect on limitation. The freeze only matters if it overlaps with (or is reached by extension of) the limitation window.

2. **Freeze period entirely AFTER filing_date** — irrelevant. Limitation is always backwards from filing date.

3. **Multiple overlapping freeze periods** — merge before computing. If freeze A is Jan 1–Jun 30 and freeze B is Mar 1–Sep 30, merged = Jan 1–Sep 30 (273 days, not 362).

4. **Freeze period spans the entire base window** — the window extends backwards by the full freeze duration.

5. **Employment started AFTER effective_window_start** — the window doesn't extend the claimable period beyond employment. The limitation window defines the MAXIMUM claimable range; employment dates define the ACTUAL range. The intersection is what counts.

6. **Filing date is within a freeze period** — the freeze period still counts. Days from freeze start to filing date are frozen; the limitation window extends accordingly.

7. **Vacation limitation edge — December 31 filing** — Filing on Dec 31, 2025: current year = 2025, window starts Jan 1, 2022. Filing on Jan 1, 2026: current year = 2026, window starts Jan 1, 2023. One day difference → one full year difference in coverage. This is correct per the "3 + שוטף" rule.

8. **No freeze periods configured** — effective window = base window. The algorithm handles this naturally (zero freeze gaps to skip).

9. **No limitation types configured** — should not happen (general is always present). If it does, treat all rights as using general.

10. **Election day (יום בחירה) in a year split by limitation** — The holidays module computes `election_day_value` as `max(salary_daily)` across ALL period_month_records in a year. When limitation splits a year, the post-processing filter in pipeline.py must recalculate election_day_value using only the salary_daily values from months that fall WITHIN the claimable window. This ensures the worker doesn't receive a day value based on a salary from the expired portion of the year. Note: years where the worker didn't work some months are already handled — period_month_records exist only for months with actual shifts.

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** cut input periods before calculation. Calculate all rights over the full employment period, then filter.
2. **DO NOT** hardcode the war freeze. It must be a configurable entry in the freeze periods list.
3. **DO NOT** hardcode limitation durations or types. Use the configurable limitation type registry.
4. **DO NOT** assume monthly granularity. Some rights may have daily granularity. The filter must handle both.
5. **DO NOT** silently discard limited-out amounts. Track them separately for transparency.
6. **DO NOT** apply limitation during calculation. Limitation is a POST-PROCESSING step.
7. **DO NOT** forget to merge overlapping freeze periods before computing. Two overlapping freezes should not double-count days.
8. **DO NOT** confuse calendar years with anniversary years for vacation limitation. "3 + שוטף" means calendar years (Jan 1 to Dec 31), not years from employment start.
9. **DO NOT** hardcode the right-to-limitation mapping. It must be configurable so new limitation types can be assigned to rights from the UI.
