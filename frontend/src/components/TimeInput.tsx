/**
 * TimeInput - Simple time input component.
 * Format: HH:MM (auto-inserts colon after 2 digits)
 * Validates hours 00-23, minutes 00-59
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

const parseTimeValue = (display: string): string | null => {
  const parts = display.split(':');
  if (parts.length !== 2) return null;
  const h = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  if (isNaN(h) || isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) return null;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`;
};

const displayFromValue = (val: string): string => {
  if (!val) return '';
  return val.substring(0, 5);  // "HH:mm:ss" → "HH:mm"
};

const TimeInput: React.FC<TimeInputProps> = ({ value, onChange, placeholder, style, size }) => {
  const [display, setDisplay] = useState(displayFromValue(value || ''));
  const [isValid, setIsValid] = useState(true);

  useEffect(() => {
    setDisplay(displayFromValue(value || ''));
    setIsValid(true);
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatTimeInput(e.target.value);
    setDisplay(formatted);
    if (formatted.length === 5) {
      setIsValid(parseTimeValue(formatted) !== null);
    } else {
      setIsValid(true);
    }
  };

  const handleBlur = () => {
    if (!display) {
      setIsValid(true);
      onChange('');
      return;
    }
    const parsed = parseTimeValue(display);
    if (parsed) {
      setIsValid(true);
      onChange(parsed);
    } else {
      setIsValid(false);
    }
  };

  return (
    <Input
      value={display}
      onChange={handleChange}
      onBlur={handleBlur}
      placeholder={placeholder || 'HH:MM'}
      status={isValid ? undefined : 'error'}
      style={{ width: 80, textAlign: 'center', ...style }}
      size={size}
      maxLength={5}
    />
  );
};

export default TimeInput;
