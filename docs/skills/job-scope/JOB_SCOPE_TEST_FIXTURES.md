# היקף משרה — Test Fixtures

## Test 1: Full-Time

**Input:** 182 regular hours in month
**Expected:** scope = 182 / 182 = 1.0 (100%)

---

## Test 2: Part-Time

**Input:** 91 regular hours in month
**Expected:** scope = 91 / 182 = 0.5 (50%)

---

## Test 3: Over 182 Hours — Capped

**Input:** 200 regular hours in month
**Expected:** raw = 200 / 182 = 1.099, effective = 1.0 (capped)

---

## Test 4: Zero Hours

**Input:** 0 regular hours in month
**Expected:** scope = 0.0

---

## Test 5: Partial Month (Started Mid-Month)

**Input:** Employment started on the 15th. 80 regular hours in the month.
**Expected:** scope = 80 / 182 = 0.4396...

---

## Test 6: Varying Scope Across Months

**Input:**
- January: 160 regular hours
- February: 182 regular hours
- March: 100 regular hours

**Expected:**
- January: 0.8791...
- February: 1.0
- March: 0.5494...
