/**
 * 인증 관련 API 호출 함수. 로그인, 회원가입, 닉네임 중복 확인, 성인인증 요청.
 */
import { api } from './api';

type LoginResponse = {
  access_token: string;
  token_type: string;
};

/** 로그인 → JWT 토큰 반환. */
export async function login(nickname: string, password: string): Promise<LoginResponse> {
  return api.post<LoginResponse>('/auth/login', { nickname, password });
}

/** 회원가입 → 자동 로그인 (JWT 토큰 반환). */
export async function register(
  nickname: string,
  password: string,
  email?: string,
): Promise<LoginResponse> {
  return api.post<LoginResponse>('/auth/register', { nickname, password, email: email || null });
}

/** 닉네임 중복 확인. 사용 가능하면 true. */
export async function checkNickname(nickname: string): Promise<boolean> {
  const res = await api.get<{ available: boolean }>(`/auth/check-nickname?nickname=${encodeURIComponent(nickname)}`);
  return res.available;
}

/** 성인인증 요청 (본인확인 방법 전달). */
export async function requestAdultVerification(method: string): Promise<void> {
  await api.post('/auth/adult-verify', { method });
}
