import React, { useState, useEffect, useRef } from 'react';
import { Input, DatePicker } from 'antd';
import { CalendarOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';

interface DateInputProps {
  value?: string; // YYYY-MM-DD (ISO)
  onChange: (value: string) => void;
  placeholder?: string;
  style?: React.CSSProperties;
}

// Convert ISO (YYYY-MM-DD) to display format (DD.MM.YYYY)
const isoToDisplay = (iso: string): string => {
  if (!iso) return '';
  const parts = iso.split('-');
  if (parts.length !== 3) return '';
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
};

// Convert display format (DD.MM.YYYY) to ISO (YYYY-MM-DD)
const displayToIso = (display: string): string | null => {
  const parts = display.split('.');
  if (parts.length !== 3) return null;

  let [day, month, year] = parts;

  // If year is only 2 digits, expand it
  if (year.length === 2) {
    const yy = parseInt(year, 10);
    year = yy <= 40 ? `20${year}` : `19${year}`;
  }

  if (year.length !== 4) return null;

  const d = parseInt(day, 10);
  const m = parseInt(month, 10);
  const y = parseInt(year, 10);

  // Validate ranges
  if (m < 1 || m > 12 || d < 1 || d > 31 || y < 1900 || y > 2100) {
    return null;
  }

  // Check if valid date (handles Feb 30, etc.)
  const date = new Date(y, m - 1, d);
  if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) {
    return null;
  }

  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
};

// Format input with auto-dots
const formatWithDots = (input: string): string => {
  const digits = input.replace(/\D/g, '');
  let result = '';

  for (let i = 0; i < digits.length && i < 8; i++) {
    result += digits[i];
    if ((i === 1 || i === 3) && i < digits.length - 1) {
      result += '.';
    }
  }

  return result;
};

// Expand 2-digit year to 4-digit
const expandYear = (display: string): string => {
  const parts = display.split('.');
  if (parts.length === 3 && parts[2].length === 2) {
    const yy = parseInt(parts[2], 10);
    const fullYear = yy <= 40 ? `20${parts[2]}` : `19${parts[2]}`;
    return `${parts[0]}.${parts[1]}.${fullYear}`;
  }
  return display;
};

const DateInput: React.FC<DateInputProps> = ({ value, onChange, placeholder, style }) => {
  const [displayValue, setDisplayValue] = useState(isoToDisplay(value || ''));
  const [isValid, setIsValid] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Update display when external value changes
  useEffect(() => {
    const newDisplay = isoToDisplay(value || '');
    setDisplayValue(newDisplay);
    setIsValid(true);
  }, [value]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatWithDots(e.target.value);
    setDisplayValue(formatted);

    // Validate as user types (only when complete)
    if (formatted.replace(/\./g, '').length === 8) {
      const expanded = expandYear(formatted);
      const iso = displayToIso(expanded);
      setIsValid(iso !== null);
    } else {
      setIsValid(true); // Don't show error while typing
    }
  };

  const handleBlur = () => {
    if (!displayValue) {
      setIsValid(true);
      onChange('');
      return;
    }

    // Expand short year on blur
    const expanded = expandYear(displayValue);
    if (expanded !== displayValue) {
      setDisplayValue(expanded);
    }

    const iso = displayToIso(expanded);
    if (iso) {
      setIsValid(true);
      onChange(iso);
    } else {
      setIsValid(false);
    }
  };

  const handlePickerChange = (date: Dayjs | null) => {
    setPickerOpen(false);
    if (date) {
      const iso = date.format('YYYY-MM-DD');
      const display = date.format('DD.MM.YYYY');
      setDisplayValue(display);
      setIsValid(true);
      onChange(iso);
    }
  };

  const handleCalendarClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setPickerOpen(true);
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block', ...style }}>
      <Input
        value={displayValue}
        onChange={handleInputChange}
        onBlur={handleBlur}
        placeholder={placeholder || 'DD.MM.YYYY'}
        suffix={
          <CalendarOutlined
            style={{ cursor: 'pointer', color: 'rgba(255, 255, 255, 0.45)' }}
            onClick={handleCalendarClick}
          />
        }
        status={isValid ? undefined : 'error'}
        style={{ width: '100%' }}
        maxLength={10}
      />
      <DatePicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        value={value ? dayjs(value) : null}
        onChange={handlePickerChange}
        format="DD.MM.YYYY"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          opacity: 0,
          pointerEvents: 'none',
        }}
        getPopupContainer={() => containerRef.current || document.body}
      />
    </div>
  );
};

export default DateInput;
