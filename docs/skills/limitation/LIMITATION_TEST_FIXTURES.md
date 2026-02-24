# התיישנות — Test Fixtures

## Test 1: Basic General Limitation, No Freezes

**Input:**
- Filing date: 2025-06-01
- Limitation type: general (7 years)
- Freeze periods: none

**Expected:**
- Base window start: 2018-06-01
- Effective window start: 2018-06-01 (no freezes → effective = base)

---

## Test 2: General Limitation with One Fully-Contained Freeze

**Input:**
- Filing date: 2025-06-01
- Limitation type: general (7 years)
- Freeze: הקפאת מלחמת התקומה, 2023-10-07 to 2024-04-06 (183 days)

**Expected:**
- Base window start: 2018-06-01
- Freeze is fully inside [2018-06-01, 2025-06-01] → 183 freeze days
- Effective window start: 2017-11-30 (2018-06-01 minus 183 days)

**Algorithm trace (single-pass):**
- active_needed = daysBetween(2018-06-01, 2025-06-01) = 2557
- Process freeze (2023-10-07 to 2024-04-06) going backward from 2025-06-01:
  - Gap: 2024-04-07 to 2025-06-01 = 421 active days. 421 < 2557.
  - accumulated = 421, cursor jumps to 2023-10-06
- No more freezes. Final gap from cursor backward:
  - remaining = 2557 - 421 = 2136
  - effective_start = 2023-10-06 - 2136 + 1 = 2017-11-30

---

## Test 3: Two Freezes, One Partially Outside Base Window

**Input:**
- Filing date: 2025-06-01
- Limitation type: general (7 years)
- Freeze A: 2023-10-07 to 2024-04-06 (183 days)
- Freeze B: 2017-06-01 to 2018-01-31 (245 days)

**Expected:**
- Base window start: 2018-06-01
- active_needed = 2557

**Algorithm trace (single-pass):**
- Process Freeze A (latest first): gap 2024-04-07 to 2025-06-01 = 421 days. accumulated = 421. cursor = 2023-10-06.
- Process Freeze B (2017-06-01 to 2018-01-31): gap 2018-02-01 to 2023-10-06 = 2073 days. accumulated = 421 + 2073 = 2494. Still < 2557. cursor = 2017-05-31.
- No more freezes. remaining = 2557 - 2494 = 63. effective_start = 2017-05-31 - 63 + 1 = 2017-03-30.

**Note:** Freeze B extends beyond the base window (starts 2017-06-01, base starts 2018-06-01). The single-pass algorithm handles this naturally — it just skips the freeze and counts active days around it.

---

## Test 4: Vacation Limitation (3+שוטף), No Freezes

**Input:**
- Filing date: 2025-03-15
- Limitation type: vacation (3+שוטף)
- Freeze periods: none

**Expected:**
- Filing year: 2025
- Base window start: January 1, 2022 (2025 - 3)
- Effective window start: 2022-01-01

---

## Test 5: Vacation Limitation with Freeze

**Input:**
- Filing date: 2025-03-15
- Limitation type: vacation (3+שוטף)
- Freeze: 2023-10-07 to 2024-04-06 (183 days)

**Expected:**
- Base window start: 2022-01-01
- active_needed = daysBetween(2022-01-01, 2025-03-15) = 1170

**Algorithm trace:**
- Gap: 2024-04-07 to 2025-03-15 = 343 days. accumulated = 343. cursor = 2023-10-06.
- No more freezes. remaining = 1170 - 343 = 827. effective_start = 2023-10-06 - 827 + 1 = 2021-07-02.

**Effective window start: 2021-07-02**

---

## Test 6: Vacation Edge — December 31 vs January 1

**Input A:**
- Filing date: 2025-12-31
- Limitation type: vacation (3+שוטף)
- Freeze: none

**Expected A:**
- Filing year: 2025
- Base window start: January 1, 2022

**Input B:**
- Filing date: 2026-01-01
- Limitation type: vacation (3+שוטף)
- Freeze: none

**Expected B:**
- Filing year: 2026
- Base window start: January 1, 2023

**Key point:** One day difference in filing → one full year difference in vacation limitation window.

---

## Test 7: Overlapping Freeze Periods (Must Merge)

**Input:**
- Filing date: 2025-06-01
- Limitation type: general (7 years)
- Freeze A: 2023-08-01 to 2024-01-31 (184 days)
- Freeze B: 2023-10-07 to 2024-04-06 (183 days)

**Expected:**
- Merged freeze: 2023-08-01 to 2024-04-06 (250 days)
- Base window start: 2018-06-01
- active_needed = 2557

**Algorithm trace:**
- Gap: 2024-04-07 to 2025-06-01 = 421 days. accumulated = 421. cursor = 2023-07-31.
- No more freezes. remaining = 2557 - 421 = 2136. effective_start = 2023-07-31 - 2136 + 1 = 2017-10-08.

**Without merging (WRONG):** Would count 184 + 183 = 367 days instead of 250. This is why merging is mandatory.

---

## Test 8: Freeze Entirely After Filing Date (Irrelevant)

**Input:**
- Filing date: 2023-06-01
- Limitation type: general (7 years)
- Freeze: 2023-10-07 to 2024-04-06

**Expected:**
- Freeze is entirely after filing date → ignored
- Effective window start = base window start = 2016-06-01

---

## Test 9: No Freeze Periods

**Input:**
- Filing date: 2025-01-15
- Limitation type: general (7 years)
- Freeze periods: empty list

**Expected:**
- Effective window start = base window start = 2018-01-15

---

## Test 10: Employment Started After Effective Window Start

**Input:**
- Filing date: 2025-06-01
- Limitation type: general (7 years)
- Employment start: 2020-03-01
- Freeze: 2023-10-07 to 2024-04-06 (183 days)

**Expected:**
- Effective window start: 2017-11-30 (same as Test 2)
- But employment started 2020-03-01 → claimable range is 2020-03-01 to 2025-06-01
- The effective window is earlier than employment start → limitation does NOT cut anything for this worker

---

## Test 11: Multiple Limitation Types in Same Claim

**Input:**
- Filing date: 2025-06-01
- Employment: 2015-01-01 to 2025-05-15
- Freeze: 2023-10-07 to 2024-04-06 (183 days)
- Rights: overtime (general), vacation (vacation)

**Expected:**
- General effective start: 2017-11-30 (per Test 2)
- Vacation: base start 2022-01-01, active_needed = daysBetween(2022-01-01, 2025-06-01) = 1248. Same freeze → gap 421, remaining 827, effective start: 2021-07-02
- Overtime results from 2017-11-30 onward are included
- Vacation results from 2021-07-02 onward are included
- Overtime results from 2015-01-01 to 2017-11-29 are excluded
- Vacation results from 2015-01-01 to 2021-07-01 are excluded

**Key point:** Same claim, same worker, different cutoff dates per right.

---

## Test 12: Filtering — Partial Month at Boundary

**Input:**
- Effective window start: 2018-06-15
- Monthly result for June 2018 (period: 2018-06-01 to 2018-06-30)
- Full month amount: ₪1,000

**Expected:**
- 16 days out of 30 fall within the window (June 15–30)
- Claimable amount = ₪1,000 × (16/30) = ₪533.33
- Same principle applies to annual calculations: if a year is split, use the decimal fraction of the year within the window

---

## Test 13: Filing Date Within a Freeze Period

**Input:**
- Filing date: 2024-01-15 (inside the war freeze)
- Limitation type: general (7 years)
- Freeze: 2023-10-07 to 2024-04-06 (183 days)

**Expected:**
- Base window start: 2017-01-15
- The freeze overlaps with the window. But filing_date is inside the freeze, so the algorithm cursor starts at 2024-01-15.
- active_needed = daysBetween(2017-01-15, 2024-01-15) = 2556

**Algorithm trace:**
- cursor = 2024-01-15
- Process freeze (2023-10-07 to 2024-04-06): freeze.end (2024-04-06) >= cursor (2024-01-15) → true. But freeze.start (2023-10-07) < cursor → cursor is INSIDE freeze → cursor jumps to 2023-10-06. continue.
- No more freezes. accumulated = 0. remaining = 2556. effective_start = 2023-10-06 - 2556 + 1 = 2016-10-08 (approx — verify with exact day count).

**Key point:** When filing_date is inside a freeze, effectively ALL freeze days from freeze.start to filing_date are "dead time" — the limitation clock wasn't running. The window extends back by that amount.
