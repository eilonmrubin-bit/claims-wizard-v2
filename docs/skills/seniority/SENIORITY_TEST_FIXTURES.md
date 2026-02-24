# ותק ענפי — Test Fixtures

## Test 1: Method א — Simple, No Gaps

**Input:**
- Prior industry seniority: 24 months
- Employment at defendant: 2020-01-01 to 2022-12-31
- Work pattern: worked every weekday (no gaps)

**Expected:**
- at_defendant_months: 36 (Jan 2020 through Dec 2022)
- total_industry_months: 60 (24 + 36)
- total_industry_years: 5.0
- at_defendant_years: 3.0

---

## Test 2: Method א — With Employment Gaps

**Input:**
- Prior industry seniority: 0
- Employment at defendant: 2020-01-15 to 2022-06-20
- Work pattern: worked every weekday EXCEPT July 2021 and August 2021 (worker absent, no work days)

**Expected:**
- Months with work: Jan 2020 through Jun 2021 (18), Sep 2021 through Jun 2022 (10) = 28
- at_defendant_months: 28
- total_industry_months: 28
- total_industry_years: 2.333...

---

## Test 3: Method א — Started and Ended Mid-Month

**Input:**
- Prior industry seniority: 12
- Employment at defendant: 2023-03-20 to 2023-09-05
- Work pattern: worked every weekday

**Expected:**
- March 2023: worked (partial) → 1
- April–August 2023: worked → 5
- September 2023: worked (partial) → 1
- at_defendant_months: 7
- total_industry_months: 19 (12 + 7)
- total_industry_years: 1.583...

---

## Test 4: Method ב — Manual Entry

**Input:**
- Total industry seniority: 8 years and 3 months (99 months)
- Seniority at defendant: 4 years and 6 months (54 months)

**Expected:**
- total_industry_months: 99
- total_industry_years: 8.25
- at_defendant_months: 54
- at_defendant_years: 4.5

---

## Test 5: Method ג — מת"ש with Multiple Employers, Same Industry

**Input:**
- User-specified industry: בנייה (construction)
- מת"ש records:
  - Employer A (construction): 2015-03-01 to 2017-08-31
  - Employer B (food service): 2017-09-01 to 2018-06-30
  - Employer C (construction, defendant): 2018-07-01 to 2023-05-15
  - Employer D (construction): 2019-01-01 to 2019-06-30 (overlaps with C)

**Expected:**
- Filter: keep A, C, D (construction). Discard B (food service).
- Month sets:
  - A: Mar 2015 to Aug 2017 = 30 months
  - C: Jul 2018 to May 2023 = 59 months
  - D: Jan 2019 to Jun 2019 = 6 months (but all overlap with C)
- Union: 30 + 59 + 0 new from D = 89 months
- at_defendant_months: 59 (C only)
- total_industry_months: 89
- total_industry_years: 7.416...
- at_defendant_years: 4.916...

---

## Test 6: Method ג — Overlapping Employers, Deduplication

**Input:**
- Industry: construction
- Records (all construction):
  - Employer A: 2020-01-01 to 2020-12-31 (12 months)
  - Employer B: 2020-06-01 to 2021-06-30 (13 months)

**Expected:**
- A covers: Jan–Dec 2020
- B covers: Jun 2020–Jun 2021
- Union: Jan 2020–Jun 2021 = 18 months (not 25)

---

## Test 7: getSeniority with as_of_date

**Input:**
- Method א, prior seniority: 10 months
- Employment at defendant: 2020-01-01 to 2023-12-31
- Work pattern: every weekday
- Query: getSeniority(as_of_date = 2021-06-15)

**Expected:**
- at_defendant_months up to June 2021: 18 (Jan 2020 through Jun 2021)
- total_industry_months: 28 (10 + 18)
- total_industry_years: 2.333...

---

## Test 8: Zero Prior Seniority, Short Employment

**Input:**
- Prior seniority: 0
- Employment: 2023-11-10 to 2023-11-25
- Work pattern: worked every weekday

**Expected:**
- at_defendant_months: 1 (November 2023)
- total_industry_months: 1
- total_industry_years: 0.083...

---

## Test 9: Method ג — No Records for Specified Industry

**Input:**
- Industry: construction
- מת"ש records:
  - Employer A (food service): 2018-01-01 to 2020-12-31

**Expected:**
- Filter: no records match construction
- Warning to user: no industry records found
- total_industry_months: 0 (or suggest manual entry)

---

## Test 10: Method א — Worker Worked Only 1 Day in a Month

**Input:**
- Prior seniority: 0
- Employment: 2023-01-01 to 2023-03-31
- Work pattern: worked only on Jan 15, Feb (not at all), Mar 1

**Expected:**
- January: worked (1 day) → 1
- February: did not work → 0
- March: worked (1 day) → 1
- at_defendant_months: 2
- total_industry_years: 0.166...

---

## Test 11: Cumulative Monthly Series

**Input:**
- Prior seniority: 24 months (method א)
- Employment: 2023-01-01 to 2023-06-30
- Work pattern: worked Jan, Feb, Mar, didn't work Apr, worked May, Jun

**Expected monthly series:**

| Month | Worked | at_defendant_cum | at_defendant_years | total_industry_cum | total_industry_years |
|-------|--------|-----------------|-------------------|-------------------|---------------------|
| 2023-01 | true | 1 | 0.083 | 25 | 2.083 |
| 2023-02 | true | 2 | 0.167 | 26 | 2.167 |
| 2023-03 | true | 3 | 0.250 | 27 | 2.250 |
| 2023-04 | false | 3 | 0.250 | 27 | 2.250 |
| 2023-05 | true | 4 | 0.333 | 28 | 2.333 |
| 2023-06 | true | 5 | 0.417 | 29 | 2.417 |

**Verification:**
- April: didn't work, so cumulative stays flat
- Final totals match last row: at_defendant=5, total_industry=29
- getSeniority(as_of_date=2023-04-15) returns: at_defendant=3, total_industry=27

---

## Test 12: Cumulative Series with Employment Gap

**Input:**
- Prior seniority: 10 months (method א)
- Employment period 1: 2023-01-01 to 2023-03-31
- Employment period 2: 2023-06-01 to 2023-08-31
- Work pattern: worked all months in both periods

**Expected monthly series:**

| Month | Worked | at_defendant_cum | at_defendant_years | total_industry_cum | total_industry_years |
|-------|--------|-----------------|-------------------|-------------------|---------------------|
| 2023-01 | true | 1 | 0.083 | 11 | 0.917 |
| 2023-02 | true | 2 | 0.167 | 12 | 1.000 |
| 2023-03 | true | 3 | 0.250 | 13 | 1.083 |
| 2023-04 | false | 3 | 0.250 | 13 | 1.083 |
| 2023-05 | false | 3 | 0.250 | 13 | 1.083 |
| 2023-06 | true | 4 | 0.333 | 14 | 1.167 |
| 2023-07 | true | 5 | 0.417 | 15 | 1.250 |
| 2023-08 | true | 6 | 0.500 | 16 | 1.333 |

**Verification:**
- Gap months (Apr, May) present with worked=false, cumulative stays flat
- Series covers full range including gap
