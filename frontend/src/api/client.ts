import axios, { AxiosError } from 'axios';
import { message } from 'antd';
import type { ApiErrorResponse } from '../types';

/**
 * 创建 Axios 实例
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000, // 默认30秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 请求拦截器
 */
apiClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加token等认证信息
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * 响应拦截器
 */
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError<ApiErrorResponse>) => {
    // 统一错误处理
    if (error.response) {
      // 服务器返回错误响应
      const { status, data } = error.response;

      switch (status) {
        case 400:
          message.error(data?.message || '请求参数错误');
          break;
        case 404:
          message.error(data?.message || '资源不存在');
          break;
        case 409:
          message.error(data?.message || '任务状态冲突');
          break;
        case 422:
          message.error(data?.message || '数据验证失败');
          break;
        case 500:
          message.error(data?.message || '服务器内部错误');
          break;
        default:
          message.error(data?.message || '请求失败');
      }
    } else if (error.request) {
      // 请求已发送但没有收到响应
      message.error('网络连接失败，请检查网络后重试');
    } else {
      // 其他错误
      message.error('请求失败，请重试');
    }

    return Promise.reject(error);
  }
);

export default apiClient;
