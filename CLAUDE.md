# Claims Wizard v2 — הוראות לקלוד קוד

## כללים מוחלטים

1. **קרא את הסקיל לפני כל עבודה על מודול.** הסקילים נמצאים ב-`docs/skills/`. לפני שאתה נוגע במודול — קרא את הסקיל שלו במלואו.
2. **לא להמציא כללים משפטיים.** אם לא כתוב בסקיל — תשאל.
3. **הסקיל הוא מקור האמת.** אם הקוד סותר את הסקיל — הקוד שגוי.
4. **סתירה בין סקילים = עצירה.** לא לבחור צד. לשאול.
5. **קוד באנגלית, UI בעברית, תיעוד בעברית.**
6. **תאריכים פנימיים: `datetime.date`. תצוגה: DD.MM.YYYY. סריאליזציה: ISO 8601.**
7. **מספרים: לא לעגל בשום שלב ביניים.** עיגול לאגורה רק בתצוגה סופית.
8. **כל מודול = פונקציה ראשית אחת.** מקבלת קלט, מחזירה תוצאה. לא ניגשת ל-SSOT ישירות.
9. **רק `pipeline.py` קורא וכותב ל-SSOT.**
10. **אסור להעתיק קוד מ-claims-wizard (v1).** כתיבה מאפס בלבד.

## סקילים זמינים

| מודול | קובץ סקיל |
|---|---|
| SSOT (מבנה נתונים) | `docs/skills/ssot/SKILL.md` |
| מפרט כללי | `docs/skills/claims-wizard-spec/SKILL.md` + `PIPELINE.md` + `ARCHITECTURE.md` |
| מתרגם הדפוסים | `docs/skills/pattern-translator/SKILL.md` |
| מארג | `docs/skills/weaver/SKILL.md` |
| שעות נוספות | `docs/skills/overtime-calculation/SKILL.md` |
| אגרגטור | `docs/skills/aggregator/SKILL.md` |
| המרת שכר | `docs/skills/salary-conversion/SKILL.md` |
| היקף משרה | `docs/skills/job-scope/SKILL.md` |
| ותק ענפי | `docs/skills/seniority/SKILL.md` |
| דמי חגים | `docs/skills/holidays/SKILL.md` |
| התיישנות | `docs/skills/limitation/SKILL.md` |
| ניכויים | `docs/skills/employer-deductions/SKILL.md` |
| נתונים סטטיים | `docs/skills/static-data/SKILL.md` |

## מדיניות בדיקות

- בדיקות מקרי קצה מהסקיל — חובה
- בדיקות אנטי-פטרנים מהסקיל — חובה
- מסלול רגיל אחד — חובה
- אינטגרציה אחת — חובה
- **לא ממציאים מקרי בדיקה.** משתמשים בקבצי TEST_FIXTURES כשקיימים
- לא ממשיכים למודול הבא אם הנוכחי לא עובר

## קבצי TEST_FIXTURES

- `docs/skills/seniority/SENIORITY_TEST_FIXTURES.md`
- `docs/skills/job-scope/JOB_SCOPE_TEST_FIXTURES.md`
- `docs/skills/limitation/LIMITATION_TEST_FIXTURES.md`
- `docs/skills/employer-deductions/EMPLOYER_DEDUCTIONS_TEST_FIXTURES.md`

## גיט

- עבודה על `main` ישירות
- קומיט בעברית: `[מודול] מה נעשה`
- קומיט רק על קוד שעובד
