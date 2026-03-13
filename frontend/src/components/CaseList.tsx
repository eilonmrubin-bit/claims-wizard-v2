/**
 * CaseList - Case management UI component.
 *
 * Features:
 * - List all cases with metadata
 * - Search/filter cases
 * - Create new case
 * - Delete case with confirmation
 * - Load case on click
 */

import { useState, useEffect } from 'react';
import {
  Card,
  List,
  Input,
  Button,
  Space,
  Modal,
  Empty,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  DeleteOutlined,
  FileOutlined,
  UserOutlined,
  TeamOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';

const { Text, Title } = Typography;
const { Search } = Input;

interface CaseListItem {
  case_id: string;
  case_name: string;
  worker_name: string | null;
  defendant_name: string | null;
  last_modified: string;
  created_at: string;
  has_results: boolean;
}

interface CaseListProps {
  onSelectCase: (caseId: string) => void;
  onNewCase: () => void;
  hasUnsavedChanges: boolean;
}

const CaseList: React.FC<CaseListProps> = ({
  onSelectCase,
  onNewCase,
  hasUnsavedChanges,
}) => {
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteModal, setDeleteModal] = useState<{ visible: boolean; caseId: string; caseName: string }>({
    visible: false,
    caseId: '',
    caseName: '',
  });

  // Load cases on mount
  useEffect(() => {
    loadCases();
  }, []);

  const loadCases = async () => {
    setLoading(true);
    try {
      const response = await fetch('/cases/list');
      const data = await response.json();
      setCases(data.cases || []);
    } catch (err) {
      message.error('שגיאה בטעינת רשימת התיקים');
      console.error('Error loading cases:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      loadCases();
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`/cases/search?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      setCases(data.cases || []);
    } catch (err) {
      message.error('שגיאה בחיפוש');
      console.error('Error searching cases:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    try {
      const response = await fetch(`/cases/${deleteModal.caseId}`, {
        method: 'DELETE',
      });
      const data = await response.json();

      if (data.success) {
        message.success('התיק נמחק בהצלחה');
        loadCases();
      } else {
        message.error(data.error || 'שגיאה במחיקת התיק');
      }
    } catch (err) {
      message.error('שגיאה במחיקת התיק');
      console.error('Error deleting case:', err);
    } finally {
      setDeleteModal({ visible: false, caseId: '', caseName: '' });
    }
  };

  const handleSelectCase = (caseId: string) => {
    if (hasUnsavedChanges) {
      Modal.confirm({
        title: 'שינויים לא שמורים',
        content: 'יש שינויים שלא נשמרו. האם להמשיך בכל זאת?',
        okText: 'המשך',
        cancelText: 'ביטול',
        okType: 'danger',
        onOk: () => onSelectCase(caseId),
      });
    } else {
      onSelectCase(caseId);
    }
  };

  const handleNewCase = () => {
    if (hasUnsavedChanges) {
      Modal.confirm({
        title: 'שינויים לא שמורים',
        content: 'יש שינויים שלא נשמרו. האם להמשיך בכל זאת?',
        okText: 'המשך',
        cancelText: 'ביטול',
        okType: 'danger',
        onOk: () => onNewCase(),
      });
    } else {
      onNewCase();
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('he-IL', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Title level={4} style={{ margin: 0 }}>
            <FileOutlined style={{ marginLeft: 8 }} />
            ניהול תיקים
          </Title>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleNewCase}
          >
            תיק חדש
          </Button>
        </div>
      }
      style={{ maxWidth: 800, margin: '0 auto' }}
    >
      <Search
        placeholder="חיפוש לפי שם תיק, שם עובד או שם נתבע..."
        allowClear
        enterButton={<SearchOutlined />}
        size="large"
        onSearch={handleSearch}
        onChange={(e) => {
          if (!e.target.value) {
            setSearchQuery('');
            loadCases();
          }
        }}
        style={{ marginBottom: 16 }}
      />

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip="טוען תיקים..." />
        </div>
      ) : cases.length === 0 ? (
        <Empty
          description={searchQuery ? 'לא נמצאו תוצאות' : 'אין תיקים עדיין'}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          {!searchQuery && (
            <Button type="primary" icon={<PlusOutlined />} onClick={handleNewCase}>
              צור תיק חדש
            </Button>
          )}
        </Empty>
      ) : (
        <List
          dataSource={cases}
          renderItem={(item) => (
            <List.Item
              style={{
                cursor: 'pointer',
                borderRadius: 8,
                marginBottom: 8,
                padding: '12px 16px',
                backgroundColor: 'rgba(78, 205, 196, 0.05)',
                border: '1px solid rgba(78, 205, 196, 0.2)',
              }}
              onClick={() => handleSelectCase(item.case_id)}
              actions={[
                <Button
                  key="delete"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteModal({
                      visible: true,
                      caseId: item.case_id,
                      caseName: item.case_name,
                    });
                  }}
                />,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Text strong style={{ fontSize: 16 }}>
                      {item.case_name || 'תיק ללא שם'}
                    </Text>
                    {item.has_results && (
                      <Tag color="success">מחושב</Tag>
                    )}
                  </Space>
                }
                description={
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space wrap>
                      {item.worker_name && (
                        <span>
                          <UserOutlined style={{ marginLeft: 4 }} />
                          {item.worker_name}
                        </span>
                      )}
                      {item.defendant_name && (
                        <span>
                          <TeamOutlined style={{ marginLeft: 4 }} />
                          {item.defendant_name}
                        </span>
                      )}
                    </Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      <ClockCircleOutlined style={{ marginLeft: 4 }} />
                      עודכן: {formatDate(item.last_modified)}
                    </Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      )}

      <Modal
        title="מחיקת תיק"
        open={deleteModal.visible}
        onOk={handleDelete}
        onCancel={() => setDeleteModal({ visible: false, caseId: '', caseName: '' })}
        okText="מחק"
        cancelText="ביטול"
        okType="danger"
      >
        <p>
          האם למחוק את התיק "{deleteModal.caseName}"?
        </p>
        <p style={{ color: '#FF6B6B' }}>
          פעולה זו אינה ניתנת לביטול.
        </p>
      </Modal>
    </Card>
  );
};

export default CaseList;
