import { useState } from 'react';
import {
  ConfigProvider,
  Form,
  Input,
  InputNumber,
  Button,
  Select,
  TimePicker,
  Checkbox,
  Radio,
  Card,
  Collapse,
  Space,
  Divider,
  Row,
  Col,
  Spin,
  message,
  theme,
  Tooltip,
  Popover,
  Dropdown,
  Tabs,
  Switch,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  CalculatorOutlined,
  LinkOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import heIL from 'antd/locale/he_IL';

// Agartha theme colors
const agarthaTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#4ECDC4',
    colorBgContainer: '#0B1929',
    colorBgElevated: '#132B4A',
    colorBgLayout: '#060D19',
    colorText: '#E8F4F8',
    colorTextSecondary: '#88D8E0',
    colorBorder: 'rgba(78, 205, 196, 0.3)',
    colorBorderSecondary: 'rgba(78, 205, 196, 0.2)',
    borderRadius: 8,
    fontFamily: "'Heebo', system-ui, sans-serif",
  },
};
import dayjs from 'dayjs';
import 'dayjs/locale/he';
import ResultsView from './ResultsView';
import DateInput from './components/DateInput';
import WeekPanel from './components/WeekPanel';
import type {
  SSOTInput,
  EmploymentPeriod,
  WorkPattern,
  SalaryTier,
  TimeRange,
  SeniorityMethod,
  RestDay,
  District,
  PatternType,
  DayTypeInput,
  PatternLevelC,
  CountPeriod,
  NightPlacement,
  PerDayShifts,
  ShiftInputMode,
  ShiftEntry,
  WeekPattern,
  PatternLevelB,
  TerminationReason,
} from './types';

dayjs.locale('he');

// Helper: generate unique ID
const generateId = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

// Time conversion helpers
const timeToMinutes = (timeStr: string): number => {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(':').map(Number);
  return h * 60 + m;
};

const minutesToTimeStr = (mins: number): string => {
  const normalizedMins = ((mins % (24 * 60)) + 24 * 60) % (24 * 60);
  const h = Math.floor(normalizedMins / 60);
  const m = normalizedMins % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`;
};

// Convert break_minutes to TimeRange centered in the shift
const breakToTimeRange = (breakMinutes: number, shiftStart: string, shiftEnd: string): TimeRange | null => {
  if (breakMinutes <= 0) return null;
  const sMins = timeToMinutes(shiftStart);
  let eMins = timeToMinutes(shiftEnd);
  // Handle overnight shifts
  if (eMins <= sMins) eMins += 24 * 60;
  const mid = Math.floor((sMins + eMins) / 2);
  const half = Math.floor(breakMinutes / 2);
  return {
    start_time: minutesToTimeStr(mid - half),
    end_time: minutesToTimeStr(mid - half + breakMinutes),
  };
};

/**
 * Check if a shift crosses midnight (end time earlier than start time).
 */
const isOvernightShift = (shift: { start_time: string; end_time: string }): boolean => {
  if (!shift.start_time || !shift.end_time) return false;
  const startMins = timeToMinutes(shift.start_time);
  const endMins = timeToMinutes(shift.end_time);
  return endMins < startMins;
};

interface ConvertedPattern {
  per_day: Record<string, { shifts: { start_time: string; end_time: string }[]; breaks?: { start_time: string; end_time: string }[] }>;
  work_days: number[];
}

/**
 * Convert frontend PerDayShifts to backend DayShifts format.
 * Each ShiftEntry has its own break_minutes which gets converted to TimeRange.
 * Handles anchor='ends_here' by moving overnight shifts to the previous day.
 * Returns updated work_days reflecting actual days with shifts after anchor adjustments.
 */
const convertPerDayForBackend = (
  perDay: Record<number, PerDayShifts>,
  _originalWorkDays: number[],
): ConvertedPattern => {
  // First pass: collect all shifts, handling anchor moves
  const adjustedPerDay: Record<number, { shifts: ShiftEntry[] }> = {};

  for (const [dayStr, dayData] of Object.entries(perDay)) {
    const day = parseInt(dayStr);
    if (!adjustedPerDay[day]) adjustedPerDay[day] = { shifts: [] };
    for (const shift of dayData.shifts) {
      if (shift.anchor === 'ends_here' && isOvernightShift(shift)) {
        // Move to previous day (0=Sunday → 6=Saturday wraps)
        const prevDay = (day - 1 + 7) % 7;
        if (!adjustedPerDay[prevDay]) adjustedPerDay[prevDay] = { shifts: [] };
        adjustedPerDay[prevDay].shifts.push({ ...shift, anchor: 'starts_here' });
      } else {
        adjustedPerDay[day].shifts.push(shift);
      }
    }
  }

  // Second pass: convert to backend format
  const result: Record<string, { shifts: { start_time: string; end_time: string }[]; breaks?: { start_time: string; end_time: string }[] }> = {};

  for (const [dayStr, dayData] of Object.entries(adjustedPerDay)) {
    if (dayData.shifts.length === 0) continue;

    const shifts = dayData.shifts.map(s => ({
      start_time: s.start_time,
      end_time: s.end_time,
    }));

    const breaks: { start_time: string; end_time: string }[] = [];
    for (const shift of dayData.shifts) {
      if (shift.break_minutes > 0) {
        const br = breakToTimeRange(shift.break_minutes, shift.start_time, shift.end_time);
        if (br) breaks.push(br);
      }
    }

    result[dayStr] = {
      shifts,
      breaks: breaks.length > 0 ? breaks : undefined,
    };
  }

  // Compute updated work_days: days that have at least one shift after adjustment
  const updatedWorkDays = Object.entries(adjustedPerDay)
    .filter(([_, data]) => data.shifts.length > 0)
    .map(([dayStr]) => parseInt(dayStr))
    .sort((a, b) => a - b);

  return { per_day: result, work_days: updatedWorkDays };
};

// Get end of current month as default filing date
const getEndOfCurrentMonth = (): string => {
  return dayjs().endOf('month').format('YYYY-MM-DD');
};

// Initial empty data
const createEmptyInput = (): SSOTInput => ({
  case_metadata: { case_name: '', notes: '' },
  personal_details: { birth_year: 0 },
  defendant_details: {},
  employment_periods: [],
  work_patterns: [],
  salary_tiers: [],
  rest_day: 'saturday',
  district: 'tel_aviv',
  industry: 'general',
  filing_date: getEndOfCurrentMonth(),
  termination_reason: 'fired',
  seniority_input: { method: 'prior_plus_pattern', prior_months: 0 },
  right_toggles: {
    overtime: { enabled: true },
    holidays: { enabled: true },
    severance: { enabled: true },
  },
  deductions_input: {},
  right_specific_inputs: {},
});

type SeniorityUnit = 'months' | 'years';

// Example JSON input for debug tab
const EXAMPLE_JSON_INPUT = {
  case_metadata: { case_name: "תיק בדיקה — 8 שנות עבודה, דפוס משתנה, התיישנות חלקית", notes: "עובד בניין, שינוי דפוס מ-6 ל-5 ימים, 3 מדרגות שכר, ~1.5 שנים מתיישנות" },
  personal_details: { first_name: "אחמד", last_name: "חסן", id_number: "123456789", birth_year: 1985 },
  defendant_details: { name: "חברת בנייה בע\"מ", id_number: "514000000", address: "תל אביב" },
  employment_periods: [
    { id: "ep1", start: "2017-01-01", end: "2024-12-31" }
  ],
  work_patterns: [
    {
      id: "wp1",
      start: "2017-01-01",
      end: "2021-06-30",
      work_days: [0, 1, 2, 3, 4, 5],
      default_shifts: [{ start_time: "06:00:00", end_time: "14:00:00" }],
      default_breaks: [{ start_time: "10:00:00", end_time: "10:30:00" }]
    },
    {
      id: "wp2",
      start: "2021-07-01",
      end: "2024-12-31",
      work_days: [0, 1, 2, 3, 4],
      default_shifts: [{ start_time: "08:00:00", end_time: "18:00:00" }],
      default_breaks: [{ start_time: "12:00:00", end_time: "12:30:00" }]
    }
  ],
  salary_tiers: [
    {
      id: "st1",
      start: "2017-01-01",
      end: "2019-12-31",
      amount: "30",
      type: "hourly",
      net_or_gross: "gross"
    },
    {
      id: "st2",
      start: "2020-01-01",
      end: "2022-12-31",
      amount: "35",
      type: "hourly",
      net_or_gross: "gross"
    },
    {
      id: "st3",
      start: "2023-01-01",
      end: "2024-12-31",
      amount: "45",
      type: "hourly",
      net_or_gross: "gross"
    }
  ],
  rest_day: "saturday",
  district: "tel_aviv",
  industry: "general",
  filing_date: "2025-12-31",
  termination_reason: "fired",
  seniority_input: { method: "prior_plus_pattern", prior_months: 0 },
  right_toggles: {},
  deductions_input: { overtime: "0", holidays: "0", severance: "15000" },
  right_specific_inputs: {}
};

// Example for testing rest window (stage 7 + stage 8 pricing)
const EXAMPLE_REST_WINDOW = {
  case_metadata: {
    case_name: "בדיקת חלון מנוחה — משמרת שישי חוצה שבת",
    notes: "משמרת שישי 14:00-22:00 חוצה כניסת שבת (~16:31-17:40). בודק stage 7 אופטימיזציה + stage 8 pricing split."
  },
  personal_details: { first_name: "בדיקה", last_name: "חלון-מנוחה", id_number: "999888777", birth_year: 1990 },
  defendant_details: { name: "חברת בדיקות בע\"מ", id_number: "514111111", address: "תל אביב" },
  employment_periods: [
    { id: "ep1", start: "2024-01-01", end: "2024-03-31" }
  ],
  work_patterns: [
    {
      id: "wp1",
      start: "2024-01-01",
      end: "2024-03-31",
      work_days: [0, 1, 2, 3, 4, 5],
      default_shifts: [{ start_time: "07:00:00", end_time: "15:30:00" }],
      default_breaks: [{ start_time: "12:00:00", end_time: "12:30:00" }],
      per_day: {
        "5": {
          shifts: [{ start_time: "14:00:00", end_time: "22:00:00" }],
          breaks: [{ start_time: "18:00:00", end_time: "18:30:00" }]
        }
      }
    }
  ],
  salary_tiers: [
    { id: "st1", start: "2024-01-01", end: "2024-03-31", amount: "40", type: "hourly", net_or_gross: "gross" }
  ],
  rest_day: "saturday",
  district: "tel_aviv",
  industry: "general",
  filing_date: "2025-12-31",
  seniority_input: { method: "prior_plus_pattern", prior_months: 0 },
  right_toggles: {},
  deductions_input: { overtime: "0", holidays: "0" },
  right_specific_inputs: {}
};

// Format months as "X שנים ו-Y חודשים"
const formatMonthsDisplay = (totalMonths: number): string => {
  if (totalMonths === 0) return '0 חודשים';

  const years = Math.floor(totalMonths / 12);
  const months = totalMonths % 12;

  if (years === 0) {
    return months === 1 ? 'חודש' : `${months} חודשים`;
  }

  const yearsStr = years === 1 ? 'שנה' : `${years} שנים`;

  if (months === 0) {
    return yearsStr;
  }

  const monthsStr = months === 1 ? 'חודש' : `${months} חודשים`;
  return `${yearsStr} ו-${monthsStr}`;
};

function App() {
  const [formData, setFormData] = useState<SSOTInput>(createEmptyInput());
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [priorSeniorityUnit, setPriorSeniorityUnit] = useState<SeniorityUnit>('months');
  const [totalSeniorityUnit, setTotalSeniorityUnit] = useState<SeniorityUnit>('months');
  const [jsonInput, setJsonInput] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  // SNAP selection state: keyed by pattern/tier ID
  const [snapSelections, setSnapSelections] = useState<Record<string, number[]>>({});

  // Helper: toggle period selection for SNAP
  const toggleSnapSelection = (id: string, periodIndex: number) => {
    setSnapSelections((prev) => {
      const current = prev[id] || [];
      const exists = current.includes(periodIndex);
      return {
        ...prev,
        [id]: exists
          ? current.filter((i) => i !== periodIndex)
          : [...current, periodIndex],
      };
    });
  };

  // Helper: compute min start, max end from multiple periods
  const computeSnapRange = (periodIndices: number[]): { start: string; end: string } | null => {
    if (periodIndices.length === 0) return null;
    const periods = periodIndices
      .map((i) => formData.employment_periods[i])
      .filter((p) => p && p.start && p.end);
    if (periods.length === 0) return null;

    const starts = periods.map((p) => p.start).sort();
    const ends = periods.map((p) => p.end).sort();
    return {
      start: starts[0],
      end: ends[ends.length - 1],
    };
  };

  // Update nested fields
  const updateField = <K extends keyof SSOTInput>(
    key: K,
    value: SSOTInput[K]
  ) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const updateNestedField = <K extends keyof SSOTInput>(
    parentKey: K,
    childKey: string,
    value: unknown
  ) => {
    setFormData((prev) => ({
      ...prev,
      [parentKey]: {
        ...(prev[parentKey] as Record<string, unknown>),
        [childKey]: value,
      },
    }));
  };

  // Employment periods handlers
  const addEmploymentPeriod = () => {
    const newPeriod: EmploymentPeriod = {
      id: generateId(),
      start: '',
      end: '',
    };
    updateField('employment_periods', [...formData.employment_periods, newPeriod]);
  };

  const updateEmploymentPeriod = (index: number, field: keyof EmploymentPeriod, value: string) => {
    const updated = [...formData.employment_periods];
    updated[index] = { ...updated[index], [field]: value };
    updateField('employment_periods', updated);
  };

  const removeEmploymentPeriod = (index: number) => {
    const updated = formData.employment_periods.filter((_, i) => i !== index);
    updateField('employment_periods', updated);
  };

  // Default Level C data
  const createDefaultLevelC = (): PatternLevelC => ({
    day_types: [
      { type_id: 'regular', count: 5, count_period: 'weekly', hours: 9, break_minutes: 0 },
      { type_id: 'eve_of_rest', count: 0, count_period: 'weekly', hours: 6, break_minutes: 0 },
      { type_id: 'rest_day', count: 0, count_period: 'weekly', hours: 0, break_minutes: 0 },
      { type_id: 'night', count: 0, count_period: 'weekly', hours: 0, break_minutes: 0 },
    ],
    night_placement: 'average',
  });

  // Work patterns handlers
  const addWorkPattern = () => {
    const newPattern: WorkPattern = {
      id: generateId(),
      start: '',
      end: '',
      pattern_type: 'statistical', // Default to statistical (Level C)
      work_days: [0, 1, 2, 3, 4], // Default: Sunday-Thursday
      default_shifts: [{ start_time: '08:00:00', end_time: '17:00:00' }],
      default_breaks: [{ start_time: '12:00:00', end_time: '12:30:00' }],
      level_c: createDefaultLevelC(),
    };
    updateField('work_patterns', [...formData.work_patterns, newPattern]);
  };

  const updateWorkPattern = (index: number, field: keyof WorkPattern, value: unknown) => {
    const updated = [...formData.work_patterns];
    updated[index] = { ...updated[index], [field]: value };
    updateField('work_patterns', updated);
  };

  const removeWorkPattern = (index: number) => {
    const updated = formData.work_patterns.filter((_, i) => i !== index);
    updateField('work_patterns', updated);
  };

  // Level C handlers
  const updateDayType = (
    patternIndex: number,
    dayTypeIndex: number,
    field: keyof DayTypeInput,
    value: number | CountPeriod | string
  ) => {
    const updated = [...formData.work_patterns];
    const pattern = updated[patternIndex];
    if (!pattern.level_c) return;
    const dayTypes = [...pattern.level_c.day_types];
    dayTypes[dayTypeIndex] = { ...dayTypes[dayTypeIndex], [field]: value };
    updated[patternIndex] = {
      ...pattern,
      level_c: { ...pattern.level_c, day_types: dayTypes },
    };
    updateField('work_patterns', updated);
  };

  const updateNightPlacement = (patternIndex: number, placement: NightPlacement) => {
    const updated = [...formData.work_patterns];
    const pattern = updated[patternIndex];
    if (!pattern.level_c) return;
    updated[patternIndex] = {
      ...pattern,
      level_c: { ...pattern.level_c, night_placement: placement },
    };
    updateField('work_patterns', updated);
  };

  const updateLevelCInputMode = (patternIndex: number, mode: ShiftInputMode) => {
    const updated = [...formData.work_patterns];
    const pattern = updated[patternIndex];
    if (!pattern.level_c) return;
    updated[patternIndex] = {
      ...pattern,
      level_c: { ...pattern.level_c, input_mode: mode },
    };
    updateField('work_patterns', updated);
  };

  // Create default per_day structure for weekly_simple
  const createDefaultPerDay = (): Record<number, PerDayShifts> => ({
    0: { shifts: [{ start_time: '07:00:00', end_time: '16:00:00', break_minutes: 0 }] },
    1: { shifts: [{ start_time: '07:00:00', end_time: '16:00:00', break_minutes: 0 }] },
    2: { shifts: [{ start_time: '07:00:00', end_time: '16:00:00', break_minutes: 0 }] },
    3: { shifts: [{ start_time: '07:00:00', end_time: '16:00:00', break_minutes: 0 }] },
    4: { shifts: [{ start_time: '07:00:00', end_time: '16:00:00', break_minutes: 0 }] },
  });

  // Create default week for cyclic patterns
  const createDefaultWeek = (): WeekPattern => ({
    work_days: [0, 1, 2, 3, 4],
    per_day: createDefaultPerDay(),
  });

  // Create default level_b structure for cyclic patterns
  const createDefaultLevelB = (): PatternLevelB => ({
    cycle_length: 2,
    cycle: [createDefaultWeek(), createDefaultWeek()],
  });

  // Switch pattern type and initialize appropriate data
  const switchPatternType = (patternIndex: number, newType: PatternType) => {
    const updated = [...formData.work_patterns];
    const pattern = updated[patternIndex];
    updated[patternIndex] = {
      ...pattern,
      pattern_type: newType,
      level_c: newType === 'statistical' && !pattern.level_c ? createDefaultLevelC() : pattern.level_c,
      level_b: newType === 'cyclic' && !pattern.level_b ? createDefaultLevelB() : pattern.level_b,
      per_day: newType === 'weekly_simple' && !pattern.per_day ? createDefaultPerDay() : pattern.per_day,
      work_days: newType === 'weekly_simple' && (!pattern.work_days || pattern.work_days.length === 0) ? [0, 1, 2, 3, 4] : pattern.work_days,
      input_mode: (newType === 'weekly_simple' || newType === 'cyclic') && !pattern.input_mode ? 'time_range' : pattern.input_mode,
    };
    updateField('work_patterns', updated);
  };

  // Update a week in the cyclic pattern
  const updateCycleWeek = (patternIndex: number, weekIndex: number, workDays: number[], perDay: Record<number, PerDayShifts>) => {
    const updated = [...formData.work_patterns];
    const levelB = { ...updated[patternIndex].level_b! };
    const cycle = [...levelB.cycle];
    cycle[weekIndex] = { work_days: workDays, per_day: perDay };
    levelB.cycle = cycle;
    updated[patternIndex] = { ...updated[patternIndex], level_b: levelB };
    updateField('work_patterns', updated);
  };

  // Update week repeats in cyclic pattern
  const updateWeekRepeats = (patternIndex: number, weekIndex: number, value: number) => {
    const updated = [...formData.work_patterns];
    const levelB = { ...updated[patternIndex].level_b! };
    const cycle = [...levelB.cycle];
    cycle[weekIndex] = { ...cycle[weekIndex], repeats: value };
    levelB.cycle = cycle;
    levelB.cycle_length = cycle.reduce((sum, w) => sum + (w.repeats || 1), 0);
    updated[patternIndex] = { ...updated[patternIndex], level_b: levelB };
    updateField('work_patterns', updated);
  };

  // Remove a specific week from cyclic pattern
  const removeCycleWeek = (patternIndex: number, weekIndex: number) => {
    const updated = [...formData.work_patterns];
    const levelB = { ...updated[patternIndex].level_b! };
    if (levelB.cycle.length <= 2) return;  // minimum 2 weeks
    const cycle = levelB.cycle.filter((_, i) => i !== weekIndex);
    levelB.cycle = cycle;
    levelB.cycle_length = cycle.reduce((sum, w) => sum + (w.repeats || 1), 0);
    updated[patternIndex] = { ...updated[patternIndex], level_b: levelB };
    updateField('work_patterns', updated);
  };

  // Add a new week to cyclic pattern
  const addCycleWeek = (patternIndex: number) => {
    const updated = [...formData.work_patterns];
    const levelB = { ...updated[patternIndex].level_b! };
    levelB.cycle = [...levelB.cycle, createDefaultWeek()];
    levelB.cycle_length = levelB.cycle.reduce((sum, w) => sum + (w.repeats || 1), 0);
    updated[patternIndex] = { ...updated[patternIndex], level_b: levelB };
    updateField('work_patterns', updated);
  };

  // SNAP work pattern to multiple periods (uses min start, max end)
  const snapWorkPatternToMultiple = (patternIndex: number, periodIndices: number[]) => {
    const range = computeSnapRange(periodIndices);
    if (!range) return;
    const updated = [...formData.work_patterns];
    updated[patternIndex] = {
      ...updated[patternIndex],
      start: range.start,
      end: range.end,
    };
    updateField('work_patterns', updated);
    // Clear selection after snap
    setSnapSelections((prev) => {
      const newSel = { ...prev };
      delete newSel[formData.work_patterns[patternIndex].id];
      return newSel;
    });
    message.success(`דפוס עבודה ${patternIndex + 1} הותאם ל-${periodIndices.length} תקופות`);
  };

  // SNAP salary tier to multiple periods
  const snapSalaryTierToMultiple = (tierIndex: number, periodIndices: number[]) => {
    const range = computeSnapRange(periodIndices);
    if (!range) return;
    const updated = [...formData.salary_tiers];
    updated[tierIndex] = {
      ...updated[tierIndex],
      start: range.start,
      end: range.end,
    };
    updateField('salary_tiers', updated);
    // Clear selection after snap
    setSnapSelections((prev) => {
      const newSel = { ...prev };
      delete newSel[formData.salary_tiers[tierIndex].id];
      return newSel;
    });
    message.success(`מדרגת שכר ${tierIndex + 1} הותאמה ל-${periodIndices.length} תקופות`);
  };

  // SNAP to all employment periods
  const snapWorkPatternToAll = (patternIndex: number) => {
    const allIndices = formData.employment_periods.map((_, i) => i);
    snapWorkPatternToMultiple(patternIndex, allIndices);
  };

  const snapSalaryTierToAll = (tierIndex: number) => {
    const allIndices = formData.employment_periods.map((_, i) => i);
    snapSalaryTierToMultiple(tierIndex, allIndices);
  };

  // Render SNAP popover content for multi-select
  const renderSnapContent = (
    id: string,
    onSnapSelected: (indices: number[]) => void,
    onSnapAll: () => void
  ) => {
    const selected = snapSelections[id] || [];
    if (formData.employment_periods.length === 0) {
      return <div style={{ padding: 8, color: '#88D8E0' }}>אין תקופות העסקה</div>;
    }
    return (
      <div style={{ minWidth: 260 }}>
        {formData.employment_periods.map((period, index) => (
          <div key={index} style={{ padding: '4px 0' }}>
            <Checkbox
              checked={selected.includes(index)}
              onChange={() => toggleSnapSelection(id, index)}
            >
              תקופה {index + 1}: {period.start ? dayjs(period.start).format('DD.MM.YYYY') : '?'} - {period.end ? dayjs(period.end).format('DD.MM.YYYY') : '?'}
            </Checkbox>
          </div>
        ))}
        <Divider style={{ margin: '8px 0' }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Button
            size="small"
            type="primary"
            disabled={selected.length === 0}
            onClick={() => onSnapSelected(selected)}
            block
          >
            התאם לנבחרות ({selected.length})
          </Button>
          <Button
            size="small"
            onClick={onSnapAll}
            block
          >
            התאם לכולן
          </Button>
        </div>
      </div>
    );
  };

  // Salary tiers handlers
  const addSalaryTier = () => {
    const newTier: SalaryTier = {
      id: generateId(),
      start: '',
      end: '',
      amount: '0',
      type: 'hourly',
      net_or_gross: 'gross',
    };
    updateField('salary_tiers', [...formData.salary_tiers, newTier]);
  };

  const updateSalaryTier = (index: number, field: keyof SalaryTier, value: string) => {
    const updated = [...formData.salary_tiers];
    updated[index] = { ...updated[index], [field]: value };
    updateField('salary_tiers', updated);
  };

  const removeSalaryTier = (index: number) => {
    const updated = formData.salary_tiers.filter((_, i) => i !== index);
    updateField('salary_tiers', updated);
  };

  // Deductions handlers
  const updateDeduction = (rightId: string, value: string) => {
    updateField('deductions_input', {
      ...formData.deductions_input,
      [rightId]: value,
    });
  };

  // Right toggles handlers
  const updateRightToggle = (rightId: string, toggleKey: string, value: boolean) => {
    const currentToggles = formData.right_toggles[rightId] || {};
    updateField('right_toggles', {
      ...formData.right_toggles,
      [rightId]: {
        ...currentToggles,
        [toggleKey]: value,
      },
    });
  };

  // Build pattern_sources for patterns that need translation
  // Returns backend-compatible format (may differ from frontend types)
  const buildPatternSources = () => {
    return formData.work_patterns
      .filter(p => p.pattern_type && p.pattern_type !== 'weekly_simple')
      .map(p => {
        let level_c_data = p.pattern_type === 'statistical' ? p.level_c : undefined;

        // Convert time_range mode to shifts/breaks format for Level C
        if (level_c_data && level_c_data.input_mode === 'time_range') {
          level_c_data = {
            ...level_c_data,
            day_types: level_c_data.day_types.map(dt => {
              if (dt.shift_start && dt.shift_end) {
                const shifts = [{ start_time: dt.shift_start, end_time: dt.shift_end }];
                const breakRange = breakToTimeRange(dt.break_minutes, dt.shift_start, dt.shift_end);
                return {
                  ...dt,
                  hours: 0, // Backend will calculate from shifts
                  shifts,
                  breaks: breakRange ? [breakRange] : undefined,
                };
              }
              return dt;
            }),
          };
        }

        // Convert cyclic pattern to backend format
        const level_b_data = p.pattern_type === 'cyclic' && p.level_b ? {
          cycle_length: p.level_b.cycle.reduce((sum, w) => sum + (w.repeats || 1), 0),
          cycle: p.level_b.cycle.flatMap(week => {
            const reps = week.repeats || 1;
            const convertedPerDay = convertPerDayForBackend(week.per_day, week.work_days);
            const item = {
              id: p.id,
              start: p.start,
              end: p.end,
              work_days: convertedPerDay.work_days,
              default_shifts: [],
              default_breaks: [],
              per_day: convertedPerDay.per_day,
            };
            return Array(reps).fill(item);
          }),
        } : undefined;

        return {
          id: p.id,
          type: p.pattern_type as PatternType,
          start: p.start,
          end: p.end,
          level_c_data,
          level_b_data,
        };
      });
  };

  // Submit handler
  const handleCalculate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const patternSources = buildPatternSources();

      // Convert per_day for all work patterns before sending
      const convertedWorkPatterns = formData.work_patterns.map(wp => {
        if (wp.per_day) {
          const converted = convertPerDayForBackend(wp.per_day, wp.work_days || []);
          return {
            ...wp,
            per_day: converted.per_day,
            work_days: converted.work_days,
          };
        }
        return wp;
      });

      const requestBody = {
        ...formData,
        work_patterns: convertedWorkPatterns,
        pattern_sources: patternSources.length > 0 ? patternSources : undefined,
      };

      const response = await fetch('/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();

      if (!response.ok) {
        // Handle error response
        const errorDetail = data.detail;
        if (errorDetail && errorDetail.errors) {
          const errorMessages = errorDetail.errors
            .map((e: { message: string }) => e.message)
            .join('\n');
          setError(errorMessages);
        } else {
          setError('שגיאה בחישוב');
        }
      } else {
        setResult(data.ssot);
        message.success('החישוב הושלם בהצלחה');
      }
    } catch (err) {
      setError(`שגיאת תקשורת: ${err instanceof Error ? err.message : 'לא ידוע'}`);
    } finally {
      setLoading(false);
    }
  };

  // JSON tab handlers
  const handleJsonCalculate = async () => {
    setJsonError(null);
    let parsed;
    try {
      parsed = JSON.parse(jsonInput);
    } catch (e) {
      setJsonError(`שגיאת פרסור JSON: ${e instanceof Error ? e.message : 'לא ידוע'}`);
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch('/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsed),
      });
      const data = await response.json();
      if (!response.ok) {
        const errorDetail = data.detail;
        if (errorDetail?.errors) {
          setError(errorDetail.errors.map((e: { message: string }) => e.message).join('\n'));
        } else {
          setError('שגיאה בחישוב');
        }
      } else {
        setResult(data.ssot);
        message.success('החישוב הושלם בהצלחה');
      }
    } catch (err) {
      setError(`שגיאת תקשורת: ${err instanceof Error ? err.message : 'לא ידוע'}`);
    } finally {
      setLoading(false);
    }
  };

  const loadExample = (example: 'main' | 'rest_window' = 'main') => {
    const examples = {
      main: EXAMPLE_JSON_INPUT,
      rest_window: EXAMPLE_REST_WINDOW,
    };
    setJsonInput(JSON.stringify(examples[example], null, 2));
    setJsonError(null);
  };

  const saveJsonToFile = () => {
    if (!jsonInput) return;
    const blob = new Blob([jsonInput], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'claims-wizard-input.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <ConfigProvider direction="rtl" locale={heIL} theme={agarthaTheme}>
      <div className="app-container">
        {/* Loading overlay */}
        {loading && (
          <div className="loading-overlay">
            <Spin size="large" tip="מחשב..." />
          </div>
        )}

        {/* Header */}
        <h1 className="main-title">אשף התביעות</h1>
        <p className="main-subtitle">מחשבון זכויות עובדים בדיני עבודה ישראליים</p>

        <Tabs
          defaultActiveKey="form"
          items={[
            {
              key: 'form',
              label: 'טופס קלט',
              children: (
                <Form layout="vertical">
                  <Collapse
            defaultActiveKey={['case', 'personal', 'defendant', 'employment', 'patterns', 'salary', 'settings', 'seniority', 'toggles', 'deductions']}
            items={[
              {
                key: 'case',
                label: 'פרטי תיק',
                children: (
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="שם התיק">
                        <Input
                          value={formData.case_metadata.case_name}
                          onChange={(e) => updateNestedField('case_metadata', 'case_name', e.target.value)}
                          placeholder="לדוגמה: תיק אחמד נגד חברה בע״מ"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="הערות">
                        <Input.TextArea
                          value={formData.case_metadata.notes}
                          onChange={(e) => updateNestedField('case_metadata', 'notes', e.target.value)}
                          placeholder="הערות נוספות..."
                          rows={2}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'personal',
                label: 'פרטי עובד',
                children: (
                  <Row gutter={16}>
                    <Col span={6}>
                      <Form.Item label="שנת לידה" required>
                        <InputNumber
                          value={formData.personal_details.birth_year || undefined}
                          onChange={(v) => updateNestedField('personal_details', 'birth_year', v || 0)}
                          min={1940}
                          max={2010}
                          style={{ width: '100%' }}
                          placeholder="1980"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item label="שם פרטי">
                        <Input
                          value={formData.personal_details.first_name || ''}
                          onChange={(e) => updateNestedField('personal_details', 'first_name', e.target.value)}
                          placeholder="שם פרטי"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item label="שם משפחה">
                        <Input
                          value={formData.personal_details.last_name || ''}
                          onChange={(e) => updateNestedField('personal_details', 'last_name', e.target.value)}
                          placeholder="שם משפחה"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item label="תעודת זהות">
                        <Input
                          value={formData.personal_details.id_number || ''}
                          onChange={(e) => updateNestedField('personal_details', 'id_number', e.target.value)}
                          placeholder="מספר ת״ז"
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'defendant',
                label: 'פרטי נתבע',
                children: (
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="שם הנתבע">
                        <Input
                          value={formData.defendant_details.name || ''}
                          onChange={(e) => updateNestedField('defendant_details', 'name', e.target.value)}
                          placeholder="שם החברה / המעסיק"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="ח.פ. / ע.מ.">
                        <Input
                          value={formData.defendant_details.id_number || ''}
                          onChange={(e) => updateNestedField('defendant_details', 'id_number', e.target.value)}
                          placeholder="מספר חברה"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="כתובת">
                        <Input
                          value={formData.defendant_details.address || ''}
                          onChange={(e) => updateNestedField('defendant_details', 'address', e.target.value)}
                          placeholder="כתובת הנתבע"
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'employment',
                label: `תקופות העסקה (${formData.employment_periods.length})`,
                children: (
                  <div>
                    {formData.employment_periods.map((period, index) => (
                      <div key={period.id} className="dynamic-list-item">
                        <Row gutter={16} align="middle">
                          <Col span={10}>
                            <Form.Item label="תאריך התחלה">
                              <DateInput
                                value={period.start}
                                onChange={(v) => updateEmploymentPeriod(index, 'start', v)}
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={10}>
                            <Form.Item label="תאריך סיום">
                              <DateInput
                                value={period.end}
                                onChange={(v) => updateEmploymentPeriod(index, 'end', v)}
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={4}>
                            <Button
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={() => removeEmploymentPeriod(index)}
                            >
                              מחק
                            </Button>
                          </Col>
                        </Row>
                      </div>
                    ))}
                    <Button type="dashed" onClick={addEmploymentPeriod} icon={<PlusOutlined />} block>
                      הוסף תקופת העסקה
                    </Button>
                  </div>
                ),
              },
              {
                key: 'patterns',
                label: `דפוסי עבודה (${formData.work_patterns.length})`,
                children: (
                  <div>
                    {formData.work_patterns.map((pattern, pIndex) => (
                      <Card
                        key={pattern.id}
                        title={`דפוס עבודה ${pIndex + 1}`}
                        extra={
                          <Button
                            type="text"
                            danger
                            icon={<DeleteOutlined />}
                            onClick={() => removeWorkPattern(pIndex)}
                          />
                        }
                        style={{ marginBottom: 16 }}
                      >
                        <Row gutter={16}>
                          <Col span={11}>
                            <Form.Item label="תאריך התחלה">
                              <DateInput
                                value={pattern.start}
                                onChange={(v) => updateWorkPattern(pIndex, 'start', v)}
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={11}>
                            <Form.Item label="תאריך סיום">
                              <DateInput
                                value={pattern.end}
                                onChange={(v) => updateWorkPattern(pIndex, 'end', v)}
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={2} style={{ display: 'flex', alignItems: 'center', paddingTop: 30 }}>
                            <Popover
                              content={renderSnapContent(
                                pattern.id,
                                (indices) => snapWorkPatternToMultiple(pIndex, indices),
                                () => snapWorkPatternToAll(pIndex)
                              )}
                              trigger="click"
                              placement="bottomRight"
                            >
                              <Tooltip title="התאם לתקופות העסקה">
                                <Button
                                  type="default"
                                  size="small"
                                  icon={<LinkOutlined />}
                                />
                              </Tooltip>
                            </Popover>
                          </Col>
                        </Row>

                        <Form.Item label="סוג דפוס">
                          <Radio.Group
                            value={pattern.pattern_type || 'weekly_simple'}
                            onChange={(e) => switchPatternType(pIndex, e.target.value as PatternType)}
                          >
                            <Radio value="statistical">סטטיסטי</Radio>
                            <Radio value="weekly_simple">דפוס שבועי</Radio>
                            <Radio value="cyclic">מחזורי</Radio>
                          </Radio.Group>
                        </Form.Item>

                        {/* Level C (Statistical) Form */}
                        {pattern.pattern_type === 'statistical' && pattern.level_c && (
                          <>
                            {/* Input mode selector */}
                            <Form.Item label="מצב הזנה" style={{ marginBottom: 8 }}>
                              <Radio.Group
                                value={pattern.level_c.input_mode || 'duration'}
                                onChange={(e) => updateLevelCInputMode(pIndex, e.target.value as ShiftInputMode)}
                                size="small"
                              >
                                <Radio value="duration">אורך (שעות)</Radio>
                                <Radio value="time_range">טווח (שעה-שעה)</Radio>
                              </Radio.Group>
                            </Form.Item>

                            <Divider>סוגי משמרות</Divider>
                            {pattern.level_c.day_types.map((dayType, dtIndex) => {
                              const labels: Record<string, string> = {
                                regular: 'יום רגיל',
                                eve_of_rest: 'ערב מנוחה',
                                rest_day: 'יום מנוחה',
                                night: 'לילה',
                              };
                              const levelCMode = pattern.level_c?.input_mode || 'duration';
                              return (
                                <Row key={dayType.type_id} gutter={8} align="middle" style={{ marginBottom: 8 }}>
                                  <Col span={3}>
                                    <span style={{ color: '#88D8E0' }}>{labels[dayType.type_id]}:</span>
                                  </Col>
                                  <Col span={3}>
                                    <InputNumber
                                      value={dayType.count}
                                      onChange={(v) => updateDayType(pIndex, dtIndex, 'count', v || 0)}
                                      min={0}
                                      max={dayType.count_period === 'weekly' ? 7 : 31}
                                      precision={1}
                                      step={0.5}
                                      style={{ width: '100%' }}
                                      addonAfter="ימים"
                                    />
                                  </Col>
                                  <Col span={3}>
                                    <Select
                                      value={dayType.count_period}
                                      onChange={(v) => updateDayType(pIndex, dtIndex, 'count_period', v as CountPeriod)}
                                      style={{ width: '100%' }}
                                      size="small"
                                    >
                                      <Select.Option value="weekly">לשבוע</Select.Option>
                                      <Select.Option value="monthly">לחודש</Select.Option>
                                    </Select>
                                  </Col>
                                  {levelCMode === 'duration' ? (
                                    <Col span={4}>
                                      <InputNumber
                                        value={dayType.hours}
                                        onChange={(v) => updateDayType(pIndex, dtIndex, 'hours', v || 0)}
                                        min={0}
                                        max={dayType.type_id === 'night' ? 12 : 14}
                                        precision={1}
                                        step={0.5}
                                        style={{ width: '100%' }}
                                        addonAfter="שעות"
                                      />
                                    </Col>
                                  ) : (
                                    <>
                                      <Col span={3}>
                                        <TimePicker
                                          value={dayType.shift_start ? dayjs(dayType.shift_start, 'HH:mm:ss') : null}
                                          onChange={(d) => updateDayType(pIndex, dtIndex, 'shift_start', d ? d.format('HH:mm:ss') : '')}
                                          format="HH:mm"
                                          size="small"
                                          style={{ width: '100%' }}
                                          placeholder="התחלה"
                                        />
                                      </Col>
                                      <Col span={1} style={{ textAlign: 'center' }}>-</Col>
                                      <Col span={3}>
                                        <TimePicker
                                          value={dayType.shift_end ? dayjs(dayType.shift_end, 'HH:mm:ss') : null}
                                          onChange={(d) => updateDayType(pIndex, dtIndex, 'shift_end', d ? d.format('HH:mm:ss') : '')}
                                          format="HH:mm"
                                          size="small"
                                          style={{ width: '100%' }}
                                          placeholder="סיום"
                                        />
                                      </Col>
                                    </>
                                  )}
                                  <Col span={5}>
                                    <InputNumber
                                      value={dayType.break_minutes}
                                      onChange={(v) => updateDayType(pIndex, dtIndex, 'break_minutes', v || 0)}
                                      min={0}
                                      max={180}
                                      precision={0}
                                      size="small"
                                      style={{ width: '100%', minWidth: 120 }}
                                      addonBefore="הפ'"
                                      addonAfter="דק'"
                                    />
                                  </Col>
                                </Row>
                              );
                            })}

                            {/* Night placement - only show if night count > 0 */}
                            {(pattern.level_c?.day_types.find(dt => dt.type_id === 'night')?.count ?? 0) > 0 && (
                              <Form.Item label="שיבוץ לילות" style={{ marginTop: 16 }}>
                                <Radio.Group
                                  value={pattern.level_c.night_placement}
                                  onChange={(e) => updateNightPlacement(pIndex, e.target.value as NightPlacement)}
                                >
                                  <Radio value="employer_favor">לטובת מעביד</Radio>
                                  <Radio value="employee_favor">לטובת עובד</Radio>
                                  <Radio value="average">ממוצע</Radio>
                                </Radio.Group>
                              </Form.Item>
                            )}
                          </>
                        )}

                        {/* Level A (Weekly Simple) Form - WeekPanel */}
                        {(pattern.pattern_type === 'weekly_simple' || !pattern.pattern_type) && (
                          <WeekPanel
                            workDays={pattern.work_days}
                            perDay={pattern.per_day || {}}
                            restDay={formData.rest_day}
                            inputMode={pattern.input_mode || 'time_range'}
                            onInputModeChange={(mode) => updateWorkPattern(pIndex, 'input_mode', mode)}
                            onChange={(workDays, perDay) => {
                              const updated = [...formData.work_patterns];
                              updated[pIndex] = { ...updated[pIndex], work_days: workDays, per_day: perDay };
                              updateField('work_patterns', updated);
                            }}
                          />
                        )}

                        {/* Level B (Cyclic) Form */}
                        {pattern.pattern_type === 'cyclic' && pattern.level_b && (
                          <>
                            <Collapse
                              defaultActiveKey={pattern.level_b.cycle.map((_, i) => String(i))}
                              items={pattern.level_b.cycle.map((week, wIndex) => ({
                                key: String(wIndex),
                                label: (
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
                                    <span>שבוע {wIndex + 1}</span>
                                    <span style={{ fontSize: 12, color: '#888' }}>
                                      ×
                                      <InputNumber
                                        value={week.repeats || 1}
                                        onChange={(v) => updateWeekRepeats(pIndex, wIndex, v || 1)}
                                        min={1}
                                        max={20}
                                        size="small"
                                        style={{ width: 55, marginRight: 4, marginLeft: 4 }}
                                        onClick={(e) => e.stopPropagation()}
                                      />
                                      חזרות
                                    </span>
                                    {pattern.level_b!.cycle.length > 2 && (
                                      <Button
                                        type="text"
                                        danger
                                        size="small"
                                        icon={<DeleteOutlined />}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          removeCycleWeek(pIndex, wIndex);
                                        }}
                                        style={{ marginRight: 'auto' }}
                                      />
                                    )}
                                  </div>
                                ),
                                children: (
                                  <WeekPanel
                                    workDays={week.work_days}
                                    perDay={week.per_day}
                                    restDay={formData.rest_day}
                                    inputMode={pattern.input_mode || 'time_range'}
                                    onInputModeChange={(mode) => updateWorkPattern(pIndex, 'input_mode', mode)}
                                    onChange={(wd, pd) => updateCycleWeek(pIndex, wIndex, wd, pd)}
                                  />
                                ),
                              }))}
                            />

                            <Button
                              type="dashed"
                              size="small"
                              onClick={() => addCycleWeek(pIndex)}
                              disabled={pattern.level_b.cycle.length >= 52}
                              icon={<PlusOutlined />}
                              style={{ marginTop: 12 }}
                            >
                              הוסף שבוע
                            </Button>
                          </>
                        )}
                      </Card>
                    ))}
                    <Button type="dashed" onClick={addWorkPattern} icon={<PlusOutlined />} block>
                      הוסף דפוס עבודה
                    </Button>
                  </div>
                ),
              },
              {
                key: 'salary',
                label: `מדרגות שכר (${formData.salary_tiers.length})`,
                children: (
                  <div>
                    {formData.salary_tiers.map((tier, index) => (
                      <div key={tier.id} className="dynamic-list-item">
                        <Row gutter={16} align="middle">
                          <Col span={3}>
                            <Form.Item label="סכום">
                              <InputNumber
                                value={parseFloat(tier.amount) || undefined}
                                onChange={(v) => updateSalaryTier(index, 'amount', String(v || 0))}
                                min={0}
                                style={{ width: '100%' }}
                                placeholder="0"
                              />
                            </Form.Item>
                          </Col>
                          <Col span={3}>
                            <Form.Item label="סוג">
                              <Select
                                value={tier.type}
                                onChange={(v) => updateSalaryTier(index, 'type', v)}
                                style={{ width: '100%' }}
                              >
                                <Select.Option value="hourly">שעתי</Select.Option>
                                <Select.Option value="daily">יומי</Select.Option>
                                <Select.Option value="monthly">חודשי</Select.Option>
                                <Select.Option value="per_shift">למשמרת</Select.Option>
                              </Select>
                            </Form.Item>
                          </Col>
                          <Col span={3}>
                            <Form.Item label="נטו/ברוטו">
                              <Select
                                value={tier.net_or_gross}
                                onChange={(v) => updateSalaryTier(index, 'net_or_gross', v)}
                                style={{ width: '100%' }}
                              >
                                <Select.Option value="gross">ברוטו</Select.Option>
                                <Select.Option value="net">נטו</Select.Option>
                              </Select>
                            </Form.Item>
                          </Col>
                          <Col span={5}>
                            <Form.Item label="מתאריך">
                              <DateInput
                                value={tier.start}
                                onChange={(v) => updateSalaryTier(index, 'start', v)}
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={5}>
                            <Form.Item label="עד תאריך">
                              <DateInput
                                value={tier.end}
                                onChange={(v) => updateSalaryTier(index, 'end', v)}
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={3} style={{ display: 'flex', alignItems: 'center', paddingTop: 30, gap: 4 }}>
                            <Popover
                              content={renderSnapContent(
                                tier.id,
                                (indices) => snapSalaryTierToMultiple(index, indices),
                                () => snapSalaryTierToAll(index)
                              )}
                              trigger="click"
                              placement="bottomRight"
                            >
                              <Tooltip title="התאם לתקופות העסקה">
                                <Button
                                  type="default"
                                  size="small"
                                  icon={<LinkOutlined />}
                                />
                              </Tooltip>
                            </Popover>
                          </Col>
                          <Col span={2}>
                            <Button
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={() => removeSalaryTier(index)}
                            />
                          </Col>
                        </Row>
                      </div>
                    ))}
                    <Button type="dashed" onClick={addSalaryTier} icon={<PlusOutlined />} block>
                      הוסף מדרגת שכר
                    </Button>
                  </div>
                ),
              },
              {
                key: 'settings',
                label: 'הגדרות כלליות',
                children: (
                  <>
                    <Row gutter={16}>
                      <Col span={6}>
                        <Form.Item label="יום מנוחה">
                          <Select
                            value={formData.rest_day}
                            onChange={(v: RestDay) => updateField('rest_day', v)}
                            style={{ width: '100%' }}
                          >
                            <Select.Option value="saturday">שבת</Select.Option>
                            <Select.Option value="friday">שישי</Select.Option>
                            <Select.Option value="sunday">ראשון</Select.Option>
                          </Select>
                        </Form.Item>
                      </Col>
                      <Col span={6}>
                        <Form.Item label="מחוז">
                          <Select
                            value={formData.district}
                            onChange={(v: District) => updateField('district', v)}
                            style={{ width: '100%' }}
                          >
                            <Select.Option value="tel_aviv">תל אביב</Select.Option>
                            <Select.Option value="jerusalem">ירושלים</Select.Option>
                            <Select.Option value="haifa">חיפה</Select.Option>
                            <Select.Option value="south">דרום</Select.Option>
                            <Select.Option value="galil">גליל</Select.Option>
                          </Select>
                        </Form.Item>
                      </Col>
                      <Col span={6}>
                        <Form.Item label="ענף">
                          <Select
                            value={formData.industry}
                            onChange={(v) => updateField('industry', v)}
                            style={{ width: '100%' }}
                          >
                            <Select.Option value="general">כללי</Select.Option>
                            <Select.Option value="construction">בנייה</Select.Option>
                            <Select.Option value="cleaning">ניקיון</Select.Option>
                            <Select.Option value="agriculture">חקלאות</Select.Option>
                          </Select>
                        </Form.Item>
                      </Col>
                      <Col span={6}>
                        <Form.Item label="תאריך הגשת תביעה">
                          <DateInput
                            value={formData.filing_date || ''}
                            onChange={(v) => updateField('filing_date', v || undefined)}
                            style={{ width: '100%' }}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={6}>
                        <Form.Item label="סיבת סיום העסקה">
                          <Select
                            value={formData.termination_reason}
                            onChange={(v: TerminationReason) => updateField('termination_reason', v)}
                            style={{ width: '100%' }}
                            placeholder="בחר סיבה"
                            allowClear
                          >
                            <Select.Option value="fired">פוטר</Select.Option>
                            <Select.Option value="resigned_as_fired">התפטר בדין מפוטר</Select.Option>
                            <Select.Option value="resigned">התפטר</Select.Option>
                          </Select>
                        </Form.Item>
                      </Col>
                    </Row>
                  </>
                ),
              },
              {
                key: 'seniority',
                label: 'ותק ענפי',
                children: (
                  <div>
                    <Form.Item label="שיטת חישוב ותק">
                      <Radio.Group
                        value={formData.seniority_input.method}
                        onChange={(e) =>
                          updateField('seniority_input', {
                            ...formData.seniority_input,
                            method: e.target.value as SeniorityMethod,
                          })
                        }
                      >
                        <Space direction="vertical">
                          <Radio value="prior_plus_pattern">
                            ותק קודם + חישוב מדפוס העבודה
                          </Radio>
                          <Radio value="total_plus_pattern">
                            סה״כ ותק ענפי + חישוב מדפוס
                          </Radio>
                          <Radio value="matash_pdf">חילוץ מקובץ מת״ש (בקרוב)</Radio>
                        </Space>
                      </Radio.Group>
                    </Form.Item>

                    {formData.seniority_input.method === 'prior_plus_pattern' && (
                      <Form.Item label="ותק קודם בענף (לפני הנתבע)">
                        <Space>
                          <InputNumber
                            value={
                              priorSeniorityUnit === 'years'
                                ? (formData.seniority_input.prior_months || 0) / 12
                                : formData.seniority_input.prior_months || 0
                            }
                            onChange={(v) => {
                              const value = v || 0;
                              updateField('seniority_input', {
                                ...formData.seniority_input,
                                prior_months: priorSeniorityUnit === 'years' ? value * 12 : value,
                              });
                            }}
                            min={0}
                            max={priorSeniorityUnit === 'years' ? 50 : 600}
                            precision={0}
                            style={{ width: 100 }}
                          />
                          <Select
                            value={priorSeniorityUnit}
                            onChange={(unit: SeniorityUnit) => {
                              const currentMonths = formData.seniority_input.prior_months || 0;
                              setPriorSeniorityUnit(unit);
                              if (unit === 'years') {
                                // Round to nearest year when switching
                                const years = Math.round(currentMonths / 12);
                                updateField('seniority_input', {
                                  ...formData.seniority_input,
                                  prior_months: years * 12,
                                });
                              }
                            }}
                            style={{ width: 100 }}
                          >
                            <Select.Option value="months">חודשים</Select.Option>
                            <Select.Option value="years">שנים</Select.Option>
                          </Select>
                          <span style={{ color: '#88D8E0' }}>
                            = {formatMonthsDisplay(formData.seniority_input.prior_months || 0)}
                          </span>
                        </Space>
                      </Form.Item>
                    )}

                    {formData.seniority_input.method === 'total_plus_pattern' && (
                      <Form.Item label="סה״כ ותק ענפי (כולל כל המעסיקים בענף)">
                        <Space>
                          <InputNumber
                            value={
                              totalSeniorityUnit === 'years'
                                ? (formData.seniority_input.total_industry_months || 0) / 12
                                : formData.seniority_input.total_industry_months || 0
                            }
                            onChange={(v) => {
                              const value = v || 0;
                              updateField('seniority_input', {
                                ...formData.seniority_input,
                                total_industry_months: totalSeniorityUnit === 'years' ? value * 12 : value,
                              });
                            }}
                            min={0}
                            max={totalSeniorityUnit === 'years' ? 50 : 600}
                            precision={0}
                            style={{ width: 100 }}
                          />
                          <Select
                            value={totalSeniorityUnit}
                            onChange={(unit: SeniorityUnit) => {
                              const currentMonths = formData.seniority_input.total_industry_months || 0;
                              setTotalSeniorityUnit(unit);
                              if (unit === 'years') {
                                const years = Math.round(currentMonths / 12);
                                updateField('seniority_input', {
                                  ...formData.seniority_input,
                                  total_industry_months: years * 12,
                                });
                              }
                            }}
                            style={{ width: 100 }}
                          >
                            <Select.Option value="months">חודשים</Select.Option>
                            <Select.Option value="years">שנים</Select.Option>
                          </Select>
                          <span style={{ color: '#88D8E0' }}>
                            = {formatMonthsDisplay(formData.seniority_input.total_industry_months || 0)}
                          </span>
                        </Space>
                      </Form.Item>
                    )}
                  </div>
                ),
              },
              {
                key: 'toggles',
                label: 'זכויות נתבעות',
                children: (
                  <Row gutter={24}>
                    <Col span={8}>
                      <div style={{ marginBottom: 16 }}>
                        <Space>
                          <Switch
                            checked={formData.right_toggles.overtime?.enabled !== false}
                            onChange={(checked) => updateRightToggle('overtime', 'enabled', checked)}
                          />
                          <span style={{ fontWeight: 500 }}>שעות נוספות</span>
                        </Space>
                      </div>
                    </Col>
                    <Col span={8}>
                      <div style={{ marginBottom: 16 }}>
                        <Space>
                          <Switch
                            checked={formData.right_toggles.holidays?.enabled !== false}
                            onChange={(checked) => updateRightToggle('holidays', 'enabled', checked)}
                          />
                          <span style={{ fontWeight: 500 }}>חגים</span>
                        </Space>
                      </div>
                    </Col>
                    <Col span={8}>
                      <div style={{ marginBottom: 16 }}>
                        <Space>
                          <Switch
                            checked={formData.right_toggles.severance?.enabled !== false}
                            onChange={(checked) => updateRightToggle('severance', 'enabled', checked)}
                          />
                          <span style={{ fontWeight: 500 }}>פיצויי פיטורין</span>
                        </Space>
                      </div>
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'deductions',
                label: 'ניכויי מעסיק',
                children: (
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="ניכוי משעות נוספות">
                        <InputNumber
                          value={parseFloat(formData.deductions_input.overtime) || undefined}
                          onChange={(v) => updateDeduction('overtime', String(v || 0))}
                          min={0}
                          style={{ width: '100%' }}
                          placeholder="סכום בש״ח"
                          addonAfter="₪"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="ניכוי מדמי חגים">
                        <InputNumber
                          value={parseFloat(formData.deductions_input.holidays) || undefined}
                          onChange={(v) => updateDeduction('holidays', String(v || 0))}
                          min={0}
                          style={{ width: '100%' }}
                          placeholder="סכום בש״ח"
                          addonAfter="₪"
                        />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="הפרשות בפועל לפיצויים">
                        <InputNumber
                          value={parseFloat(formData.deductions_input.severance) || undefined}
                          onChange={(v) => updateDeduction('severance', String(v || 0))}
                          min={0}
                          style={{ width: '100%' }}
                          placeholder="סכום בש״ח"
                          addonAfter="₪"
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                ),
              },
            ]}
          />

                  {/* Calculate button */}
                  <div style={{ marginTop: 24, textAlign: 'center' }}>
                    <Button
                      type="primary"
                      size="large"
                      icon={<CalculatorOutlined />}
                      onClick={handleCalculate}
                      loading={loading}
                      style={{ minWidth: 200, height: 48, fontSize: 18 }}
                    >
                      חשב
                    </Button>
                  </div>
                </Form>
              ),
            },
            {
              key: 'json',
              label: (
                <span>
                  <CodeOutlined /> הזנת JSON (דיבאג)
                </span>
              ),
              children: (
                <div>
                  <div style={{ direction: 'ltr', textAlign: 'left' }}>
                    <Input.TextArea
                      value={jsonInput}
                      onChange={(e) => setJsonInput(e.target.value)}
                      rows={22}
                      style={{ fontFamily: 'monospace', fontSize: 13 }}
                      placeholder='הדבק כאן SSOT input בפורמט JSON...'
                    />
                  </div>
                  {jsonError && (
                    <div style={{ color: '#ff6b6b', marginTop: 8 }}>{jsonError}</div>
                  )}
                  <div style={{ marginTop: 16, display: 'flex', gap: 12, justifyContent: 'center' }}>
                    <Button type="primary" onClick={handleJsonCalculate} loading={loading}>
                      חשב מ-JSON
                    </Button>
                    <Dropdown
                      menu={{
                        items: [
                          { key: 'main', label: '8 שנים, דפוס משתנה, התיישנות' },
                          { key: 'rest_window', label: 'חלון מנוחה — שישי חוצה שבת' },
                        ],
                        onClick: ({ key }) => loadExample(key as 'main' | 'rest_window'),
                      }}
                    >
                      <Button>טען דוגמה ▾</Button>
                    </Dropdown>
                    <Button onClick={saveJsonToFile} disabled={!jsonInput}>
                      שמור input לקובץ
                    </Button>
                  </div>
                </div>
              ),
            },
          ]}
        />

        {/* Error display */}
        {error && (
          <div className="error-container" style={{ marginTop: 24 }}>
            <div className="error-title">שגיאה בחישוב</div>
            <div className="error-message" style={{ whiteSpace: 'pre-wrap' }}>{error}</div>
          </div>
        )}

        {/* Results display */}
        {result && <ResultsView ssot={result} />}
      </div>
    </ConfigProvider>
  );
}

export default App;
