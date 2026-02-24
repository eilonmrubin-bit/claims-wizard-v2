/**
 * SmartErrorDisplay - תצוגת שגיאות חכמה עם המלצות לתיקון
 */

import { Alert, Button, Space, Typography } from 'antd';
import {
  WarningOutlined,
  CalendarOutlined,
  DollarOutlined,
  ToolOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

interface ParsedError {
  type: 'work_pattern_missing' | 'salary_tier_missing' | 'other';
  periodId?: string;
  missingStart?: string;
  missingEnd?: string;
  originalMessage: string;
}

interface Suggestion {
  icon: React.ReactNode;
  text: string;
  action?: () => void;
  actionLabel?: string;
}

interface SmartErrorDisplayProps {
  errorMessage: string;
  employmentPeriods: Array<{ id: string; start: string; end: string }>;
  workPatterns: Array<{ id: string; start: string; end: string }>;
  salaryTiers: Array<{ id: string; start: string; end: string }>;
  onExtendWorkPattern?: (index: number, start: string, end: string) => void;
  onExtendSalaryTier?: (index: number, start: string, end: string) => void;
  onAddWorkPattern?: (start: string, end: string) => void;
  onAddSalaryTier?: (start: string, end: string) => void;
}

// Parse error message to extract structured info
const parseError = (message: string): ParsedError => {
  // Match: "דפוס עבודה חסר: תקופת העסקה X לא מכוסה בין Y ל-Z"
  const workPatternMatch = message.match(
    /דפוס עבודה חסר: תקופת העסקה (\S+) לא מכוסה בין (\d{4}-\d{2}-\d{2}) ל-?(\d{4}-\d{2}-\d{2})/
  );
  if (workPatternMatch) {
    return {
      type: 'work_pattern_missing',
      periodId: workPatternMatch[1],
      missingStart: workPatternMatch[2],
      missingEnd: workPatternMatch[3],
      originalMessage: message,
    };
  }

  // Match: "רמת שכר חסרה: תקופת העסקה X לא מכוסה בין Y ל-Z"
  const salaryMatch = message.match(
    /רמת שכר חסרה: תקופת העסקה (\S+) לא מכוסה בין (\d{4}-\d{2}-\d{2}) ל-?(\d{4}-\d{2}-\d{2})/
  );
  if (salaryMatch) {
    return {
      type: 'salary_tier_missing',
      periodId: salaryMatch[1],
      missingStart: salaryMatch[2],
      missingEnd: salaryMatch[3],
      originalMessage: message,
    };
  }

  return {
    type: 'other',
    originalMessage: message,
  };
};

// Format date for display
const formatDate = (dateStr: string): string => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1).toString().padStart(2, '0')}.${d.getFullYear()}`;
};

// Generate suggestions based on parsed error
const generateSuggestions = (
  error: ParsedError,
  props: SmartErrorDisplayProps
): Suggestion[] => {
  const suggestions: Suggestion[] = [];

  if (error.type === 'work_pattern_missing' && error.missingStart && error.missingEnd) {
    // Find an existing pattern to extend
    const existingPattern = props.workPatterns.findIndex((p) => {
      if (!p.start || !p.end) return false;
      // Check if pattern ends just before missing start or starts just after missing end
      const patternEnd = new Date(p.end);
      const missingStart = new Date(error.missingStart!);
      const dayBefore = new Date(missingStart);
      dayBefore.setDate(dayBefore.getDate() - 1);
      return patternEnd.toISOString().split('T')[0] === dayBefore.toISOString().split('T')[0];
    });

    if (existingPattern !== -1 && props.onExtendWorkPattern) {
      const pattern = props.workPatterns[existingPattern];
      suggestions.push({
        icon: <CalendarOutlined style={{ color: '#4ECDC4' }} />,
        text: `הרחב את דפוס עבודה ${existingPattern + 1} עד ${formatDate(error.missingEnd)}`,
        action: () => props.onExtendWorkPattern!(existingPattern, pattern.start, error.missingEnd!),
        actionLabel: 'הרחב',
      });
    }

    if (props.onAddWorkPattern) {
      suggestions.push({
        icon: <CalendarOutlined style={{ color: '#88D8E0' }} />,
        text: `צור דפוס עבודה חדש לתקופה ${formatDate(error.missingStart)} - ${formatDate(error.missingEnd)}`,
        action: () => props.onAddWorkPattern!(error.missingStart!, error.missingEnd!),
        actionLabel: 'צור',
      });
    }
  }

  if (error.type === 'salary_tier_missing' && error.missingStart && error.missingEnd) {
    // Find an existing tier to extend
    const existingTier = props.salaryTiers.findIndex((t) => {
      if (!t.start || !t.end) return false;
      const tierEnd = new Date(t.end);
      const missingStart = new Date(error.missingStart!);
      const dayBefore = new Date(missingStart);
      dayBefore.setDate(dayBefore.getDate() - 1);
      return tierEnd.toISOString().split('T')[0] === dayBefore.toISOString().split('T')[0];
    });

    if (existingTier !== -1 && props.onExtendSalaryTier) {
      const tier = props.salaryTiers[existingTier];
      suggestions.push({
        icon: <DollarOutlined style={{ color: '#4ECDC4' }} />,
        text: `הרחב את מדרגת שכר ${existingTier + 1} עד ${formatDate(error.missingEnd)}`,
        action: () => props.onExtendSalaryTier!(existingTier, tier.start, error.missingEnd!),
        actionLabel: 'הרחב',
      });
    }

    if (props.onAddSalaryTier) {
      suggestions.push({
        icon: <DollarOutlined style={{ color: '#88D8E0' }} />,
        text: `צור מדרגת שכר חדשה לתקופה ${formatDate(error.missingStart)} - ${formatDate(error.missingEnd)}`,
        action: () => props.onAddSalaryTier!(error.missingStart!, error.missingEnd!),
        actionLabel: 'צור',
      });
    }
  }

  return suggestions;
};

// Format error message for display
const formatErrorMessage = (error: ParsedError): React.ReactNode => {
  if (error.type === 'work_pattern_missing') {
    return (
      <span>
        <CalendarOutlined style={{ marginLeft: 8 }} />
        <strong>דפוס עבודה חסר:</strong> התקופה{' '}
        <Text code>{formatDate(error.missingStart || '')}</Text> עד{' '}
        <Text code>{formatDate(error.missingEnd || '')}</Text>{' '}
        לא מכוסה בדפוס עבודה
      </span>
    );
  }

  if (error.type === 'salary_tier_missing') {
    return (
      <span>
        <DollarOutlined style={{ marginLeft: 8 }} />
        <strong>מדרגת שכר חסרה:</strong> התקופה{' '}
        <Text code>{formatDate(error.missingStart || '')}</Text> עד{' '}
        <Text code>{formatDate(error.missingEnd || '')}</Text>{' '}
        לא מכוסה במדרגת שכר
      </span>
    );
  }

  return error.originalMessage;
};

const SmartErrorDisplay: React.FC<SmartErrorDisplayProps> = (props) => {
  const { errorMessage } = props;

  // Split by newlines and parse each error
  const errorLines = errorMessage.split('\n').filter((line) => line.trim());
  const parsedErrors = errorLines.map(parseError);

  return (
    <div className="smart-error-display">
      {parsedErrors.map((error, index) => {
        const suggestions = generateSuggestions(error, props);

        return (
          <Alert
            key={index}
            type="error"
            showIcon
            icon={<WarningOutlined />}
            style={{ marginBottom: 12 }}
            message={formatErrorMessage(error)}
            description={
              suggestions.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                    <ToolOutlined style={{ marginLeft: 4 }} />
                    הצעות לתיקון:
                  </Text>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {suggestions.map((suggestion, sIdx) => (
                      <div
                        key={sIdx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 12px',
                          background: 'rgba(78, 205, 196, 0.1)',
                          borderRadius: 4,
                        }}
                      >
                        <span>
                          {suggestion.icon}
                          <span style={{ marginRight: 8 }}>{suggestion.text}</span>
                        </span>
                        {suggestion.action && (
                          <Button
                            type="primary"
                            size="small"
                            onClick={suggestion.action}
                          >
                            {suggestion.actionLabel}
                          </Button>
                        )}
                      </div>
                    ))}
                  </Space>
                </div>
              )
            }
          />
        );
      })}
    </div>
  );
};

export default SmartErrorDisplay;
