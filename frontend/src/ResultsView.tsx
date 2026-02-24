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
            valueStyle={{ color: '#4ECDC4', fontSize: '1.5em', fontWeight: 'bold' }}
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
      title: 'זכות',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'סכום מלא',
      dataIndex: 'full_amount',
      key: 'full_amount',
      render: (v: number) => <span className="ltr-number">{formatCurrency(v)}</span>,
    },
    {
      title: 'התיישנות',
      dataIndex: 'limitation_excluded',
      key: 'limitation_excluded',
      render: (v: number) => (
        <span className="ltr-number" style={{ color: v > 0 ? '#FF6B6B' : undefined }}>
          {v > 0 ? `-${formatCurrency(v)}` : '-'}
        </span>
      ),
    },
    {
      title: 'אחרי התיישנות',
      dataIndex: 'after_limitation',
      key: 'after_limitation',
      render: (v: number) => <span className="ltr-number">{formatCurrency(v)}</span>,
    },
    {
      title: 'ניכוי מעסיק',
      dataIndex: 'deduction_amount',
      key: 'deduction_amount',
      render: (v: number, record: ClaimSummaryRight) => {
        const showDeduction = deductionResults?.[record.right_id]?.show_deduction;
        if (!showDeduction || v === 0) return '-';
        return <span className="ltr-number" style={{ color: '#FFD93D' }}>-{formatCurrency(v)}</span>;
      },
    },
    {
      title: 'לתביעה',
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
// ג. OvertimeBreakdown - פירוט שעות נוספות
// ============================================================================

const OvertimeBreakdown: React.FC<{ overtime: OvertimeResult }> = ({ overtime }) => {
  const columns = [
    {
      title: 'חודש',
      dataIndex: 'month',
      key: 'month',
      render: (m: [number, number]) => formatMonth(m),
    },
    {
      title: 'משמרות',
      dataIndex: 'shifts_count',
      key: 'shifts_count',
    },
    {
      title: 'שעות רגילות',
      dataIndex: 'regular_hours',
      key: 'regular_hours',
      render: (v: number) => <span className="ltr-number">{formatHours(v)}</span>,
    },
    {
      title: 'שעות נוספות',
      dataIndex: 'ot_hours',
      key: 'ot_hours',
      render: (v: number) => (
        <span className="ltr-number" style={{ color: v > 0 ? '#FFD93D' : undefined }}>
          {formatHours(v)}
        </span>
      ),
    },
    {
      title: 'סכום',
      dataIndex: 'claim_amount',
      key: 'claim_amount',
      render: (v: number) => <span className="ltr-number">{formatCurrency(v)}</span>,
    },
  ];

  // Calculate totals
  const totals = overtime.monthly_breakdown.reduce(
    (acc, row) => ({
      shifts_count: acc.shifts_count + row.shifts_count,
      regular_hours: acc.regular_hours + row.regular_hours,
      ot_hours: acc.ot_hours + row.ot_hours,
      claim_amount: acc.claim_amount + row.claim_amount,
    }),
    { shifts_count: 0, regular_hours: 0, ot_hours: 0, claim_amount: 0 }
  );

  return (
    <Card
      title={
        <Space>
          <ClockCircleOutlined />
          <span>שעות נוספות — פירוט חודשי</span>
          <Tag color="cyan">{formatCurrency(overtime.total_claim)}</Tag>
        </Space>
      }
      className="results-card"
    >
      <Table
        dataSource={overtime.monthly_breakdown}
        columns={columns}
        rowKey={(r) => `${r.month[0]}-${r.month[1]}`}
        pagination={overtime.monthly_breakdown.length > 24 ? { pageSize: 24 } : false}
        size="small"
        summary={() => (
          <Table.Summary fixed>
            <Table.Summary.Row style={{ background: 'rgba(78, 205, 196, 0.1)' }}>
              <Table.Summary.Cell index={0}><strong>סה״כ</strong></Table.Summary.Cell>
              <Table.Summary.Cell index={1}><strong>{totals.shifts_count}</strong></Table.Summary.Cell>
              <Table.Summary.Cell index={2}>
                <strong className="ltr-number">{formatHours(totals.regular_hours)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={3}>
                <strong className="ltr-number" style={{ color: '#FFD93D' }}>{formatHours(totals.ot_hours)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={4}>
                <strong className="ltr-number" style={{ color: '#4ECDC4' }}>{formatCurrency(totals.claim_amount)}</strong>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          </Table.Summary>
        )}
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
    { title: 'שם', dataIndex: 'name', key: 'name' },
    { title: 'תאריך עברי', dataIndex: 'hebrew_date', key: 'hebrew_date' },
    {
      title: 'תאריך לועזי',
      dataIndex: 'gregorian_date',
      key: 'gregorian_date',
      render: (d: string) => <span className="ltr-number">{formatDate(d)}</span>,
    },
    {
      title: 'יום',
      dataIndex: 'day_of_week',
      key: 'day_of_week',
      render: (d: string) => translateDayOfWeek(d),
    },
    {
      title: 'שבוע',
      dataIndex: 'week_type',
      key: 'week_type',
      render: (w: number) => `${w} ימים`,
    },
    {
      title: 'זכאות',
      key: 'entitlement',
      render: (_: unknown, record: HolidayEntry) => renderEntitlement(record),
    },
    {
      title: 'ערך יום',
      dataIndex: 'day_value',
      key: 'day_value',
      render: (v: number | undefined) => v ? <span className="ltr-number">{formatCurrency(v)}</span> : '-',
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
  } = ssot;

  return (
    <div className="results-view">
      <Title level={2} style={{ color: '#FFD93D', textAlign: 'center', marginBottom: 24 }}>
        תוצאות החישוב
      </Title>

      {/* א. Summary Card */}
      {claim_summary && <SummaryCard summary={claim_summary} />}

      {/* ב. Rights Table */}
      {claim_summary?.per_right && claim_summary.per_right.length > 0 && (
        <RightsTable rights={claim_summary.per_right} deductionResults={deduction_results} />
      )}

      {/* ג. Overtime Breakdown */}
      {rights_results?.overtime && (
        <OvertimeBreakdown overtime={rights_results.overtime} />
      )}

      {/* ד. Holidays Breakdown */}
      {rights_results?.holidays && (
        <HolidaysBreakdown holidays={rights_results.holidays} />
      )}

      {/* ה. Limitation Timeline */}
      {limitation_results && limitation_results.windows?.length > 0 && (
        <LimitationTimeline limitation={limitation_results} />
      )}

      {/* ו. Employment Details */}
      {(total_employment || seniority_totals) && (
        <EmploymentDetails employment={total_employment} seniority={seniority_totals} />
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
