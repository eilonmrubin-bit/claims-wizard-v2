---
name: employer-deductions
description: |
  Employer contribution deductions (ניכויי הפרשות מעסיק) module for the Claims Wizard (אשף התביעות).
  Use this skill whenever working on deducting employer-paid amounts from calculated rights,
  pension/severance employer contributions, or the deduction display logic.
  ALWAYS read this skill before touching any deduction-related code.
---

# ניכויי הפרשות מעסיק — Israeli Labor Law

## CRITICAL WARNINGS

1. **Deductions are POST-CALCULATION.** First compute the full right amount, then deduct. Never reduce inputs before calculation.
2. **Never invent which rights have deductions.** The user defines deduction amounts per right. This module only stores and applies them.
3. **If deduction > calculated amount → do not display the right. Show a warning in the developer console.**
4. **If deduction = 0 → do not display the deduction row at all.** The right appears as if no deduction exists.

---

## Conceptual Model

```
┌─────────────────────────────────┐
│  User Input                     │
│  Per right: employer-paid       │
│  amount (flat ₪ number)         │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  SSOT Storage                   │
│  employer_deductions: {         │
│    right_id: decimal (₪)        │
│  }                              │
└──────────────┬──────────────────┘
               │ queried per right
               ▼
┌─────────────────────────────────┐
│  Right Calculation              │
│  1. Compute full amount         │
│  2. Check SSOT for deduction    │
│  3. If deduction > 0:           │
│     net = amount - deduction    │
│  4. If net <= 0: suppress right │
└─────────────────────────────────┘
```

---

## Input

The user enters employer-paid amounts in the input stage. Three levels:

1. **פנסיה (pension):** הפרשות מעביד לפנסיה — flat ₪ amount
2. **פיצויי פיטורין (severance):** הפרשות מעביד לפיצויים — flat ₪ amount
3. **אחר (other rights):** expandable section where the user can enter a deduction amount for any other right — each as a flat ₪ amount with a right selector

All values are flat numbers (₪), not percentages, not formulas.

---

## SSOT Data Structure

```
EmployerDeductions {
  deductions: Map<right_id, decimal>
  // e.g., { "pension": 15000, "severance": 22000, "recreation": 0 }
}
```

Default: all values are 0 (no deductions).

---

## Application Logic

Each right, after computing its full claim amount, calls:

```
function applyDeduction(right_id, calculated_amount):
  deduction = SSOT.employer_deductions[right_id] ?? 0
  
  if deduction == 0:
    return { net_amount: calculated_amount, deduction: 0, show_deduction: false }
  
  net = calculated_amount - deduction
  
  if net <= 0:
    console.warn("Deduction for {right_id} (₪{deduction}) exceeds calculated amount (₪{calculated_amount})")
    return { net_amount: 0, deduction: deduction, show_right: false, warning: true }
  
  return { net_amount: net, deduction: deduction, show_deduction: true }
```

---

## Display Rules

### When deduction = 0:
- Show the right normally
- No deduction row, no mention of deductions

### When 0 < deduction < calculated amount:
- Show the full calculated amount
- Show a deduction row: "ניכוי הפרשות מעסיק: -₪X"
- Show the net amount as the final claim for this right

Example:
```
פיצויי פיטורין
  סכום מחושב:          ₪45,000
  ניכוי הפרשות מעסיק:  -₪22,000
  סה"כ לתביעה:         ₪23,000
```

### When deduction ≥ calculated amount:
- Do NOT display the right in the claim
- Show a warning in developer/admin console (not to the end user in the claim output)

---

## Anti-Patterns (DO NOT DO)

1. **DO NOT** apply deductions before or during calculation. Compute the full amount first.
2. **DO NOT** show a deduction row when the deduction is 0.
3. **DO NOT** show negative claim amounts. If deduction exceeds the right, suppress the right entirely.
4. **DO NOT** hardcode which rights can have deductions. Any right can potentially have one.
5. **DO NOT** treat deductions as percentages or formulas. They are always flat ₪ amounts.
