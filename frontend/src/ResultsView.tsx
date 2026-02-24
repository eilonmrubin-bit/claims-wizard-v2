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

interface LimitationResults {
  windows: LimitationWindow[];
  timeline_data: {
    summary: TimelineSummary;
  };
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
// ג. OvertimeBreakdown - פירוט שעות נוספות (משופר)
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
  const restLabels: Record<number, string> = { 0: '150%', 1: '175%', 2: '200%' };
  return inRest ? restLabels[tier] : baseLabels[tier];
};

// Helper: get tier color
const getTierColor = (tier: number, inRest: boolean): string => {
  if (inRest) return '#FF6B6B'; // Red for rest window
  if (tier === 0) return '#88D8E0'; // Light cyan for regular
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
    'eve_of_rest': 'ערב מנוחה',
    'eve_rest': 'ערב מנוחה',
    'rest_day': 'יום מנוחה',
    'night_shift': 'משמרת לילה',
    'night': 'משמרת לילה',
    'eve_of_rest_5day': 'ערב מנוחה (5 ימים)',
    'eve_rest+night': 'ערב מנוחה + לילה',
  };
  return map[reason] || reason;
};

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

  // Sort by percentage (100%, 125%, 150%, 175%, 200%)
  const order = ['100%', '125%', '150%', '175%', '200%'];
  return order
    .filter((tier) => tierMap[tier])
    .map((tier) => ({
      tier,
      hours: tierMap[tier].hours,
      amount: tierMap[tier].amount,
      color: tierMap[tier].color,
    }));
};

// OvertimeSummaryTab - סיכום כללי
const OvertimeSummaryTab: React.FC<{ shifts: ShiftData[]; totalClaim: number }> = ({
  shifts,
  totalClaim,
}) => {
  const tierSummary = aggregateByTier(shifts);
  const totalHours = shifts.reduce((sum, s) => sum + s.net_hours, 0);
  const totalRegular = shifts.reduce((sum, s) => sum + s.regular_hours, 0);
  const totalOT = shifts.reduce((sum, s) => sum + s.ot_tier1_hours + s.ot_tier2_hours, 0);

  return (
    <div>
      {/* Overall stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Statistic title="סה״כ משמרות" value={shifts.length} />
        </Col>
        <Col span={6}>
          <Statistic title="סה״כ שעות עבודה" value={totalHours.toFixed(1)} />
        </Col>
        <Col span={6}>
          <Statistic title="שעות רגילות" value={totalRegular.toFixed(1)} valueStyle={{ color: '#88D8E0' }} />
        </Col>
        <Col span={6}>
          <Statistic title="שעות נוספות" value={totalOT.toFixed(1)} valueStyle={{ color: '#FFD93D' }} />
        </Col>
      </Row>

      {/* Tier breakdown */}
      <Title level={5} style={{ color: '#88D8E0', marginBottom: 16 }}>פירוט לפי דרגה</Title>
      <Table
        dataSource={tierSummary}
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
            render: (v: number) => <span className="ltr-number" style={{ fontWeight: 'bold' }}>{formatCurrency(v)}</span>,
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
                <strong className="ltr-number">{tierSummary.reduce((sum, t) => sum + t.hours, 0).toFixed(1)}</strong>
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
            <span style={{ color: '#88D8E0' }}>{shift.regular_hours.toFixed(1)} רגיל</span>
            {shift.ot_tier1_hours > 0 && <span style={{ color: '#FFD93D' }}> + {shift.ot_tier1_hours.toFixed(1)} (125%)</span>}
            {shift.ot_tier2_hours > 0 && <span style={{ color: '#FF9F43' }}> + {shift.ot_tier2_hours.toFixed(1)} (150%)</span>}
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
            {shift.pricing_breakdown.map((item, idx) => (
              <Tag key={idx} color={getTierColor(item.tier, item.in_rest)} style={{ marginBottom: 4 }}>
                {item.hours.toFixed(2)}h × {getTierLabel(item.tier, item.in_rest)}
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
const WeekCollapseContent: React.FC<{ week: WeekData; shifts: ShiftData[] }> = ({ week, shifts }) => {
  // Group shifts by date
  const shiftsByDate: Record<string, ShiftData[]> = {};
  shifts.forEach((shift) => {
    if (!shiftsByDate[shift.date]) shiftsByDate[shift.date] = [];
    shiftsByDate[shift.date].push(shift);
  });

  const sortedDates = Object.keys(shiftsByDate).sort();

  const dayItems = sortedDates.map((date) => {
    const dayShifts = shiftsByDate[date];
    const dayTotal = dayShifts.reduce((sum, s) => sum + (s.claim_amount || 0), 0);
    const dayHours = dayShifts.reduce((sum, s) => sum + s.net_hours, 0);
    const dayOfWeek = dayOfWeekFromDate(date);
    const isFriday = dayOfWeek === 'שישי';
    const isShabbat = dayOfWeek === 'שבת';

    return {
      key: date,
      label: (
        <Space>
          <CalendarOutlined />
          <span style={{ fontWeight: 500 }}>{dayOfWeek}</span>
          <span className="ltr-number">{formatDate(date)}</span>
          {isFriday && week.rest_window_start && (
            <Tag color="gold">כניסת שבת: {formatTime(week.rest_window_start)}</Tag>
          )}
          {isShabbat && week.rest_window_end && (
            <Tag color="gold">צאת שבת: {formatTime(week.rest_window_end)}</Tag>
          )}
          <Tag>{dayShifts.length} משמרות</Tag>
          <Tag color="blue">{dayHours.toFixed(1)}h</Tag>
          {dayTotal > 0 && <Tag color="cyan">{formatCurrency(dayTotal)}</Tag>}
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
            <div><Tag color={week.week_type === 5 ? 'green' : 'blue'}>{week.week_type} ימים</Tag></div>
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

        {/* Rest window info */}
        {(week.rest_window_start || week.rest_window_end) && (
          <Row gutter={16} style={{ marginTop: 12 }}>
            <Col span={24}>
              <Text type="secondary" strong style={{ color: '#FF6B6B' }}>חלון מנוחה (36 שעות):</Text>
            </Col>
            <Col span={8}>
              <Text type="secondary">כניסת שבת:</Text>
              <div className="ltr-number">{formatDateTime(week.rest_window_start)}</div>
            </Col>
            <Col span={8}>
              <Text type="secondary">יציאת שבת:</Text>
              <div className="ltr-number">{formatDateTime(week.rest_window_end)}</div>
            </Col>
            <Col span={8}>
              <Text type="secondary">שעות עבודה בחלון:</Text>
              <div style={{ color: week.rest_window_work_hours > 0 ? '#FF6B6B' : '#4ECDC4' }}>
                {week.rest_window_work_hours?.toFixed(1) || 0}
              </div>
            </Col>
          </Row>
        )}

        {/* Partial week warning */}
        {week.is_partial && (
          <Alert
            message="שבוע חלקי"
            description={week.partial_detail || week.partial_reason}
            type="info"
            showIcon
            style={{ marginTop: 12 }}
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

          // Build week items (ascending chronological order)
          const weekItems = Object.keys(monthData)
            .sort((a, b) => {
              const weekA = weekMap[a];
              const weekB = weekMap[b];
              return (weekA?.week_number || 0) - (weekB?.week_number || 0);
            })
            .map((weekId) => {
              const weekShifts = monthData[weekId];
              const week = weekMap[weekId];
              const weekTotal = weekShifts.reduce((sum, s) => sum + (s.claim_amount || 0), 0);
              const weekHours = weekShifts.reduce((sum, s) => sum + s.net_hours, 0);

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
                    <Tag>{weekShifts.length} משמרות</Tag>
                    <Tag color="blue">{weekHours.toFixed(1)}h</Tag>
                    <Tag color="cyan">{formatCurrency(weekTotal)}</Tag>
                  </Space>
                ),
                children: week ? (
                  <WeekCollapseContent week={week} shifts={weekShifts} />
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
                <Tag color="blue">{monthHours.toFixed(1)}h</Tag>
                <Tag color="cyan">{formatCurrency(monthTotal)}</Tag>
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
            <Tag color="blue">{yearHours.toFixed(1)}h</Tag>
            <Tag color="cyan" style={{ fontWeight: 'bold' }}>{formatCurrency(yearTotal)}</Tag>
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
}> = ({ overtime, shifts = [], weeks = [] }) => {
  const tabItems = [
    {
      key: 'summary',
      label: (
        <Space>
          <ClockCircleOutlined />
          <span>סיכום כללי</span>
        </Space>
      ),
      children: <OvertimeSummaryTab shifts={shifts} totalClaim={overtime.total_claim} />,
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
      render: (d: string) => <span className="ltr-number" style={{ color: '#E8F4F8' }}>{formatDate(d)}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>יום</span>,
      dataIndex: 'day_of_week',
      key: 'day_of_week',
      render: (d: string) => <span style={{ color: '#E8F4F8' }}>{translateDayOfWeek(d)}</span>,
    },
    {
      title: <span style={{ color: '#88D8E0' }}>שבוע</span>,
      dataIndex: 'week_type',
      key: 'week_type',
      render: (w: number) => <span style={{ color: '#E8F4F8' }}>{w} ימים</span>,
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
            message="לא עמד בסף 1/10"
            description={`ימי עבודה בשנה: ${year.employment_days_in_year} (מינימום נדרש: 10)`}
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        {year.met_threshold && (
          <>
            <Table
              dataSource={year.holidays}
              columns={holidayColumns}
              rowKey="name"
              pagination={false}
              size="small"
            />
            {year.election_day_entitled && (
              <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(78, 205, 196, 0.1)', borderRadius: 4 }}>
                <CheckCircleOutlined style={{ color: '#4ECDC4', marginLeft: 8 }} />
                <Text>זכאי לדמי יום בחירות</Text>
              </div>
            )}
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
  const { windows, timeline_data } = limitation;
  const summary = timeline_data?.summary;

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
              title="ימים תבעיים"
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

      {/* Windows */}
      {windows.map((window, idx) => (
        <div key={idx} style={{ marginBottom: 16 }}>
          <Text strong>{window.type_name}</Text>
          <Progress
            percent={claimablePercent}
            strokeColor="#4ECDC4"
            trailColor="rgba(255, 107, 107, 0.3)"
            format={() => `${claimablePercent}% תבעי`}
          />
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

      {/* ג. Overtime Breakdown */}
      {rights_results?.overtime && (
        <div style={{ marginBottom: 24 }}><OvertimeBreakdown overtime={rights_results.overtime} shifts={shifts} weeks={weeks} /></div>
      )}

      {/* ד. Holidays Breakdown */}
      {rights_results?.holidays && (
        <div style={{ marginBottom: 24 }}><HolidaysBreakdown holidays={rights_results.holidays} /></div>
      )}

      {/* ה. Limitation Timeline */}
      {limitation_results && limitation_results.windows?.length > 0 && (
        <div style={{ marginBottom: 24 }}><LimitationTimeline limitation={limitation_results} /></div>
      )}

      {/* ו. Employment Details */}
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
    </div>
  );
};

export default ResultsView;
