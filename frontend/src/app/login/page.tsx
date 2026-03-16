'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Swords, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';

type AuthMode = 'login' | 'register';

/** 하드코딩 사용자 계정 (백엔드 미연동) */
const MOCK_ACCOUNTS: Record<string, { password: string; nickname: string; role: 'user' | 'admin' }> = {
  nemo_user: { password: '123456', nickname: '토론왕김철수', role: 'user' },
  admin: { password: 'admin123', nickname: '관리자', role: 'admin' },
};

function validateLoginId(value: string): string | null {
  if (value.length < 2) return '2자 이상 입력하세요';
  if (value.length > 30) return '30자 이하로 입력하세요';
  if (!/^[a-zA-Z0-9_]+$/.test(value)) return '영문, 숫자, 밑줄(_)만 가능';
  return null;
}

function validateNickname(value: string): string | null {
  if (value.length < 2) return '2자 이상 입력하세요';
  if (value.length > 20) return '20자 이하로 입력하세요';
  if (!/^[a-zA-Z0-9가-힣_]+$/.test(value)) return '한글, 영문, 숫자, 밑줄(_)만 가능';
  return null;
}

function getPasswordStrength(pw: string): { level: 0 | 1 | 2 | 3; label: string; color: string } {
  if (pw.length < 6) return { level: 0, label: '6자 이상 필요', color: 'bg-gray-300' };
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  if (score <= 1) return { level: 1, label: '약함', color: 'bg-red-500' };
  if (score <= 2) return { level: 2, label: '보통', color: 'bg-yellow-500' };
  return { level: 3, label: '강함', color: 'bg-green-500' };
}

export default function LoginPage() {
  const router = useRouter();
  const { setUser } = useUserStore();
  const [mode, setMode] = useState<AuthMode>('login');
  const [loginId, setLoginId] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const passwordStrength = getPasswordStrength(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // 짧은 딜레이로 실제 통신 느낌
    await new Promise((r) => setTimeout(r, 500));

    if (mode === 'login') {
      // 하드코딩 로그인 검증
      const account = MOCK_ACCOUNTS[loginId];
      if (!account || account.password !== password) {
        setError('아이디 또는 비밀번호가 올바르지 않습니다');
        setLoading(false);
        return;
      }
      setUser({
        id: `user-${loginId}`,
        login_id: loginId,
        nickname: account.nickname,
        role: account.role,
        ageGroup: 'adult_verified',
        adultVerifiedAt: '2025-11-15T09:00:00Z',
        preferredLlmModelId: null,
        creditBalance: 1000,
        subscriptionPlanKey: null,
      });
      router.push(account.role === 'admin' ? '/admin' : '/');
    } else {
      // 하드코딩 회원가입 검증
      const loginIdErr = validateLoginId(loginId.trim());
      if (loginIdErr) { setError(loginIdErr); setLoading(false); return; }
      const nicknameErr = validateNickname(nickname.trim());
      if (nicknameErr) { setError(nicknameErr); setLoading(false); return; }
      if (password.length < 6) { setError('비밀번호는 6자 이상이어야 합니다'); setLoading(false); return; }
      if (password !== confirmPassword) { setError('비밀번호가 일치하지 않습니다'); setLoading(false); return; }
      if (MOCK_ACCOUNTS[loginId.trim()]) { setError('이미 사용 중인 아이디입니다'); setLoading(false); return; }

      // 새 계정을 메모리에 추가
      MOCK_ACCOUNTS[loginId.trim()] = { password, nickname: nickname.trim(), role: 'user' };
      setUser({
        id: `user-${loginId.trim()}`,
        login_id: loginId.trim(),
        nickname: nickname.trim(),
        role: 'user',
        ageGroup: 'unverified',
        adultVerifiedAt: null,
        preferredLlmModelId: null,
        creditBalance: 0,
        subscriptionPlanKey: null,
      });
      router.push('/');
    }
    setLoading(false);
  };

  return (
    <div className="flex justify-center items-center min-h-screen" style={{ background: 'linear-gradient(135deg, #FFFBF1 0%, #e8f4fd 50%, #d4ecff 100%)' }}>
      <div className="bg-white rounded-2xl py-10 px-6 md:px-10 w-full max-w-[440px] mx-4 brutal-border brutal-shadow-sm">
        {/* 로고 */}
        <div className="flex justify-center mb-3">
          <Swords size={48} className="text-primary" />
        </div>
        <h1 className="m-0 text-2xl text-center text-black font-black">NEMo</h1>
        <p className="text-center text-gray-500 text-sm mb-6">LLM 에이전트 AI 토론 플랫폼</p>

        {/* 탭 토글 */}
        <div className="flex mb-6 border-b-2 border-black">
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm font-bold transition-all ${
              mode === 'login'
                ? 'text-primary border-b-2 border-primary -mb-[2px]'
                : 'text-gray-400 hover:text-gray-600'
            }`}
            onClick={() => { setMode('login'); setError(''); }}
          >
            로그인
          </button>
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm font-bold transition-all ${
              mode === 'register'
                ? 'text-primary border-b-2 border-primary -mb-[2px]'
                : 'text-gray-400 hover:text-gray-600'
            }`}
            onClick={() => { setMode('register'); setError(''); }}
          >
            회원가입
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3">
          {/* 아이디 */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-bold text-gray-600">아이디</label>
            <input
              type="text"
              placeholder={mode === 'register' ? '2~30자, 영문/숫자/밑줄' : '아이디'}
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              required
              maxLength={30}
              className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
            />
          </div>

          {/* 닉네임 (회원가입만) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-bold text-gray-600">닉네임</label>
              <input
                type="text"
                placeholder="2~20자, 한글/영문/숫자"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                required
                maxLength={20}
                className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
              />
            </div>
          )}

          {/* 이메일 (회원가입만) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-bold text-gray-600">
                이메일 <span className="text-gray-400 font-normal">(선택)</span>
              </label>
              <input
                type="email"
                placeholder="example@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
              />
            </div>
          )}

          {/* 비밀번호 */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-bold text-gray-600">비밀번호</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder={mode === 'register' ? '6자 이상' : '비밀번호'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 pr-10 text-sm text-black focus:outline-none focus:border-primary"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-gray-400 hover:text-black p-0"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {mode === 'register' && password.length > 0 && (
              <div className="flex items-center gap-2 mt-1">
                <div className="flex gap-1 flex-1">
                  {[1, 2, 3].map((level) => (
                    <div
                      key={level}
                      className={`h-1.5 flex-1 rounded-full ${
                        level <= passwordStrength.level ? passwordStrength.color : 'bg-gray-200'
                      }`}
                    />
                  ))}
                </div>
                <span className="text-xs text-gray-500 font-semibold">{passwordStrength.label}</span>
              </div>
            )}
          </div>

          {/* 비밀번호 확인 (회원가입만) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-bold text-gray-600">비밀번호 확인</label>
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="비밀번호 다시 입력"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className={`w-full bg-gray-50 border-2 rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary ${
                  confirmPassword && password !== confirmPassword ? 'border-red-500' : 'border-black'
                } ${confirmPassword && password === confirmPassword && password.length >= 6 ? 'border-green-500' : ''}`}
              />
              {confirmPassword && password !== confirmPassword && (
                <span className="text-red-500 text-xs font-semibold">비밀번호가 일치하지 않습니다</span>
              )}
              {confirmPassword && password === confirmPassword && password.length >= 6 && (
                <span className="text-green-500 text-xs font-semibold">비밀번호가 일치합니다</span>
              )}
            </div>
          )}

          {/* 에러 메시지 */}
          {error && (
            <div className="flex items-center gap-2 py-2.5 px-3 rounded-xl bg-red-50 border-2 border-red-300">
              <AlertCircle size={14} className="text-red-500 shrink-0" />
              <p className="text-red-600 text-[13px] font-semibold m-0">{error}</p>
            </div>
          )}

          {/* 제출 버튼 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 mt-2 bg-primary text-white text-[15px] font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
          >
            {loading ? '처리 중...' : mode === 'login' ? '로그인' : '가입하기'}
          </button>

          {/* 테스트 계정 안내 */}
          {mode === 'login' && (
            <div className="mt-2 p-3 bg-blue-50 border-2 border-blue-200 rounded-xl">
              <p className="text-xs font-bold text-blue-700 m-0 mb-1">🧪 테스트 계정</p>
              <p className="text-xs text-blue-600 m-0">아이디: <strong>nemo_user</strong> / 비밀번호: <strong>123456</strong></p>
              <p className="text-xs text-blue-600 m-0">아이디: <strong>admin</strong> / 비밀번호: <strong>admin123</strong></p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
