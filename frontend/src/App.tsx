import { useState } from 'react';
import {
  ConfigProvider,
  Form,
  Input,
  InputNumber,
  Button,
  Select,
  DatePicker,
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
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  CalculatorOutlined,
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
import dayjs, { Dayjs } from 'dayjs';
import 'dayjs/locale/he';
import type {
  SSOTInput,
  EmploymentPeriod,
  WorkPattern,
  SalaryTier,
  TimeRange,
  SeniorityMethod,
  RestDay,
  District,
} from './types';

dayjs.locale('he');

// Helper: generate unique ID
const generateId = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

// Day names in Hebrew
const DAY_NAMES: Record<number, string> = {
  0: 'ראשון',
  1: 'שני',
  2: 'שלישי',
  3: 'רביעי',
  4: 'חמישי',
  5: 'שישי',
  6: 'שבת',
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
  filing_date: undefined,
  seniority_input: { method: 'prior_plus_pattern', prior_months: 0 },
  right_toggles: {},
  deductions_input: {},
  right_specific_inputs: {},
});

function App() {
  const [formData, setFormData] = useState<SSOTInput>(createEmptyInput());
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  // Work patterns handlers
  const addWorkPattern = () => {
    const newPattern: WorkPattern = {
      id: generateId(),
      start: '',
      end: '',
      work_days: [0, 1, 2, 3, 4], // Default: Sunday-Thursday
      default_shifts: [{ start_time: '08:00:00', end_time: '17:00:00' }],
      default_breaks: [{ start_time: '12:00:00', end_time: '12:30:00' }],
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

  const updateShift = (patternIndex: number, shiftIndex: number, field: keyof TimeRange, value: string) => {
    const updated = [...formData.work_patterns];
    const shifts = [...updated[patternIndex].default_shifts];
    shifts[shiftIndex] = { ...shifts[shiftIndex], [field]: value };
    updated[patternIndex] = { ...updated[patternIndex], default_shifts: shifts };
    updateField('work_patterns', updated);
  };

  const addShift = (patternIndex: number) => {
    const updated = [...formData.work_patterns];
    updated[patternIndex].default_shifts.push({ start_time: '08:00:00', end_time: '17:00:00' });
    updateField('work_patterns', updated);
  };

  const removeShift = (patternIndex: number, shiftIndex: number) => {
    const updated = [...formData.work_patterns];
    updated[patternIndex].default_shifts = updated[patternIndex].default_shifts.filter((_, i) => i !== shiftIndex);
    updateField('work_patterns', updated);
  };

  const updateBreak = (patternIndex: number, breakIndex: number, field: keyof TimeRange, value: string) => {
    const updated = [...formData.work_patterns];
    const breaks = [...updated[patternIndex].default_breaks];
    breaks[breakIndex] = { ...breaks[breakIndex], [field]: value };
    updated[patternIndex] = { ...updated[patternIndex], default_breaks: breaks };
    updateField('work_patterns', updated);
  };

  const addBreak = (patternIndex: number) => {
    const updated = [...formData.work_patterns];
    updated[patternIndex].default_breaks.push({ start_time: '12:00:00', end_time: '12:30:00' });
    updateField('work_patterns', updated);
  };

  const removeBreak = (patternIndex: number, breakIndex: number) => {
    const updated = [...formData.work_patterns];
    updated[patternIndex].default_breaks = updated[patternIndex].default_breaks.filter((_, i) => i !== breakIndex);
    updateField('work_patterns', updated);
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

  // Submit handler
  const handleCalculate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
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

  // Helper: convert Dayjs to ISO string
  const dayjsToIso = (d: Dayjs | null): string => {
    return d ? d.format('YYYY-MM-DD') : '';
  };

  const timeToString = (d: Dayjs | null): string => {
    return d ? d.format('HH:mm:ss') : '';
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
                              <DatePicker
                                value={period.start ? dayjs(period.start) : null}
                                onChange={(d) => updateEmploymentPeriod(index, 'start', dayjsToIso(d))}
                                format="DD.MM.YYYY"
                                style={{ width: '100%' }}
                                placeholder="בחר תאריך"
                              />
                            </Form.Item>
                          </Col>
                          <Col span={10}>
                            <Form.Item label="תאריך סיום">
                              <DatePicker
                                value={period.end ? dayjs(period.end) : null}
                                onChange={(d) => updateEmploymentPeriod(index, 'end', dayjsToIso(d))}
                                format="DD.MM.YYYY"
                                style={{ width: '100%' }}
                                placeholder="בחר תאריך"
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
                          <Col span={12}>
                            <Form.Item label="תאריך התחלה">
                              <DatePicker
                                value={pattern.start ? dayjs(pattern.start) : null}
                                onChange={(d) => updateWorkPattern(pIndex, 'start', dayjsToIso(d))}
                                format="DD.MM.YYYY"
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item label="תאריך סיום">
                              <DatePicker
                                value={pattern.end ? dayjs(pattern.end) : null}
                                onChange={(d) => updateWorkPattern(pIndex, 'end', dayjsToIso(d))}
                                format="DD.MM.YYYY"
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Form.Item label="ימי עבודה">
                          <Checkbox.Group
                            value={pattern.work_days}
                            onChange={(vals) => updateWorkPattern(pIndex, 'work_days', vals)}
                          >
                            <Row>
                              {[0, 1, 2, 3, 4, 5, 6].map((day) => (
                                <Col span={3} key={day}>
                                  <Checkbox value={day}>{DAY_NAMES[day]}</Checkbox>
                                </Col>
                              ))}
                            </Row>
                          </Checkbox.Group>
                        </Form.Item>

                        <Divider>משמרות</Divider>
                        {pattern.default_shifts.map((shift, sIndex) => (
                          <Row gutter={16} key={sIndex} align="middle" style={{ marginBottom: 8 }}>
                            <Col span={10}>
                              <TimePicker
                                value={shift.start_time ? dayjs(shift.start_time, 'HH:mm:ss') : null}
                                onChange={(d) => updateShift(pIndex, sIndex, 'start_time', timeToString(d))}
                                format="HH:mm"
                                style={{ width: '100%' }}
                                placeholder="שעת התחלה"
                              />
                            </Col>
                            <Col span={10}>
                              <TimePicker
                                value={shift.end_time ? dayjs(shift.end_time, 'HH:mm:ss') : null}
                                onChange={(d) => updateShift(pIndex, sIndex, 'end_time', timeToString(d))}
                                format="HH:mm"
                                style={{ width: '100%' }}
                                placeholder="שעת סיום"
                              />
                            </Col>
                            <Col span={4}>
                              {pattern.default_shifts.length > 1 && (
                                <Button
                                  type="text"
                                  danger
                                  icon={<DeleteOutlined />}
                                  onClick={() => removeShift(pIndex, sIndex)}
                                />
                              )}
                            </Col>
                          </Row>
                        ))}
                        <Button type="dashed" size="small" onClick={() => addShift(pIndex)} icon={<PlusOutlined />}>
                          הוסף משמרת
                        </Button>

                        <Divider>הפסקות</Divider>
                        {pattern.default_breaks.map((brk, bIndex) => (
                          <Row gutter={16} key={bIndex} align="middle" style={{ marginBottom: 8 }}>
                            <Col span={10}>
                              <TimePicker
                                value={brk.start_time ? dayjs(brk.start_time, 'HH:mm:ss') : null}
                                onChange={(d) => updateBreak(pIndex, bIndex, 'start_time', timeToString(d))}
                                format="HH:mm"
                                style={{ width: '100%' }}
                                placeholder="תחילת הפסקה"
                              />
                            </Col>
                            <Col span={10}>
                              <TimePicker
                                value={brk.end_time ? dayjs(brk.end_time, 'HH:mm:ss') : null}
                                onChange={(d) => updateBreak(pIndex, bIndex, 'end_time', timeToString(d))}
                                format="HH:mm"
                                style={{ width: '100%' }}
                                placeholder="סיום הפסקה"
                              />
                            </Col>
                            <Col span={4}>
                              <Button
                                type="text"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={() => removeBreak(pIndex, bIndex)}
                              />
                            </Col>
                          </Row>
                        ))}
                        <Button type="dashed" size="small" onClick={() => addBreak(pIndex)} icon={<PlusOutlined />}>
                          הוסף הפסקה
                        </Button>
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
                          <Col span={4}>
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
                          <Col span={4}>
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
                          <Col span={4}>
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
                              <DatePicker
                                value={tier.start ? dayjs(tier.start) : null}
                                onChange={(d) => updateSalaryTier(index, 'start', dayjsToIso(d))}
                                format="DD.MM.YYYY"
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
                          </Col>
                          <Col span={5}>
                            <Form.Item label="עד תאריך">
                              <DatePicker
                                value={tier.end ? dayjs(tier.end) : null}
                                onChange={(d) => updateSalaryTier(index, 'end', dayjsToIso(d))}
                                format="DD.MM.YYYY"
                                style={{ width: '100%' }}
                              />
                            </Form.Item>
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
                          <Select.Option value="security">אבטחה</Select.Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item label="תאריך הגשת תביעה">
                        <DatePicker
                          value={formData.filing_date ? dayjs(formData.filing_date) : null}
                          onChange={(d) => updateField('filing_date', dayjsToIso(d) || undefined)}
                          format="DD.MM.YYYY"
                          style={{ width: '100%' }}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
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
                          <Radio value="manual">הזנה ידנית של סך הותק</Radio>
                          <Radio value="matash_pdf">חילוץ מקובץ מת״ש (בקרוב)</Radio>
                        </Space>
                      </Radio.Group>
                    </Form.Item>

                    {formData.seniority_input.method === 'prior_plus_pattern' && (
                      <Form.Item label="חודשי ותק קודמים בענף">
                        <InputNumber
                          value={formData.seniority_input.prior_months}
                          onChange={(v) =>
                            updateField('seniority_input', {
                              ...formData.seniority_input,
                              prior_months: v || 0,
                            })
                          }
                          min={0}
                          style={{ width: 200 }}
                        />
                      </Form.Item>
                    )}

                    {formData.seniority_input.method === 'manual' && (
                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item label="סך חודשי ותק בענף">
                            <InputNumber
                              value={formData.seniority_input.manual_industry_months}
                              onChange={(v) =>
                                updateField('seniority_input', {
                                  ...formData.seniority_input,
                                  manual_industry_months: v || 0,
                                })
                              }
                              min={0}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="חודשי ותק אצל הנתבע">
                            <InputNumber
                              value={formData.seniority_input.manual_defendant_months}
                              onChange={(v) =>
                                updateField('seniority_input', {
                                  ...formData.seniority_input,
                                  manual_defendant_months: v || 0,
                                })
                              }
                              min={0}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                      </Row>
                    )}
                  </div>
                ),
              },
              {
                key: 'toggles',
                label: 'אפשרויות זכויות',
                children: (
                  <Row gutter={16}>
                    <Col span={12}>
                      <Card title="שעות נוספות" size="small">
                        <Checkbox
                          checked={formData.right_toggles.overtime?.employer_paid_rest_premium || false}
                          onChange={(e) =>
                            updateRightToggle('overtime', 'employer_paid_rest_premium', e.target.checked)
                          }
                        >
                          המעסיק שילם פרמיית מנוחה שבועית
                        </Checkbox>
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card title="חגים" size="small">
                        <Checkbox
                          checked={formData.right_toggles.holidays?.include_election_day || false}
                          onChange={(e) =>
                            updateRightToggle('holidays', 'include_election_day', e.target.checked)
                          }
                        >
                          כלול יום בחירות
                        </Checkbox>
                      </Card>
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
                      <Form.Item label="ניכוי מדמי הבראה">
                        <InputNumber
                          value={parseFloat(formData.deductions_input.recreation) || undefined}
                          onChange={(v) => updateDeduction('recreation', String(v || 0))}
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

        {/* Error display */}
        {error && (
          <div className="error-container">
            <div className="error-title">שגיאה בחישוב</div>
            <div className="error-message" style={{ whiteSpace: 'pre-wrap' }}>
              {error}
            </div>
          </div>
        )}

        {/* Results display */}
        {result && (
          <div className="results-container">
            <div className="results-title">תוצאות החישוב</div>
            <div className="json-display">
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </ConfigProvider>
  );
}

export default App;
