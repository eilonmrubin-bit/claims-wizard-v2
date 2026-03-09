/**
 * ResultsView - תצוגת תוצאות אשף התביעות
 *
 * מציג את תוצאות החישוב בצורה מעוצבת ומאורגנת.
 */

import { useState } from 'react';
import {
  Card,
  Table,
  Collapse,
  Statistic,
  Tag,
  Progress,
  Row,
  Col,
  Tooltip,
  Typography,
  Space,
  Alert,
  Button,
  Descriptions,
  Modal,
  Divider,
} from 'antd';
import {
  ClockCircleOutlined,
  GiftOutlined,
  StopOutlined,
  CalendarOutlined,
  UserOutlined,
  BankOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  DollarOutlined,
  PercentageOutlined,
  DownloadOutlined,
  SafetyOutlined,
  CarOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;

// Types for SSOT data
interface ClaimSummaryRight {
  right_id: string;
  name: string;
  full_amount: number;
  after_limitation: number;
  after_deductions: number;
  deduction_amount: number;
  show: boolean;
  limitation_type: string;
  limitation_excluded: number;
}

interface EmploymentSummary {
  worker_name?: string;
  defendant_name?: string;
  total_duration_display: string;
  worked_duration_display: string;
  filing_date?: string;
  filing_date_display: string;
}

interface ClaimSummary {
  total_before_limitation: number;
  total_after_limitation: number;
  total_after_deductions: number;
  per_right: ClaimSummaryRight[];
  employment_summary: EmploymentSummary;
}

interface OvertimeMonthlyBreakdown {
  month: [number, number];
  claim_amount: number;
  regular_hours: number;
  ot_hours: number;
  shifts_count: number;
}

interface OvertimeResult {
  total_claim: number;
  monthly_breakdown: OvertimeMonthlyBreakdown[];
}

// Shift pricing breakdown item
interface PricingBreakdownItem {
  hours: number;
  tier: 0 | 1 | 2;
  in_rest: boolean;
  rate_multiplier: number;
  claim_multiplier: number;
  hourly_wage: number;
  claim_amount: number;
}

// Full shift data from SSOT
interface ShiftData {
  id: string;
  date: string;
  assigned_day: string;
  shift_index: number;
  effective_period_id: string;
  week_id: string;
  assigned_week: string;
  start: string;
  end: string;
  net_hours: number;
  threshold: number;
  threshold_reason: string;
  regular_hours: number;
  ot_tier1_hours: number;
  ot_tier2_hours: number;
  daily_ot_hours: number;
  weekly_ot_hours: number;
  rest_window_regular_hours: number;
  rest_window_ot_tier1_hours: number;
  rest_window_ot_tier2_hours: number;
  non_rest_regular_hours: number;
  non_rest_ot_tier1_hours: number;
  non_rest_ot_tier2_hours: number;
  claim_amount?: number;
  pricing_breakdown?: PricingBreakdownItem[];
}

// Week data from SSOT
interface WeekData {
  id: string;
  year: number;
  week_number: number;
  start_date: string;
  end_date: string;
  distinct_work_days: number;
  week_type: 5 | 6;
  total_regular_hours: number;
  weekly_ot_hours: number;
  weekly_threshold: number;
  rest_window_start?: string;
  rest_window_end?: string;
  rest_window_work_hours: number;
  is_partial: boolean;
  partial_reason?: string;
  partial_detail?: string;
}

interface HolidayEntry {
  name: string;
  hebrew_date: string;
  gregorian_date: string;
  employed_on_date: boolean;
  before_seniority?: boolean;
  day_of_week: string;
  week_type?: number;
  is_rest_day: boolean;
  is_eve_of_rest: boolean;
  excluded: boolean;
  exclude_reason?: string;
  entitled: boolean;
  day_value?: number;
  claim_amount?: number;
}

interface HolidayYearResult {
  year: number;
  holidays: HolidayEntry[];
  election_day_entitled: boolean;
  election_day_value?: number;
  total_entitled_days: number;
  total_claim: number;
}

interface HolidaysResult {
  seniority_eligibility_date?: string;
  per_year: HolidayYearResult[];
  grand_total_days: number;
  grand_total_claim: number;
}

interface SeverancePeriodSummary {
  effective_period_id: string;
  start: string;
  end: string;
  months_count: number;
  avg_job_scope: number;
  avg_salary_monthly: number | null;
  subtotal: number;
}

interface SeveranceMonthlyDetail {
  month: [number, number];
  effective_period_id: string;
  calendar_days_employed: number;
  total_calendar_days: number;
  partial_fraction: number;
  job_scope: number;
  salary_used: number;
  amount: number;
}

interface SeveranceSectionData {
  base_total: number;
  ot_total: number;
  recreation_total: number;
  recreation_pending: boolean;
  grand_total: number;
  base_monthly_detail: SeveranceMonthlyDetail[];
  period_summaries: SeverancePeriodSummary[];
}

interface Section14Comparison {
  actual_deposits: number;
  required_contributions_total: number;
  difference: number;
  status: string; // "holds" | "falls"
}

interface OtAdditionMonthlyDetail {
  month: [number, number];
  effective_period_id: string;
  full_ot_monthly_pay: number;
  job_scope: number;
  amount: number;
}

interface OtAdditionData {
  rate: number;
  total: number;
  monthly_detail: OtAdditionMonthlyDetail[];
}

interface RecreationAdditionMonthlyDetail {
  month: [number, number];
  annual_recreation_value: number;
  monthly_value: number;
  partial_fraction: number;
  amount: number;
}

interface RecreationAdditionData {
  rate: number;
  total: number;
  recreation_pending: boolean;
  monthly_detail: RecreationAdditionMonthlyDetail[];
}

interface SeveranceResult {
  eligible: boolean;
  ineligible_reason: string | null;
  termination_reason: string;
  industry: string;
  path: string; // "contributions" | "section_14_holds" | "section_14_falls"
  section_14_status: string | null;
  limitation_type: string;
  severance_rate: number;
  contribution_rate: number;
  last_salary_info: {
    last_salary: number;
    method: string;
    salary_changed_in_last_year: boolean;
  };
  full_severance: SeveranceSectionData;
  required_contributions: SeveranceSectionData;
  ot_addition: OtAdditionData | null;
  recreation_addition: RecreationAdditionData | null;
  section_14_comparison: Section14Comparison | null;
  claim_before_deductions: number;
  deduction_override: number | null;
  total_claim: number;
}

interface RecreationDayValueSegment {
  segment_start: string;
  segment_end: string;
  day_value: number;
  day_value_effective_date: string;
  weight: number;
  segment_value: number;
}

interface RecreationYearData {
  year_number: number;
  year_start: string;
  year_end: string;
  is_partial: boolean;
  partial_fraction: number | null;
  seniority_years: number;
  base_days: number;
  avg_scope: number;
  entitled_days: number;
  segments: RecreationDayValueSegment[];
  entitled_value: number;
}

interface RecreationResult {
  entitled: boolean;
  not_entitled_reason: string | null;
  industry: string;
  industry_fallback_used: boolean;
  years: RecreationYearData[];
  grand_total_days: number;
  grand_total_value: number;
}

interface VacationWeekTypeSegment {
  segment_start: string;
  segment_end: string;
  week_type: string;  // "five_day" | "six_day"
  weeks_count: number;
  weight: number;
  base_days: number;
  weighted_days: number;
}

interface VacationYearData {
  year: number;
  year_start: string;
  year_end: string;
  is_partial: boolean;
  partial_fraction: number | null;
  partial_description: string;
  seniority_years: number;
  age_at_year_start: number | null;
  age_55_split: boolean;
  is_55_plus?: boolean;
  week_type_segments: VacationWeekTypeSegment[];
  weighted_base_days: number;
  entitled_days: number;
  avg_daily_salary: number;
  year_value: number;
  claimable_fraction?: number | null;  // 1.0=full, 0.0=excluded, 0<x<1=partial (split by limitation)
}

interface VacationResult {
  entitled: boolean;
  industry: string;
  seniority_basis: string;  // "employer" | "industry"
  years: VacationYearData[];
  grand_total_days: number;
  grand_total_value: number;
}

interface PensionMonthData {
  month: [number, number];
  month_start: string;
  salary_monthly: number;
  job_scope: number;
  pension_rate: number;
  month_value: number;
}

interface PensionResult {
  entitled: boolean;
  industry: string;
  months: PensionMonthData[];
  grand_total_value: number;
}

// Training Fund types
interface TrainingFundSegment {
  days: number;
  days_total: number;
  employer_rate: number;
  employee_rate: number;
  eligible: boolean;
  tier_source: 'industry' | 'custom';
  segment_required: number;
}

interface TrainingFundMonthDetail {
  month: [number, number];
  effective_period_id: string;
  salary_base: number;
  recreation_component: number;
  total_regular_hours: number;        // from PMR
  month_total_regular_hours: number;  // from MonthAggregate
  hours_weight: number;               // = total / month_total
  eligible_this_month: boolean;
  seniority_years: number | null;
  is_split_month: boolean;
  month_required: number;
  segments: TrainingFundSegment[];
}

interface TrainingFundMonthlyBreakdown {
  month: [number, number];
  claim_amount: number;
}

interface TrainingFundResult {
  eligible: boolean;
  ineligible_reason: string | null;
  industry: string;
  is_construction_foreman: boolean;
  used_custom_tiers: boolean;
  recreation_pending: boolean;
  monthly_detail: TrainingFundMonthDetail[];
  required_total: number;
  actual_deposits: number;
  claim_before_deductions: number;
  monthly_breakdown: TrainingFundMonthlyBreakdown[];
}

interface TravelWeekDetail {
  week_start: string;
  week_end: string;
  effective_period_id: string;
  work_days: number;
  cycle_position: number | null;
  week_pattern: string;  // "full_lodging" | "daily_return" | "no_lodging"
  travel_days: number;
  daily_rate: number;
  week_travel_value: number;
}

interface TravelMonthlyBreakdown {
  month: [number, number];
  travel_days: number;
  claim_amount: number;
}

interface TravelResult {
  industry: string;
  daily_rate: number;
  distance_km: number | null;
  distance_tier: string | null;  // "standard" | "far" | null
  has_lodging: boolean;
  lodging_periods_count: number;
  weekly_detail: TravelWeekDetail[];
  monthly_breakdown: TravelMonthlyBreakdown[];
  grand_total_travel_days: number;
  grand_total_value: number;
  claim_before_deductions: number;
}

// Meal Allowance (אש"ל) types
interface MealAllowanceMonthlyBreakdown {
  month: [number, number];
  nights: number;
  nightly_rate: number;
  claim_amount: number;
}

interface MealAllowanceResult {
  entitled: boolean;
  not_entitled_reason: string | null;  // "not_construction" | "no_lodging_input" | "disabled"
  industry: string;
  monthly_breakdown: MealAllowanceMonthlyBreakdown[];
  grand_total_nights: number;
  grand_total_value: number;
  claim_before_deductions: number;
}

interface FreezePeriodApplied {
  name: string;
  start_date: string;
  end_date: string;
  days: number;
}

interface LimitationWindow {
  type_id: string;
  type_name: string;
  base_window_start: string;
  effective_window_start: string;
  freeze_periods_applied: FreezePeriodApplied[];
}

interface TimelineSummary {
  total_employment_days: number;
  claimable_days_general: number;
  excluded_days_general: number;
  claimable_days_vacation?: number;
  excluded_days_vacation?: number;
  total_freeze_days: number;
}

interface LimitationRightResult {
  limitation_type_id?: string;
  full_amount?: number;
  claimable_amount?: number;
  excluded_amount?: number;
  claimable_duration?: { display: string; days?: number; years_whole?: number; months_remainder?: number };
  excluded_duration?: { display: string; days?: number; years_whole?: number; months_remainder?: number } | null;
}

interface LimitationResults {
  windows: LimitationWindow[];
  timeline_data: {
    filing_date?: string;
    summary: TimelineSummary;
  };
  per_right?: Record<string, LimitationRightResult>;
}

interface TotalEmployment {
  first_day?: string;
  last_day?: string;
  total_duration: { display: string };
  worked_duration: { display: string };
  gap_duration: { display: string };
  periods_count: number;
  gaps_count: number;
}

interface SeniorityTotals {
  at_defendant_months: number;
  at_defendant_years: number;
  total_industry_months: number;
  total_industry_years: number;
  prior_seniority_months: number;
}

interface DeductionResult {
  show_deduction: boolean;
}

interface EffectivePeriodData {
  id: string;
  start: string;
  end: string;
  salary_amount: number;
  salary_type: string;
  salary_net_or_gross: string;
}

interface PeriodMonthRecord {
  effective_period_id: string;
  month: [number, number];
  work_days_count: number;
  shifts_count: number;
  avg_regular_hours_per_day: number;
  avg_regular_hours_per_shift: number;
  salary_input_amount: number;
  salary_input_type: string;
  salary_input_net_or_gross: string;
  salary_gross_amount: number;
  minimum_wage_value: number;
  minimum_wage_type: string;
  minimum_applied: boolean;
  minimum_gap: number;
  effective_amount: number;
  salary_hourly: number;
  salary_daily: number;
  salary_monthly: number;
}

interface MonthAggregate {
  month: [number, number];
  total_regular_hours: number;
  total_ot_hours: number;
  total_work_days: number;
  total_shifts: number;
  full_time_hours_base: number;
  raw_scope: number;
  job_scope: number;
}

interface ResultsViewProps {
  ssot: {
    claim_summary?: ClaimSummary;
    rights_results?: {
      overtime?: OvertimeResult;
      holidays?: HolidaysResult;
      severance?: SeveranceResult;
      recreation?: RecreationResult;
      vacation?: VacationResult;
      pension?: PensionResult;
      training_fund?: TrainingFundResult;
      travel?: TravelResult;
      meal_allowance?: MealAllowanceResult;
    };
    limitation_results?: LimitationResults;
    total_employment?: TotalEmployment;
    seniority_totals?: SeniorityTotals;
    deduction_results?: Record<string, DeductionResult>;
    shifts?: ShiftData[];
    weeks?: WeekData[];
    effective_periods?: EffectivePeriodData[];
    period_month_records?: PeriodMonthRecord[];
    month_aggregates?: MonthAggregate[];
  };
}

// Helper: format currency
const formatCurrency = (amount: number | undefined): string => {
  if (amount === undefined || amount === null) return '₪0';
  return `₪${amount.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

// Helper: format date
const formatDate = (dateStr: string | undefined): string => {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  return `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1).toString().padStart(2, '0')}.${d.getFullYear()}`;
};

// Helper: format month
const formatMonth = (month: [number, number]): string => {
  const monthNames = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'];
  return `${monthNames[month[1] - 1]} ${month[0]}`;
};

// Helper: translate day of week
const translateDayOfWeek = (day: string): string => {
  const days: Record<string, string> = {
    Sunday: 'ראשון',
    Monday: 'שני',
    Tuesday: 'שלישי',
    Wednesday: 'רביעי',
    Thursday: 'חמישי',
    Friday: 'שישי',
    Saturday: 'שבת',
  };
  return days[day] || day;
};

// Helper: translate salary type
const translateSalaryType = (type: string): string => {
  const map: Record<string, string> = {
    hourly: 'שעתי',
    daily: 'יומי',
    monthly: 'חודשי',
    per_shift: 'למשמרת',
  };
  return map[type] || type;
};

// Helper: translate net/gross
const translateNetGross = (ng: string): string => (ng === 'net' ? 'נטו' : 'ברוטו');

// ============================================================================
// א. SummaryCard - כרטיס סיכום ראשי
// ============================================================================

const SummaryCard: React.FC<{ summary: ClaimSummary }> = ({ summary }) => {
  const { employment_summary } = summary;

  return (
    <Card
      title={
        <Space>
          <BankOutlined />
          <span>סיכום תביעה</span>
        </Space>
      }
      className="results-card summary-card"
    >
      {/* Employment info */}
      <Row gutter={[16, 8]} style={{ marginBottom: 24 }}>
        {employment_summary.worker_name && (
          <Col span={6}>
            <Text type="secondary">שם עובד:</Text>
            <div><Text strong>{employment_summary.worker_name}</Text></div>
          </Col>
        )}
        {employment_summary.defendant_name && (
          <Col span={6}>
            <Text type="secondary">שם נתבע:</Text>
            <div><Text strong>{employment_summary.defendant_name}</Text></div>
          </Col>
        )}
        {employment_summary.total_duration_display && (
          <Col span={6}>
            <Text type="secondary">משך העסקה:</Text>
            <div><Text strong>{employment_summary.total_duration_display}</Text></div>
          </Col>
        )}
        {employment_summary.filing_date_display && (
          <Col span={6}>
            <Text type="secondary">תאריך הגשה:</Text>
            <div><Text strong>{employment_summary.filing_date_display}</Text></div>
          </Col>
        )}
      </Row>

      {/* Totals */}
      <Row gutter={[24, 16]}>
        <Col span={8}>
          <Statistic
            title="סה״כ לפני התיישנות"
            value={summary.total_before_limitation}
            precision={2}
            prefix="₪"
            valueStyle={{ color: '#88D8E0' }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="סה״כ אחרי התיישנות"
            value={summary.total_after_limitation}
            precision={2}
            prefix="₪"
            valueStyle={{ color: '#E8F4F8' }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="סה״כ לתביעה"
            value={summary.total_after_deductions}
            precision={2}
            prefix="₪"
            valueStyle={{ color: '#4ECDC4', fontSize: '2em', fontWeight: 'bold' }}
          />
        </Col>
      </Row>
    </Card>
  );
};

// ============================================================================
// ב. RightsTable - טבלת פירוט זכויות
// ============================================================================

// Translation map for right names (English IDs to Hebrew)
const rightNameTranslations: Record<string, string> = {
  'training_fund': 'קרן השתלמות',
  'pension': 'פנסיה',
  'vacation': 'חופשה שנתית',
  'recreation': 'דמי הבראה',
  'holidays': 'דמי חגים',
  'overtime': 'שעות נוספות',
  'severance': 'פיצויי פיטורים',
  'prior_notice': 'דמי הודעה מוקדמת',
  'convalescence': 'דמי הבראה',
};

const translateRightName = (name: string): string => {
  return rightNameTranslations[name] || name;
};

const RightsTable: React.FC<{
  rights: ClaimSummaryRight[];
  deductionResults?: Record<string, DeductionResult>;
}> = ({ rights, deductionResults }) => {
  const columns = [
    {
      title: <span style={{ color: '#88D8E0' }}>זכות</span>,
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <span style={{ color: '#E8F4F8' }}>{translateRightName(v)}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>סכום מלא</span>,
      dataIndex: 'full_amount',
      key: 'full_amount',
      render: (v: number) => <span className="ltr-number" style={{ color: '#E8F4F8' }}>{formatCurrency(v)}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>התיישנות</span>,
      dataIndex: 'limitation_excluded',
      key: 'limitation_excluded',
      render: (v: number) => (
        <span className="ltr-number" style={{ color: v > 0 ? '#ff6b6b' : '#E8F4F8' }}>
          {v > 0 ? `-${formatCurrency(v)}` : '-'}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>אחרי התיישנות</span>,
      dataIndex: 'after_limitation',
      key: 'after_limitation',
      render: (v: number) => <span className="ltr-number" style={{ color: '#E8F4F8' }}>{formatCurrency(v)}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>ניכוי מעסיק</span>,
      dataIndex: 'deduction_amount',
      key: 'deduction_amount',
      render: (v: number, record: ClaimSummaryRight) => {
        const showDeduction = deductionResults?.[record.right_id]?.show_deduction;
        if (!showDeduction || v === 0) return <span style={{ color: '#E8F4F8' }}>-</span>;
        return <span className="ltr-number" style={{ color: '#ff6b6b' }}>-{formatCurrency(v)}</span>;
      },
    },
    {
      title: <span style={{ color: '#88D8E0' }}>לתביעה</span>,
      dataIndex: 'after_deductions',
      key: 'after_deductions',
      render: (v: number) => (
        <span className="ltr-number" style={{ fontWeight: 'bold', color: '#4ECDC4' }}>
          {formatCurrency(v)}
        </span>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <CalendarOutlined />
          <span>פירוט זכויות</span>
        </Space>
      }
      className="results-card"
    >
      <Table
        dataSource={rights}
        columns={columns}
        rowKey="right_id"
        pagination={false}
        size="small"
        rowClassName={(record) => (!record.show ? 'dimmed-row' : '')}
      />
    </Card>
  );
};

// ============================================================================
// ג. SalaryBreakdown - פירוט שכר (מאוחד)
// ============================================================================

// Helper: short month name
const shortMonthName = (month: number): string => {
  const names = ['', 'ינו', 'פבר', 'מרץ', 'אפר', 'מאי', 'יוני', 'יולי', 'אוג', 'ספט', 'אוק', 'נוב', 'דצמ'];
  return names[month] || '';
};

// Helper: format period range
const formatPeriodRange = (first: [number, number], last: [number, number], count: number): string => {
  const f = `${shortMonthName(first[1])} ${first[0]}`;
  if (first[0] === last[0] && first[1] === last[1]) return f;
  const l = `${shortMonthName(last[1])} ${last[0]}`;
  return `${f} — ${l} (${count} ח׳)`;
};

// Consolidated salary row
interface SalaryPeriodRow {
  periodId: string;
  firstMonth: [number, number];
  lastMonth: [number, number];
  monthCount: number;
  salaryInputAmount: number;
  salaryInputType: string;
  salaryNetOrGross: string;
  salaryGrossAmount: number;
  minimumWageValue: number;
  minimumApplied: boolean;
  minimumGap: number;
  effectiveAmount: number;
  salaryHourly: number;
  salaryDaily: number;
  salaryMonthly: number;
}

// Consolidate records - merge months with identical salary data
const consolidateRecords = (records: PeriodMonthRecord[]): SalaryPeriodRow[] => {
  if (records.length === 0) return [];

  // Sort records by month
  const sorted = [...records].sort((a, b) => {
    if (a.month[0] !== b.month[0]) return a.month[0] - b.month[0];
    return a.month[1] - b.month[1];
  });

  const rows: SalaryPeriodRow[] = [];
  let current: SalaryPeriodRow | null = null;

  for (const rec of sorted) {
    const shouldSplit = !current
      || rec.effective_period_id !== current.periodId
      || rec.salary_input_amount !== current.salaryInputAmount
      || rec.minimum_applied !== current.minimumApplied
      || (rec.minimum_applied && rec.minimum_wage_value !== current.minimumWageValue)
      || rec.effective_amount !== current.effectiveAmount;

    if (shouldSplit) {
      if (current) rows.push(current);
      current = {
        periodId: rec.effective_period_id,
        firstMonth: rec.month as [number, number],
        lastMonth: rec.month as [number, number],
        monthCount: 1,
        salaryInputAmount: rec.salary_input_amount,
        salaryInputType: rec.salary_input_type,
        salaryNetOrGross: rec.salary_input_net_or_gross,
        salaryGrossAmount: rec.salary_gross_amount,
        minimumWageValue: rec.minimum_wage_value,
        minimumApplied: rec.minimum_applied,
        minimumGap: rec.minimum_gap,
        effectiveAmount: rec.effective_amount,
        salaryHourly: rec.salary_hourly,
        salaryDaily: rec.salary_daily,
        salaryMonthly: rec.salary_monthly,
      };
    } else {
      current!.lastMonth = rec.month as [number, number];
      current!.monthCount++;
    }
  }
  if (current) rows.push(current);
  return rows;
};

const SalaryBreakdown: React.FC<{
  effectivePeriods?: EffectivePeriodData[];
  periodMonthRecords?: PeriodMonthRecord[];
}> = ({ effectivePeriods: _effectivePeriods = [], periodMonthRecords = [] }) => {
  if (!periodMonthRecords.length) {
    return null;
  }

  // Consolidate all records across all periods
  const consolidatedRows = consolidateRecords(periodMonthRecords);
  const hasAnyMinimumApplied = consolidatedRows.some((r) => r.minimumApplied);

  // Single row - simple card display
  if (consolidatedRows.length === 1) {
    const row = consolidatedRows[0];
    return (
      <Card
        title={
          <Space>
            <DollarOutlined />
            <span>פירוט שכר</span>
          </Space>
        }
        className="results-card"
      >
        <div style={{ padding: '8px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <Text strong style={{ fontSize: '1.1em', color: '#E8F4F8' }}>
              {formatPeriodRange(row.firstMonth, row.lastMonth, row.monthCount)}
            </Text>
          </div>
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary">קלט: </Text>
            <span className="ltr-number" style={{ color: '#E8F4F8' }}>
              {formatCurrency(row.salaryInputAmount)} {translateSalaryType(row.salaryInputType)} {translateNetGross(row.salaryNetOrGross)}
            </span>
          </div>
          {row.minimumApplied && (
            <Alert
              message={`השכר הושלם לשכר מינימום (${formatCurrency(row.minimumWageValue)})`}
              type="warning"
              showIcon
              icon={<WarningOutlined />}
              style={{
                marginBottom: 12,
                background: 'rgba(255, 107, 107, 0.08)',
                borderColor: 'rgba(255, 107, 107, 0.3)',
              }}
            />
          )}
          <div>
            <Text type="secondary">שכר: </Text>
            <span style={{ color: '#4ECDC4' }}>
              שעתי <span className="ltr-number">{formatCurrency(row.salaryHourly)}</span>
            </span>
            <span style={{ margin: '0 8px', color: '#88D8E0' }}>|</span>
            <span style={{ color: '#E8F4F8' }}>
              יומי <span className="ltr-number">{formatCurrency(row.salaryDaily)}</span>
            </span>
            <span style={{ margin: '0 8px', color: '#88D8E0' }}>|</span>
            <span style={{ color: '#E8F4F8' }}>
              חודשי <span className="ltr-number">{formatCurrency(row.salaryMonthly)}</span>
            </span>
          </div>
        </div>
      </Card>
    );
  }

  // Multiple rows - table display
  const columns = [
    {
      title: <span style={{ color: '#88D8E0' }}>תקופה</span>,
      key: 'period',
      render: (_: unknown, record: SalaryPeriodRow) => (
        <span style={{ color: '#E8F4F8' }}>
          {formatPeriodRange(record.firstMonth, record.lastMonth, record.monthCount)}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>קלט</span>,
      key: 'input',
      render: (_: unknown, record: SalaryPeriodRow) => (
        <Space style={{ color: record.minimumApplied ? '#FF6B6B' : '#E8F4F8' }}>
          <span className="ltr-number">{formatCurrency(record.salaryInputAmount)}</span>
          <span>{translateSalaryType(record.salaryInputType)}</span>
          {record.minimumApplied && <WarningOutlined style={{ color: '#FF6B6B' }} />}
        </Space>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>מינימום</span>,
      key: 'minimum',
      render: (_: unknown, record: SalaryPeriodRow) => (
        record.minimumApplied
          ? <span className="ltr-number" style={{ color: '#FF6B6B' }}>{formatCurrency(record.minimumWageValue)}</span>
          : <Text type="secondary">—</Text>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>אפקטיבי</span>,
      key: 'effective',
      render: (_: unknown, record: SalaryPeriodRow) => (
        <span className="ltr-number" style={{ color: '#4ECDC4', fontWeight: 'bold' }}>
          {formatCurrency(record.effectiveAmount)}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>שעתי</span>,
      key: 'hourly',
      render: (_: unknown, record: SalaryPeriodRow) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>
          {formatCurrency(record.salaryHourly)}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>יומי</span>,
      key: 'daily',
      render: (_: unknown, record: SalaryPeriodRow) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>
          {formatCurrency(record.salaryDaily)}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>חודשי</span>,
      key: 'monthly',
      render: (_: unknown, record: SalaryPeriodRow) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>
          {formatCurrency(record.salaryMonthly)}
        </span>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <DollarOutlined />
          <span>פירוט שכר</span>
        </Space>
      }
      className="results-card"
    >
      {hasAnyMinimumApplied && (
        <Alert
          message="בחלק מהתקופה השכר היה נמוך משכר מינימום — הושלם אוטומטית"
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          style={{
            marginBottom: 16,
            background: 'rgba(255, 107, 107, 0.08)',
            borderColor: 'rgba(255, 107, 107, 0.3)',
          }}
        />
      )}
      <Table
        dataSource={consolidatedRows}
        columns={columns}
        rowKey={(record) => `${record.periodId}-${record.firstMonth[0]}-${record.firstMonth[1]}`}
        pagination={false}
        size="small"
        rowClassName={(record) =>
          record.minimumApplied ? 'minimum-applied-row' : ''
        }
      />
    </Card>
  );
};

// ============================================================================
// ג2. JobScopeDisplay - היקף משרה — פירוט חודשי
// ============================================================================

const JobScopeDisplay: React.FC<{ monthAggregates?: MonthAggregate[] }> = ({
  monthAggregates = [],
}) => {
  if (!monthAggregates.length) {
    return null;
  }

  // Calculate average job_scope
  const avgJobScope = monthAggregates.reduce((sum, m) => sum + m.job_scope, 0) / monthAggregates.length;
  const avgPercent = (avgJobScope * 100).toFixed(1);

  // Sort by month (ascending chronological order)
  const sorted = [...monthAggregates].sort((a, b) => {
    if (a.month[0] !== b.month[0]) return a.month[0] - b.month[0];
    return a.month[1] - b.month[1];
  });

  const columns = [
    {
      title: <span style={{ color: '#88D8E0' }}>חודש</span>,
      key: 'month',
      render: (_: unknown, record: MonthAggregate) => (
        <span style={{ color: '#E8F4F8' }}>{formatMonth(record.month)}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>ימי עבודה</span>,
      dataIndex: 'total_work_days',
      key: 'work_days',
      render: (v: number) => <span style={{ color: '#E8F4F8' }}>{v}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>שעות רגילות</span>,
      dataIndex: 'total_regular_hours',
      key: 'regular_hours',
      render: (v: number) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>{v.toFixed(1)}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>בסיס משרה</span>,
      dataIndex: 'full_time_hours_base',
      key: 'base',
      render: (v: number) => <span style={{ color: '#88D8E0' }}>{v}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>היקף גולמי</span>,
      dataIndex: 'raw_scope',
      key: 'raw_scope',
      render: (v: number) => {
        const percent = (v * 100).toFixed(1);
        const color = v > 1.0 ? '#4ECDC4' : '#E8F4F8'; // Green if over 100%
        return (
          <span className="ltr-number" style={{ color }}>
            {percent}%
          </span>
        );
      },
    },
    {
      title: <span style={{ color: '#88D8E0' }}>היקף אפקטיבי</span>,
      dataIndex: 'job_scope',
      key: 'job_scope',
      render: (v: number) => {
        const percent = (v * 100).toFixed(1);
        // Red if under 100%, regular color if 100%
        const color = v < 1.0 ? '#FF6B6B' : '#E8F4F8';
        return (
          <span className="ltr-number" style={{ color, fontWeight: 'bold' }}>
            {percent}%
          </span>
        );
      },
    },
  ];

  const collapseItems = [
    {
      key: 'job-scope',
      label: (
        <Space>
          <PercentageOutlined />
          <span>היקף משרה — ממוצע: {avgPercent}% ({monthAggregates.length} חודשים)</span>
        </Space>
      ),
      children: (
        <Table
          dataSource={sorted}
          columns={columns}
          rowKey={(record) => `${record.month[0]}-${record.month[1]}`}
          pagination={false}
          size="small"
          rowClassName={(record) => {
            if (record.raw_scope > 1.0) return 'over-scope-row';
            if (record.job_scope < 1.0) return 'under-scope-row';
            return '';
          }}
        />
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <PercentageOutlined />
          <span>היקף משרה — פירוט חודשי</span>
        </Space>
      }
      className="results-card"
    >
      <Collapse items={collapseItems} defaultActiveKey={[]} />
    </Card>
  );
};

// ============================================================================
// ד. OvertimeBreakdown - פירוט שעות נוספות (משופר)
// ============================================================================

// Helper: format datetime to time only
const formatTime = (datetime: string | undefined): string => {
  if (!datetime) return '-';
  const d = new Date(datetime);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
};

// Helper: format datetime to date and time
const formatDateTime = (datetime: string | undefined): string => {
  if (!datetime) return '-';
  return `${formatDate(datetime)} ${formatTime(datetime)}`;
};

// Helper: get tier label
const getTierLabel = (tier: number, inRest: boolean): string => {
  const baseLabels: Record<number, string> = { 0: '100%', 1: '125%', 2: '150%' };
  const restLabels: Record<number, string> = { 0: '150% (מנוחה)', 1: '175% (מנוחה)', 2: '200% (מנוחה)' };
  return inRest ? restLabels[tier] : baseLabels[tier];
};

// Helper: get claim percentage label (what we actually claim, not the full rate)
const getClaimLabel = (tier: number, inRest: boolean): string => {
  const claimPct: Record<string, number> = {
    '0-false': 0, '1-false': 25, '2-false': 50,
    '0-true': 50, '1-true': 75, '2-true': 100,
  };
  return `${claimPct[`${tier}-${inRest}`]}%`;
};

// Helper: get tier color
const getTierColor = (tier: number, inRest: boolean): string => {
  if (inRest) {
    if (tier === 0) return '#FF8E8E'; // Light red - 150% מנוחה רגיל
    if (tier === 1) return '#FF6B6B'; // Medium red - 175%
    return '#E74C3C';                  // Dark red - 200%
  }
  if (tier === 0) return '#88D8E0'; // Light cyan for regular 100%
  if (tier === 1) return '#FFD93D'; // Yellow for 125%
  return '#FF9F43'; // Orange for 150%
};

// Helper: translate day of week from number
const dayOfWeekFromDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  const days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'];
  return days[d.getDay()];
};

// Helper: translate threshold reason to Hebrew
const translateThresholdReason = (reason: string): string => {
  const map: Record<string, string> = {
    '5-day week': 'שבוע 5 ימים',
    '6-day week': 'שבוע 6 ימים',
    '5day': 'שבוע 5 ימים',
    '6day': 'שבוע 6 ימים',
    'eve of rest': 'ערב מנוחה',
    'eve_of_rest': 'ערב מנוחה',
    'eve_rest': 'ערב מנוחה',
    'rest_day': 'יום מנוחה',
    'night_shift': 'משמרת לילה',
    'night shift': 'משמרת לילה',
    'night': 'משמרת לילה',
    'eve_of_rest_5day': 'ערב מנוחה (5 ימים)',
    'eve_rest+night': 'ערב מנוחה + לילה',
  };

  // Exact match first
  if (map[reason]) return map[reason];

  // Compound reasons: split by ' + ' and translate each part
  if (reason.includes(' + ')) {
    return reason
      .split(' + ')
      .map((part) => map[part.trim()] || part.trim())
      .join(' + ');
  }

  return reason;
};

/** Calculate hours summary from array of shifts */
const calcHoursSummary = (shifts: ShiftData[]) => {
  const regular = shifts.reduce((s, sh) => s + sh.regular_hours, 0);
  const ot1 = shifts.reduce((s, sh) => s + sh.ot_tier1_hours, 0);
  const ot2 = shifts.reduce((s, sh) => s + sh.ot_tier2_hours, 0);
  const total = shifts.reduce((s, sh) => s + sh.net_hours, 0);
  const claim = shifts.reduce((s, sh) => s + (sh.claim_amount || 0), 0);
  return { regular, ot1, ot2, total, claim };
};

/** Display Tags for hours summary */
const HoursSummaryTags: React.FC<{ summary: ReturnType<typeof calcHoursSummary>; compact?: boolean }> = ({ summary, compact }) => (
  <>
    <Tag>{summary.regular.toFixed(1)} רגיל</Tag>
    {summary.ot1 > 0 && <Tag color="gold">{summary.ot1.toFixed(1)} ב-125%</Tag>}
    {summary.ot2 > 0 && <Tag color="orange">{summary.ot2.toFixed(1)} ב-150%</Tag>}
    {!compact && <Tag color="cyan">{formatCurrency(summary.claim)}</Tag>}
  </>
);

// Aggregate hours by tier across all shifts
interface TierSummary {
  tier: string;
  hours: number;
  amount: number;
  color: string;
}

const aggregateByTier = (shifts: ShiftData[]): TierSummary[] => {
  const tierMap: Record<string, { hours: number; amount: number; color: string }> = {};

  shifts.forEach((shift) => {
    if (shift.pricing_breakdown) {
      shift.pricing_breakdown.forEach((item) => {
        const label = getTierLabel(item.tier, item.in_rest);
        const color = getTierColor(item.tier, item.in_rest);
        if (!tierMap[label]) {
          tierMap[label] = { hours: 0, amount: 0, color };
        }
        tierMap[label].hours += item.hours;
        tierMap[label].amount += item.claim_amount;
      });
    }
  });

  // Sort by percentage (regular first, then rest)
  const order = ['100%', '125%', '150%', '150% (מנוחה)', '175% (מנוחה)', '200% (מנוחה)'];
  return order
    .filter((tier) => tierMap[tier])
    .map((tier) => ({
      tier,
      hours: tierMap[tier].hours,
      amount: tierMap[tier].amount,
      color: tierMap[tier].color,
    }));
};

// Period summary for overtime
interface PeriodOvertimeSummary {
  periodId: string;
  firstMonth: string;
  lastMonth: string;
  hourlyWage: number;
  salaryInputAmount: number;
  minimumApplied: boolean;
  tierSummary: TierSummary[];
  totalHours: number;
  regularHours: number;
  otHours: number;
  totalClaim: number;
  completionAmount: number; // (hourly_wage - salary_input) * regular_hours if minimum_applied
}

// OvertimeSummaryTab - סיכום כללי לפי תקופות
const OvertimeSummaryTab: React.FC<{
  shifts: ShiftData[];
  totalClaim: number;
  effectivePeriods?: EffectivePeriodData[];
  periodMonthRecords?: PeriodMonthRecord[];
}> = ({
  shifts,
  totalClaim,
  effectivePeriods = [],
  periodMonthRecords = [],
}) => {
  // Group shifts by effective_period_id
  const shiftsByPeriod: Record<string, ShiftData[]> = {};
  shifts.forEach((shift) => {
    const epId = shift.effective_period_id;
    if (!shiftsByPeriod[epId]) shiftsByPeriod[epId] = [];
    shiftsByPeriod[epId].push(shift);
  });

  const periodIds = Object.keys(shiftsByPeriod).sort();
  const hasMutiplePeriods = periodIds.length > 1;

  // Build period summaries
  const periodSummaries: PeriodOvertimeSummary[] = periodIds.map((periodId) => {
    const periodShifts = shiftsByPeriod[periodId];
    const ep = effectivePeriods.find((p) => p.id === periodId);
    const pmrs = periodMonthRecords.filter((pmr) => pmr.effective_period_id === periodId);

    // Get hourly wage from first shift's pricing_breakdown
    let hourlyWage = 0;
    if (periodShifts[0]?.pricing_breakdown?.[0]?.hourly_wage) {
      hourlyWage = periodShifts[0].pricing_breakdown[0].hourly_wage;
    }

    // Get salary input amount from effective period
    const salaryInputAmount = ep?.salary_amount || 0;

    // Check if minimum was applied for any month in this period
    const minimumApplied = pmrs.some((pmr) => pmr.minimum_applied);

    // Calculate tier summary
    const tierSummary = aggregateByTier(periodShifts);
    const totalHours = periodShifts.reduce((sum, s) => sum + s.net_hours, 0);
    const regularHours = periodShifts.reduce((sum, s) => sum + s.regular_hours, 0);
    const otHours = periodShifts.reduce((sum, s) => sum + s.ot_tier1_hours + s.ot_tier2_hours, 0);
    const periodClaim = periodShifts.reduce((sum, s) => sum + (s.claim_amount || 0), 0);

    // Calculate completion amount if minimum was applied
    let completionAmount = 0;
    if (minimumApplied && hourlyWage > salaryInputAmount) {
      const gap = hourlyWage - salaryInputAmount;
      completionAmount = gap * regularHours;
    }

    // Get first and last months
    const months = pmrs.map((pmr) => pmr.month).sort((a, b) => a[0] * 100 + a[1] - (b[0] * 100 + b[1]));
    const firstMonth = months.length > 0 ? formatMonth(months[0]) : '';
    const lastMonth = months.length > 0 ? formatMonth(months[months.length - 1]) : '';

    return {
      periodId,
      firstMonth,
      lastMonth,
      hourlyWage,
      salaryInputAmount,
      minimumApplied,
      tierSummary,
      totalHours,
      regularHours,
      otHours,
      totalClaim: periodClaim,
      completionAmount,
    };
  });

  // Single period - simple display (like before)
  if (!hasMutiplePeriods) {
    const summary = periodSummaries[0] || {
      tierSummary: aggregateByTier(shifts),
      totalHours: shifts.reduce((sum, s) => sum + s.net_hours, 0),
      regularHours: shifts.reduce((sum, s) => sum + s.regular_hours, 0),
      otHours: shifts.reduce((sum, s) => sum + s.ot_tier1_hours + s.ot_tier2_hours, 0),
      totalClaim,
      minimumApplied: false,
      completionAmount: 0,
      hourlyWage: 0,
      salaryInputAmount: 0,
    };

    return (
      <div>
        {/* Overall stats */}
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Statistic title="סה״כ משמרות" value={shifts.length} />
          </Col>
          <Col span={6}>
            <Statistic title="סה״כ שעות עבודה" value={summary.totalHours.toFixed(1)} />
          </Col>
          <Col span={6}>
            <Statistic title="שעות רגילות" value={summary.regularHours.toFixed(1)} valueStyle={{ color: '#88D8E0' }} />
          </Col>
          <Col span={6}>
            <Statistic title="שעות נוספות" value={summary.otHours.toFixed(1)} valueStyle={{ color: '#FFD93D' }} />
          </Col>
        </Row>

        {/* Tier breakdown */}
        <Title level={5} style={{ color: '#88D8E0', marginBottom: 16 }}>פירוט לפי דרגה</Title>
        <Table
          dataSource={summary.tierSummary}
          columns={[
            {
              title: 'דרגה',
              dataIndex: 'tier',
              key: 'tier',
              render: (tier: string, record: TierSummary) => (
                <Tag color={record.color} style={{ fontSize: '1em' }}>{tier}</Tag>
              ),
            },
            {
              title: 'שעות',
              dataIndex: 'hours',
              key: 'hours',
              render: (v: number) => <span className="ltr-number">{v.toFixed(1)}</span>,
            },
            {
              title: 'סכום לתביעה',
              dataIndex: 'amount',
              key: 'amount',
              render: (v: number, record: TierSummary) => {
                if (record.tier === '100%') {
                  return <span className="ltr-number">{formatCurrency(v)} (לא נתבע)</span>;
                }
                return <span className="ltr-number" style={{ fontWeight: 'bold' }}>{formatCurrency(v)}</span>;
              },
            },
          ]}
          rowKey="tier"
          pagination={false}
          size="small"
          summary={() => (
            <Table.Summary fixed>
              <Table.Summary.Row style={{ background: 'rgba(78, 205, 196, 0.1)' }}>
                <Table.Summary.Cell index={0}><strong>סה״כ</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={1}>
                  <strong className="ltr-number">{summary.tierSummary.reduce((sum, t) => sum + t.hours, 0).toFixed(1)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={2}>
                  <strong className="ltr-number" style={{ color: '#4ECDC4' }}>{formatCurrency(totalClaim)}</strong>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            </Table.Summary>
          )}
        />
      </div>
    );
  }

  // Multiple periods - show per-period breakdown
  return (
    <div>
      {periodSummaries.map((summary, idx) => (
        <div key={summary.periodId} style={{ marginBottom: 32, paddingBottom: 24, borderBottom: idx < periodSummaries.length - 1 ? '1px solid rgba(78, 205, 196, 0.2)' : 'none' }}>
          {/* Period header */}
          <Title level={5} style={{ color: '#88D8E0', marginBottom: 16 }}>
            תקופה {idx + 1}: {summary.firstMonth} — {summary.lastMonth}
            <span style={{ marginRight: 16, color: '#E8F4F8', fontWeight: 'normal', fontSize: '0.9em' }}>
              | שכר שעתי: {formatCurrency(summary.hourlyWage)}
              {summary.minimumApplied && (
                <span style={{ color: '#FF6B6B' }}> (מינימום, קלט {formatCurrency(summary.salaryInputAmount)})</span>
              )}
            </span>
          </Title>

          {/* Period stats */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Statistic title="משמרות" value={shiftsByPeriod[summary.periodId].length} />
            </Col>
            <Col span={6}>
              <Statistic title="שעות עבודה" value={summary.totalHours.toFixed(1)} />
            </Col>
            <Col span={6}>
              <Statistic title="שעות רגילות" value={summary.regularHours.toFixed(1)} valueStyle={{ color: '#88D8E0' }} />
            </Col>
            <Col span={6}>
              <Statistic title="שעות נוספות" value={summary.otHours.toFixed(1)} valueStyle={{ color: '#FFD93D' }} />
            </Col>
          </Row>

          {/* Period tier breakdown */}
          <Table
            dataSource={summary.tierSummary}
            columns={[
              {
                title: 'דרגה',
                dataIndex: 'tier',
                key: 'tier',
                render: (tier: string, record: TierSummary) => (
                  <Tag color={record.color} style={{ fontSize: '1em' }}>{tier}</Tag>
                ),
              },
              {
                title: 'שעות',
                dataIndex: 'hours',
                key: 'hours',
                render: (v: number) => <span className="ltr-number">{v.toFixed(1)}</span>,
              },
              {
                title: 'תעריף שעתי',
                key: 'rate',
                render: (_: unknown, record: TierSummary) => {
                  const rateMap: Record<string, number> = {
                    '100%': 1.0, '125%': 1.25, '150%': 1.5, '175%': 1.75, '200%': 2.0,
                  };
                  const rate = (rateMap[record.tier] || 1.0) * summary.hourlyWage;
                  return <span className="ltr-number">{formatCurrency(rate)}</span>;
                },
              },
              {
                title: 'סכום לתביעה',
                dataIndex: 'amount',
                key: 'amount',
                render: (v: number, record: TierSummary) => {
                  if (record.tier === '100%') {
                    return <span className="ltr-number">{formatCurrency(v)} (לא נתבע)</span>;
                  }
                  return <span className="ltr-number" style={{ fontWeight: 'bold' }}>{formatCurrency(v)}</span>;
                },
              },
            ]}
            rowKey="tier"
            pagination={false}
            size="small"
            summary={() => (
              <Table.Summary fixed>
                <Table.Summary.Row style={{ background: 'rgba(78, 205, 196, 0.1)' }}>
                  <Table.Summary.Cell index={0}><strong>סה״כ תקופה</strong></Table.Summary.Cell>
                  <Table.Summary.Cell index={1}>
                    <strong className="ltr-number">{summary.tierSummary.reduce((sum, t) => sum + t.hours, 0).toFixed(1)}</strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={2}></Table.Summary.Cell>
                  <Table.Summary.Cell index={3}>
                    <strong className="ltr-number" style={{ color: '#4ECDC4' }}>{formatCurrency(summary.totalClaim)}</strong>
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              </Table.Summary>
            )}
          />
        </div>
      ))}

      {/* Grand total */}
      <div style={{ padding: '16px', background: 'rgba(78, 205, 196, 0.1)', borderRadius: 8, textAlign: 'center' }}>
        <Title level={4} style={{ color: '#4ECDC4', margin: 0 }}>
          סה״כ כל התקופות: {formatCurrency(totalClaim)}
        </Title>
      </div>
    </div>
  );
};

// Single shift detail component
const ShiftDetail: React.FC<{ shift: ShiftData }> = ({ shift }) => {
  return (
    <div style={{ padding: '8px 0' }}>
      <Row gutter={16}>
        <Col span={6}>
          <Text type="secondary">זמן:</Text>
          <div className="ltr-number">{formatTime(shift.start)} - {formatTime(shift.end)}</div>
        </Col>
        <Col span={4}>
          <Text type="secondary">נטו:</Text>
          <div>{shift.net_hours.toFixed(2)} שעות</div>
        </Col>
        <Col span={4}>
          <Text type="secondary">סף:</Text>
          <div>{shift.threshold} ({translateThresholdReason(shift.threshold_reason)})</div>
        </Col>
        <Col span={5}>
          <Text type="secondary">שעות:</Text>
          <div>
            {/* Regular hours - split if rest window */}
            {(shift.non_rest_regular_hours || 0) > 0 && (
              <span style={{ color: '#88D8E0' }}>{shift.non_rest_regular_hours.toFixed(1)} רגיל</span>
            )}
            {(shift.rest_window_regular_hours || 0) > 0 && (
              <span style={{ color: '#FF8E8E' }}>{(shift.non_rest_regular_hours || 0) > 0 ? ' + ' : ''}{shift.rest_window_regular_hours.toFixed(1)} מנוחה</span>
            )}
            {/* Fallback if no split data */}
            {!(shift.non_rest_regular_hours || 0) && !(shift.rest_window_regular_hours || 0) && shift.regular_hours > 0 && (
              <span style={{ color: '#88D8E0' }}>{shift.regular_hours.toFixed(1)} רגיל</span>
            )}
            {/* OT tier 1 - split rest/non-rest */}
            {(shift.non_rest_ot_tier1_hours || 0) > 0 && (
              <span style={{ color: '#FFD93D' }}> + {shift.non_rest_ot_tier1_hours.toFixed(1)} (125%)</span>
            )}
            {(shift.rest_window_ot_tier1_hours || 0) > 0 && (
              <span style={{ color: '#FF6B6B' }}> + {shift.rest_window_ot_tier1_hours.toFixed(1)} (175%)</span>
            )}
            {/* Fallback tier1 - if no split data */}
            {!(shift.non_rest_ot_tier1_hours || 0) && !(shift.rest_window_ot_tier1_hours || 0) && shift.ot_tier1_hours > 0 && (
              <span style={{ color: '#FFD93D' }}> + {shift.ot_tier1_hours.toFixed(1)} (125%)</span>
            )}
            {/* OT tier 2 - split rest/non-rest */}
            {(shift.non_rest_ot_tier2_hours || 0) > 0 && (
              <span style={{ color: '#FF9F43' }}> + {shift.non_rest_ot_tier2_hours.toFixed(1)} (150%)</span>
            )}
            {(shift.rest_window_ot_tier2_hours || 0) > 0 && (
              <span style={{ color: '#E74C3C' }}> + {shift.rest_window_ot_tier2_hours.toFixed(1)} (200%)</span>
            )}
            {/* Fallback tier2 - if no split data */}
            {!(shift.non_rest_ot_tier2_hours || 0) && !(shift.rest_window_ot_tier2_hours || 0) && shift.ot_tier2_hours > 0 && (
              <span style={{ color: '#FF9F43' }}> + {shift.ot_tier2_hours.toFixed(1)} (150%)</span>
            )}
          </div>
        </Col>
        <Col span={5}>
          <Text type="secondary">לתביעה:</Text>
          <div className="ltr-number" style={{ color: '#4ECDC4', fontWeight: 'bold' }}>
            {formatCurrency(shift.claim_amount || 0)}
          </div>
        </Col>
      </Row>

      {/* Pricing breakdown */}
      {shift.pricing_breakdown && shift.pricing_breakdown.length > 0 && (
        <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(19, 43, 74, 0.5)', borderRadius: 4 }}>
          <Text type="secondary" style={{ fontSize: '0.85em' }}>פירוט תמחור:</Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4 }}>
            {shift.pricing_breakdown
              .filter((item) => item.claim_amount !== 0)
              .map((item, idx) => (
                <Tag key={idx} color={getTierColor(item.tier, item.in_rest)} style={{ marginBottom: 4 }}>
                  {item.hours.toFixed(2)}ש׳ × {formatCurrency(item.hourly_wage)} × {getClaimLabel(item.tier, item.in_rest)}
                  {item.in_rest && ' (מנוחה)'}
                  {' = '}
                  {formatCurrency(item.claim_amount)}
                </Tag>
              ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Day collapse item
const DayCollapseItem: React.FC<{ date: string; shifts: ShiftData[] }> = ({ shifts }) => {
  return (
    <div>
      {shifts.map((shift, idx) => (
        <div key={shift.id} style={{ borderBottom: idx < shifts.length - 1 ? '1px solid rgba(78, 205, 196, 0.1)' : 'none' }}>
          <Text strong style={{ color: '#88D8E0' }}>משמרת {idx + 1}</Text>
          <ShiftDetail shift={shift} />
        </div>
      ))}
    </div>
  );
};

// Week collapse item with rest window info
const WeekCollapseContent: React.FC<{
  week: WeekData;
  shifts: ShiftData[];
  allWeekShifts?: ShiftData[];
  currentMonth?: string;
}> = ({ week, shifts, allWeekShifts, currentMonth }) => {
  // Group shifts by assigned_day (current month shifts)
  const shiftsByDate: Record<string, ShiftData[]> = {};
  shifts.forEach((shift) => {
    if (!shiftsByDate[shift.assigned_day]) shiftsByDate[shift.assigned_day] = [];
    shiftsByDate[shift.assigned_day].push(shift);
  });

  // Find ghost days (shifts from other months in the same week)
  const ghostDays: Record<string, { shifts: ShiftData[]; monthName: string }> = {};
  if (allWeekShifts && currentMonth) {
    allWeekShifts.forEach((shift) => {
      const assignedDate = new Date(shift.assigned_day);
      const shiftMonth = `${assignedDate.getFullYear()}-${(assignedDate.getMonth() + 1).toString().padStart(2, '0')}`;
      if (shiftMonth !== currentMonth) {
        if (!ghostDays[shift.assigned_day]) {
          ghostDays[shift.assigned_day] = {
            shifts: [],
            monthName: formatMonth([assignedDate.getFullYear(), assignedDate.getMonth() + 1]),
          };
        }
        ghostDays[shift.assigned_day].shifts.push(shift);
      }
    });
  }

  // Combine and sort all dates (current + ghost)
  const allDates = [...new Set([...Object.keys(shiftsByDate), ...Object.keys(ghostDays)])].sort();

  const dayItems = allDates.map((date) => {
    const isGhost = !shiftsByDate[date];
    const dayShifts = shiftsByDate[date] || [];
    const ghostInfo = ghostDays[date];
    const dayOfWeek = dayOfWeekFromDate(date);

    if (isGhost && ghostInfo) {
      // Ghost day - show grayed out
      return {
        key: date,
        label: (
          <Tooltip title={`יום זה שייך לחודש ${ghostInfo.monthName}`}>
            <Space style={{ opacity: 0.5, color: '#888' }}>
              <CalendarOutlined />
              <span style={{ fontWeight: 500 }}>{dayOfWeek}</span>
              <span className="ltr-number">{formatDate(date)}</span>
              <Tag color="default">{ghostInfo.shifts.length} משמרות</Tag>
              <Tag color="default">{ghostInfo.monthName}</Tag>
            </Space>
          </Tooltip>
        ),
        children: null,
        collapsible: 'disabled' as const,
      };
    }

    // Normal day
    return {
      key: date,
      label: (
        <Space>
          <CalendarOutlined />
          <span style={{ fontWeight: 500 }}>{dayOfWeek}</span>
          <span className="ltr-number">{formatDate(date)}</span>
          <Tag>{dayShifts.length} משמרות</Tag>
          <HoursSummaryTags summary={calcHoursSummary(dayShifts)} />
        </Space>
      ),
      children: <DayCollapseItem date={date} shifts={dayShifts} />,
    };
  });

  return (
    <div>
      {/* Week info */}
      <div style={{ marginBottom: 16, padding: '12px 16px', background: 'rgba(78, 205, 196, 0.05)', borderRadius: 8 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Text type="secondary">סוג שבוע:</Text>
            <div>
              <Tag color={week.week_type === 5 ? 'green' : 'blue'}>{week.week_type} ימים</Tag>
              {week.is_partial && <Tag color="purple">שבוע חלקי</Tag>}
            </div>
          </Col>
          <Col span={6}>
            <Text type="secondary">ימי עבודה:</Text>
            <div>{week.distinct_work_days}</div>
          </Col>
          <Col span={6}>
            <Text type="secondary">שעות רגילות:</Text>
            <div>{week.total_regular_hours?.toFixed(1) || 0}</div>
          </Col>
          <Col span={6}>
            <Text type="secondary">ש״נ שבועי:</Text>
            <div style={{ color: week.weekly_ot_hours > 0 ? '#FFD93D' : undefined }}>
              {week.weekly_ot_hours?.toFixed(1) || 0}
            </div>
          </Col>
        </Row>

        {/* Rest window info - only show if there's work in rest window */}
        {week.rest_window_work_hours > 0 && (
          <Row gutter={16} style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(255, 107, 107, 0.08)', borderRadius: 8 }}>
            <Col span={24} style={{ marginBottom: 8 }}>
              <Text strong style={{ color: '#FF6B6B' }}>
                ⚠ עבודה בחלון מנוחה (36 שעות)
              </Text>
            </Col>
            <Col span={8}>
              <Text type="secondary">תחילת חלון:</Text>
              <div className="ltr-number">{formatDateTime(week.rest_window_start)}</div>
            </Col>
            <Col span={8}>
              <Text type="secondary">סוף חלון:</Text>
              <div className="ltr-number">{formatDateTime(week.rest_window_end)}</div>
            </Col>
            <Col span={8}>
              <Text type="secondary">שעות עבודה בחלון:</Text>
              <div style={{ color: '#FF6B6B', fontWeight: 'bold' }}>
                {week.rest_window_work_hours.toFixed(1)}
              </div>
            </Col>
          </Row>
        )}

        {/* Partial week info */}
        {week.is_partial && (
          <Alert
            message={`שבוע חלקי — ${week.partial_detail || week.partial_reason}`}
            type="info"
            showIcon
            style={{ marginTop: 8, padding: '6px 12px' }}
          />
        )}
      </div>

      {/* Days collapse */}
      <Collapse items={dayItems} />
    </div>
  );
};

// OvertimeDetailedTab - פירוט מלא
const OvertimeDetailedTab: React.FC<{ shifts: ShiftData[]; weeks: WeekData[] }> = ({
  shifts,
  weeks,
}) => {
  // Create week lookup
  const weekMap: Record<string, WeekData> = {};
  weeks.forEach((w) => { weekMap[w.id] = w; });

  // Group shifts by year → month → week
  const hierarchy: Record<number, Record<string, Record<string, ShiftData[]>>> = {};

  shifts.forEach((shift) => {
    const assignedDate = new Date(shift.assigned_day);
    const year = assignedDate.getFullYear();
    const month = `${year}-${(assignedDate.getMonth() + 1).toString().padStart(2, '0')}`;
    const weekId = shift.assigned_week || shift.week_id;

    if (!hierarchy[year]) hierarchy[year] = {};
    if (!hierarchy[year][month]) hierarchy[year][month] = {};
    if (!hierarchy[year][month][weekId]) hierarchy[year][month][weekId] = [];
    hierarchy[year][month][weekId].push(shift);
  });

  // Build year items (ascending chronological order)
  const yearItems = Object.keys(hierarchy)
    .sort((a, b) => parseInt(a) - parseInt(b))
    .map((year) => {
      const yearData = hierarchy[parseInt(year)];
      const yearShifts = Object.values(yearData).flatMap((m) => Object.values(m).flat());

      // Build month items (ascending chronological order)
      const monthItems = Object.keys(yearData)
        .sort((a, b) => a.localeCompare(b))
        .map((month) => {
          const monthData = yearData[month];
          const monthShifts = Object.values(monthData).flat();
          const monthName = formatMonth([parseInt(month.split('-')[0]), parseInt(month.split('-')[1])]);

          // Build week items (ascending chronological order by start_date)
          const weekItems = Object.keys(monthData)
            .sort((a, b) => {
              const weekA = weekMap[a];
              const weekB = weekMap[b];
              if (!weekA || !weekB) return 0;
              return new Date(weekA.start_date).getTime() - new Date(weekB.start_date).getTime();
            })
            .map((weekId) => {
              const weekShifts = monthData[weekId];
              const week = weekMap[weekId];

              // Get ALL shifts in this week (from all months) for ghost days
              const allWeekShifts = shifts.filter((s) => (s.assigned_week || s.week_id) === weekId);

              return {
                key: weekId,
                label: (
                  <Space>
                    <span>שבוע {week?.week_number || '?'}</span>
                    {week && (
                      <>
                        <span className="ltr-number" style={{ fontSize: '0.85em', color: '#88D8E0' }}>
                          ({formatDate(week.start_date)} - {formatDate(week.end_date)})
                        </span>
                        <Tag color={week.week_type === 5 ? 'green' : 'blue'}>{week.week_type} ימים</Tag>
                      </>
                    )}
                    {week?.is_partial && <Tag color="purple">שבוע חלקי</Tag>}
                    <Tag>{weekShifts.length} משמרות</Tag>
                    <HoursSummaryTags summary={calcHoursSummary(weekShifts)} />
                  </Space>
                ),
                children: week ? (
                  <WeekCollapseContent week={week} shifts={weekShifts} allWeekShifts={allWeekShifts} currentMonth={month} />
                ) : (
                  <div>{weekShifts.map((s) => <ShiftDetail key={s.id} shift={s} />)}</div>
                ),
              };
            });

          return {
            key: month,
            label: (
              <Space>
                <span>{monthName}</span>
                <Tag>{monthShifts.length} משמרות</Tag>
                <HoursSummaryTags summary={calcHoursSummary(monthShifts)} />
              </Space>
            ),
            children: <Collapse items={weekItems} />,
          };
        });

      return {
        key: year,
        label: (
          <Space>
            <span style={{ fontWeight: 'bold', fontSize: '1.1em' }}>{year}</span>
            <Tag>{yearShifts.length} משמרות</Tag>
            <HoursSummaryTags summary={calcHoursSummary(yearShifts)} />
          </Space>
        ),
        children: <Collapse items={monthItems} />,
      };
    });

  return <Collapse items={yearItems} />;
};

// Main OvertimeBreakdown component
const OvertimeBreakdown: React.FC<{
  overtime: OvertimeResult;
  shifts?: ShiftData[];
  weeks?: WeekData[];
  effectivePeriods?: EffectivePeriodData[];
  periodMonthRecords?: PeriodMonthRecord[];
}> = ({ overtime, shifts = [], weeks = [], effectivePeriods = [], periodMonthRecords = [] }) => {
  const tabItems = [
    {
      key: 'summary',
      label: (
        <Space>
          <ClockCircleOutlined />
          <span>סיכום כללי</span>
        </Space>
      ),
      children: (
        <OvertimeSummaryTab
          shifts={shifts}
          totalClaim={overtime.total_claim}
          effectivePeriods={effectivePeriods}
          periodMonthRecords={periodMonthRecords}
        />
      ),
    },
    {
      key: 'detailed',
      label: (
        <Space>
          <CalendarOutlined />
          <span>פירוט מלא</span>
        </Space>
      ),
      children: <OvertimeDetailedTab shifts={shifts} weeks={weeks} />,
    },
  ];

  return (
    <Card
      title={
        <Space>
          <ClockCircleOutlined />
          <span>שעות נוספות</span>
          <Tag color="cyan" style={{ fontSize: '1em' }}>{formatCurrency(overtime.total_claim)}</Tag>
        </Space>
      }
      className="results-card"
    >
      <Collapse
        items={tabItems}
        defaultActiveKey={['summary']}
        style={{ background: 'transparent' }}
      />
    </Card>
  );
};

// ============================================================================
// ד. HolidaysBreakdown - פירוט דמי חגים
// ============================================================================

interface HolidaysBreakdownProps {
  holidays: HolidaysResult;
  limitation?: LimitationRightResult;
  generalWindow?: LimitationWindow;
  filingDate?: string;
}

const HolidaysBreakdown: React.FC<HolidaysBreakdownProps> = ({ holidays, limitation: _limitation, generalWindow, filingDate: _filingDate }) => {
  // Helper: check if a year is within the limitation window
  const isYearClaimable = (year: number): boolean => {
    if (!generalWindow?.effective_window_start) return true;
    const windowStart = new Date(generalWindow.effective_window_start);
    // Check if Dec 31 of the year is after the window start
    const yearEnd = new Date(year, 11, 31);
    return yearEnd >= windowStart;
  };

  const renderEntitlement = (entry: HolidayEntry) => {
    if (!entry.employed_on_date) {
      return <Tag color="default">לא הועסק</Tag>;
    }
    if (entry.excluded) {
      return (
        <Tooltip title={entry.exclude_reason}>
          <Tag color="orange" icon={<WarningOutlined />}>מוחרג</Tag>
        </Tooltip>
      );
    }
    if (entry.entitled) {
      return <Tag color="green" icon={<CheckCircleOutlined />}>זכאי</Tag>;
    }
    return <Tag color="default">לא זכאי</Tag>;
  };

  const holidayColumns = [
    {
      title: <span style={{ color: '#88D8E0' }}>שם</span>,
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <span style={{ color: '#E8F4F8' }}>{v}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>תאריך עברי</span>,
      dataIndex: 'hebrew_date',
      key: 'hebrew_date',
      render: (v: string) => <span style={{ color: '#E8F4F8' }}>{v}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>תאריך לועזי</span>,
      dataIndex: 'gregorian_date',
      key: 'gregorian_date',
      render: (d: string) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>
          {d ? formatDate(d) : '—'}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>יום</span>,
      dataIndex: 'day_of_week',
      key: 'day_of_week',
      render: (d: string) => (
        <span style={{ color: '#E8F4F8' }}>
          {d === '—' ? '—' : translateDayOfWeek(d)}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>שבוע</span>,
      dataIndex: 'week_type',
      key: 'week_type',
      render: (w: number | undefined) => (
        <span style={{ color: '#E8F4F8' }}>
          {w == null ? '—' : `${w} ימים`}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>זכאות</span>,
      key: 'entitlement',
      render: (_: unknown, record: HolidayEntry) => {
        if (record.exclude_reason) {
          return (
            <Tooltip title={record.exclude_reason}>
              {renderEntitlement(record)}
            </Tooltip>
          );
        }
        return renderEntitlement(record);
      },
    },
    {
      title: <span style={{ color: '#88D8E0' }}>ערך יום</span>,
      dataIndex: 'day_value',
      key: 'day_value',
      render: (v: number | undefined) => v ? <span className="ltr-number" style={{ color: '#E8F4F8' }}>{formatCurrency(v)}</span> : <span style={{ color: '#E8F4F8' }}>-</span>,
    },
  ];

  const yearItems = holidays.per_year.map((year) => {
    // Check if all employed holidays in this year are before_seniority
    const employedHolidays = year.holidays.filter((h) => h.employed_on_date);
    const allBeforeSeniority = employedHolidays.length > 0 &&
      employedHolidays.every((h) => h.before_seniority);
    const hasEntitledDays = year.total_entitled_days > 0;
    const excluded = !isYearClaimable(year.year);

    return {
      key: String(year.year),
      label: (
        <Space>
          {excluded
            ? <Tooltip title="מחוץ לחלון ההתיישנות — התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
            : <Tooltip title="בתוך חלון ההתיישנות — ניתן לתבוע"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
          }
          <span style={{ color: excluded ? '#888' : undefined }}>{year.year}</span>
          <Tag color={hasEntitledDays && !excluded ? 'green' : 'default'}>
            {year.total_entitled_days} ימים
          </Tag>
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : undefined,
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(year.total_claim)}
          </span>
        </Space>
      ),
      className: excluded ? 'row-excluded' : '',
      children: (
        <div>
          {allBeforeSeniority && (
            <Alert
              message="טרם השלמת 3 חודשי ותק"
              description="כל החגים בשנה זו היו לפני השלמת 3 חודשי ותק אצל הנתבע"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}
          <Table
            dataSource={[
              ...year.holidays,
              // Add election day as the last row (only if entitled)
              ...(year.election_day_entitled ? [{
                name: 'יום בחירה',
                hebrew_date: '—',
                gregorian_date: '',
                employed_on_date: true,
                before_seniority: false,
                day_of_week: '—',
                week_type: undefined,  // Mark as election day, not a regular week_type
                is_rest_day: false,
                is_eve_of_rest: false,
                excluded: false,
                exclude_reason: undefined,
                entitled: true,
                day_value: year.election_day_value ?? undefined,
                claim_amount: year.election_day_value ?? undefined,
              }] : []),
            ]}
            columns={holidayColumns}
            rowKey="name"
            pagination={false}
            size="small"
            rowClassName={(record) =>
              record.name === 'יום בחירה' ? 'election-day-row' : ''
            }
          />
        </div>
      ),
    };
  });

  return (
    <Card
      title={
        <Space>
          <GiftOutlined />
          <span>דמי חגים — פירוט שנתי</span>
          <Tag color="cyan">{holidays.grand_total_days} ימים</Tag>
          <Tag color="green">{formatCurrency(holidays.grand_total_claim)}</Tag>
        </Space>
      }
      className="results-card"
    >
      <Collapse items={yearItems} />
    </Card>
  );
};

// ============================================================================
// ה. SeveranceBreakdown - פירוט פיצויי פיטורין
// ============================================================================

const SeveranceBreakdown: React.FC<{
  severance: SeveranceResult;
  recreation?: RecreationResult;
}> = ({ severance, recreation }) => {
  // Translate path to Hebrew
  const pathLabels: Record<string, string> = {
    contributions: 'הפרשות נדרשות (התפטרות)',
    section_14_holds: 'סעיף 14 עומד',
    section_14_falls: 'סעיף 14 נופל',
  };

  // Translate termination reason
  const terminationLabels: Record<string, string> = {
    fired: 'פוטר',
    resigned: 'התפטר',
    resigned_as_fired: 'התפטר בדין מפוטר',
  };

  // Translate industry
  const industryLabels: Record<string, string> = {
    general: 'כללי',
    construction: 'בנייה',
    agriculture: 'חקלאות',
    cleaning: 'ניקיון',
  };

  // Translate salary method
  const salaryMethodLabels: Record<string, string> = {
    avg_12_months: 'ממוצע 12 חודשים אחרונים',
    last_month: 'שכר חודשי אחרון',
    last_pmr: 'שכר חודשי אחרון',
  };

  const pathLabel = pathLabels[severance.path] || severance.path;
  const isContributionsPath = severance.path === 'contributions';
  const showOTRow = severance.ot_addition !== null;
  const isRecreationPending = !!(severance.recreation_addition?.recreation_pending);
  const showRecreationRow = severance.recreation_addition !== null;

  // Detail columns for monthly breakdown
  const detailColumns = [
    {
      title: <span style={{ color: '#88D8E0' }}>חודש</span>,
      key: 'month',
      render: (_: unknown, record: SeveranceMonthlyDetail) => (
        <span style={{ color: '#E8F4F8' }}>{formatMonth(record.month)}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>היקף משרה</span>,
      key: 'scope',
      render: (_: unknown, record: SeveranceMonthlyDetail) => (
        <span style={{ color: record.job_scope < 1 ? '#FF6B6B' : '#E8F4F8' }}>
          {(record.job_scope * 100).toFixed(1)}%
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>שכר קובע</span>,
      key: 'salary',
      render: (_: unknown, record: SeveranceMonthlyDetail) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>
          {formatCurrency(record.salary_used)}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>סכום</span>,
      key: 'amount',
      render: (_: unknown, record: SeveranceMonthlyDetail) => (
        <span className="ltr-number" style={{ color: '#4ECDC4', fontWeight: 'bold' }}>
          {formatCurrency(record.amount)}
        </span>
      ),
    },
  ];

  // Group monthly details by calendar year
  const allMonthlyDetails = severance.full_severance.base_monthly_detail
    .slice()
    .sort((a, b) => a.month[0] !== b.month[0] ? a.month[0] - b.month[0] : a.month[1] - b.month[1]);

  const byYear: Record<number, SeveranceMonthlyDetail[]> = {};
  for (const detail of allMonthlyDetails) {
    const yr = detail.month[0];
    if (!byYear[yr]) byYear[yr] = [];
    byYear[yr].push(detail);
  }

  const yearItems = Object.entries(byYear)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([yearStr, details]) => {
      const year = Number(yearStr);
      const yearTotal = details.reduce((sum, d) => sum + d.amount, 0);
      const avgScope = details.reduce((sum, d) => sum + d.job_scope, 0) / details.length;

      return {
        key: String(year),
        label: (
          <Space>
            <span>{year}</span>
            <Tag>{details.length} חודשים</Tag>
            <Tag>היקף ממוצע {(avgScope * 100).toFixed(1)}%</Tag>
            <Tag color="cyan">{formatCurrency(yearTotal)}</Tag>
          </Space>
        ),
        children: (
          <Table
            dataSource={details.map((d, i) => ({ ...d, key: i }))}
            columns={detailColumns}
            pagination={false}
            size="small"
          />
        ),
      };
    });

  // Summary table columns
  const summaryColumns = [
    {
      title: '',
      dataIndex: 'label',
      key: 'label',
      render: (v: string) => <span style={{ color: '#E8F4F8' }}>{v}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>פיצויים מלאים</span>,
      dataIndex: 'full',
      key: 'full',
      render: (v: number | string) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>
          {typeof v === 'string' ? v : formatCurrency(v)}
        </span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>הפרשות נדרשות</span>,
      dataIndex: 'required',
      key: 'required',
      render: (v: number | string) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>
          {typeof v === 'string' ? v : formatCurrency(v)}
        </span>
      ),
    },
    ...(isContributionsPath ? [{
      title: <span style={{ color: '#88D8E0' }}>תביעה</span>,
      dataIndex: 'claim',
      key: 'claim',
      render: (v: number | undefined) => v !== undefined ? (
        <span className="ltr-number" style={{ color: '#4ECDC4', fontWeight: 'bold' }}>{formatCurrency(v)}</span>
      ) : <span>—</span>,
    }] : []),
  ];

  const summaryData = [
    {
      key: 'base',
      label: 'בסיס',
      full: severance.full_severance.base_total,
      required: severance.required_contributions.base_total,
      claim: isContributionsPath ? severance.claim_before_deductions : undefined,
    },
    ...(showOTRow ? [{
      key: 'ot',
      label: 'שע"נ (6%)',
      full: severance.full_severance.ot_total,
      required: severance.required_contributions.ot_total,
      claim: undefined,
    }] : []),
    ...(showRecreationRow ? [{
      key: 'recreation',
      label: 'הבראה (8.333%)',
      full: isRecreationPending ? 'ממתין לחישוב' : severance.recreation_addition?.total ?? 0,
      required: isRecreationPending ? 'ממתין לחישוב' : severance.recreation_addition?.total ?? 0,
      claim: undefined,
    }] : []),
    {
      key: 'total',
      label: 'סה"כ',
      full: severance.full_severance.grand_total,
      required: severance.required_contributions.grand_total,
      claim: isContributionsPath ? severance.total_claim : undefined,
    },
  ];

  return (
    <Card
      title={
        <Space>
          <SafetyOutlined />
          <span>פיצויי פיטורין — {pathLabel}</span>
          <Tag color="cyan" style={{ fontSize: '1em' }}>{formatCurrency(severance.total_claim)}</Tag>
        </Space>
      }
      className="results-card"
    >
      {/* Basic details */}
      <Descriptions
        column={5}
        size="small"
        style={{ marginBottom: 16 }}
        labelStyle={{ color: '#88D8E0' }}
        contentStyle={{ color: '#E8F4F8' }}
      >
        <Descriptions.Item label="סיבת סיום">
          {terminationLabels[severance.termination_reason] || severance.termination_reason}
        </Descriptions.Item>
        <Descriptions.Item label="ענף">
          {industryLabels[severance.industry] || severance.industry}
        </Descriptions.Item>
        <Descriptions.Item label="שיעור פיצויים">
          {(severance.severance_rate * 100).toFixed(1)}%
        </Descriptions.Item>
        <Descriptions.Item label="שכר קובע">
          <span className="ltr-number">{formatCurrency(severance.last_salary_info.last_salary)}</span>
        </Descriptions.Item>
        <Descriptions.Item label="שיטת חישוב שכר">
          {salaryMethodLabels[severance.last_salary_info.method] || severance.last_salary_info.method}
        </Descriptions.Item>
      </Descriptions>

      {/* Section 14 comparison alert */}
      {severance.section_14_comparison && (
        <Alert
          type={severance.section_14_comparison.status === 'holds' ? 'success' : 'error'}
          showIcon
          style={{ marginBottom: 16 }}
          message={
            severance.section_14_comparison.status === 'holds'
              ? `סעיף 14 עומד — הפרשות בפועל (${formatCurrency(severance.section_14_comparison.actual_deposits)}) ≥ הפרשות נדרשות (${formatCurrency(severance.section_14_comparison.required_contributions_total)})`
              : `סעיף 14 נופל — הפרשות בפועל (${formatCurrency(severance.section_14_comparison.actual_deposits)}) < הפרשות נדרשות (${formatCurrency(severance.section_14_comparison.required_contributions_total)}). הפרש: ${formatCurrency(severance.section_14_comparison.difference)}`
          }
        />
      )}

      {/* Yearly details (collapsed by default) */}
      <Collapse defaultActiveKey={[]} items={yearItems} style={{ marginBottom: 16 }} />

      {/* Summary table */}
      <Table
        dataSource={summaryData}
        columns={summaryColumns}
        pagination={false}
        size="small"
        rowClassName={(record) => record.key === 'total' ? 'summary-total-row' : ''}
        style={{ background: 'rgba(78, 205, 196, 0.05)' }}
      />

      {/* OT Addition Collapse (cleaning industry only) */}
      {severance.ot_addition && (
        <Collapse
          defaultActiveKey={[]}
          style={{ marginTop: 12 }}
          items={[{
            key: 'ot',
            label: (
              <Space>
                <span>תוספת שעות נוספות לפיצויים — 6%</span>
                <Tag color="cyan">{formatCurrency(severance.ot_addition.total)}</Tag>
              </Space>
            ),
            children: (
              <Table
                dataSource={severance.ot_addition.monthly_detail.map((d, i) => ({ ...d, key: i }))}
                columns={[
                  {
                    title: <span style={{ color: '#88D8E0' }}>חודש</span>,
                    key: 'month',
                    render: (_: unknown, record: OtAdditionMonthlyDetail) => (
                      <span style={{ color: '#E8F4F8' }}>{formatMonth(record.month)}</span>
                    ),
                  },
                  {
                    title: <span style={{ color: '#88D8E0' }}>שע"נ חודשי ברוטו</span>,
                    key: 'full_ot',
                    render: (_: unknown, record: OtAdditionMonthlyDetail) => (
                      <span className="ltr-number" style={{ color: '#E8F4F8' }}>
                        {formatCurrency(record.full_ot_monthly_pay)}
                      </span>
                    ),
                  },
                  {
                    title: <span style={{ color: '#88D8E0' }}>היקף משרה</span>,
                    key: 'scope',
                    render: (_: unknown, record: OtAdditionMonthlyDetail) => (
                      <span style={{ color: '#E8F4F8' }}>{(record.job_scope * 100).toFixed(1)}%</span>
                    ),
                  },
                  {
                    title: <span style={{ color: '#88D8E0' }}>סכום</span>,
                    key: 'amount',
                    render: (_: unknown, record: OtAdditionMonthlyDetail) => (
                      <span className="ltr-number" style={{ color: '#4ECDC4', fontWeight: 'bold' }}>
                        {formatCurrency(record.amount)}
                      </span>
                    ),
                  },
                ]}
                pagination={false}
                size="small"
              />
            ),
          }]}
        />
      )}

      {/* Recreation Addition Collapse (cleaning industry only) */}
      {severance.recreation_addition && (
        <Collapse
          defaultActiveKey={[]}
          style={{ marginTop: 12 }}
          items={[{
            key: 'rec',
            label: (
              <Space>
                <span>תוספת הבראה לפיצויים — 8.333%</span>
                {!severance.recreation_addition.recreation_pending && (
                  <Tag color="cyan">{formatCurrency(severance.recreation_addition.total)}</Tag>
                )}
              </Space>
            ),
            children: severance.recreation_addition.recreation_pending ? (
              <Alert
                type="warning"
                showIcon
                message="הבראה טרם חושבה — הסכום יתעדכן אוטומטית"
              />
            ) : recreation ? (
              <Table
                dataSource={recreation.years.flatMap((year, yi) =>
                  year.segments.length <= 1
                    ? [{
                        key: `y${yi}`,
                        period: `שנה ${year.year_number} (${formatDate(year.year_start)}–${formatDate(year.year_end)})`,
                        entitled_days: year.entitled_days,
                        day_value: year.segments[0]?.day_value ?? 0,
                        weight: null as string | null,
                        amount: year.entitled_value,
                      }]
                    : year.segments.map((seg, si) => ({
                        key: `y${yi}s${si}`,
                        period: `שנה ${year.year_number} — ${formatDate(seg.segment_start)}–${formatDate(seg.segment_end)}`,
                        entitled_days: year.entitled_days,
                        day_value: seg.day_value,
                        weight: `${(seg.weight * 100).toFixed(1)}%`,
                        amount: seg.segment_value,
                      }))
                )}
                columns={[
                  {
                    title: <span style={{ color: '#88D8E0' }}>תקופה</span>,
                    dataIndex: 'period',
                    key: 'period',
                    render: (v: string) => <span style={{ color: '#E8F4F8' }}>{v}</span>,
                  },
                  {
                    title: <span style={{ color: '#88D8E0' }}>ימים מזכים</span>,
                    dataIndex: 'entitled_days',
                    key: 'days',
                    render: (v: number) => <span style={{ color: '#E8F4F8' }}>{v.toFixed(2)}</span>,
                  },
                  {
                    title: <span style={{ color: '#88D8E0' }}>ערך יום</span>,
                    dataIndex: 'day_value',
                    key: 'dv',
                    render: (v: number) => (
                      <span className="ltr-number" style={{ color: '#E8F4F8' }}>
                        {formatCurrency(v)}
                      </span>
                    ),
                  },
                  {
                    title: <span style={{ color: '#88D8E0' }}>משקל</span>,
                    dataIndex: 'weight',
                    key: 'wt',
                    render: (v: string | null) => (
                      <span style={{ color: '#88D8E0' }}>{v ?? '—'}</span>
                    ),
                  },
                  {
                    title: <span style={{ color: '#88D8E0' }}>סכום</span>,
                    dataIndex: 'amount',
                    key: 'amt',
                    render: (v: number) => (
                      <span className="ltr-number" style={{ color: '#4ECDC4', fontWeight: 'bold' }}>
                        {formatCurrency(v)}
                      </span>
                    ),
                  },
                ]}
                pagination={false}
                size="small"
              />
            ) : (
              <Alert type="info" showIcon message="נתוני הבראה לא זמינים" />
            ),
          }]}
        />
      )}
    </Card>
  );
};

// ============================================================================
// ו. RecreationBreakdown - פירוט דמי הבראה
// ============================================================================

const RECREATION_DAYS_TABLES: Record<string, { range: string; days: number }[]> = {
  general: [
    { range: '1', days: 5 },
    { range: '2–3', days: 6 },
    { range: '4–10', days: 7 },
    { range: '11–15', days: 8 },
    { range: '16–19', days: 9 },
    { range: '20+', days: 10 },
  ],
  construction: [
    { range: '1–2', days: 6 },
    { range: '3–4', days: 8 },
    { range: '5–10', days: 9 },
    { range: '11–15', days: 10 },
    { range: '16–19', days: 11 },
    { range: '20+', days: 12 },
  ],
  agriculture: [
    { range: '1–7', days: 7 },
    { range: '8', days: 8 },
    { range: '9', days: 9 },
    { range: '10+', days: 10 },
  ],
  cleaning: [
    { range: '1–3', days: 7 },
    { range: '4–10', days: 9 },
    { range: '11–15', days: 10 },
    { range: '16–19', days: 11 },
    { range: '20–24', days: 12 },
    { range: '25+', days: 13 },
  ],
};

interface RecreationBreakdownProps {
  recreation: RecreationResult;
  limitation?: LimitationRightResult;
  generalWindow?: LimitationWindow;
  filingDate?: string;
}

const RecreationBreakdown: React.FC<RecreationBreakdownProps> = ({ recreation, limitation, generalWindow, filingDate: _filingDate }) => {
  const [showDaysTable, setShowDaysTable] = useState(false);

  // Helper: check if a year is within the limitation window
  const isYearClaimable = (yearStart: string): boolean => {
    if (!generalWindow?.effective_window_start) return true;
    const windowStart = new Date(generalWindow.effective_window_start);
    const yearStartDate = new Date(yearStart);
    return yearStartDate >= windowStart;
  };

  const industryLabels: Record<string, string> = {
    general: 'כללי',
    construction: 'בניין',
    agriculture: 'חקלאות',
    cleaning: 'ניקיון',
  };

  // Get the recreation days table for the current industry
  const daysTable = RECREATION_DAYS_TABLES[recreation.industry] || RECREATION_DAYS_TABLES.general;

  // Get seniority values used in this case for highlighting
  const usedSeniorities = recreation.years.map(y => y.seniority_years);

  if (!recreation.entitled) {
    return (
      <Card
        title={
          <span>
            <GiftOutlined style={{ marginLeft: 8 }} />
            דמי הבראה
          </span>
        }
        size="small"
        style={{
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
          background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
        }}
      >
        <Alert
          type="warning"
          showIcon
          message={recreation.not_entitled_reason || 'לא זכאי לדמי הבראה'}
        />
      </Card>
    );
  }

  // Year details
  const yearColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: RecreationYearData) => (
        isYearClaimable(record.year_start)
          ? <Tooltip title="בתוך חלון ההתיישנות — ניתן לתבוע"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
          : <Tooltip title="מחוץ לחלון ההתיישנות — התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
      ),
    },
    { title: 'שנה', dataIndex: 'year_number', key: 'year_number', width: 60 },
    {
      title: 'תקופה',
      key: 'period',
      render: (_: unknown, record: RecreationYearData) => (
        <span>
          {formatDate(record.year_start)} – {formatDate(record.year_end)}
          {record.is_partial && <Tag color="orange" style={{ marginRight: 4 }}>חלקית</Tag>}
        </span>
      ),
    },
    { title: 'ותק', dataIndex: 'seniority_years', key: 'seniority', width: 60 },
    { title: 'ימי בסיס', dataIndex: 'base_days', key: 'base_days', width: 80 },
    {
      title: 'היקף',
      key: 'scope',
      width: 80,
      render: (_: unknown, record: RecreationYearData) => (
        <span>{(record.avg_scope * 100).toFixed(0)}%</span>
      ),
    },
    {
      title: 'ימים מזכים',
      key: 'entitled_days',
      width: 100,
      render: (_: unknown, record: RecreationYearData) => (
        <span className="ltr-number">{record.entitled_days.toFixed(2)}</span>
      ),
    },
    {
      title: 'שווי',
      key: 'entitled_value',
      width: 100,
      render: (_: unknown, record: RecreationYearData) => {
        const excluded = !isYearClaimable(record.year_start);
        return (
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : '#4ECDC4',
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(record.entitled_value)}
          </span>
        );
      },
    },
  ];

  // Expand row to show segments if more than one
  const expandedRowRender = (record: RecreationYearData) => {
    if (record.segments.length <= 1) return null;

    const segmentColumns = [
      {
        title: 'תקופה',
        key: 'period',
        render: (_: unknown, seg: RecreationDayValueSegment) => (
          <span>{formatDate(seg.segment_start)} – {formatDate(seg.segment_end)}</span>
        ),
      },
      {
        title: 'ערך יום',
        key: 'day_value',
        render: (_: unknown, seg: RecreationDayValueSegment) => (
          <span className="ltr-number">{formatCurrency(seg.day_value)}</span>
        ),
      },
      {
        title: 'משקל',
        key: 'weight',
        render: (_: unknown, seg: RecreationDayValueSegment) => (
          <span>{(seg.weight * 100).toFixed(1)}%</span>
        ),
      },
      {
        title: 'שווי',
        key: 'segment_value',
        render: (_: unknown, seg: RecreationDayValueSegment) => (
          <span className="ltr-number">{formatCurrency(seg.segment_value)}</span>
        ),
      },
    ];

    return (
      <Table
        dataSource={record.segments.map((s, i) => ({ ...s, key: i }))}
        columns={segmentColumns}
        pagination={false}
        size="small"
        style={{ margin: 0 }}
      />
    );
  };

  // Helper to check if seniority falls in range
  const seniorityInRange = (seniority: number, range: string): boolean => {
    if (range.includes('+')) {
      const min = parseInt(range.replace('+', ''));
      return seniority >= min;
    }
    if (range.includes('–')) {
      const [minStr, maxStr] = range.split('–');
      return seniority >= parseInt(minStr) && seniority <= parseInt(maxStr);
    }
    return seniority === parseInt(range);
  };

  return (
    <>
    <Card
      title={
        <Space>
          <span>
            <GiftOutlined style={{ marginLeft: 8 }} />
            דמי הבראה — {industryLabels[recreation.industry] || recreation.industry}
          </span>
          <Button size="small" onClick={() => setShowDaysTable(true)}>
            טבלת ימי הבראה ▾
          </Button>
        </Space>
      }
      size="small"
      style={{
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
      }}
    >
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic
            title="סה״כ ימים"
            value={recreation.grand_total_days.toFixed(2)}
            precision={2}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="שווי לפני התיישנות"
            value={recreation.grand_total_value}
            precision={2}
            prefix="₪"
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="שווי אחרי התיישנות"
            value={limitation?.claimable_amount ?? recreation.grand_total_value}
            precision={2}
            prefix="₪"
            valueStyle={{ color: '#52c41a' }}
          />
        </Col>
      </Row>

      {recreation.industry_fallback_used && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="הענף לא נמצא בטבלה — שימוש בטבלה כללית"
        />
      )}

      <Table
        dataSource={recreation.years.map(y => ({ ...y, key: y.year_number }))}
        columns={yearColumns}
        pagination={false}
        size="small"
        expandable={{
          expandedRowRender,
          rowExpandable: (record) => record.segments.length > 1,
        }}
        rowClassName={(record) => !isYearClaimable(record.year_start) ? 'row-excluded' : ''}
      />
    </Card>

    <Modal
      title={`טבלת ימי הבראה — ${industryLabels[recreation.industry] || recreation.industry}`}
      open={showDaysTable}
      onCancel={() => setShowDaysTable(false)}
      footer={null}
      width={400}
    >
      <Table
        dataSource={daysTable.map((row, i) => ({ ...row, key: i }))}
        columns={[
          {
            title: 'ותק (שנים שלמות)',
            dataIndex: 'range',
            key: 'range',
          },
          {
            title: 'ימי הבראה לשנה',
            dataIndex: 'days',
            key: 'days',
          },
        ]}
        rowClassName={(record) =>
          usedSeniorities.some(s => seniorityInRange(s, record.range))
            ? 'highlighted-row'
            : ''
        }
        pagination={false}
        size="small"
      />
    </Modal>
    </>
  );
};

// ============================================================================
// ז. PensionBreakdown - פירוט פנסיה
// ============================================================================

const PENSION_RATE_LABELS: Record<string, string> = {
  general: 'כללי (6.5%)',
  agriculture: 'חקלאות (6.5%)',
  cleaning: 'ניקיון (7.5%)',
  construction: 'בניין (6% / 7.1%)',
};

interface PensionBreakdownProps {
  pension: PensionResult;
  limitation?: LimitationRightResult;
  generalWindow?: LimitationWindow;
  filingDate?: string;
}

const PensionBreakdown: React.FC<PensionBreakdownProps> = ({ pension, limitation, generalWindow, filingDate: _filingDate }) => {
  const [expandedYears, setExpandedYears] = useState<number[]>([]);

  const industryLabels: Record<string, string> = {
    general: 'כללי',
    construction: 'בניין',
    agriculture: 'חקלאות',
    cleaning: 'ניקיון',
  };

  if (!pension.entitled) {
    return (
      <Card
        title={
          <span>
            <SafetyOutlined style={{ marginLeft: 8 }} />
            פנסיה
          </span>
        }
        size="small"
        style={{
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
          background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
        }}
      >
        <Alert
          type="warning"
          showIcon
          message="לא זכאי לפנסיה (הופעל ביטול)"
        />
      </Card>
    );
  }

  // Group months by year for collapsible display
  const monthsByYear: Record<number, PensionMonthData[]> = {};
  for (const m of pension.months) {
    const year = m.month[0];
    if (!monthsByYear[year]) monthsByYear[year] = [];
    monthsByYear[year].push(m);
  }
  const years = Object.keys(monthsByYear).map(Number).sort((a, b) => a - b);

  // Helper: check if a month is within the limitation window
  const isMonthClaimable = (month: [number, number]): boolean => {
    if (!generalWindow?.effective_window_start) return true;
    const windowStart = new Date(generalWindow.effective_window_start);
    const monthDate = new Date(month[0], month[1] - 1, 1);
    return monthDate >= windowStart;
  };

  // Helper: check if entire year is excluded (all months before limitation window)
  const isYearFullyExcluded = (year: number): boolean => {
    if (!generalWindow?.effective_window_start) return false;
    const yearMonths = monthsByYear[year] || [];
    return yearMonths.length > 0 && yearMonths.every(m => !isMonthClaimable(m.month));
  };

  // Calculate yearly summaries
  const yearSummaries = years.map(year => {
    const yearMonths = monthsByYear[year];
    const totalValue = yearMonths.reduce((sum, m) => sum + m.month_value, 0);
    const avgSalary = yearMonths.reduce((sum, m) => sum + m.salary_monthly, 0) / yearMonths.length;
    const avgRate = yearMonths.reduce((sum, m) => sum + m.pension_rate, 0) / yearMonths.length;
    return {
      year,
      monthsCount: yearMonths.length,
      totalValue,
      avgSalary,
      avgRate,
    };
  });

  // Month columns for expanded view
  const monthColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: PensionMonthData) => (
        isMonthClaimable(record.month)
          ? <Tooltip title="בתוך חלון ההתיישנות"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
          : <Tooltip title="התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
      ),
    },
    {
      title: 'חודש',
      key: 'month',
      width: 120,
      render: (_: unknown, record: PensionMonthData) => formatMonth(record.month),
    },
    {
      title: 'שכר חודשי',
      key: 'salary',
      width: 120,
      render: (_: unknown, record: PensionMonthData) => (
        <span className="ltr-number">{formatCurrency(record.salary_monthly)}</span>
      ),
    },
    {
      title: 'היקף משרה',
      key: 'scope',
      width: 80,
      render: (_: unknown, record: PensionMonthData) => (
        <span>{(record.job_scope * 100).toFixed(0)}%</span>
      ),
    },
    {
      title: 'שיעור',
      key: 'rate',
      width: 80,
      render: (_: unknown, record: PensionMonthData) => (
        <span>{(record.pension_rate * 100).toFixed(1)}%</span>
      ),
    },
    {
      title: 'שווי',
      key: 'value',
      width: 100,
      render: (_: unknown, record: PensionMonthData) => {
        const excluded = !isMonthClaimable(record.month);
        return (
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : '#4ECDC4',
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(record.month_value)}
          </span>
        );
      },
    },
  ];

  // Year columns for summary table
  const yearColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: typeof yearSummaries[0]) => (
        isYearFullyExcluded(record.year)
          ? <Tooltip title="מחוץ לחלון ההתיישנות — התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
          : <Tooltip title="בתוך חלון ההתיישנות — ניתן לתבוע"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
      ),
    },
    { title: 'שנה', dataIndex: 'year', key: 'year', width: 80 },
    { title: 'חודשים', dataIndex: 'monthsCount', key: 'months', width: 80 },
    {
      title: 'שיעור ממוצע',
      key: 'avgRate',
      width: 100,
      render: (_: unknown, record: typeof yearSummaries[0]) => (
        <span>{(record.avgRate * 100).toFixed(1)}%</span>
      ),
    },
    {
      title: 'שכר ממוצע',
      key: 'avgSalary',
      width: 120,
      render: (_: unknown, record: typeof yearSummaries[0]) => (
        <span className="ltr-number">{formatCurrency(record.avgSalary)}</span>
      ),
    },
    {
      title: 'שווי',
      key: 'totalValue',
      width: 120,
      render: (_: unknown, record: typeof yearSummaries[0]) => {
        const excluded = isYearFullyExcluded(record.year);
        return (
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : '#4ECDC4',
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(record.totalValue)}
          </span>
        );
      },
    },
  ];

  // Expandable row to show monthly breakdown
  const expandedRowRender = (record: typeof yearSummaries[0]) => {
    const yearMonths = monthsByYear[record.year];
    return (
      <Table
        dataSource={yearMonths.map((m, i) => ({ ...m, key: i }))}
        columns={monthColumns}
        pagination={false}
        size="small"
        style={{ margin: 0 }}
        rowClassName={(record) => !isMonthClaimable(record.month) ? 'row-excluded' : ''}
      />
    );
  };

  return (
    <Card
      title={
        <Space>
          <span>
            <SafetyOutlined style={{ marginLeft: 8 }} />
            פנסיה — {industryLabels[pension.industry] || pension.industry}
          </span>
          <Tag color="blue">{PENSION_RATE_LABELS[pension.industry] || pension.industry}</Tag>
        </Space>
      }
      size="small"
      style={{
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
      }}
    >
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic
            title="סה״כ חודשים"
            value={pension.months.length}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="שווי לפני התיישנות"
            value={pension.grand_total_value}
            precision={2}
            prefix="₪"
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="שווי אחרי התיישנות"
            value={limitation?.claimable_amount ?? pension.grand_total_value}
            precision={2}
            prefix="₪"
            valueStyle={{ color: '#52c41a' }}
          />
        </Col>
      </Row>

      <Table
        dataSource={yearSummaries.map(s => ({ ...s, key: s.year }))}
        columns={yearColumns}
        pagination={false}
        size="small"
        expandable={{
          expandedRowRender,
          rowExpandable: () => true,
          expandedRowKeys: expandedYears,
          onExpand: (expanded, record) => {
            setExpandedYears(expanded
              ? [...expandedYears, record.year]
              : expandedYears.filter(y => y !== record.year)
            );
          },
        }}
        rowClassName={(record) => isYearFullyExcluded(record.year) ? 'row-excluded' : ''}
      />
    </Card>
  );
};

// ============================================================================
// ז2. TrainingFundBreakdown - פירוט קרן השתלמות
// ============================================================================

const TRAINING_FUND_INDUSTRY_LABELS: Record<string, string> = {
  general: 'כללי',
  construction: 'בניין',
  cleaning: 'ניקיון',
  agriculture: 'חקלאות',
};

interface TrainingFundBreakdownProps {
  trainingFund: TrainingFundResult;
  limitation?: LimitationRightResult;
  generalWindow?: LimitationWindow;
  filingDate?: string;
}

const TrainingFundBreakdown: React.FC<TrainingFundBreakdownProps> = ({ trainingFund, limitation, generalWindow, filingDate: _filingDate }) => {
  const [expandedYears, setExpandedYears] = useState<number[]>([]);

  if (!trainingFund.eligible) {
    return (
      <Card
        title={
          <span>
            <BankOutlined style={{ marginLeft: 8 }} />
            קרן השתלמות
          </span>
        }
        size="small"
        style={{
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
          background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
        }}
      >
        <Alert
          type="warning"
          showIcon
          message={trainingFund.ineligible_reason || 'לא זכאי לקרן השתלמות'}
        />
      </Card>
    );
  }

  // Group months by year for collapsible display
  const monthsByYear: Record<number, TrainingFundMonthDetail[]> = {};
  for (const m of trainingFund.monthly_detail) {
    const year = m.month[0];
    if (!monthsByYear[year]) monthsByYear[year] = [];
    monthsByYear[year].push(m);
  }
  const years = Object.keys(monthsByYear).map(Number).sort((a, b) => a - b);

  // Helper: check if a month is within the limitation window
  const isMonthClaimable = (month: [number, number]): boolean => {
    if (!generalWindow?.effective_window_start) return true;
    const windowStart = new Date(generalWindow.effective_window_start);
    const monthDate = new Date(month[0], month[1] - 1, 1);
    return monthDate >= windowStart;
  };

  // Helper: check if entire year is excluded
  const isYearFullyExcluded = (year: number): boolean => {
    if (!generalWindow?.effective_window_start) return false;
    const yearMonths = monthsByYear[year] || [];
    return yearMonths.length > 0 && yearMonths.every(m => !isMonthClaimable(m.month));
  };

  // Helper to get effective rate from segments (weighted average)
  const getEffectiveRate = (m: TrainingFundMonthDetail): number => {
    if (!m.segments || m.segments.length === 0) return 0;
    if (m.segments.length === 1) return m.segments[0].employer_rate;
    // Weighted average by days
    const totalDays = m.segments.reduce((sum, s) => sum + s.days, 0);
    if (totalDays === 0) return 0;
    return m.segments.reduce((sum, s) => sum + s.employer_rate * s.days, 0) / totalDays;
  };

  // Calculate yearly summaries
  const yearSummaries = years.map(year => {
    const yearMonths = monthsByYear[year];
    const totalValue = yearMonths.reduce((sum, m) => sum + m.month_required, 0);
    const avgSalary = yearMonths.reduce((sum, m) => sum + m.salary_base, 0) / yearMonths.length;
    const avgRate = yearMonths.reduce((sum, m) => sum + getEffectiveRate(m), 0) / yearMonths.length;
    const eligibleCount = yearMonths.filter(m => m.eligible_this_month).length;
    const splitMonthCount = yearMonths.filter(m => m.is_split_month).length;
    return {
      year,
      monthsCount: yearMonths.length,
      eligibleCount,
      totalValue,
      avgSalary,
      avgRate,
      splitMonthCount,
    };
  });

  // Month columns for expanded view
  const monthColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: TrainingFundMonthDetail) => (
        isMonthClaimable(record.month)
          ? <Tooltip title="בתוך חלון ההתיישנות"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
          : <Tooltip title="התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
      ),
    },
    {
      title: 'חודש',
      key: 'month',
      width: 100,
      render: (_: unknown, record: TrainingFundMonthDetail) => (
        <Space>
          {formatMonth(record.month)}
          {record.is_split_month && <Tag color="orange" style={{ fontSize: 10 }}>חצוי</Tag>}
        </Space>
      ),
    },
    {
      title: 'שכר בסיס',
      key: 'salary',
      width: 110,
      render: (_: unknown, record: TrainingFundMonthDetail) => (
        <span className="ltr-number">{formatCurrency(record.salary_base)}</span>
      ),
    },
    {
      title: 'משקל',
      key: 'hours_weight',
      width: 70,
      render: (_: unknown, record: TrainingFundMonthDetail) => (
        <span>{(record.hours_weight * 100).toFixed(0)}%</span>
      ),
    },
    {
      title: 'שיעור',
      key: 'rate',
      width: 100,
      render: (_: unknown, record: TrainingFundMonthDetail) => {
        if (record.is_split_month && record.segments.length > 1) {
          // Show both rates for split months
          return (
            <Space direction="vertical" size={0} style={{ fontSize: 11 }}>
              {record.segments.map((seg, i) => (
                <span key={i}>
                  {seg.days}י׳: {(seg.employer_rate * 100).toFixed(1)}%
                </span>
              ))}
            </Space>
          );
        }
        const rate = record.segments[0]?.employer_rate ?? 0;
        return <span>{(rate * 100).toFixed(1)}%</span>;
      },
    },
    {
      title: 'ותק',
      key: 'seniority',
      width: 60,
      render: (_: unknown, record: TrainingFundMonthDetail) => (
        record.seniority_years !== null
          ? <span>{record.seniority_years.toFixed(1)}</span>
          : <span>—</span>
      ),
    },
    {
      title: 'זכאי',
      key: 'eligible',
      width: 60,
      render: (_: unknown, record: TrainingFundMonthDetail) => (
        record.eligible_this_month
          ? <Tag color="green">כן</Tag>
          : <Tag color="red">לא</Tag>
      ),
    },
    {
      title: 'נדרש',
      key: 'required',
      width: 100,
      render: (_: unknown, record: TrainingFundMonthDetail) => {
        const excluded = !isMonthClaimable(record.month);
        return (
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : '#4ECDC4',
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(record.month_required)}
          </span>
        );
      },
    },
  ];

  // Year columns for summary table
  const yearColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: typeof yearSummaries[0]) => (
        isYearFullyExcluded(record.year)
          ? <Tooltip title="מחוץ לחלון ההתיישנות — התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
          : <Tooltip title="בתוך חלון ההתיישנות — ניתן לתבוע"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
      ),
    },
    { title: 'שנה', dataIndex: 'year', key: 'year', width: 70 },
    { title: 'חודשים', dataIndex: 'monthsCount', key: 'months', width: 70 },
    { title: 'זכאים', dataIndex: 'eligibleCount', key: 'eligible', width: 70 },
    {
      title: 'שיעור ממוצע',
      key: 'avgRate',
      width: 90,
      render: (_: unknown, record: typeof yearSummaries[0]) => (
        <span>{(record.avgRate * 100).toFixed(1)}%</span>
      ),
    },
    {
      title: 'שכר ממוצע',
      key: 'avgSalary',
      width: 110,
      render: (_: unknown, record: typeof yearSummaries[0]) => (
        <span className="ltr-number">{formatCurrency(record.avgSalary)}</span>
      ),
    },
    {
      title: 'שווי',
      key: 'totalValue',
      width: 110,
      render: (_: unknown, record: typeof yearSummaries[0]) => {
        const excluded = isYearFullyExcluded(record.year);
        return (
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : '#4ECDC4',
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(record.totalValue)}
          </span>
        );
      },
    },
  ];

  // Expandable row to show monthly breakdown
  const expandedRowRender = (record: typeof yearSummaries[0]) => {
    const yearMonths = monthsByYear[record.year];
    return (
      <Table
        dataSource={yearMonths.map((m, i) => ({ ...m, key: i }))}
        columns={monthColumns}
        pagination={false}
        size="small"
        style={{ margin: 0 }}
        rowClassName={(record) => !isMonthClaimable(record.month) ? 'row-excluded' : (!record.eligible_this_month ? 'row-disabled' : '')}
      />
    );
  };

  // Build title with tags
  const titleTags = [];
  if (trainingFund.is_construction_foreman) {
    titleTags.push(<Tag key="foreman" color="purple">מנהל עבודה</Tag>);
  }
  if (trainingFund.used_custom_tiers) {
    titleTags.push(<Tag key="custom" color="orange">חוזה אישי</Tag>);
  }
  if (trainingFund.recreation_pending) {
    titleTags.push(<Tag key="pending" color="gold">ממתין להבראה</Tag>);
  }

  return (
    <Card
      title={
        <Space>
          <span>
            <BankOutlined style={{ marginLeft: 8 }} />
            קרן השתלמות — {TRAINING_FUND_INDUSTRY_LABELS[trainingFund.industry] || trainingFund.industry}
          </span>
          {titleTags}
        </Space>
      }
      size="small"
      style={{
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
      }}
    >
      {trainingFund.recreation_pending && (
        <Alert
          type="info"
          showIcon
          message="הסכום יעודכן לאחר חישוב הבראה"
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Statistic
            title="סה״כ חודשים"
            value={trainingFund.monthly_detail.length}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="סה״כ נדרש"
            value={trainingFund.required_total}
            precision={2}
            prefix="₪"
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="הפרשות בפועל"
            value={trainingFund.actual_deposits}
            precision={2}
            prefix="₪"
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="אחרי התיישנות"
            value={limitation?.claimable_amount ?? trainingFund.claim_before_deductions}
            precision={2}
            prefix="₪"
            valueStyle={{ color: '#52c41a' }}
          />
        </Col>
      </Row>

      <Table
        dataSource={yearSummaries.map(s => ({ ...s, key: s.year }))}
        columns={yearColumns}
        pagination={false}
        size="small"
        expandable={{
          expandedRowRender,
          rowExpandable: () => true,
          expandedRowKeys: expandedYears,
          onExpand: (expanded, record) => {
            setExpandedYears(expanded
              ? [...expandedYears, record.year]
              : expandedYears.filter(y => y !== record.year)
            );
          },
        }}
        rowClassName={(record) => isYearFullyExcluded(record.year) ? 'row-excluded' : ''}
      />
    </Card>
  );
};

// ============================================================================
// ח. VacationBreakdown - פירוט חופשה שנתית
// ============================================================================

const VACATION_DAYS_TABLES: Record<string, { range: string; five_day: number; six_day: number }[]> = {
  general: [
    { range: '1–5',  five_day: 12, six_day: 14 },
    { range: '6',    five_day: 14, six_day: 16 },
    { range: '7',    five_day: 15, six_day: 18 },
    { range: '8',    five_day: 16, six_day: 19 },
    { range: '9',    five_day: 17, six_day: 20 },
    { range: '10',   five_day: 18, six_day: 21 },
    { range: '11',   five_day: 19, six_day: 22 },
    { range: '12',   five_day: 20, six_day: 23 },
    { range: '13+',  five_day: 20, six_day: 24 },
  ],
  construction: [
    { range: '1–2',  five_day: 10, six_day: 12 },
    { range: '3',    five_day: 11, six_day: 13 },
    { range: '4',    five_day: 14, six_day: 16 },
    { range: '5',    five_day: 15, six_day: 18 },
    { range: '6–7',  five_day: 17, six_day: 19 },
    { range: '8',    five_day: 17, six_day: 19 },
    { range: '9+',   five_day: 23, six_day: 26 },
  ],
  construction_55plus: [
    { range: '11+',  five_day: 24, six_day: 28 },
  ],
  agriculture: [
    { range: '1–3',  five_day: 12, six_day: 12 },
    { range: '4–6',  five_day: 16, six_day: 16 },
    { range: '7–9',  five_day: 20, six_day: 20 },
    { range: '10',   five_day: 24, six_day: 24 },
    { range: '11+',  five_day: 26, six_day: 26 },
  ],
  cleaning: [
    { range: '1–2',  five_day: 10, six_day: 12 },
    { range: '3–4',  five_day: 11, six_day: 13 },
    { range: '5',    five_day: 13, six_day: 15 },
    { range: '6',    five_day: 18, six_day: 20 },
    { range: '7–8',  five_day: 19, six_day: 21 },
    { range: '9+',   five_day: 23, six_day: 26 },
  ],
};

// ====== Travel Breakdown ======

interface TravelBreakdownProps {
  travel: TravelResult;
  limitation?: LimitationRightResult;
  generalWindow?: LimitationWindow;
}

const TravelBreakdown: React.FC<TravelBreakdownProps> = ({ travel, limitation, generalWindow }) => {
  const industryLabels: Record<string, string> = {
    general: 'כללי',
    construction: 'בניין',
    agriculture: 'חקלאות',
    cleaning: 'ניקיון',
  };

  // Helper: check if a month is within the limitation window
  const isMonthClaimable = (month: [number, number]): boolean => {
    if (!generalWindow?.effective_window_start) return true;
    const windowStart = new Date(generalWindow.effective_window_start);
    const monthStart = new Date(month[0], month[1] - 1, 1);
    return monthStart >= windowStart;
  };

  // Get lodging description
  const getLodgingDescription = (): string => {
    return travel.has_lodging ? 'עם לינה באתר' : 'ללא לינה';
  };

  const monthColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: TravelMonthlyBreakdown) => (
        isMonthClaimable(record.month)
          ? <Tooltip title="בתוך חלון ההתיישנות — ניתן לתבוע"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
          : <Tooltip title="מחוץ לחלון ההתיישנות — התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>חודש</span>,
      key: 'month',
      render: (_: unknown, record: TravelMonthlyBreakdown) => (
        <span style={{ color: '#E8F4F8' }}>{formatMonth(record.month)}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>ימי נסיעה</span>,
      key: 'travel_days',
      render: (_: unknown, record: TravelMonthlyBreakdown) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>{record.travel_days}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>סכום</span>,
      key: 'amount',
      render: (_: unknown, record: TravelMonthlyBreakdown) => {
        const excluded = !isMonthClaimable(record.month);
        return (
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : '#4ECDC4',
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(record.claim_amount)}
          </span>
        );
      },
    },
  ];

  return (
    <Card
      title={
        <Space>
          <span>
            <CarOutlined style={{ marginLeft: 8 }} />
            דמי נסיעות — {industryLabels[travel.industry] || travel.industry}
          </span>
        </Space>
      }
      size="small"
      style={{
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
      }}
    >
      {/* Summary Statistics */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic
            title={<span style={{ color: '#88D8E0' }}>סה״כ זכאות</span>}
            value={travel.grand_total_value}
            precision={2}
            suffix="₪"
            valueStyle={{ color: '#4ECDC4', fontWeight: 'bold' }}
          />
          <div style={{ fontSize: 12, color: '#88D8E0', marginTop: 4 }}>
            סה״כ ימי נסיעה: <span dir="ltr">{travel.grand_total_travel_days}</span>
          </div>
        </Col>
        <Col span={8}>
          <Statistic
            title={<span style={{ color: '#88D8E0' }}>תעריף יומי</span>}
            value={travel.daily_rate}
            precision={2}
            suffix="₪"
            valueStyle={{ color: '#E8F4F8' }}
          />
        </Col>
        {limitation && (
          <Col span={8}>
            <Statistic
              title={<span style={{ color: '#88D8E0' }}>לאחר התיישנות</span>}
              value={limitation.claimable_amount || 0}
              precision={2}
              suffix="₪"
              valueStyle={{ color: '#FFD93D' }}
            />
            {limitation.excluded_amount !== undefined && limitation.excluded_amount > 0 && (
              <div style={{ fontSize: 12, color: '#FF6B6B', marginTop: 4 }}>
                התיישן: <span dir="ltr">{formatCurrency(limitation.excluded_amount)}</span>
              </div>
            )}
          </Col>
        )}
      </Row>

      {/* Construction info row */}
      {travel.industry === 'construction' && (
        <div style={{
          padding: '8px 12px',
          background: 'rgba(78, 205, 196, 0.1)',
          borderRadius: 6,
          marginBottom: 16,
          fontSize: 13,
        }}>
          <Space split={<Divider type="vertical" />}>
            <span>תעריף: <strong dir="ltr">{travel.daily_rate} ₪</strong>/יום</span>
            {travel.distance_km !== null && (
              <span>מרחק: <strong>{travel.distance_km >= 40 ? '40 ק״מ ומעלה' : 'מתחת ל-40 ק״מ'}</strong></span>
            )}
            <span>{getLodgingDescription()}</span>
          </Space>
        </div>
      )}

      {/* Monthly breakdown */}
      <Collapse
        size="small"
        items={[
          {
            key: 'monthly',
            label: <span style={{ fontWeight: 500 }}>פירוט חודשי</span>,
            children: (
              <Table
                dataSource={travel.monthly_breakdown.map((m, i) => ({ ...m, key: i }))}
                columns={monthColumns}
                pagination={false}
                size="small"
                style={{ marginTop: 8 }}
              />
            ),
          },
        ]}
      />
    </Card>
  );
};

// ====== Meal Allowance Breakdown ======

interface MealAllowanceBreakdownProps {
  mealAllowance: MealAllowanceResult;
  limitation?: LimitationRightResult;
  generalWindow?: LimitationWindow;
}

const MealAllowanceBreakdown: React.FC<MealAllowanceBreakdownProps> = ({ mealAllowance, limitation, generalWindow }) => {
  // Helper: check if a month is within the limitation window
  const isMonthClaimable = (month: [number, number]): boolean => {
    if (!generalWindow?.effective_window_start) return true;
    const windowStart = new Date(generalWindow.effective_window_start);
    const monthStart = new Date(month[0], month[1] - 1, 1);
    return monthStart >= windowStart;
  };

  const monthColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: MealAllowanceMonthlyBreakdown) => (
        isMonthClaimable(record.month)
          ? <Tooltip title="בתוך חלון ההתיישנות — ניתן לתבוע"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
          : <Tooltip title="מחוץ לחלון ההתיישנות — התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>חודש</span>,
      key: 'month',
      render: (_: unknown, record: MealAllowanceMonthlyBreakdown) => (
        <span style={{ color: '#E8F4F8' }}>{formatMonth(record.month)}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>לילות</span>,
      key: 'nights',
      render: (_: unknown, record: MealAllowanceMonthlyBreakdown) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>{record.nights.toFixed(1)}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>תעריף</span>,
      key: 'rate',
      render: (_: unknown, record: MealAllowanceMonthlyBreakdown) => (
        <span className="ltr-number" style={{ color: '#E8F4F8' }}>{formatCurrency(record.nightly_rate)}</span>
      ),
    },
    {
      title: <span style={{ color: '#88D8E0' }}>סכום</span>,
      key: 'amount',
      render: (_: unknown, record: MealAllowanceMonthlyBreakdown) => {
        const excluded = !isMonthClaimable(record.month);
        return (
          <span
            className="ltr-number"
            style={{
              color: excluded ? '#888' : '#4ECDC4',
              textDecoration: excluded ? 'line-through' : 'none',
            }}
          >
            {formatCurrency(record.claim_amount)}
          </span>
        );
      },
    },
  ];

  if (!mealAllowance.entitled) {
    return (
      <Card
        title={
          <span>
            <GiftOutlined style={{ marginLeft: 8 }} />
            אש״ל (לינה באתר)
          </span>
        }
        size="small"
        style={{
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
          background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
        }}
      >
        <Alert
          type="warning"
          showIcon
          message={
            mealAllowance.not_entitled_reason === 'not_construction'
              ? 'אש״ל מגיע רק לעובדי בניין'
              : mealAllowance.not_entitled_reason === 'no_lodging_input'
                ? 'לא הוזנו תקופות לינה'
                : 'הזכות מושבתת'
          }
        />
      </Card>
    );
  }

  return (
    <Card
      title={
        <Space>
          <span>
            <GiftOutlined style={{ marginLeft: 8 }} />
            אש״ל (לינה באתר)
          </span>
        </Space>
      }
      size="small"
      style={{
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
      }}
    >
      {/* Summary Statistics */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic
            title={<span style={{ color: '#88D8E0' }}>סה״כ לילות</span>}
            value={mealAllowance.grand_total_nights}
            precision={1}
            valueStyle={{ color: '#E8F4F8' }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title={<span style={{ color: '#88D8E0' }}>שווי לפני התיישנות</span>}
            value={mealAllowance.grand_total_value}
            precision={2}
            suffix="₪"
            valueStyle={{ color: '#4ECDC4', fontWeight: 'bold' }}
          />
        </Col>
        {limitation && (
          <Col span={8}>
            <Statistic
              title={<span style={{ color: '#88D8E0' }}>לאחר התיישנות</span>}
              value={limitation.claimable_amount || 0}
              precision={2}
              suffix="₪"
              valueStyle={{ color: '#FFD93D' }}
            />
            {limitation.excluded_amount !== undefined && limitation.excluded_amount > 0 && (
              <div style={{ fontSize: 12, color: '#FF6B6B', marginTop: 4 }}>
                התיישן: <span dir="ltr">{formatCurrency(limitation.excluded_amount)}</span>
              </div>
            )}
          </Col>
        )}
      </Row>

      {/* Monthly breakdown */}
      <Collapse
        size="small"
        items={[
          {
            key: 'monthly',
            label: <span style={{ fontWeight: 500 }}>פירוט חודשי</span>,
            children: (
              <Table
                dataSource={mealAllowance.monthly_breakdown.map((m, i) => ({ ...m, key: i }))}
                columns={monthColumns}
                pagination={false}
                size="small"
                style={{ marginTop: 8 }}
                rowClassName={(record) => !isMonthClaimable(record.month) ? 'row-excluded' : ''}
              />
            ),
          },
        ]}
      />
    </Card>
  );
};

interface VacationBreakdownProps {
  vacation: VacationResult;
  limitation?: LimitationRightResult;
  vacationWindow?: LimitationWindow;
  filingDate?: string;
}

const VacationBreakdown: React.FC<VacationBreakdownProps> = ({ vacation, limitation, vacationWindow, filingDate }) => {
  const [showDaysTable, setShowDaysTable] = useState(false);

  const industryLabels: Record<string, string> = {
    general: 'כללי',
    construction: 'בניין',
  };

  const seniorityBasisLabels: Record<string, string> = {
    employer: 'אצל המעסיק',
    industry: 'ענפי',
  };

  const weekTypeLabels: Record<string, string> = {
    five_day: '5 ימים',
    six_day: '6 ימים',
  };

  // Get the vacation days table for the current industry
  const daysTable = VACATION_DAYS_TABLES[vacation.industry] || VACATION_DAYS_TABLES.general;

  // Get seniority values used in this case for highlighting
  const usedSeniorities = vacation.years.map(y => y.seniority_years);

  // Check if any year uses 55+ table (for construction)
  const has55Plus = vacation.years.some(y => y.is_55_plus || y.age_55_split);

  // Check if a year is claimable (within limitation window) - uses backend-computed claimable_fraction
  const isYearClaimable = (year: VacationYearData): boolean => {
    if (year.claimable_fraction === null || year.claimable_fraction === undefined) return true;
    return year.claimable_fraction > 0;
  };

  // Check if a year is partially claimable (split by limitation boundary)
  const isYearPartiallyClaimable = (year: VacationYearData): boolean => {
    const f = year.claimable_fraction;
    return f != null && f > 0 && f < 1;
  };

  if (!vacation.entitled) {
    return (
      <Card
        title={
          <span>
            <CalendarOutlined style={{ marginLeft: 8 }} />
            חופשה שנתית
          </span>
        }
        size="small"
        style={{
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
          background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
        }}
      >
        <Alert
          type="warning"
          showIcon
          message="לא זכאי לחופשה שנתית"
        />
      </Card>
    );
  }

  // Year columns
  const yearColumns = [
    {
      title: '',
      key: 'status',
      width: 32,
      render: (_: unknown, record: VacationYearData) => (
        isYearClaimable(record)
          ? <Tooltip title="בתוך חלון ההתיישנות — ניתן לתבוע"><CheckCircleOutlined style={{ color: '#4ECDC4' }} /></Tooltip>
          : <Tooltip title="מחוץ לחלון ההתיישנות — התיישן"><ClockCircleOutlined style={{ color: '#FF6B6B' }} /></Tooltip>
      ),
    },
    { title: 'שנה', dataIndex: 'year', key: 'year', width: 60 },
    {
      title: 'תקופה',
      key: 'period',
      render: (_: unknown, record: VacationYearData) => (
        <span>
          {formatDate(record.year_start)} – {formatDate(record.year_end)}
          {record.is_partial && (
            <Tooltip title={record.partial_description}>
              <Tag color="orange" style={{ marginRight: 4 }}>שנה חלקית</Tag>
            </Tooltip>
          )}
          {(record.is_55_plus || record.age_55_split) && (
            <Tooltip title={record.age_55_split ? 'פיצול לפי גיל 55 באמצע השנה' : 'כל השנה חושבה לפי טבלת גיל 55+'}>
              <Tag color="purple" style={{ marginRight: 4 }}>גיל 55+</Tag>
            </Tooltip>
          )}
        </span>
      ),
    },
    { title: 'ותק', dataIndex: 'seniority_years', key: 'seniority', width: 60 },
    {
      title: 'בסיס ימים',
      key: 'weighted_base_days',
      width: 90,
      render: (_: unknown, record: VacationYearData) => (
        <span className="ltr-number">{record.weighted_base_days.toFixed(2)}</span>
      ),
    },
    {
      title: 'ימים מזכים',
      key: 'entitled_days',
      width: 100,
      render: (_: unknown, record: VacationYearData) => (
        <span className="ltr-number">{record.entitled_days.toFixed(2)}</span>
      ),
    },
    {
      title: 'שכר יומי',
      key: 'avg_daily_salary',
      width: 100,
      render: (_: unknown, record: VacationYearData) => (
        <span className="ltr-number">{formatCurrency(record.avg_daily_salary)}</span>
      ),
    },
    {
      title: 'שווי',
      key: 'year_value',
      width: 120,
      render: (_: unknown, record: VacationYearData) => {
        const excluded = !isYearClaimable(record);
        const partial = isYearPartiallyClaimable(record);
        const claimableValue = record.claimable_fraction != null
          ? record.year_value * record.claimable_fraction
          : record.year_value;

        return (
          <span>
            {partial && (
              <Tooltip title={`חלק יחסי: ${(record.claimable_fraction! * 100).toFixed(1)}% מהשנה בתוך החלון`}>
                <span className="ltr-number" style={{ color: '#FFD93D' }}>
                  {formatCurrency(claimableValue)}
                </span>
                <span className="ltr-number" style={{ color: '#888', textDecoration: 'line-through', marginRight: 4, fontSize: 11 }}>
                  {formatCurrency(record.year_value)}
                </span>
              </Tooltip>
            )}
            {!partial && (
              <span
                className="ltr-number"
                style={{
                  color: excluded ? '#888' : '#4ECDC4',
                  textDecoration: excluded ? 'line-through' : 'none',
                }}
              >
                {formatCurrency(record.year_value)}
              </span>
            )}
          </span>
        );
      },
    },
  ];

  // Expand row to show week type segments if more than one
  const expandedRowRender = (record: VacationYearData) => {
    if (record.week_type_segments.length <= 1) return null;

    const segmentColumns = [
      {
        title: 'תקופה',
        key: 'period',
        render: (_: unknown, seg: VacationWeekTypeSegment) => (
          <span>{formatDate(seg.segment_start)} – {formatDate(seg.segment_end)}</span>
        ),
      },
      {
        title: 'סוג שבוע',
        key: 'week_type',
        render: (_: unknown, seg: VacationWeekTypeSegment) => (
          <Tag color={seg.week_type === 'five_day' ? 'blue' : 'green'}>
            {weekTypeLabels[seg.week_type] || seg.week_type}
          </Tag>
        ),
      },
      {
        title: 'משקל',
        key: 'weight',
        render: (_: unknown, seg: VacationWeekTypeSegment) => (
          <span>{(seg.weight * 100).toFixed(1)}%</span>
        ),
      },
      {
        title: 'ימי בסיס',
        key: 'base_days',
        dataIndex: 'base_days',
      },
      {
        title: 'ימים משוקללים',
        key: 'weighted_days',
        render: (_: unknown, seg: VacationWeekTypeSegment) => (
          <span className="ltr-number">{seg.weighted_days.toFixed(2)}</span>
        ),
      },
    ];

    return (
      <Table
        dataSource={record.week_type_segments.map((s, i) => ({ ...s, key: i }))}
        columns={segmentColumns}
        pagination={false}
        size="small"
        style={{ margin: 0 }}
      />
    );
  };

  // Helper to check if seniority falls in range
  const seniorityInRange = (seniority: number, range: string): boolean => {
    if (range.includes('+')) {
      const min = parseInt(range.replace('+', ''));
      return seniority >= min;
    }
    if (range.includes('–')) {
      const [minStr, maxStr] = range.split('–');
      return seniority >= parseInt(minStr) && seniority <= parseInt(maxStr);
    }
    return seniority === parseInt(range);
  };

  return (
    <>
    <Card
      title={
        <Space>
          <span>
            <CalendarOutlined style={{ marginLeft: 8 }} />
            חופשה שנתית — {industryLabels[vacation.industry] || vacation.industry}
            {vacation.seniority_basis && (
              <Tag color="cyan" style={{ marginRight: 8 }}>
                ותק {seniorityBasisLabels[vacation.seniority_basis] || vacation.seniority_basis}
              </Tag>
            )}
          </span>
          <Button size="small" onClick={() => setShowDaysTable(true)}>
            טבלת ימי חופשה ▾
          </Button>
        </Space>
      }
      size="small"
      style={{
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
        background: 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
      }}
    >
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic
            title="סה״כ ימים"
            value={vacation.years.reduce((sum, y) => sum + y.entitled_days * (y.claimable_fraction ?? 1), 0).toFixed(2)}
            precision={2}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="שווי לפני התיישנות"
            value={vacation.grand_total_value}
            precision={2}
            prefix="₪"
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="שווי אחרי התיישנות"
            value={limitation?.claimable_amount ?? vacation.grand_total_value}
            precision={2}
            prefix="₪"
            valueStyle={{ color: '#52c41a' }}
          />
        </Col>
      </Row>

      <Table
        dataSource={vacation.years.map(y => ({ ...y, key: y.year }))}
        columns={yearColumns}
        pagination={false}
        size="small"
        expandable={{
          expandedRowRender,
          rowExpandable: (record) => record.week_type_segments.length > 1,
        }}
        rowClassName={(record) => isYearClaimable(record) ? '' : 'vacation-year-excluded'}
      />

      {/* פאנל התיישנות חופשה */}
      {limitation && vacationWindow && (
        <div style={{
          marginTop: 16, padding: '16px',
          background: 'rgba(78,205,196,0.06)',
          borderRadius: 8, border: '1px solid rgba(78,205,196,0.2)',
        }}>
          <Text strong style={{ color: '#88D8E0', display: 'block', marginBottom: 12, fontSize: 15 }}>
            התיישנות חופשה — 3 שנים + שוטף
          </Text>

          {/* שורת מידע ראשית */}
          <Row gutter={[16, 8]} style={{ marginBottom: 12 }}>
            <Col span={12}>
              <div style={{ padding: '8px 12px', background: 'rgba(255,107,107,0.08)', borderRadius: 6, border: '1px solid rgba(255,107,107,0.2)' }}>
                <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>תאריך הגשת תביעה</Text>
                <Text strong className="ltr-number" style={{ fontSize: 14 }}>
                  {filingDate ? formatDate(filingDate) : '—'}
                </Text>
              </div>
            </Col>
            <Col span={12}>
              <div style={{ padding: '8px 12px', background: 'rgba(78,205,196,0.1)', borderRadius: 6, border: '1px solid rgba(78,205,196,0.3)' }}>
                <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>ניתן לתבוע חופשה החל מתאריך:</Text>
                <Text strong className="ltr-number" style={{ fontSize: 16, color: '#4ECDC4' }}>
                  {formatDate(vacationWindow.effective_window_start)}
                </Text>
                {vacationWindow.base_window_start !== vacationWindow.effective_window_start && (
                  <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                    חלון בסיסי {formatDate(vacationWindow.base_window_start)} | הורחב בשל הקפאות
                  </Text>
                )}
              </div>
            </Col>
          </Row>

          {/* מספרים */}
          <Row gutter={16}>
            <Col span={6}>
              <Statistic
                title="תקופה בת-תביעה"
                value={limitation.claimable_duration?.display ?? '—'}
                valueStyle={{ color: '#4ECDC4', fontSize: 13 }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="שנים שהתיישנו"
                value={vacation.years.filter(y => (y.claimable_fraction ?? 1) === 0).length}
                formatter={(val) => (
                  <span>
                    מתוך {vacation.years.length} שנים התיישנו {val}
                  </span>
                )}
                valueStyle={{ fontSize: 13 }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="שווי שהתיישן"
                value={limitation.excluded_amount ?? 0}
                precision={2}
                prefix="₪"
                valueStyle={{ color: '#FF6B6B', fontSize: 13 }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="שווי בר-תביעה"
                value={limitation.claimable_amount ?? vacation.grand_total_value}
                precision={2}
                prefix="₪"
                valueStyle={{ color: '#52c41a', fontSize: 13 }}
              />
            </Col>
          </Row>
        </div>
      )}
    </Card>

    <Modal
      title={`טבלת ימי חופשה — ${industryLabels[vacation.industry] || vacation.industry}`}
      open={showDaysTable}
      onCancel={() => setShowDaysTable(false)}
      footer={null}
      width={500}
    >
      <Table
        dataSource={daysTable.map((row, i) => ({ ...row, key: i }))}
        columns={[
          {
            title: 'ותק (שנים שלמות)',
            dataIndex: 'range',
            key: 'range',
          },
          {
            title: 'שבוע 5 ימים',
            dataIndex: 'five_day',
            key: 'five_day',
          },
          {
            title: 'שבוע 6 ימים',
            dataIndex: 'six_day',
            key: 'six_day',
          },
        ]}
        rowClassName={(record) =>
          usedSeniorities.some(s => seniorityInRange(s, record.range))
            ? 'highlighted-row'
            : ''
        }
        pagination={false}
        size="small"
      />
      {vacation.industry === 'construction' && has55Plus && (
        <>
          <Divider />
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            טבלת גיל 55+ (ותק 11 ומעלה)
          </Text>
          <Table
            dataSource={VACATION_DAYS_TABLES.construction_55plus.map((row, i) => ({ ...row, key: i }))}
            columns={[
              { title: 'ותק (שנים שלמות)', dataIndex: 'range', key: 'range' },
              { title: 'שבוע 5 ימים', dataIndex: 'five_day', key: 'five_day' },
              { title: 'שבוע 6 ימים', dataIndex: 'six_day', key: 'six_day' },
            ]}
            pagination={false}
            size="small"
            rowClassName={(row) => {
              const sen = vacation.years.find(y => y.is_55_plus || y.age_55_split)?.seniority_years ?? 0;
              return seniorityInRange(sen, row.range) ? 'highlighted-row' : '';
            }}
          />
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            * חל על עובדי בנייה שהגיעו לגיל 55 עם ותק ענפי 11 שנים ומעלה
          </Text>
        </>
      )}
    </Modal>
    </>
  );
};

// ============================================================================
// ח. LimitationTimeline - התיישנות
// ============================================================================

const LimitationTimeline: React.FC<{ limitation: LimitationResults }> = ({ limitation }) => {
  const { windows, timeline_data, per_right } = limitation;
  const summary = timeline_data?.summary;

  // Get claimable_duration display from general limitation (or first available)
  const claimableDurationDisplay = per_right?.general?.claimable_duration?.display
    || Object.values(per_right || {})[0]?.claimable_duration?.display
    || '';

  // Per-window claimable percent
  const getWindowPercent = (window: LimitationWindow) => {
    if (!summary?.total_employment_days) return 0;
    const isVacation = window.type_id === 'vacation';
    const claimableDays = isVacation
      ? (summary.claimable_days_vacation ?? summary.claimable_days_general)
      : summary.claimable_days_general;
    return Math.round((claimableDays / summary.total_employment_days) * 100);
  };

  return (
    <Card
      title={
        <Space>
          <StopOutlined />
          <span>התיישנות</span>
        </Space>
      }
      className="results-card"
    >
      {/* Summary stats */}
      {summary && (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Statistic title="ימי העסקה" value={summary.total_employment_days} />
          </Col>
          <Col span={6}>
            <Statistic
              title="ימים שלא התיישנו"
              value={summary.claimable_days_general}
              valueStyle={{ color: '#4ECDC4' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="ימים שהתיישנו"
              value={summary.excluded_days_general}
              valueStyle={{ color: '#FF6B6B' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="ימי הקפאה"
              value={summary.total_freeze_days}
              valueStyle={{ color: '#FFD93D' }}
            />
          </Col>
        </Row>
      )}

      {/* Claimable duration display */}
      {claimableDurationDisplay && (
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">סך התקופה שלא התיישנה: </Text>
          <Text strong style={{ color: '#4ECDC4' }}>{claimableDurationDisplay}</Text>
        </div>
      )}

      {/* Windows - only general, vacation is displayed in VacationBreakdown */}
      {windows.filter(w => w.type_id !== 'vacation').map((window, idx) => {
        const pct = getWindowPercent(window);
        return (
        <div key={idx} style={{ marginBottom: 16 }}>
          <Text strong>{window.type_name}</Text>
          <Progress
            percent={pct}
            strokeColor="#4ECDC4"
            trailColor="rgba(255, 107, 107, 0.3)"
            format={() => `${pct}% לא התיישן`}
          />
          <Row gutter={16} style={{ marginTop: 8 }}>
            <Col span={24}>
              <Text type="secondary">תאריך הגשת תביעה: </Text>
              <span className="ltr-number">{formatDate(timeline_data?.filing_date)}</span>
            </Col>
          </Row>
          <Row gutter={16} style={{ marginTop: 8 }}>
            <Col span={12}>
              <Text type="secondary">חלון בסיסי: </Text>
              <span className="ltr-number">{formatDate(window.base_window_start)}</span>
            </Col>
            {window.base_window_start !== window.effective_window_start && (
              <Col span={12}>
                <Text type="secondary">חלון אפקטיבי: </Text>
                <span className="ltr-number" style={{ color: '#4ECDC4' }}>
                  {formatDate(window.effective_window_start)}
                </span>
              </Col>
            )}
          </Row>

          {/* Freeze periods */}
          {window.freeze_periods_applied?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Text type="secondary">תקופות הקפאה: </Text>
              {window.freeze_periods_applied.map((freeze, fidx) => (
                <Tag key={fidx} color="gold" style={{ marginTop: 4 }}>
                  {freeze.name}: {formatDate(freeze.start_date)} - {formatDate(freeze.end_date)} ({freeze.days} ימים)
                </Tag>
              ))}
            </div>
          )}
        </div>
      ); })}
    </Card>
  );
};

// ============================================================================
// ו. EmploymentDetails - פרטי העסקה
// ============================================================================

const EmploymentDetails: React.FC<{
  employment?: TotalEmployment;
  seniority?: SeniorityTotals;
}> = ({ employment, seniority }) => {
  return (
    <Card
      title={
        <Space>
          <UserOutlined />
          <span>פרטי העסקה וותק</span>
        </Space>
      }
      className="results-card"
    >
      <Row gutter={[24, 16]}>
        {/* Employment */}
        {employment && (
          <>
            <Col span={6}>
              <Text type="secondary">יום ראשון:</Text>
              <div className="ltr-number">{formatDate(employment.first_day)}</div>
            </Col>
            <Col span={6}>
              <Text type="secondary">יום אחרון:</Text>
              <div className="ltr-number">{formatDate(employment.last_day)}</div>
            </Col>
            <Col span={6}>
              <Text type="secondary">משך כולל:</Text>
              <div>{employment.total_duration?.display || '-'}</div>
            </Col>
            <Col span={6}>
              <Text type="secondary">משך עבודה בפועל:</Text>
              <div>{employment.worked_duration?.display || '-'}</div>
            </Col>
            {employment.gaps_count > 0 && (
              <>
                <Col span={6}>
                  <Text type="secondary">תקופות:</Text>
                  <div>{employment.periods_count}</div>
                </Col>
                <Col span={6}>
                  <Text type="secondary">פערים:</Text>
                  <div>{employment.gaps_count}</div>
                </Col>
                <Col span={6}>
                  <Text type="secondary">משך פערים:</Text>
                  <div>{employment.gap_duration?.display || '-'}</div>
                </Col>
              </>
            )}
          </>
        )}

        {/* Seniority */}
        {seniority && (
          <>
            <Col span={24}>
              <Title level={5} style={{ marginTop: 16, color: '#88D8E0' }}>ותק ענפי</Title>
            </Col>
            <Col span={6}>
              <Text type="secondary">ותק אצל הנתבע:</Text>
              <div>{seniority.at_defendant_months} חודשים ({seniority.at_defendant_years?.toFixed(1)} שנים)</div>
            </Col>
            <Col span={6}>
              <Text type="secondary">ותק ענפי כולל:</Text>
              <div>{seniority.total_industry_months} חודשים ({seniority.total_industry_years?.toFixed(1)} שנים)</div>
            </Col>
            {seniority.prior_seniority_months > 0 && (
              <Col span={6}>
                <Text type="secondary">ותק קודם:</Text>
                <div>{seniority.prior_seniority_months} חודשים</div>
              </Col>
            )}
          </>
        )}
      </Row>
    </Card>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const ResultsView: React.FC<ResultsViewProps> = ({ ssot }) => {
  const {
    claim_summary,
    rights_results,
    limitation_results,
    total_employment,
    seniority_totals,
    deduction_results,
    shifts,
    weeks,
    effective_periods,
    period_month_records,
    month_aggregates,
  } = ssot;

  // Extract limitation windows for passing to components
  const generalWindow = limitation_results?.windows?.find(w => w.type_id === 'general');
  const filingDate = limitation_results?.timeline_data?.filing_date;

  return (
    <div className="results-view">
      <Title level={2} style={{ color: '#FFD93D', textAlign: 'center', marginBottom: 24 }}>
        תוצאות החישוב
      </Title>

      {/* א. Summary Card */}
      {claim_summary && <div style={{ marginBottom: 24 }}><SummaryCard summary={claim_summary} /></div>}

      {/* ב. Rights Table */}
      {claim_summary?.per_right && claim_summary.per_right.length > 0 && (
        <div style={{ marginBottom: 24 }}><RightsTable rights={claim_summary.per_right} deductionResults={deduction_results} /></div>
      )}

      {/* ג. Salary Breakdown */}
      {(effective_periods?.length || period_month_records?.length) && (
        <div style={{ marginBottom: 24 }}>
          <SalaryBreakdown
            effectivePeriods={effective_periods}
            periodMonthRecords={period_month_records}
          />
        </div>
      )}

      {/* ג2. Job Scope Display */}
      {month_aggregates && month_aggregates.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <JobScopeDisplay monthAggregates={month_aggregates} />
        </div>
      )}

      {/* ד. Overtime Breakdown */}
      {rights_results?.overtime && (
        <div style={{ marginBottom: 24 }}>
          <OvertimeBreakdown
            overtime={rights_results.overtime}
            shifts={shifts}
            weeks={weeks}
            effectivePeriods={effective_periods}
            periodMonthRecords={period_month_records}
          />
        </div>
      )}

      {/* ה. Holidays Breakdown */}
      {rights_results?.holidays && (
        <div style={{ marginBottom: 24 }}>
          <HolidaysBreakdown
            holidays={rights_results.holidays}
            limitation={limitation_results?.per_right?.holidays}
            generalWindow={generalWindow}
            filingDate={filingDate}
          />
        </div>
      )}

      {/* ו. Severance Breakdown */}
      {rights_results?.severance?.eligible && (
        <div style={{ marginBottom: 24 }}>
          <SeveranceBreakdown
            severance={rights_results.severance}
            recreation={rights_results.recreation}
          />
        </div>
      )}

      {/* ז. Recreation Breakdown */}
      {rights_results?.recreation && (
        <div style={{ marginBottom: 24 }}>
          <RecreationBreakdown
            recreation={rights_results.recreation}
            limitation={limitation_results?.per_right?.recreation}
            generalWindow={generalWindow}
            filingDate={filingDate}
          />
        </div>
      )}

      {/* ז2. Pension Breakdown */}
      {rights_results?.pension && rights_results.pension.entitled && (
        <div style={{ marginBottom: 24 }}>
          <PensionBreakdown
            pension={rights_results.pension}
            limitation={limitation_results?.per_right?.pension}
            generalWindow={generalWindow}
            filingDate={filingDate}
          />
        </div>
      )}

      {/* ז3. Training Fund Breakdown */}
      {rights_results?.training_fund && (
        <div style={{ marginBottom: 24 }}>
          <TrainingFundBreakdown
            trainingFund={rights_results.training_fund}
            limitation={limitation_results?.per_right?.training_fund}
            generalWindow={generalWindow}
            filingDate={filingDate}
          />
        </div>
      )}

      {/* ז4. Travel Breakdown */}
      {rights_results?.travel && rights_results.travel.grand_total_value > 0 && (
        <div style={{ marginBottom: 24 }}>
          <TravelBreakdown
            travel={rights_results.travel}
            limitation={limitation_results?.per_right?.travel}
            generalWindow={generalWindow}
          />
        </div>
      )}

      {/* ז5. Meal Allowance Breakdown */}
      {rights_results?.meal_allowance?.entitled && (
        <div style={{ marginBottom: 24 }}>
          <MealAllowanceBreakdown
            mealAllowance={rights_results.meal_allowance}
            limitation={limitation_results?.per_right?.meal_allowance}
            generalWindow={generalWindow}
          />
        </div>
      )}

      {/* ח. Vacation Breakdown */}
      {rights_results?.vacation && (
        <div style={{ marginBottom: 24 }}>
          <VacationBreakdown
            vacation={rights_results.vacation}
            limitation={limitation_results?.per_right?.vacation}
            vacationWindow={limitation_results?.windows?.find(w => w.type_id === 'vacation')}
            filingDate={limitation_results?.timeline_data?.filing_date}
          />
        </div>
      )}

      {/* ט. Limitation Timeline */}
      {limitation_results && limitation_results.windows?.length > 0 && (
        <div style={{ marginBottom: 24 }}><LimitationTimeline limitation={limitation_results} /></div>
      )}

      {/* ח. Employment Details */}
      {(total_employment || seniority_totals) && (
        <div style={{ marginBottom: 24 }}><EmploymentDetails employment={total_employment} seniority={seniority_totals} /></div>
      )}

      {/* ט. Raw JSON for debugging */}
      <Collapse
        items={[
          {
            key: 'debug',
            label: 'JSON גולמי (לדיבאג)',
            children: (
              <div className="json-display">
                <pre>{JSON.stringify(ssot, null, 2)}</pre>
              </div>
            ),
          },
        ]}
        defaultActiveKey={[]}
        style={{ marginTop: 24 }}
      />

      {/* Export buttons */}
      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <Button
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => {
            const summary = {
              claim_summary: ssot.claim_summary,
              rights_results: ssot.rights_results,
              limitation_results: ssot.limitation_results,
              deduction_results: ssot.deduction_results,
              total_employment: ssot.total_employment,
              seniority_totals: ssot.seniority_totals,
              effective_periods: ssot.effective_periods,
            };
            const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'claims-wizard-results.json';
            a.click();
            URL.revokeObjectURL(url);
          }}
        >
          ייצוא תוצאות
        </Button>
        <Button
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => {
            const blob = new Blob([JSON.stringify(ssot, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'claims-wizard-ssot-full.json';
            a.click();
            URL.revokeObjectURL(url);
          }}
        >
          ייצוא SSOT מלא
        </Button>
      </div>
    </div>
  );
};

export default ResultsView;
