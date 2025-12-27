import axios, { AxiosError } from 'axios';

// 创建 axios 实例
export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const getApiKey = (): string | null => {
  const envKey = import.meta.env.VITE_MA_API_KEY;
  if (envKey) {
    return envKey;
  }
  return localStorage.getItem('MA_API_KEY');
};

// Request interceptor - inject API key if available
apiClient.interceptors.request.use((config) => {
  const apiKey = getApiKey();
  if (apiKey) {
    config.headers = config.headers ?? {};
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // 提取错误信息
    const message =
      (error.response?.data as { detail?: string })?.detail ||
      error.message ||
      '网络错误，请稍后重试';

    console.error('API Error:', message);
    return Promise.reject(new Error(message));
  }
);

// 通用 API 错误类型
export interface ApiError {
  message: string;
  status?: number;
}
