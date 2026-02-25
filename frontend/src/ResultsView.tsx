/**
 * ResultsView - תצוגת תוצאות אשף התביעות
 *
 * מציג את תוצאות החישוב בצורה מעוצבת ומאורגנת.
 */

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
  CloseCircleOutlined,
  DollarOutlined,
  PercentageOutlined,
  DownloadOutlined,
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
  day_of_week: string;
  week_type: number;
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
  met_threshold: boolean;
  employment_days_in_year: number;
  holidays: HolidayEntry[];
  election_day_entitled: boolean;
  election_day_value?: number;
  total_entitled_days: number;
  total_claim: number;
}

interface HolidaysResult {
  per_year: HolidayYearResult[];
  grand_total_days: number;
  grand_total_claim: number;
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
  total_freeze_days: number;
}

interface LimitationRightResult {
  claimable_duration?: { display: string };
  full_amount?: number;
  claimable_amount?: number;
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

// Helper: format hours
const formatHours = (hours: number | undefined): string => {
  if (hours === undefined || hours === null) return '0';
  return hours.toFixed(1);
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

const RightsTable: React.FC<{
  rights: ClaimSummaryRight[];
  deductionResults?: Record<string, DeductionResult>;
}> = ({ rights, deductionResults }) => {
  const columns = [
    {
      title: <span style={{ color: '#88D8E0' }}>זכות</span>,
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <span style={{ color: '#E8F4F8' }}>{v}</span>,
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
}> = ({ effectivePeriods = [], periodMonthRecords = [] }) => {
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
  const d = new Date(datetime);
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
  const periodSummaries: PeriodOvertimeSummary[] = periodIds.map((periodId, idx) => {
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
                  {item.hours.toFixed(2)}h × {formatCurrency(item.hourly_wage)} × {getClaimLabel(item.tier, item.in_rest)}
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
const DayCollapseItem: React.FC<{ date: string; shifts: ShiftData[] }> = ({ date, shifts }) => {
  const dayTotal = shifts.reduce((sum, s) => sum + (s.claim_amount || 0), 0);
  const dayHours = shifts.reduce((sum, s) => sum + s.net_hours, 0);

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
  // Group shifts by date (current month shifts)
  const shiftsByDate: Record<string, ShiftData[]> = {};
  shifts.forEach((shift) => {
    if (!shiftsByDate[shift.date]) shiftsByDate[shift.date] = [];
    shiftsByDate[shift.date].push(shift);
  });

  // Find ghost days (shifts from other months in the same week)
  const ghostDays: Record<string, { shifts: ShiftData[]; monthName: string }> = {};
  if (allWeekShifts && currentMonth) {
    allWeekShifts.forEach((shift) => {
      const shiftDate = new Date(shift.date);
      const shiftMonth = `${shiftDate.getFullYear()}-${(shiftDate.getMonth() + 1).toString().padStart(2, '0')}`;
      if (shiftMonth !== currentMonth) {
        if (!ghostDays[shift.date]) {
          ghostDays[shift.date] = {
            shifts: [],
            monthName: formatMonth([shiftDate.getFullYear(), shiftDate.getMonth() + 1]),
          };
        }
        ghostDays[shift.date].shifts.push(shift);
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
            <Text type="secondary">OT שבועי:</Text>
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
    const date = new Date(shift.date);
    const year = date.getFullYear();
    const month = `${year}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
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
      const yearTotal = yearShifts.reduce((sum, s) => sum + (s.claim_amount || 0), 0);
      const yearHours = yearShifts.reduce((sum, s) => sum + s.net_hours, 0);

      // Build month items (ascending chronological order)
      const monthItems = Object.keys(yearData)
        .sort((a, b) => a.localeCompare(b))
        .map((month) => {
          const monthData = yearData[month];
          const monthShifts = Object.values(monthData).flat();
          const monthTotal = monthShifts.reduce((sum, s) => sum + (s.claim_amount || 0), 0);
          const monthHours = monthShifts.reduce((sum, s) => sum + s.net_hours, 0);
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
              const weekTotal = weekShifts.reduce((sum, s) => sum + (s.claim_amount || 0), 0);
              const weekHours = weekShifts.reduce((sum, s) => sum + s.net_hours, 0);

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

const HolidaysBreakdown: React.FC<{ holidays: HolidaysResult }> = ({ holidays }) => {
  const renderEntitlement = (entry: HolidayEntry) => {
    if (!entry.employed_on_date) {
      return <Tag color="default">לא מועסק</Tag>;
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
      render: (w: number) => (
        <span style={{ color: '#E8F4F8' }}>
          {w === -1 ? '—' : `${w} ימים`}
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

  const yearItems = holidays.per_year.map((year) => ({
    key: String(year.year),
    label: (
      <Space>
        <span>{year.year}</span>
        <Tag color={year.met_threshold ? 'green' : 'red'}>
          {year.total_entitled_days} ימים
        </Tag>
        <span className="ltr-number">{formatCurrency(year.total_claim)}</span>
      </Space>
    ),
    children: (
      <div>
        {!year.met_threshold && (
          <Alert
            message="לא עמד בתנאי סף — עבד פחות מעשירית השנה"
            description={`ימי עבודה בשנה: ${year.employment_days_in_year} (מינימום נדרש: 37)`}
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        {year.met_threshold && (
          <>
            <Table
              dataSource={[
                ...year.holidays,
                // Add election day as the last row
                {
                  name: 'יום בחירה',
                  hebrew_date: '—',
                  gregorian_date: '',
                  employed_on_date: true,
                  day_of_week: '—',
                  week_type: -1,  // Mark as election day, not a regular week_type
                  is_rest_day: false,
                  is_eve_of_rest: false,
                  excluded: false,
                  exclude_reason: undefined,
                  entitled: true,
                  day_value: year.election_day_value ?? undefined,
                  claim_amount: year.election_day_value ?? undefined,
                },
              ]}
              columns={holidayColumns}
              rowKey="name"
              pagination={false}
              size="small"
              rowClassName={(record) =>
                record.name === 'יום בחירה' ? 'election-day-row' : ''
              }
            />
          </>
        )}
      </div>
    ),
  }));

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
// ה. LimitationTimeline - התיישנות
// ============================================================================

const LimitationTimeline: React.FC<{ limitation: LimitationResults }> = ({ limitation }) => {
  const { windows, timeline_data, per_right } = limitation;
  const summary = timeline_data?.summary;

  // Get claimable_duration display from general limitation (or first available)
  const claimableDurationDisplay = per_right?.general?.claimable_duration?.display
    || Object.values(per_right || {})[0]?.claimable_duration?.display
    || '';

  const claimablePercent = summary?.total_employment_days
    ? Math.round((summary.claimable_days_general / summary.total_employment_days) * 100)
    : 0;

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

      {/* Windows */}
      {windows.map((window, idx) => (
        <div key={idx} style={{ marginBottom: 16 }}>
          <Text strong>{window.type_name}</Text>
          <Progress
            percent={claimablePercent}
            strokeColor="#4ECDC4"
            trailColor="rgba(255, 107, 107, 0.3)"
            format={() => `${claimablePercent}% לא התיישן`}
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
      ))}
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
        <div style={{ marginBottom: 24 }}><HolidaysBreakdown holidays={rights_results.holidays} /></div>
      )}

      {/* ו. Limitation Timeline */}
      {limitation_results && limitation_results.windows?.length > 0 && (
        <div style={{ marginBottom: 24 }}><LimitationTimeline limitation={limitation_results} /></div>
      )}

      {/* ז. Employment Details */}
      {(total_employment || seniority_totals) && (
        <div style={{ marginBottom: 24 }}><EmploymentDetails employment={total_employment} seniority={seniority_totals} /></div>
      )}

      {/* ז. Raw JSON for debugging */}
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
