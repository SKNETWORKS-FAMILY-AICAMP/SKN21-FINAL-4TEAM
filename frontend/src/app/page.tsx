'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Drama, Check, X, AlertCircle, Eye, EyeOff,
  Heart, Swords, Sparkles, Smile, Ghost, Laugh, Clapperboard, Rocket, ChevronRight,
} from 'lucide-react';
import { login, register, checkNickname } from '@/lib/auth';
import { useUserStore } from '@/stores/userStore';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';
import { CATEGORIES } from '@/constants/categories';

type AuthMode = 'login' | 'register';
type NicknameStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';
type Step = 'auth' | 'themes';

const THEME_ICONS: Record<string, { icon: typeof Heart; color: string }> = {
  romance: { icon: Heart, color: 'text-pink-400' },
  action: { icon: Swords, color: 'text-orange-400' },
  fantasy: { icon: Sparkles, color: 'text-purple-400' },
  daily: { icon: Smile, color: 'text-green-400' },
  horror: { icon: Ghost, color: 'text-red-400' },
  comedy: { icon: Laugh, color: 'text-yellow-400' },
  drama: { icon: Clapperboard, color: 'text-blue-400' },
  scifi: { icon: Rocket, color: 'text-cyan-400' },
};

const THEMES = CATEGORIES.map((c) => ({
  ...c,
  icon: THEME_ICONS[c.id]?.icon ?? Heart,
  color: THEME_ICONS[c.id]?.color ?? 'text-text-muted',
}));

function validateNickname(value: string): string | null {
  if (value.length < 2) return '2자 이상 입력하세요';
  if (value.length > 20) return '20자 이하로 입력하세요';
  if (!/^[a-zA-Z0-9가-힣_]+$/.test(value)) return '한글, 영문, 숫자, 밑줄(_)만 가능';
  return null;
}

function getPasswordStrength(pw: string): { level: 0 | 1 | 2 | 3; label: string; color: string } {
  if (pw.length < 6) return { level: 0, label: '6자 이상 필요', color: 'bg-text-muted' };
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  if (score <= 1) return { level: 1, label: '약함', color: 'bg-danger' };
  if (score <= 2) return { level: 2, label: '보통', color: 'bg-warning' };
  return { level: 3, label: '강함', color: 'bg-success' };
}

export default function HomePage() {
  const router = useRouter();
  const { setUser, setToken } = useUserStore();
  const [mode, setMode] = useState<AuthMode>('login');
  const [step, setStep] = useState<Step>('auth');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Theme selection (after registration)
  const [selectedThemes, setSelectedThemes] = useState<string[]>([]);
  const [registeredToken, setRegisteredToken] = useState<string | null>(null);

  // Nickname duplicate check
  const [nicknameStatus, setNicknameStatus] = useState<NicknameStatus>('idle');
  const [nicknameError, setNicknameError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const checkNicknameAvailability = useCallback((value: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const validationError = validateNickname(value);
    if (validationError) {
      setNicknameStatus('invalid');
      setNicknameError(validationError);
      return;
    }
    setNicknameStatus('checking');
    setNicknameError(null);
    debounceRef.current = setTimeout(async () => {
      try {
        const available = await checkNickname(value);
        setNicknameStatus(available ? 'available' : 'taken');
        setNicknameError(available ? null : '이미 사용 중인 닉네임입니다');
      } catch {
        setNicknameStatus('idle');
      }
    }, 500);
  }, []);

  const handleNicknameChange = (value: string) => {
    setNickname(value);
    if (mode === 'register' && value.trim().length > 0) {
      checkNicknameAvailability(value.trim());
    } else {
      setNicknameStatus('idle');
      setNicknameError(null);
    }
  };

  useEffect(() => {
    setError('');
    setNicknameStatus('idle');
    setNicknameError(null);
    setConfirmPassword('');
    setEmail('');
    setStep('auth');
    setSelectedThemes([]);
  }, [mode]);

  const passwordStrength = getPasswordStrength(password);
  const isRegisterValid =
    mode === 'register' &&
    nicknameStatus === 'available' &&
    password.length >= 6 &&
    password === confirmPassword;

  const toggleTheme = (themeId: string) => {
    setSelectedThemes((prev) =>
      prev.includes(themeId) ? prev.filter((t) => t !== themeId) : [...prev, themeId],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (mode === 'register') {
      const validationError = validateNickname(nickname.trim());
      if (validationError) { setError(validationError); return; }
      if (password.length < 6) { setError('비밀번호는 6자 이상이어야 합니다'); return; }
      if (password !== confirmPassword) { setError('비밀번호가 일치하지 않습니다'); return; }
      if (nicknameStatus !== 'available') { setError('닉네임 중복 확인이 필요합니다'); return; }
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        const res = await login(nickname, password);
        // 쿠키는 백엔드에서 자동 설정됨 — localStorage 저장 불필요
        setToken(res.access_token); // 하위 호환성 (no-op)
        const user = await api.get<{
          id: string; nickname: string; role: 'user' | 'admin' | 'superadmin';
          age_group: string; adult_verified_at: string | null;
          preferred_llm_model_id: string | null;
          credit_balance?: number; subscription_plan_key?: string | null;
        }>('/auth/me');
        setUser({
          id: user.id, nickname: user.nickname, role: user.role,
          ageGroup: user.age_group, adultVerifiedAt: user.adult_verified_at,
          preferredLlmModelId: user.preferred_llm_model_id,
          creditBalance: user.credit_balance ?? 0,
          subscriptionPlanKey: user.subscription_plan_key ?? null,
        });
        router.push(['admin', 'superadmin'].includes(user.role) ? '/admin' : '/personas');
      } else {
        const res = await register(nickname.trim(), password, email || undefined);
        // 쿠키는 백엔드에서 자동 설정됨 — localStorage 저장 불필요
        setToken(res.access_token); // 하위 호환성 (no-op)
        setRegisteredToken(res.access_token);
        setStep('themes');
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '오류가 발생했습니다';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleThemeComplete = async () => {
    setLoading(true);
    try {
      if (selectedThemes.length > 0) {
        await api.put('/auth/me', { preferred_themes: selectedThemes });
      }
      const user = await api.get<{
        id: string; nickname: string; role: 'user' | 'admin' | 'superadmin';
        age_group: string; adult_verified_at: string | null;
        preferred_llm_model_id: string | null;
        credit_balance?: number; subscription_plan_key?: string | null;
      }>('/auth/me');
      setUser({
        id: user.id, nickname: user.nickname, role: user.role,
        ageGroup: user.age_group, adultVerifiedAt: user.adult_verified_at,
        preferredLlmModelId: user.preferred_llm_model_id,
        creditBalance: user.credit_balance ?? 0,
        subscriptionPlanKey: user.subscription_plan_key ?? null,
      });
      toast.success('가입이 완료되었습니다!');
      router.push('/personas');
    } catch {
      toast.error('설정 저장에 실패했습니다');
      router.push('/personas');
    } finally {
      setLoading(false);
    }
  };

  // Theme selection step
  if (step === 'themes') {
    return (
      <div className="flex justify-center items-center min-h-screen bg-bg">
        <div className="bg-bg-surface rounded-2xl py-10 px-6 md:px-10 w-full max-w-[480px] mx-4 shadow-card">
          <div className="flex justify-center mb-3">
            <Sparkles size={40} className="text-primary" />
          </div>
          <h1 className="m-0 text-xl text-center text-text">관심 테마를 선택하세요</h1>
          <p className="text-center text-text-secondary text-sm mb-6">
            선택한 테마에 맞는 챗봇을 추천해드립니다 (복수 선택 가능)
          </p>

          <div className="grid grid-cols-2 gap-3 mb-6">
            {THEMES.map((theme) => {
              const Icon = theme.icon;
              const selected = selectedThemes.includes(theme.id);
              return (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => toggleTheme(theme.id)}
                  className={`flex items-center gap-3 p-3.5 rounded-xl border-2 transition-all duration-150 cursor-pointer bg-transparent text-left ${
                    selected
                      ? 'border-primary bg-primary/10'
                      : 'border-border hover:border-primary/40'
                  }`}
                >
                  <div className={`${theme.color}`}>
                    <Icon size={22} />
                  </div>
                  <span className={`text-sm font-medium ${selected ? 'text-text' : 'text-text-secondary'}`}>
                    {theme.label}
                  </span>
                  {selected && (
                    <Check size={16} className="text-primary ml-auto" />
                  )}
                </button>
              );
            })}
          </div>

          <div className="flex flex-col gap-2">
            <button
              onClick={handleThemeComplete}
              disabled={loading}
              className="btn-primary py-3 text-[15px] flex items-center justify-center gap-2"
            >
              {loading ? '설정 중...' : (
                <>
                  {selectedThemes.length > 0
                    ? `${selectedThemes.length}개 테마 선택 완료`
                    : '시작하기'}
                  <ChevronRight size={16} />
                </>
              )}
            </button>
            {selectedThemes.length === 0 && (
              <button
                onClick={handleThemeComplete}
                disabled={loading}
                className="text-sm text-text-muted bg-transparent border-none cursor-pointer hover:text-text py-1"
              >
                건너뛰기
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Auth form (login / register)
  return (
    <div className="flex justify-center items-center min-h-screen bg-bg">
      <div className="bg-bg-surface rounded-2xl py-12 px-6 md:px-10 w-full max-w-[420px] mx-4 shadow-card">
        <div className="flex justify-center mb-3">
          <Drama size={48} className="text-primary" />
        </div>
        <h1 className="m-0 text-2xl text-center text-text">Webtoon Review Chatbot</h1>
        <p className="text-center text-text-secondary text-sm mb-6">웹툰 리뷰 챗봇 프로토타입</p>

        <div className="flex mb-6 border-b-2 border-border">
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm ${
              mode === 'login'
                ? 'font-semibold text-primary border-b-2 border-primary -mb-0.5'
                : 'text-text-muted'
            }`}
            onClick={() => setMode('login')}
          >
            로그인
          </button>
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm ${
              mode === 'register'
                ? 'font-semibold text-primary border-b-2 border-primary -mb-0.5'
                : 'text-text-muted'
            }`}
            onClick={() => setMode('register')}
          >
            회원가입
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3">
          {/* Nickname */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">닉네임</label>
            <div className="relative">
              <input
                type="text"
                placeholder={mode === 'register' ? '2~20자, 한글/영문/숫자' : '닉네임'}
                value={nickname}
                onChange={(e) => handleNicknameChange(e.target.value)}
                required
                maxLength={20}
                className={`input py-3 px-4 pr-10 w-full ${
                  mode === 'register' && nicknameStatus === 'taken' ? 'border-danger' : ''
                } ${mode === 'register' && nicknameStatus === 'available' ? 'border-success' : ''}`}
              />
              {mode === 'register' && nickname.trim().length > 0 && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2">
                  {nicknameStatus === 'checking' && (
                    <span className="inline-block w-4 h-4 border-2 border-text-muted border-t-primary rounded-full animate-spin" />
                  )}
                  {nicknameStatus === 'available' && <Check size={16} className="text-success" />}
                  {nicknameStatus === 'taken' && <X size={16} className="text-danger" />}
                  {nicknameStatus === 'invalid' && <AlertCircle size={16} className="text-warning" />}
                </span>
              )}
            </div>
            {mode === 'register' && nicknameError && (
              <span className="text-danger-text text-xs">{nicknameError}</span>
            )}
            {mode === 'register' && nicknameStatus === 'available' && (
              <span className="text-success text-xs">사용 가능한 닉네임입니다</span>
            )}
          </div>

          {/* Email (register only) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">
                이메일 <span className="text-text-muted font-normal">(선택)</span>
              </label>
              <input
                type="email"
                placeholder="example@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input py-3 px-4"
              />
            </div>
          )}

          {/* Password */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">비밀번호</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder={mode === 'register' ? '6자 이상' : '비밀번호'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input py-3 px-4 pr-10 w-full"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-text-muted hover:text-text p-0"
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
                      className={`h-1 flex-1 rounded-full ${
                        level <= passwordStrength.level ? passwordStrength.color : 'bg-border'
                      }`}
                    />
                  ))}
                </div>
                <span className="text-xs text-text-muted">{passwordStrength.label}</span>
              </div>
            )}
          </div>

          {/* Confirm Password (register only) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">비밀번호 확인</label>
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="비밀번호 다시 입력"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className={`input py-3 px-4 w-full ${
                  confirmPassword && password !== confirmPassword ? 'border-danger' : ''
                } ${confirmPassword && password === confirmPassword && password.length >= 6 ? 'border-success' : ''}`}
              />
              {confirmPassword && password !== confirmPassword && (
                <span className="text-danger-text text-xs">비밀번호가 일치하지 않습니다</span>
              )}
              {confirmPassword && password === confirmPassword && password.length >= 6 && (
                <span className="text-success text-xs">비밀번호가 일치합니다</span>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-danger/10 border border-danger/20">
              <AlertCircle size={14} className="text-danger shrink-0" />
              <p className="text-danger-text text-[13px] m-0">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || (mode === 'register' && !isRegisterValid)}
            className="btn-primary py-3 text-[15px] mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '처리 중...' : mode === 'login' ? '로그인' : '다음'}
          </button>
        </form>
      </div>
    </div>
  );
}
