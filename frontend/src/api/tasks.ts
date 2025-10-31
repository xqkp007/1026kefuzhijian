import apiClient from './client';
import type {
  CreateTaskRequest,
  CreateTaskResponse,
  GetTasksRequest,
  GetTasksResponse,
  GetResultsRequest,
  GetResultsResponse,
} from '../types';

/**
 * 创建评测任务
 */
export const createTask = async (
  data: CreateTaskRequest
): Promise<CreateTaskResponse> => {
  const formData = new FormData();
  formData.append('task_name', data.task_name);
  formData.append('agent_api_url', data.agent_api_url);
  formData.append('dataset_file', data.dataset_file, data.dataset_file.name);
  formData.append('enable_correction', String(data.enable_correction));

  const response = await apiClient.post<CreateTaskResponse>(
    '/v1/evaluation-tasks',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );

  return response.data;
};

/**
 * 获取任务列表
 */
export const getTasks = async (
  params: GetTasksRequest = {}
): Promise<GetTasksResponse> => {
  const response = await apiClient.get<GetTasksResponse>(
    '/v1/evaluation-tasks',
    {
      params: {
        page: params.page || 1,
        page_size: params.page_size || 20,
        ...(params.status && { status: params.status }),
        ...(params.query && { query: params.query }),
      },
    }
  );

  return response.data;
};

/**
 * 获取任务结果
 */
export const getTaskResults = async (
  taskId: string,
  params: GetResultsRequest = {}
): Promise<GetResultsResponse> => {
  const response = await apiClient.get<GetResultsResponse>(
    `/v1/evaluation-tasks/${taskId}/results`,
    {
      params: {
        page: params.page || 1,
        page_size: params.page_size || 20,
        ...(params.question_id && { question_id: params.question_id }),
      },
    }
  );

  return response.data;
};

/**
 * 导出任务结果为CSV
 */
export const exportTaskResults = async (
  taskId: string,
  taskName: string
): Promise<void> => {
  const response = await apiClient.get(`/v1/evaluation-tasks/${taskId}/export`, {
    responseType: 'blob',
    timeout: 60000, // 导出可能需要更长时间
  });

  // 创建下载链接
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;

  // 文件名安全处理
  const safeTaskName = taskName.replace(/[/\\:*?"<>|]/g, '_');
  link.setAttribute('download', `${safeTaskName}_评测报告.csv`);

  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};
