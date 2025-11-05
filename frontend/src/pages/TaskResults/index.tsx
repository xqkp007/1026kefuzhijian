import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card,
  Button,
  Typography,
  Space,
  Tag,
  Pagination,
  Spin,
  Result,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  CloseCircleOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { getTaskResults, exportTaskResults } from '../../api/tasks';
import {
  RunStatus,
  type EvaluationItem,
  type EvaluationRun,
  type ApiErrorResponse,
  type TaskDetails,
} from '../../types';
import type { AxiosError } from 'axios';
import { formatLatencySeconds } from '../../utils/date';
import './style.css';

const { Title, Text, Paragraph } = Typography;

type GroupedResult = {
  key: string;
  sessionGroup: string | null;
  items: EvaluationItem[];
};

const VERDICT_MAP: Record<string, { color: string; text: string; hint: string }> = {
  PASS: { color: 'green', text: '通过', hint: '5 次输出均被判定为正确' },
  PARTIAL_ERROR: {
    color: 'red',
    text: '部分错误',
    hint: '存在被矫正判定为错误的输出',
  },
  CORRECTION_FAILED: {
    color: 'orange',
    text: '矫正失败',
    hint: '矫正调用失败或未执行，无法判定该题',
  },
  UNDETERMINED: {
    color: 'default',
    text: '未判定',
    hint: '矫正未执行或尚未完成',
  },
};

const TaskResults: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [taskName, setTaskName] = useState('');
  const [items, setItems] = useState<EvaluationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1'));
  const [error, setError] = useState<string>('');
  const [taskInfo, setTaskInfo] = useState<TaskDetails | null>(null);

  const groupedItems = useMemo<GroupedResult[]>(() => {
    const results: GroupedResult[] = [];
    items.forEach((item, index) => {
      const groupKey = item.session_group ?? null;
      if (groupKey) {
        const last = results[results.length - 1];
        if (last && last.sessionGroup === groupKey) {
          last.items.push(item);
        } else {
          results.push({
            key: `group-${groupKey}-${results.length}`,
            sessionGroup: groupKey,
            items: [item],
          });
        }
      } else {
        results.push({
          key: `single-${item.question_id}-${index}`,
          sessionGroup: null,
          items: [item],
        });
      }
    });
    return results;
  }, [items]);

  // 获取结果
  const fetchResults = useCallback(
    async (currentPage: number) => {
      if (!taskId) return;

      setLoading(true);
      setError('');

      try {
        const response = await getTaskResults(taskId, {
          page: currentPage,
          page_size: 20,
        });

        setTaskName(response.task.task_name);
        setTaskInfo(response.task);
        setItems(response.items);
        setTotal(response.pagination.total);
      } catch (err) {
        const axiosError = err as AxiosError<ApiErrorResponse>;
        if (axiosError.response?.status === 409) {
          setError('任务尚未完成，请稍后查看');
        } else {
          setError('加载评测结果失败，请刷新重试');
        }
      } finally {
        setLoading(false);
      }
    },
    [taskId]
  );

  // 初始加载
  useEffect(() => {
    fetchResults(page);
  }, [fetchResults, page]);

  // 分页变化
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    setSearchParams({ page: newPage.toString() });
    // 滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // 导出CSV
  const handleExport = async () => {
    if (!taskId) return;

    setExporting(true);
    try {
      await exportTaskResults(taskId, taskName);
      message.success('导出成功');
    } catch (err) {
      const axiosError = err as AxiosError<ApiErrorResponse>;
      if (axiosError.response?.status === 409) {
        message.error('任务尚未完成，无法导出');
      } else {
        message.error('导出CSV失败，请重试');
      }
    } finally {
      setExporting(false);
    }
  };

  // 渲染运行结果
  const renderCorrectionInfo = (run: EvaluationRun) => {
    if (!taskInfo?.enable_correction) {
      return null;
    }
    const status = run.correction_status || 'PENDING';

    switch (status) {
      case 'SUCCESS': {
        const isCorrect = run.correction_result === true;
        return {
          tag: (
            <Tag color={isCorrect ? 'green' : 'red'}>
              {isCorrect ? '矫正：正确' : '矫正：错误'}
            </Tag>
          ),
          hint: run.correction_reason || undefined,
        };
      }
      case 'FAILED':
        return {
          tag: <Tag color="orange">矫正失败</Tag>,
          hint: run.correction_error_message || '矫正调用失败',
        };
      case 'SKIPPED':
        return {
          tag: <Tag>未执行矫正</Tag>,
          hint: run.correction_error_message || '未能执行矫正逻辑',
        };
      case 'PENDING':
      default:
        return {
          tag: <Tag color="default">矫正中</Tag>,
          hint: undefined,
        };
    }
  };

  const renderRun = (run: EvaluationRun, index: number) => {
    const isError = run.status === RunStatus.TIMEOUT || run.status === RunStatus.FAILED;

    const correctionInfo = renderCorrectionInfo(run);

    return (
      <div key={index} className="run-item">
        <div className="run-header">
          <Space>
            <Text strong>#{run.run_index}</Text>
            {isError ? (
              <Tag icon={<CloseCircleOutlined />} color="error">
                {run.error_code || '失败'}
              </Tag>
            ) : (
              <Tag icon={<CheckCircleOutlined />} color="success">
                成功
              </Tag>
            )}
            <Text type="secondary">
              耗时: {formatLatencySeconds(run.latency_ms)}
            </Text>
            {correctionInfo?.tag}
          </Space>
        </div>

        <div className="run-content">
          {isError ? (
            <Text type="danger">
              {run.error_message || run.error_code || '调用失败'}
            </Text>
          ) : (
            <Paragraph
              ellipsis={{
                rows: 3,
                expandable: true,
                symbol: '展开',
              }}
            >
              {run.response_body}
            </Paragraph>
          )}
          {correctionInfo?.hint && (
            <Text type="secondary" className="correction-hint">
              {correctionInfo.hint}
            </Text>
          )}
        </div>
      </div>
    );
  };

  const renderQuestionCard = (
    item: EvaluationItem,
    questionIndex: number,
    options?: { grouped?: boolean; roundIndex?: number; sessionGroup?: string | null }
  ) => {
    const failureType = item.failure_type ?? (item.is_passed === true ? 'PASS' : undefined);
    const verdict = VERDICT_MAP[failureType ?? 'UNDETERMINED'];
    const questionLabel = options?.grouped && options.roundIndex ? `第 ${options.roundIndex} 轮` : '问题';

    const content = (
      <>
        <div className="question-section">
          <Text strong className="question-text">
            #{questionIndex} {questionLabel}: {item.question}
          </Text>
          <Text type="secondary" className="answer-text">
            标准答案: {item.standard_answer}
          </Text>
          {taskInfo?.enable_correction && (
            <Tag color={verdict.color} style={{ marginLeft: 8 }}>
              {verdict.text}
            </Tag>
          )}
          {taskInfo?.enable_correction && (
            <div className="verdict-hint">{verdict.hint}</div>
          )}
        </div>

        <div className="runs-section">
          {item.runs.map((run, index) => renderRun(run, index))}
        </div>
      </>
    );

    if (options?.grouped) {
      return (
        <Card key={item.question_id} className="group-question-card" size="small" bordered={false}>
          {content}
        </Card>
      );
    }

    return (
      <Card key={item.question_id} className="result-card">
        {content}
      </Card>
    );
  };

  // 错误页面
  if (error) {
    return (
      <Result
        status="warning"
        title={error}
        extra={
          <Space>
            <Button onClick={() => navigate('/tasks')}>返回列表</Button>
            <Button type="primary" onClick={() => fetchResults(page)}>
              重试
            </Button>
          </Space>
        }
      />
    );
  }

  // 加载中
  if (loading && items.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  return (
    <>
      {/* 头部 */}
      <Card className="results-header-card">
        <div className="results-header">
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/tasks')}
            >
              返回列表
            </Button>
            <Title level={3} style={{ margin: 0 }}>
              评测报告: {taskName}
            </Title>
          </Space>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={handleExport}
          >
            {exporting ? '正在生成CSV...' : '导出CSV'}
          </Button>
        </div>
        {taskInfo?.enable_correction && (
          <div className="results-summary">
            <Space size="large">
              <Text strong>
                任务准确率:{' '}
                {typeof taskInfo.accuracy_rate === 'number'
                  ? `${taskInfo.accuracy_rate.toFixed(1)}%`
                  : '—'}
              </Text>
              <Text>
                通过题数：{taskInfo.passed_count ?? '--'} / 总题数：
                {taskInfo.total_items ?? '--'}
              </Text>
              <Text>未通过：{taskInfo.failed_count ?? '--'}</Text>
              <Text>
                部分错误：{taskInfo.partial_error_count ?? '--'}
              </Text>
              <Text>
                矫正失败：{taskInfo.correction_failed_count ?? '--'}
              </Text>
            </Space>
          </div>
        )}
      </Card>

      {/* 结果列表 */}
      <div className="results-list">
        {(() => {
          let questionIndex = (page - 1) * 20;
          return groupedItems.map((group) => {
            if (group.sessionGroup) {
              const runsPerItem = taskInfo?.runs_per_item ?? group.items[0]?.runs.length ?? 0;
              return (
                <Card key={group.key} className="session-group-card">
                  <div className="session-group-header">
                    <Space size="small">
                      <Tag color="blue">多轮对话</Tag>
                      <Text strong>{group.sessionGroup}</Text>
                    </Space>
                    <Text type="secondary">
                      {group.items.length} 轮 × {runsPerItem} 路径
                    </Text>
                  </div>
                  <div className="session-group-items">
                    {group.items.map((item, roundIdx) => {
                      questionIndex += 1;
                      return renderQuestionCard(item, questionIndex, {
                        grouped: true,
                        roundIndex: roundIdx + 1,
                        sessionGroup: group.sessionGroup,
                      });
                    })}
                  </div>
                </Card>
              );
            }

            const item = group.items[0];
            questionIndex += 1;
            return renderQuestionCard(item, questionIndex);
          });
        })()}
      </div>

      {/* 分页 */}
      {total > 20 && (
        <Card className="results-pagination-card">
          <Pagination
            current={page}
            pageSize={20}
            total={total}
            onChange={handlePageChange}
            showSizeChanger={false}
            showTotal={(total) => `共 ${total} 个问题`}
          />
        </Card>
      )}
    </>
  );
};

export default TaskResults;
