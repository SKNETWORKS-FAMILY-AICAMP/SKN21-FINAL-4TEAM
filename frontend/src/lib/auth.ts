import { api } from './api';

type LoginResponse = {
  access_token: string;
  token_type: string;
};

type UserResponse = {
  id: string;
  nickname: string;
  role: 'user' | 'admin';
  age_group: string;
  adult_verified_at: string | null;
  preferred_llm_model_id: string | null;
};

export async function login(nickname: string, password: string): Promise<LoginResponse> {
  return api.post<LoginResponse>('/auth/login', { nickname, password });
}

export async function register(nickname: string, password: string): Promise<UserResponse> {
  return api.post<UserResponse>('/auth/register', { nickname, password });
}

export async function requestAdultVerification(method: string): Promise<void> {
  await api.post('/auth/adult-verify', { method });
}
