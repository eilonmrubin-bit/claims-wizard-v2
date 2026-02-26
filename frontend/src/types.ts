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

// Level A per-day structure
export interface PerDayShifts {
  shifts: TimeRange[];
  break_minutes: number;
  // For duration mode
  shift_type?: ShiftType;
  duration_hours?: number;
}

// Level B (Cyclic) structures
export interface WeekPattern {
  work_days: number[];
  per_day: Record<number, PerDayShifts>;
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
  seniority_input: SeniorityInput;
  right_toggles: Record<string, Record<string, boolean>>;
  deductions_input: Record<string, string>;
  right_specific_inputs: Record<string, Record<string, unknown>>;
  pattern_sources?: PatternSource[];
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
