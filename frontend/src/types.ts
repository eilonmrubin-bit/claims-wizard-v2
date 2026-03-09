/**
 * TypeScript types for Claims Wizard frontend.
 * Maps to backend SSOT structures.
 */

export interface CaseMetadata {
  case_name: string;
  notes: string;
}

export interface PersonalDetails {
  id_number?: string;
  first_name?: string;
  last_name?: string;
  birth_year: number;
}

export interface DefendantDetails {
  name?: string;
  id_number?: string;
  address?: string;
  notes?: string;
}

export interface TimeRange {
  start_time: string; // HH:MM:SS
  end_time: string;
}

// Pattern types for Level A/B/C patterns
export type PatternType = 'weekly_simple' | 'cyclic' | 'statistical';
export type DayType = 'regular' | 'eve_of_rest' | 'rest_day' | 'night';
export type CountPeriod = 'weekly' | 'monthly';
export type NightPlacement = 'employer_favor' | 'employee_favor' | 'average';
export type ShiftInputMode = 'time_range' | 'duration';
export type ShiftType = 'day' | 'night';

// Level C (Statistical) input structures
export interface DayTypeInput {
  type_id: DayType;
  count: number;           // average days per week/month
  count_period: CountPeriod;
  hours: number;           // gross hours including break (duration mode)
  break_minutes: number;   // 0-180, integer
  shift_start?: string;    // HH:mm:ss — for time_range mode
  shift_end?: string;      // HH:mm:ss — for time_range mode
}

export interface PatternLevelC {
  day_types: DayTypeInput[];
  night_placement: NightPlacement;
  input_mode?: ShiftInputMode;  // 'time_range' | 'duration' — default 'duration'
}

// Shift entry with per-shift break
export interface ShiftEntry {
  start_time: string;
  end_time: string;
  break_minutes: number;        // 0 = no break
  // Duration mode fields (optional)
  shift_type?: ShiftType;       // 'day' | 'night'
  duration_hours?: number;      // gross hours
  anchor?: 'starts_here' | 'ends_here';  // for overnight shifts — default 'starts_here'
}

// Level A per-day structure
export interface PerDayShifts {
  shifts: ShiftEntry[];
}

// Level B (Cyclic) structures
export interface WeekPattern {
  work_days: number[];
  per_day: Record<number, PerDayShifts>;
  repeats?: number;  // default 1, min 1 — number of times this week appears in cycle
}

export interface PatternLevelB {
  cycle: WeekPattern[];
  cycle_length: number;
}

// Pattern source for backend
export interface PatternSource {
  id: string;
  type: PatternType;
  start: string;
  end: string;
  level_c_data?: PatternLevelC;
  level_b_data?: PatternLevelB;
}

export interface EmploymentPeriod {
  id: string;
  start: string; // YYYY-MM-DD
  end: string;
}

export interface WorkPattern {
  id: string;
  start: string;
  end: string;
  pattern_type?: PatternType;     // default 'weekly_simple'
  work_days: number[];            // 0=Sunday..6=Saturday
  default_shifts: TimeRange[];
  default_breaks: TimeRange[];
  // Level A enhanced - per-day overrides
  input_mode?: ShiftInputMode;    // 'time_range' or 'duration'
  per_day?: Record<number, PerDayShifts>;
  // Level B - cyclic patterns
  level_b?: PatternLevelB;
  // Level C - statistical patterns
  level_c?: PatternLevelC;
}

export interface SalaryTier {
  id: string;
  start: string;
  end: string;
  amount: string;
  type: 'hourly' | 'daily' | 'monthly' | 'per_shift';
  net_or_gross: 'net' | 'gross';
}

export type SeniorityMethod = 'prior_plus_pattern' | 'total_plus_pattern' | 'matash_pdf';

export interface SeniorityInput {
  method: SeniorityMethod;
  prior_months?: number;              // Method א - prior seniority before defendant
  total_industry_months?: number;     // Method ב - total industry seniority
}

export type RestDay = 'saturday' | 'friday' | 'sunday';

export type District = 'jerusalem' | 'tel_aviv' | 'haifa' | 'south' | 'galil';

export type TerminationReason = 'fired' | 'resigned_as_fired' | 'resigned';

export type SeniorityType = 'industry' | 'employer';

export interface TrainingFundTier {
  seniority_type: SeniorityType;  // industry = ותק ענפי, employer = ותק אצל מעסיק
  from_months: number;     // Starting seniority in months
  to_months: number | null;  // Ending seniority in months, null = infinity
  employer_rate: string;   // Decimal as string, e.g. "0.075"
}

// Travel allowance types
export type LodgingPattern = 'full_lodging' | 'daily_return';

export interface LodgingWeek {
  week_in_cycle: number;  // 1-based index within the cycle
  pattern: LodgingPattern;
}

export interface LodgingInput {
  has_lodging: boolean;
  cycle_weeks: number;  // 1, 2, 3, or 4
  cycle: LodgingWeek[];
}

export interface SSOTInput {
  case_metadata: CaseMetadata;
  personal_details: PersonalDetails;
  defendant_details: DefendantDetails;
  employment_periods: EmploymentPeriod[];
  work_patterns: WorkPattern[];
  salary_tiers: SalaryTier[];
  rest_day: RestDay;
  district: District;
  industry: string;
  filing_date?: string;
  termination_reason?: TerminationReason;
  seniority_input: SeniorityInput;
  right_toggles: Record<string, Record<string, boolean>>;
  deductions_input: Record<string, string>;
  right_specific_inputs: Record<string, Record<string, unknown>>;
  pattern_sources?: PatternSource[];
  training_fund_tiers?: TrainingFundTier[];
  // Travel allowance (construction only)
  travel_distance_km?: number | null;
  lodging_input?: LodgingInput | null;
}

export interface ApiError {
  phase: string;
  module: string;
  errors: Array<{
    type: string;
    message: string;
    details: Record<string, unknown>;
  }>;
}

export interface CalculateResponse {
  success: boolean;
  ssot?: Record<string, unknown>;
  errors?: ApiError;
}
