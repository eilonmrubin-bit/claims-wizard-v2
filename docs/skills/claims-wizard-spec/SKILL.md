---
name: claims-wizard-spec
description: |
  Master specification and development instructions for the Claims Wizard (אשף התביעות).
  READ THIS SKILL FIRST before any work on the project. It defines the tech stack,
  project structure, coding conventions, testing policy, and development workflow.
  This skill does not replace module-specific skills — it complements them.
  ALWAYS read this skill at the start of any development session.
  This skill folder contains 3 documents — read ALL of them:
  1. SKILL.md (this file) — conventions, policies, skill list
  2. PIPELINE.md — full execution order
  3. ARCHITECTURE.md — system architecture description (see also architecture_v10.jsx for interactive diagram)
  For SSOT data structures, see /mnt/skills/user/ssot/SKILL.md
---

# אשף התביעות — מפרט פיתוח

> **חובה:** קרא סקיל זה במלואו לפני כל עבודה על הפרויקט.
> לא לכתוב קוד, לא ליצור קבצים, לא להתחיל משימה — לפני שקראת את הסקיל הרלוונטי.
> המפרט המלא מורכב מ-3 מסמכים — קרא את כולם:
> - `claims-wizard-spec/SKILL.md` ← אתה כאן
> - `claims-wizard-spec/PIPELINE.md` — סדר הרצה
> - `claims-wizard-spec/ARCHITECTURE.md` — ארכיטקטורה
> - מבנה נתונים: `ssot/SKILL.md`

## מטרה

מערכת לחישוב זכויות עובדים לפי דיני עבודה ישראליים. מקבלת פרטי העסקה, מחשבת זכויות (שעות נוספות, חגים, חופשה, פיצויים ועוד), מחילה התיישנות וניכויים, ומציגה סיכום תביעה.

## מסמכי המפרט

```
claims-wizard-spec/
├── SKILL.md          ← אתה כאן. נהלים, מוסכמות, רשימת סקילים
├── PIPELINE.md       ← סדר הרצה מלא — מי קורא למי ובאיזה סדר
└── ARCHITECTURE.md   ← תיאור ארכיטקטורה — 5 פאזות, זרימת נתונים
```

**מבנה נתונים (SSOT):** מתועד בסקיל נפרד — `/mnt/skills/user/ssot/SKILL.md`. זהו מסמך הייחוס המרכזי לכל מבני הנתונים במערכת. **חובה** לקרוא אותו לפני כל עבודה שנוגעת במבנה נתונים.

---

## אזהרות קריטיות — קרא לפני הכל

1. **פרויקט חדש מאפס.** קיים ריפו קודם (claims-wizard). הפרויקט הנוכחי (claims-wizard-v2) הוא כתיבה מאפס. אסור להעתיק קוד מהגרסה הקודמת, אסור להתבסס על מבני נתונים שלה, ואסור להתייחס אליה כמקור. הסקילים הם המקור היחיד.
2. **לא ממציאים כללים משפטיים.** כל כלל, נוסחה, סף, או התנהגות ספציפית לזכות חייבים להיות מתועדים בסקיל. אם לא כתוב — שואלים את המשתמש. לא מנחשים.
3. **הסקיל הוא מקור האמת, לא הקוד ולא הבדיקות.** אם הקוד סותר את הסקיל — הקוד שגוי. אם בדיקה עוברת אבל הלוגיקה סותרת את הסקיל — הבדיקה שגויה.
4. **סתירה בין סקילים = עצירה.** אם שני סקילים אומרים דברים סותרים — לא לבחור צד. עוצרים ושואלים את המשתמש.
5. **לפני כל עבודה על מודול — קוראים את הסקיל שלו.** בלי יוצא מן הכלל.
6. **זכות בלי סקיל = זכות שלא מפתחים.** אם המשתמש מבקש לפתח זכות (חופשה, פיצויים, פנסיה, הבראה, נסיעות, השלמת שכר, או כל זכות אחרת) ואין לה סקיל מוגדר — יש לסרב ולבקש מהמשתמש להכין סקיל קודם. אין להמציא לוגיקה לזכות לא מתועדת בשום מצב.

---

## סטאק טכנולוגי

### בקאנד

```
שפה: Python 3.12+
מסגרת: FastAPI
ניהול תלויות: Poetry
מבנה: מודולרי — מודול אחד לכל סקיל
```

### פרונטאנד

```
שפה: TypeScript
מסגרת: React 18+
בנייה: Vite
רכיבי UI: Ant Design 5 (תמיכת RTL מובנית מלאה)
```

### תמיכת RTL ועברית

הממשק כולו בעברית. Ant Design מספקת תמיכת RTL מובנית דרך ConfigProvider:

```tsx
import { ConfigProvider } from 'antd';
import heIL from 'antd/locale/he_IL';

<ConfigProvider direction="rtl" locale={heIL}>
  <App />
</ConfigProvider>
```

כללים נוספים:

- פונטים: שימוש בפונט שתומך עברית היטב (Heebo או Rubik מ-Google Fonts)
- מספרים ותאריכים: תמיד בכיוון LTR בתוך span עם `dir="ltr"` ו-`display: inline-block`
- DatePicker: פורמט DD.MM.YYYY דרך הגדרת format בקומפוננטה
- Table: יישור טקסט לימין, מספרים לשמאל (דרך align בהגדרת עמודה)
- CSS מותאם אישית: מינימלי. להעדיף את רכיבי Ant Design כמו שהם

---

## מבנה הפרויקט

```
claims-wizard/
├── backend/
│   ├── pyproject.toml
│   ├── settings.json                    # הגדרות (OT, התיישנות, היקף משרה)
│   ├── data/                            # נתונים סטטיים
│   │   ├── shabbat_times/               # CSV למחוז (jerusalem.csv, tel_aviv.csv...)
│   │   ├── holiday_dates.csv            # חגים עברי → לועזי
│   │   ├── minimum_wage.csv             # שכר מינימום היסטורי
│   │   ├── recreation_day_value.csv     # ערך יום הבראה
│   │   └── travel_allowance.csv         # דמי נסיעות
│   ├── app/
│   │   ├── main.py                      # FastAPI app + endpoints
│   │   ├── pipeline.py                  # המתזמר — run_full_pipeline
│   │   ├── ssot.py                      # מבנה נתונים SSOT
│   │   ├── errors.py                    # PipelineError, מבנה שגיאות
│   │   ├── modules/
│   │   │   ├── pattern_translator.py    # ⓪ מתרגם הדפוסים
│   │   │   ├── weaver/                  # ① מארג
│   │   │   │   ├── orchestrator.py
│   │   │   │   ├── validator.py
│   │   │   │   ├── sweep.py
│   │   │   │   ├── daily_records.py
│   │   │   │   └── gaps.py
│   │   │   ├── overtime/                # ② OT stages 1–7 + stage 8
│   │   │   │   ├── stage1_assembly.py
│   │   │   │   ├── stage2_assignment.py
│   │   │   │   ├── stage3_week_classification.py
│   │   │   │   ├── stage3_5_day_segments.py
│   │   │   │   ├── stage4_threshold.py
│   │   │   │   ├── stage5_daily_ot.py
│   │   │   │   ├── stage6_weekly_ot.py
│   │   │   │   ├── stage7_rest_window.py
│   │   │   │   └── stage8_pricing.py
│   │   │   ├── aggregator.py            # ③ אגרגציה
│   │   │   ├── salary_conversion.py     # ④ המרת שכר
│   │   │   ├── job_scope.py             # ⑤ב היקף משרה
│   │   │   ├── seniority.py             # ⑤א ותק ענפי
│   │   │   ├── holidays.py              # דמי חגים
│   │   │   ├── limitation.py            # ① התיישנות
│   │   │   ├── deductions.py            # ② ניכויים
│   │   │   └── summary.py              # ③ סיכום תביעה
│   │   └── utils/
│   │       ├── duration.py              # Duration חישוב + פורמטר
│   │       ├── shabbat_times.py         # שירות זמני שבת
│   │       ├── rest_window.py           # שירות חלון מנוחה
│   │       ├── static_data.py           # טעינת CSV סטטיים
│   │       └── dates.py                 # עזרי תאריכים
│   └── tests/
│       ├── test_pattern_translator.py
│       ├── test_weaver/
│       ├── test_overtime/
│       ├── test_aggregator.py
│       ├── test_salary_conversion.py
│       ├── test_job_scope.py
│       ├── test_seniority.py
│       ├── test_holidays.py
│       ├── test_limitation.py
│       ├── test_deductions.py
│       ├── test_summary.py
│       └── test_pipeline.py             # אינטגרציה — קלט → SSOT מלא
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── types/                       # טיפוסים שמתאימים ל-SSOT
│   │   └── utils/
│   └── ...
└── docs/
    └── skills/                          # עותק מקומי של הסקילים לעיון
```

---

## מוסכמות קוד

### שפה

```
קוד (משתנים, פונקציות, מחלקות, הערות): אנגלית בלבד
ממשק משתמש (תוויות, הודעות, טולטיפים): עברית בלבד
מסמכים ותיעוד: עברית
סקילים: עברית + קוד מדומה באנגלית (כמו הסקילים הקיימים)
```

### תאריכים

```
תצוגה למשתמש: DD.MM.YYYY (למשל 23.02.2026)
אחסון פנימי: date object של Python (datetime.date)
סריאליזציה (JSON / קובץ .case): ISO 8601 — YYYY-MM-DD
קלט מהמשתמש: DD.MM.YYYY (הפרונט ממיר)
```

### מספרים

```
שעות: עשרוני, בלי עיגול בשום שלב ביניים
כסף: עשרוני, עיגול לאגורה (2 ספרות) רק בתצוגה סופית
אחוזים: עשרוני (0.85, לא 85%)
```

### פונקציות

```
כל מודול חושף פונקציה ראשית אחת (run, compute, translate...)
הפונקציה מקבלת את כל הקלט כפרמטרים — לא ניגשת ל-SSOT ישירות
הפונקציה מחזירה אובייקט תוצאה — לא כותבת ל-SSOT ישירות
רק המתזמר (pipeline.py) קורא וכותב ל-SSOT
```

### טיפול בשגיאות

```
שגיאת ולידציה (קלט לא תקין): מוחזרת כרשימת שגיאות, לא exception
שגיאה פנימית (באג): exception רגיל של Python
המתזמר עוטף הכל ומחזיר PipelineResult עם success/errors

מבנה שגיאה:
  PipelineError {
    phase: string        // "weaver", "ot_pipeline", "salary_conversion"...
    module: string       // שם הקובץ
    errors: [{
      type: string       // "uncovered_range", "invalid_range"...
      message: string    // הודעה בעברית ל-UI
      details: object    // פרטים טכניים
    }]
  }
```

---

## מדיניות בדיקות

### עקרון: מעט בדיקות ממוקדות, לא הרבה בדיקות גנריות

בדיקות רבות מדי שנכתבות אוטומטית מובילות לאישור לוגיקה שגויה. הגישה:

### מה חובה לכל מודול

1. **בדיקות מקרי קצה מהסקיל.** כל סקיל מפרט מקרי קצה — לכל אחד בדיקה.
2. **בדיקות אנטי-פטרנים.** כל סקיל מפרט "מה לא לעשות" — בדיקה שמוודאת שזה לא קורה.
3. **בדיקת מסלול רגיל אחת.** קלט פשוט ותקין → תוצאה צפויה.
4. **בדיקת אינטגרציה אחת.** קלט שעובר דרך כל הצינור עד הסוף.

### מה אסור

1. **לא ממציאים מקרי בדיקה.** מקרי הבדיקה באים מהסקיל, מקבצי TEST_FIXTURES (אם קיימים), או מהמשתמש. לא מקלוד קוד.
2. **לא כותבים בדיקות שמאשרות ניחוש.** אם לא ברור מה התוצאה הנכונה — שואלים, לא מנחשים ובודקים שהניחוש עובד.
3. **לא כותבים בדיקות כפולות.** שתי בדיקות שבודקות את אותו דבר בשמות שונים = בזבוז.

### קבצי TEST_FIXTURES

הסקילים הבאים כוללים קבצי בדיקה מוכנים:
- overtime-calculation: OVERTIME_TEST_FIXTURES.md
- salary-conversion: SALARY_CONVERSION_TEST_FIXTURES.md
- seniority: SENIORITY_TEST_FIXTURES.md
- job-scope: JOB_SCOPE_TEST_FIXTURES.md
- limitation: LIMITATION_TEST_FIXTURES.md
- employer-deductions: EMPLOYER_DEDUCTIONS_TEST_FIXTURES.md

**חובה** להשתמש בהם. הם כתובים ע"י בעל הדומיין ומשקפים את הדין הנכון.

### סדר: קוד → בדיקות → אור ירוק → מודול הבא

לא ממשיכים למודול הבא אם הנוכחי לא עובר את כל הבדיקות.

---

## גיט

### ריפו

```
https://github.com/eilonmrubin-bit/claims-wizard-v2
```

### עבודה על main

עובדים ישירות על main. בלי ענפים, בלי pull requests. פרויקט עם מפתח אחד — אין צורך בתהליך.

### הודעות קומיט

קצרות וברורות בעברית. פורמט:

```
[מודול] מה נעשה

דוגמאות:
[מארג] ולידציה חוצת צירים
[OT] שלב 6 — OT שבועי
[אגרגטור] קיבוץ תקופה × חודש
[תשתית] מבנה SSOT + טעינת CSV
[בדיקות] מארג — מקרי קצה
[תיקון] המרת שכר — חלוקה באפס בחודש ריק
```

### תדירות קומיטים

קומיט אחרי כל יחידת עבודה שעובדת — מודול שלם, תיקון באג, סט בדיקות. לא קומיט על קוד שבור.

### קובץ .gitignore

```
__pycache__/
*.pyc
.venv/
node_modules/
dist/
.env
*.case
```

---

## גרסאות

### פורמט

```
vX.Y.Z

X = גרסה ראשית — שינוי שובר (מבנה SSOT השתנה, פורמט קובץ case השתנה)
Y = גרסת משנה — זכות חדשה, מודול חדש, פיצ'ר משמעותי
Z = תיקון — באג, שיפור ביצועים, תיקון תצוגה
```

### מתי מעדכנים

```
X עולה כש:
  מבנה SSOT השתנה באופן שלא תואם לאחור
  פורמט קובץ .case השתנה
  (מאפס Y ו-Z)

Y עולה כש:
  זכות חדשה נוספה (למשל חופשה, פיצויים)
  מודול חדש נוסף
  פיצ'ר משמעותי (למשל ייצוא PDF)
  (מאפס Z)

Z עולה כש:
  תיקון באג
  שיפור ביצועים
  שינוי תצוגה
  תיקון בדיקות
```

### איפה מצוין

```
backend/app/__init__.py: __version__ = "0.1.0"
קובץ .case: version field (לבדיקת תאימות בטעינה)
```

### גרסה התחלתית

```
v0.1.0 — תשתית + מארג
v0.2.0 — OT stages 1–7
v0.3.0 — אגרגטור + המרת שכר + היקף משרה + ותק
v0.4.0 — OT stage 8 + חגים (פאזה 2 ראשונית)
v0.5.0 — התיישנות + ניכויים + סיכום (פאזה 3)
v0.6.0 — פרונטאנד
v1.0.0 — גרסה ראשונה שלמה עם כל הזכויות המוגדרות
```

---

## ממשק בקאנד–פרונט

### נקודת קצה ראשית

```
POST /calculate
  גוף הבקשה: SSOT.input (כל הקלט)
  תשובה: SSOT מלא (קלט + תוצאות)
  שגיאה: PipelineError עם רשימת שגיאות בעברית
```

### נקודות קצה עתידיות

```
POST /save     — שמירת קובץ .case
POST /load     — טעינת קובץ .case
GET  /static   — רשימת מאגרי מידע סטטיים (לתצוגה/עדכון)
```

---

## קובץ תיק (.case)

### פורמט

קובץ JSON עם סיומת .case. מכיל שני חלקים:

```json
{
  "version": "0.3.0",
  "last_modified_by": "חנוך",
  "last_modified_at": "2026-02-23T18:30:00",
  "input": { ... },
  "cache": {
    "input_hash": "sha256...",
    "ssot": { ... }
  }
}
```

### לוגיקה

```
שמירה:
  1. מחשב hash של input
  2. שומר input + cache (תוצאות + hash)

טעינה:
  1. קורא את הקובץ
  2. מחשב hash של input
  3. אם תואם ל-cache.input_hash → מציג תוצאות מיד (בלי חישוב)
  4. אם לא תואם → מריץ צינור מחדש

בדיקת גרסה:
  1. בודק version בקובץ מול version של המערכת
  2. אם X שונה → הקובץ לא תואם, מציג אזהרה
  3. אם רק Y/Z שונים → טוען רגיל, מריץ חישוב מחדש
```

### עבודה משותפת ברשת (עתידי)

```
קובץ .case בתיקייה משותפת ברשת מקומית (LAN).
כל משתמש פותח, עורך, שומר. לא במקביל.
שדה last_modified_by מציין מי ערך אחרון.
לא נדרשת מערכת משתמשים/הרשאות בשלב הראשון.
```

---

## סדר פיתוח מומלץ

### שלב 1: תשתית

```
1. מבנה SSOT (ssot.py + types)
2. טעינת נתונים סטטיים (CSV)
3. מתזמר ריק (pipeline.py — שלד בלבד)
4. טיפול בשגיאות (errors.py)
```

### שלב 2: פאזה 1 — צינור עיבוד

```
1. מתרגם הדפוסים (⓪)
2. מארג (①) — הכי קריטי, הכל תלוי בו
3. OT stages 1–7 (②) — הכי מורכב
4. ותק ענפי (⑤א) — פשוט, מקבילי
5. אגרגטור (③) — פשוט, תלוי ב-②
6. המרת שכר (④) — תלוי ב-③
7. היקף משרה (⑤ב) — פשוט, תלוי ב-③
```

### שלב 3: פאזה 2 — זכויות

```
1. שעות נוספות stage 8 (תמחור)
2. דמי חגים
3. (זכויות נוספות — רק אחרי שהמשתמש מכין סקיל לכל אחת)
```

### שלב 4: פאזה 3 — פוסט-פרוססינג

```
1. התיישנות
2. ניכויים
3. סיכום תביעה
```

### שלב 5: פאזה 4 + פרונט

```
1. פורמטר Duration
2. פרונטאנד — טפסי קלט
3. פרונטאנד — תצוגת תוצאות
4. ייצוא (עתידי)
```

---

## רשימת סקילים

כל סקיל נמצא ב-/mnt/skills/user/{name}/SKILL.md

| מודול | סקיל | סטטוס |
|-------|-------|--------|
| SSOT (מבנה נתונים) | ssot | מוגדר — **מסמך ייחוס מרכזי** |
| מתרגם הדפוסים | pattern-translator | מוגדר |
| מארג | weaver | מוגדר |
| OT (שעות נוספות) | overtime-calculation | מוגדר |
| אגרגטור | aggregator | מוגדר |
| המרת שכר | salary-conversion | מוגדר |
| היקף משרה | job-scope | מוגדר |
| ותק ענפי | seniority | מוגדר |
| דמי חגים | holidays | מוגדר |
| התיישנות | limitation | מוגדר |
| ניכויים | employer-deductions | מוגדר |
| חופשה | — | **טרם הוגדר — דרוש סקיל** |
| פיצויי פיטורין | — | **טרם הוגדר — דרוש סקיל** |
| פנסיה | — | **טרם הוגדר — דרוש סקיל** |
| הבראה | — | **טרם הוגדר — דרוש סקיל** |
| דמי נסיעות | — | **טרם הוגדר — דרוש סקיל** |
| השלמת שכר | — | **טרם הוגדר — דרוש סקיל** |

**זכות שמסומנת "טרם הוגדר" — אסור לפתח אותה. יש לבקש מהמשתמש להכין סקיל.**
