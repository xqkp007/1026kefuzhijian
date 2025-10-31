import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Table,
  Button,
  Tag,
  Typography,
  Space,
  Empty,
  message,
  Card,
} from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { getTasks } from '../../api/tasks';
import { TaskStatus, type EvaluationTask } from '../../types';
import { formatBeijingTime, formatDurationMinutes } from '../../utils/date';
import './style.css';

const { Title } = Typography;

const TaskList: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState<EvaluationTask[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1'));

  // 获取任务列表
  const fetchTasks = async (currentPage: number) => {
    setLoading(true);
    try {
      const response = await getTasks({
        page: currentPage,
        page_size: 20,
      });

      setTasks(response.items);
      setTotal(response.pagination.total);
    } catch {
      message.error('加载任务列表失败，请刷新重试');
    } finally {
      setLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    fetchTasks(page);
  }, [page]);

  // 刷新
  const handleRefresh = () => {
    fetchTasks(page);
  };

  // 分页变化
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    setSearchParams({ page: newPage.toString() });
  };

  // 状态Tag颜色映射
  const getStatusTag = (status: TaskStatus) => {
    const statusConfig = {
      [TaskStatus.PENDING]: { color: 'default', text: '等待中' },
      [TaskStatus.RUNNING]: { color: 'processing', text: '运行中' },
      [TaskStatus.SUCCEEDED]: { color: 'success', text: '已完成' },
      [TaskStatus.FAILED]: { color: 'error', text: '失败' },
    };

    const config = statusConfig[status];
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  // 进度显示
  const renderProgress = (task: EvaluationTask) => {
    const { status, progress } = task;
    const progressText = `${progress.processed}/${progress.total}`;

    // FAILED状态用红色显示实际进度
    if (status === TaskStatus.FAILED) {
      return <span style={{ color: '#ff4d4f' }}>{progressText}</span>;
    }

    return progressText;
  };

  // 表格列定义
  const columns: ColumnsType<EvaluationTask> = [
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: TaskStatus) => getStatusTag(status),
    },
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      // 仅对任务名称文本做省略，确保“矫正”标签不被遮挡
      render: (_, record) => (
        <div className="task-name-cell">
          <span className="task-name-text">{record.task_name}</span>
          {record.enable_correction && <Tag color="purple">矫正</Tag>}
        </div>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (created_at: string) => formatBeijingTime(created_at),
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 180,
      render: (completed_at: string | null) =>
        completed_at ? formatBeijingTime(completed_at) : '--',
    },
    {
      title: '耗时(分钟)',
      dataIndex: 'duration_seconds',
      key: 'duration',
      width: 140,
      render: (durationSeconds: number | null) =>
        durationSeconds !== null && durationSeconds !== undefined
          ? formatDurationMinutes(durationSeconds)
          : '--',
    },
    {
      title: '进度',
      key: 'progress',
      width: 120,
      render: (_,record) => renderProgress(record),
    },
    {
      title: '准确率',
      dataIndex: 'accuracy_rate',
      key: 'accuracy_rate',
      width: 120,
      align: 'center',
      render: (_, record) => {
        if (!record.enable_correction) {
          return '-';
        }
        if (record.status === TaskStatus.PENDING) {
          return '-';
        }
        if (record.status === TaskStatus.RUNNING) {
          return '计算中..';
        }
        if (record.status === TaskStatus.SUCCEEDED) {
          const value = record.accuracy_rate ?? 0;
          return `${value.toFixed(1)}%`;
        }
        return '-';
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button
          type="link"
          disabled={record.status !== TaskStatus.SUCCEEDED}
          onClick={() => navigate(`/tasks/${record.task_id}/results`)}
        >
          查看
        </Button>
      ),
    },
  ];

  return (
    <Card className="task-list-card">
      <div className="task-list-header">
        <Title level={3} style={{ margin: 0 }}>我的评测任务</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/')}
          >
            创建新任务
          </Button>
        </Space>
      </div>

      <Table
        style={{ marginTop: 24 }}
        columns={columns}
        dataSource={tasks}
        rowKey="task_id"
        loading={loading}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: handlePageChange,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 个任务`,
        }}
        locale={{
          emptyText: (
            <Empty
              description="还没有评测任务"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Button type="primary" onClick={() => navigate('/')}>
                创建第一个任务
              </Button>
            </Empty>
          ),
        }}
      />
    </Card>
  );
};

export default TaskList;
