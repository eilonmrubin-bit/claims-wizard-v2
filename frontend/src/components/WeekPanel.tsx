/**
 * WeekPanel - Week day selection and shift configuration panel.
 * Used for Level A (weekly_simple) and Level B (cyclic) patterns.
 */

import React, { useState } from 'react';
import { Checkbox, Radio, TimePicker, InputNumber, Select, Button, Row, Col, Tooltip } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { PerDayShifts, ShiftInputMode, ShiftType, RestDay, TimeRange } from '../types';

const DAY_NAMES: Record<number, string> = {
  0: 'ראשון',
  1: 'שני',
  2: 'שלישי',
  3: 'רביעי',
  4: 'חמישי',
  5: 'שישי',
  6: 'שבת',
};

interface WeekPanelProps {
  workDays: number[];                           // active days (0=Sunday..6=Saturday)
  perDay: Record<number, PerDayShifts>;         // shift config per day
  restDay: RestDay;                             // from formData — for status tags
  inputMode: ShiftInputMode;                    // 'time_range' | 'duration'
  onInputModeChange: (mode: ShiftInputMode) => void;
  onChange: (workDays: number[], perDay: Record<number, PerDayShifts>) => void;
}

const DEFAULT_SHIFT: PerDayShifts = {
  shifts: [{ start_time: '07:00:00', end_time: '16:00:00' }],
  break_minutes: 30,
  shift_type: 'day',
  duration_hours: 9,
};

const timeToString = (d: dayjs.Dayjs | null): string => {
  return d ? d.format('HH:mm:ss') : '';
};

const formatShiftSummary = (shift: TimeRange): string => {
  const start = shift.start_time.substring(0, 5);
  const end = shift.end_time.substring(0, 5);
  return `${start}-${end}`;
};

const getStatusTag = (day: number, restDay: RestDay): string | null => {
  if (restDay === 'saturday') {
    if (day === 6) return 'מנוחה';
    if (day === 5) return 'ע.מנוחה';
  } else if (restDay === 'friday') {
    if (day === 5) return 'מנוחה';
    if (day === 4) return 'ע.מנוחה';
  } else if (restDay === 'sunday') {
    if (day === 0) return 'מנוחה';
    if (day === 6) return 'ע.מנוחה';
  }
  return null;
};

export const WeekPanel: React.FC<WeekPanelProps> = ({
  workDays,
  perDay,
  restDay,
  inputMode,
  onInputModeChange,
  onChange,
}) => {
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  const toggleDay = (day: number, checked: boolean) => {
    let newWorkDays: number[];
    let newPerDay = { ...perDay };

    if (checked) {
      newWorkDays = [...workDays, day].sort((a, b) => a - b);
      if (!newPerDay[day]) {
        newPerDay[day] = { ...DEFAULT_SHIFT, shifts: [...DEFAULT_SHIFT.shifts] };
      }
    } else {
      newWorkDays = workDays.filter(d => d !== day);
      delete newPerDay[day];
    }

    onChange(newWorkDays, newPerDay);
  };

  const updateDayShift = (day: number, shiftIndex: number, field: 'start_time' | 'end_time', value: string) => {
    const newPerDay = { ...perDay };
    const dayData = newPerDay[day] || { ...DEFAULT_SHIFT };
    const newShifts = [...dayData.shifts];
    newShifts[shiftIndex] = { ...newShifts[shiftIndex], [field]: value };
    newPerDay[day] = { ...dayData, shifts: newShifts };
    onChange(workDays, newPerDay);
  };

  const updateDayBreak = (day: number, value: number) => {
    const newPerDay = { ...perDay };
    const dayData = newPerDay[day] || { ...DEFAULT_SHIFT };
    newPerDay[day] = { ...dayData, break_minutes: value };
    onChange(workDays, newPerDay);
  };

  const updateDayDuration = (day: number, field: 'shift_type' | 'duration_hours', value: ShiftType | number) => {
    const newPerDay = { ...perDay };
    const dayData = newPerDay[day] || { ...DEFAULT_SHIFT };
    newPerDay[day] = { ...dayData, [field]: value };

    // Also update the shifts array based on duration mode values
    if (field === 'shift_type' || field === 'duration_hours') {
      const shiftType = field === 'shift_type' ? value as ShiftType : (dayData.shift_type || 'day');
      const hours = field === 'duration_hours' ? value as number : (dayData.duration_hours || 9);
      const startHour = shiftType === 'night' ? 22 : 6;
      const totalMinutes = Math.round(hours * 60);
      const endMinutes = (startHour * 60 + totalMinutes) % (24 * 60);

      const startTime = `${String(startHour).padStart(2, '0')}:00:00`;
      const endTime = `${String(Math.floor(endMinutes / 60)).padStart(2, '0')}:${String(endMinutes % 60).padStart(2, '0')}:00`;

      newPerDay[day] = {
        ...newPerDay[day],
        shifts: [{ start_time: startTime, end_time: endTime }],
        shift_type: shiftType,
        duration_hours: hours,
      };
    }

    onChange(workDays, newPerDay);
  };

  const addShiftToDay = (day: number) => {
    const newPerDay = { ...perDay };
    const dayData = newPerDay[day] || { ...DEFAULT_SHIFT };
    newPerDay[day] = {
      ...dayData,
      shifts: [...dayData.shifts, { start_time: '18:00:00', end_time: '22:00:00' }],
    };
    onChange(workDays, newPerDay);
  };

  const removeShiftFromDay = (day: number, shiftIndex: number) => {
    const newPerDay = { ...perDay };
    const dayData = newPerDay[day];
    if (dayData && dayData.shifts.length > 1) {
      newPerDay[day] = {
        ...dayData,
        shifts: dayData.shifts.filter((_, i) => i !== shiftIndex),
      };
      onChange(workDays, newPerDay);
    }
  };

  const handleCellClick = (day: number) => {
    setSelectedDay(selectedDay === day ? null : day);
  };

  const isWorkDay = (day: number) => workDays.includes(day);
  const dayData = (day: number) => perDay[day] || DEFAULT_SHIFT;

  return (
    <div className="week-panel">
      {/* 7-day cell row */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {[0, 1, 2, 3, 4, 5, 6].map(day => {
          const active = isWorkDay(day);
          const statusTag = getStatusTag(day, restDay);
          const data = dayData(day);
          const isSelected = selectedDay === day;

          return (
            <Tooltip key={day} title="לחץ לעריכה">
              <div
                onClick={() => handleCellClick(day)}
                style={{
                  flex: 1,
                  padding: '8px 4px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  borderRadius: 6,
                  border: isSelected ? '2px solid #1890ff' : '1px solid #303030',
                  background: active ? '#1a3a1a' : '#1f1f1f',
                  opacity: active ? 1 : 0.6,
                  minHeight: 80,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'flex-start',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{DAY_NAMES[day]}</div>
                {statusTag && (
                  <div style={{
                    fontSize: 10,
                    color: statusTag === 'מנוחה' ? '#ff7875' : '#faad14',
                    marginBottom: 4,
                  }}>
                    {statusTag}
                  </div>
                )}
                {active ? (
                  <>
                    <div style={{ fontSize: 11 }}>
                      {data.shifts.map((s, i) => (
                        <div key={i}>{formatShiftSummary(s)}</div>
                      ))}
                    </div>
                    {data.break_minutes > 0 && (
                      <div style={{ fontSize: 10, color: '#888' }}>
                        הפ {data.break_minutes}'
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ fontSize: 18, color: '#555' }}>—</div>
                )}
              </div>
            </Tooltip>
          );
        })}
      </div>

      {/* Accordion edit panel */}
      {selectedDay !== null && (
        <div style={{
          background: '#262626',
          border: '1px solid #404040',
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 12, borderBottom: '1px solid #404040', paddingBottom: 8 }}>
            {DAY_NAMES[selectedDay]}
          </div>

          {/* Work day checkbox */}
          <div style={{ marginBottom: 16 }}>
            <Checkbox
              checked={isWorkDay(selectedDay)}
              onChange={(e) => toggleDay(selectedDay, e.target.checked)}
            >
              יום עבודה
            </Checkbox>
          </div>

          {isWorkDay(selectedDay) && (
            <>
              {/* Input mode selector */}
              <div style={{ marginBottom: 16 }}>
                <span style={{ marginLeft: 8 }}>מצב הזנה:</span>
                <Radio.Group
                  value={inputMode}
                  onChange={(e) => onInputModeChange(e.target.value)}
                  size="small"
                >
                  <Radio value="time_range">טווח</Radio>
                  <Radio value="duration">אורך</Radio>
                </Radio.Group>
              </div>

              {/* Shifts configuration */}
              {inputMode === 'time_range' ? (
                // Time range mode
                <>
                  {dayData(selectedDay).shifts.map((shift, sIndex) => (
                    <Row gutter={8} key={sIndex} align="middle" style={{ marginBottom: 8 }}>
                      <Col span={2}>
                        <span style={{ fontSize: 12 }}>משמרת {sIndex + 1}:</span>
                      </Col>
                      <Col span={6}>
                        <TimePicker
                          value={shift.start_time ? dayjs(shift.start_time, 'HH:mm:ss') : null}
                          onChange={(d) => updateDayShift(selectedDay, sIndex, 'start_time', timeToString(d))}
                          format="HH:mm"
                          size="small"
                          style={{ width: '100%' }}
                        />
                      </Col>
                      <Col span={1} style={{ textAlign: 'center' }}>-</Col>
                      <Col span={6}>
                        <TimePicker
                          value={shift.end_time ? dayjs(shift.end_time, 'HH:mm:ss') : null}
                          onChange={(d) => updateDayShift(selectedDay, sIndex, 'end_time', timeToString(d))}
                          format="HH:mm"
                          size="small"
                          style={{ width: '100%' }}
                        />
                      </Col>
                      <Col span={6}>
                        <InputNumber
                          value={dayData(selectedDay).break_minutes}
                          onChange={(v) => updateDayBreak(selectedDay, v || 0)}
                          min={0}
                          max={180}
                          precision={0}
                          size="small"
                          style={{ width: '100%' }}
                          addonBefore="הפסקה"
                          addonAfter="דק'"
                        />
                      </Col>
                      <Col span={2}>
                        {dayData(selectedDay).shifts.length > 1 && (
                          <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={() => removeShiftFromDay(selectedDay, sIndex)}
                          />
                        )}
                      </Col>
                    </Row>
                  ))}
                  <Button
                    type="dashed"
                    size="small"
                    onClick={() => addShiftToDay(selectedDay)}
                    icon={<PlusOutlined />}
                  >
                    הוסף משמרת
                  </Button>
                </>
              ) : (
                // Duration mode
                <>
                  {dayData(selectedDay).shifts.map((_, sIndex) => (
                    <Row gutter={8} key={sIndex} align="middle" style={{ marginBottom: 8 }}>
                      <Col span={3}>
                        <span style={{ fontSize: 12 }}>משמרת {sIndex + 1}:</span>
                      </Col>
                      <Col span={5}>
                        <Select
                          value={dayData(selectedDay).shift_type || 'day'}
                          onChange={(v) => updateDayDuration(selectedDay, 'shift_type', v)}
                          size="small"
                          style={{ width: '100%' }}
                        >
                          <Select.Option value="day">יום</Select.Option>
                          <Select.Option value="night">לילה</Select.Option>
                        </Select>
                      </Col>
                      <Col span={6}>
                        <InputNumber
                          value={dayData(selectedDay).duration_hours || 9}
                          onChange={(v) => updateDayDuration(selectedDay, 'duration_hours', v || 9)}
                          min={0.5}
                          max={dayData(selectedDay).shift_type === 'night' ? 12 : 14}
                          precision={1}
                          step={0.5}
                          size="small"
                          style={{ width: '100%' }}
                          addonAfter="שעות"
                        />
                      </Col>
                      <Col span={6}>
                        <InputNumber
                          value={dayData(selectedDay).break_minutes}
                          onChange={(v) => updateDayBreak(selectedDay, v || 0)}
                          min={0}
                          max={180}
                          precision={0}
                          size="small"
                          style={{ width: '100%' }}
                          addonBefore="הפסקה"
                          addonAfter="דק'"
                        />
                      </Col>
                      <Col span={2}>
                        {dayData(selectedDay).shifts.length > 1 && (
                          <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={() => removeShiftFromDay(selectedDay, sIndex)}
                          />
                        )}
                      </Col>
                    </Row>
                  ))}
                  <Button
                    type="dashed"
                    size="small"
                    onClick={() => addShiftToDay(selectedDay)}
                    icon={<PlusOutlined />}
                  >
                    הוסף משמרת
                  </Button>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default WeekPanel;
