import { http, HttpResponse, delay } from 'msw';
import { TaskStatus, RunStatus } from '../types';
import type {
  CreateTaskResponse,
  GetTasksResponse,
  GetResultsResponse,
  EvaluationTask,
  EvaluationItem,
} from '../types';

// Mock数据生成辅助函数
const generateTaskId = () => `task-${Math.random().toString(36).substring(2, 9)}`;

// Mock任务列表数据
const mockTasks: EvaluationTask[] = [
  {
    task_id: 'task-001',
    task_name: 'A模型V1.2稳定性测试',
    status: TaskStatus.SUCCEEDED,
    progress: { processed: 100, total: 100 },
    created_at: '2025-10-26T10:30:00Z',
    updated_at: '2025-10-26T10:45:00Z',
  },
  {
    task_id: 'task-002',
    task_name: 'B模型最终验收测试',
    status: TaskStatus.RUNNING,
    progress: { processed: 75, total: 150 },
    created_at: '2025-10-26T10:25:00Z',
    updated_at: '2025-10-26T10:40:00Z',
  },
  {
    task_id: 'task-003',
    task_name: 'C模型初始化失败测试',
    status: TaskStatus.FAILED,
    progress: { processed: 25, total: 50 },
    created_at: '2025-10-26T10:20:00Z',
    updated_at: '2025-10-26T10:22:00Z',
  },
  {
    task_id: 'task-004',
    task_name: 'A模型V1.3回归测试',
    status: TaskStatus.PENDING,
    progress: { processed: 0, total: 200 },
    created_at: '2025-10-26T10:15:00Z',
    updated_at: '2025-10-26T10:15:00Z',
  },
];

// Mock结果数据
const mockResults: EvaluationItem[] = [
  {
    question_id: 'Q0001',
    question: '中国的首都是哪里？',
    standard_answer: '北京',
    system_prompt: null,
    user_context: null,
    runs: [
      {
        run_index: 1,
        status: RunStatus.SUCCEEDED,
        response_body: '北京是中国的首都。',
        latency_ms: 812,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:31:12Z',
      },
      {
        run_index: 2,
        status: RunStatus.SUCCEEDED,
        response_body: '中华人民共和国的首都是北京。',
        latency_ms: 756,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:31:13Z',
      },
      {
        run_index: 3,
        status: RunStatus.SUCCEEDED,
        response_body: '北京',
        latency_ms: 650,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:31:14Z',
      },
      {
        run_index: 4,
        status: RunStatus.TIMEOUT,
        response_body: null,
        latency_ms: 30000,
        error_code: 'TIMEOUT',
        error_message: 'Agent request timed out after 30s',
        created_at: '2025-10-26T10:32:45Z',
      },
      {
        run_index: 5,
        status: RunStatus.SUCCEEDED,
        response_body: '北京，也被称为Peking，是中华人民共和国的首都和直辖市，位于华北平原北部。',
        latency_ms: 920,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:31:15Z',
      },
    ],
  },
  {
    question_id: 'Q0002',
    question: '上海的别称是什么？',
    standard_answer: '申城、魔都',
    system_prompt: null,
    user_context: null,
    runs: [
      {
        run_index: 1,
        status: RunStatus.SUCCEEDED,
        response_body: '上海的别称包括"申城"和"魔都"。',
        latency_ms: 830,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:32:12Z',
      },
      {
        run_index: 2,
        status: RunStatus.SUCCEEDED,
        response_body: '申城、魔都',
        latency_ms: 720,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:32:13Z',
      },
      {
        run_index: 3,
        status: RunStatus.SUCCEEDED,
        response_body: '上海又被称为"申城"，源自春秋时期楚国的封地申。现代还有"魔都"的称呼。',
        latency_ms: 890,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:32:14Z',
      },
      {
        run_index: 4,
        status: RunStatus.SUCCEEDED,
        response_body: '魔都',
        latency_ms: 680,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:32:15Z',
      },
      {
        run_index: 5,
        status: RunStatus.SUCCEEDED,
        response_body: '申城',
        latency_ms: 670,
        error_code: null,
        error_message: null,
        created_at: '2025-10-26T10:32:16Z',
      },
    ],
  },
];

export const handlers = [
  // POST /api/v1/evaluation-tasks - 创建任务
  http.post('/api/v1/evaluation-tasks', async () => {
    await delay(500); // 模拟网络延迟

    const response: CreateTaskResponse = {
      task_id: generateTaskId(),
      status: TaskStatus.PENDING,
    };

    return HttpResponse.json(response, { status: 200 });
  }),

  // GET /api/v1/evaluation-tasks - 获取任务列表
  http.get('/api/v1/evaluation-tasks', async ({ request }) => {
    await delay(300);

    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const pageSize = parseInt(url.searchParams.get('page_size') || '20');

    const response: GetTasksResponse = {
      items: mockTasks,
      pagination: {
        page,
        page_size: pageSize,
        total: mockTasks.length,
      },
    };

    return HttpResponse.json(response, { status: 200 });
  }),

  // GET /api/v1/evaluation-tasks/:taskId/results - 获取任务结果
  http.get('/api/v1/evaluation-tasks/:taskId/results', async ({ params, request }) => {
    await delay(400);

    const { taskId } = params;
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const pageSize = parseInt(url.searchParams.get('page_size') || '20');

    // 查找任务
    const task = mockTasks.find((t) => t.task_id === taskId);
    if (!task) {
      return HttpResponse.json(
        { code: 'TASK_NOT_FOUND', message: '任务不存在' },
        { status: 404 }
      );
    }

    // 检查任务状态
    if (task.status !== TaskStatus.SUCCEEDED) {
      return HttpResponse.json(
        { code: 'TASK_NOT_FINISHED', message: '任务尚未完成' },
        { status: 409 }
      );
    }

    const response: GetResultsResponse = {
      task: {
        task_id: task.task_id,
        task_name: task.task_name,
        status: task.status,
        runs_per_item: 5,
        timeout_seconds: 30,
      },
      items: mockResults,
      pagination: {
        page,
        page_size: pageSize,
        total: mockResults.length,
      },
    };

    return HttpResponse.json(response, { status: 200 });
  }),

  // GET /api/v1/evaluation-tasks/:taskId/export - 导出CSV
  http.get('/api/v1/evaluation-tasks/:taskId/export', async ({ params }) => {
    await delay(800);

    const { taskId } = params;

    // 查找任务
    const task = mockTasks.find((t) => t.task_id === taskId);
    if (!task) {
      return HttpResponse.json(
        { code: 'TASK_NOT_FOUND', message: '任务不存在' },
        { status: 404 }
      );
    }

    // 检查任务状态
    if (task.status !== TaskStatus.SUCCEEDED) {
      return HttpResponse.json(
        { code: 'TASK_NOT_FINISHED', message: '任务尚未完成，无法导出' },
        { status: 409 }
      );
    }

    // 生成CSV内容
    const csv = `question_id,question,standard_answer,run_1_output,run_1_status,run_1_latency_ms,run_1_error_code,run_2_output,run_2_status,run_2_latency_ms,run_2_error_code
Q0001,中国的首都是哪里？,北京,北京是中国的首都。,SUCCEEDED,812,,中华人民共和国的首都是北京。,SUCCEEDED,756,
Q0002,上海的别称是什么？,申城、魔都,上海的别称包括"申城"和"魔都"。,SUCCEEDED,830,,申城、魔都,SUCCEEDED,720,`;

    return HttpResponse.text(csv, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="${task.task_name}_评测报告.csv"`,
      },
    });
  }),
];
