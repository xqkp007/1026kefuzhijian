/**
 * 任务状态枚举
 */
export const TaskStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  SUCCEEDED: 'SUCCEEDED',
  FAILED: 'FAILED',
} as const;

export type TaskStatus = (typeof TaskStatus)[keyof typeof TaskStatus];

/**
 * 运行状态枚举
 */
export const RunStatus = {
  SUCCEEDED: 'SUCCEEDED',
  FAILED: 'FAILED',
  TIMEOUT: 'TIMEOUT',
  RETRYING: 'RETRYING',
} as const;

export type RunStatus = (typeof RunStatus)[keyof typeof RunStatus];

/**
 * 任务进度
 */
export interface TaskProgress {
  processed: number;
  total: number;
}

/**
 * 评测任务
 */
export interface EvaluationTask {
  task_id: string;
  task_name: string;
  status: TaskStatus;
  enable_correction: boolean;
  accuracy_rate?: number | null;
  progress: TaskProgress;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}

/**
 * 运行结果
 */
export interface EvaluationRun {
  run_index: number;
  status: RunStatus;
  response_body: string | null;
  latency_ms: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  correction_status?: string | null;
  correction_result?: boolean | null;
  correction_reason?: string | null;
  correction_error_message?: string | null;
  correction_retries?: number | null;
}

/**
 * 评测项（问题 + 运行结果）
 */
export interface EvaluationItem {
  question_id: string;
  question: string;
  standard_answer: string;
  system_prompt: string | null;
  user_context: string | null;
  is_passed?: boolean | null;
  failure_type?: 'PASS' | 'PARTIAL_ERROR' | 'CORRECTION_FAILED' | 'UNDETERMINED';
  runs: EvaluationRun[];
}

/**
 * 任务详情（包含任务信息）
 */
export interface TaskDetails {
  task_id: string;
  task_name: string;
  status: TaskStatus;
  runs_per_item: number;
  timeout_seconds: number;
  enable_correction?: boolean;
  accuracy_rate?: number | null;
  passed_count?: number;
  failed_count?: number;
  partial_error_count?: number;
  correction_failed_count?: number;
  total_items?: number;
  created_at?: string;
  completed_at?: string | null;
  updated_at?: string;
}

// ==================== API 请求/响应类型 ====================

/**
 * 创建任务请求
 */
export interface CreateTaskRequest {
  task_name: string;
  agent_api_url: string;
  dataset_file: File;
  enable_correction: boolean;
}

/**
 * 创建任务响应
 */
export interface CreateTaskResponse {
  task_id: string;
  status: TaskStatus;
  enable_correction: boolean;
}

/**
 * 获取任务列表请求参数
 */
export interface GetTasksRequest {
  page?: number;
  page_size?: number;
  status?: TaskStatus;
  query?: string;
}

/**
 * 分页信息
 */
export interface Pagination {
  page: number;
  page_size: number;
  total: number;
}

/**
 * 获取任务列表响应
 */
export interface GetTasksResponse {
  items: EvaluationTask[];
  pagination: Pagination;
}

/**
 * 获取任务结果请求参数
 */
export interface GetResultsRequest {
  page?: number;
  page_size?: number;
  question_id?: string;
}

/**
 * 获取任务结果响应
 */
export interface GetResultsResponse {
  task: TaskDetails;
  items: EvaluationItem[];
  pagination: Pagination;
}

/**
 * API 错误响应
 */
export interface ApiErrorResponse {
  code: string;
  message: string;
}
