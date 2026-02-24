# ניכויי הפרשות מעסיק — Test Fixtures

## Test 1: No Deduction

**Input:**
- Right: pension, calculated amount: ₪30,000
- Employer deduction: 0

**Expected:**
- net_amount: ₪30,000
- show_deduction: false
- Right displayed normally, no deduction row

---

## Test 2: Partial Deduction

**Input:**
- Right: severance, calculated amount: ₪45,000
- Employer deduction: ₪22,000

**Expected:**
- net_amount: ₪23,000
- show_deduction: true
- Display: calculated ₪45,000, deduction -₪22,000, net ₪23,000

---

## Test 3: Deduction Equals Calculated Amount

**Input:**
- Right: pension, calculated amount: ₪15,000
- Employer deduction: ₪15,000

**Expected:**
- net_amount: 0
- show_right: false
- warning: true (console)
- Right not displayed in claim

---

## Test 4: Deduction Exceeds Calculated Amount

**Input:**
- Right: severance, calculated amount: ₪20,000
- Employer deduction: ₪25,000

**Expected:**
- net_amount: 0
- show_right: false
- warning: true (console: "Deduction ₪25,000 exceeds calculated ₪20,000")
- Right not displayed in claim

---

## Test 5: Multiple Rights, Mixed Deductions

**Input:**
- Pension: calculated ₪30,000, deduction ₪10,000
- Severance: calculated ₪45,000, deduction ₪0
- Recreation: calculated ₪5,000, deduction ₪5,000

**Expected:**
- Pension: net ₪20,000, deduction row shown
- Severance: net ₪45,000, no deduction row
- Recreation: suppressed (deduction = amount), warning in console
