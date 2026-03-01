/**
 * TimeInput - Simple time input component.
 * Format: HH:MM (auto-inserts colon after 2 digits)
 * Auto-clamps to valid hours 00-23, minutes 00-59
 * Returns HH:mm:ss format
 */

import React, { useState, useEffect } from 'react';
import { Input } from 'antd';

interface TimeInputProps {
  value?: string;  // HH:mm:ss
  onChange: (value: string) => void;
  placeholder?: string;
  style?: React.CSSProperties;
  size?: 'small' | 'middle' | 'large';
}

const formatTimeInput = (raw: string): string => {
  const digits = raw.replace(/\D/g, '');
  let result = '';
  for (let i = 0; i < digits.length && i < 4; i++) {
    result += digits[i];
    if (i === 1 && i < digits.length - 1) result += ':';
  }
  return result;
};

const clampTime = (display: string): string => {
  const parts = display.split(':');
  if (parts.length !== 2) return display;

  let h = parseInt(parts[0], 10);
  let m = parseInt(parts[1], 10);

  if (isNaN(h)) h = 0;
  if (isNaN(m)) m = 0;

  h = Math.min(Math.max(h, 0), 23);
  m = Math.min(Math.max(m, 0), 59);

  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

const displayFromValue = (val: string): string => {
  if (!val) return '';
  return val.substring(0, 5);  // "HH:mm:ss" → "HH:mm"
};

const TimeInput: React.FC<TimeInputProps> = ({ value, onChange, placeholder, style, size }) => {
  const [display, setDisplay] = useState(displayFromValue(value || ''));

  useEffect(() => {
    setDisplay(displayFromValue(value || ''));
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^\d:]/g, '');
    const colonCount = (raw.match(/:/g) || []).length;
    const cleaned = colonCount > 1 ? raw.replace(/:(?=.*:)/, '') : raw;
    const formatted = formatTimeInput(cleaned);
    setDisplay(formatted);
  };

  const handleBlur = () => {
    if (!display) { onChange(''); return; }

    let normalized = display;

    const digits = display.replace(/\D/g, '');
    if (digits.length === 1) {
      normalized = `0${digits}:00`;
    } else if (digits.length === 2) {
      normalized = `${digits}:00`;
    } else if (digits.length === 3) {
      normalized = `0${digits[0]}:${digits[1]}${digits[2]}`;
    }

    normalized = clampTime(normalized);
    setDisplay(normalized);
    onChange(`${normalized}:00`);
  };

  return (
    <Input
      value={display}
      onChange={handleChange}
      onBlur={handleBlur}
      placeholder={placeholder || 'HH:MM'}
      style={{ width: 80, textAlign: 'center', ...style }}
      size={size}
      maxLength={5}
    />
  );
};

export default TimeInput;
