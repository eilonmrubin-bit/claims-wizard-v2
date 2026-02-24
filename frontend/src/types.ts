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

export interface EmploymentPeriod {
  id: string;
  start: string; // YYYY-MM-DD
  end: string;
}

export interface WorkPattern {
  id: string;
  start: string;
  end: string;
  work_days: number[]; // 0=Sunday..6=Saturday
  default_shifts: TimeRange[];
  default_breaks: TimeRange[];
}

export interface SalaryTier {
  id: string;
  start: string;
  end: string;
  amount: string;
  type: 'hourly' | 'daily' | 'monthly' | 'per_shift';
  net_or_gross: 'net' | 'gross';
}

export type SeniorityMethod = 'prior_plus_pattern' | 'manual' | 'matash_pdf';

export interface SeniorityInput {
  method: SeniorityMethod;
  prior_months?: number;
  manual_industry_months?: number;
  manual_defendant_months?: number;
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
