/**
 * API 클라이언트. 모든 백엔드 요청은 이 모듈을 통해 수행한다.
 * - 자동으로 JWT 토큰을 Authorization 헤더에 첨부
 * - 에러 응답을 ApiError로 변환
 */
const BASE_URL = '/api';

/** 백엔드 에러 응답을 표현하는 커스텀 에러. status, code, message를 포함. */
class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** 공통 fetch 래퍼. JWT 토큰 자동 첨부 + 에러 변환. */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.error_code ?? 'UNKNOWN_ERROR',
      body.detail ?? 'An error occurred',
    );
  }

  // 204 No Content 등 본문이 없는 응답 처리
  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }

  return response.json();
}

type RequestOptions = { signal?: AbortSignal };

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { signal: options?.signal }),
  post: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined, signal: options?.signal }),
  put: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, { method: 'PUT', body: data ? JSON.stringify(data) : undefined, signal: options?.signal }),
  patch: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, { method: 'PATCH', body: data ? JSON.stringify(data) : undefined, signal: options?.signal }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { method: 'DELETE', signal: options?.signal }),
  upload: <T>(path: string, file: File, fieldName = 'file') => {
    const formData = new FormData();
    formData.append(fieldName, file);
    return request<T>(path, { method: 'POST', body: formData });
  },
};

export { ApiError };
