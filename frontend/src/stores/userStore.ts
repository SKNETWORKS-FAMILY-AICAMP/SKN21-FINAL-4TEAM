/**
 * 사용자 인증/상태 스토어. JWT 토큰 관리, 역할(RBAC) 체크, 성인인증 상태 확인.
 * initialize()로 페이지 로드 시 토큰 복원 + /auth/me로 사용자 정보 재조회.
 */
import { create } from 'zustand';

type User = {
  id: string;
  nickname: string;
  role: 'user' | 'admin' | 'superadmin';
  ageGroup: string;
  adultVerifiedAt: string | null;
  preferredLlmModelId: string | null;
  creditBalance: number;
  subscriptionPlanKey: string | null;
};

type UserState = {
  user: User | null;
  token: string | null;
  initialized: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  isAdultVerified: () => boolean;
  isAdmin: () => boolean;
  isSuperAdmin: () => boolean;
  logout: () => void;
  initialize: () => Promise<void>;
};

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  token: null,
  initialized: false,
  setUser: (user) => set({ user }),
  setToken: (token) => set({ token }),
  isAdultVerified: () => get().user?.adultVerifiedAt != null,
  isAdmin: () => ['admin', 'superadmin'].includes(get().user?.role ?? ''),
  isSuperAdmin: () => get().user?.role === 'superadmin',
  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null });
  },
  initialize: (() => {
    let pending: Promise<void> | null = null;
    return () => {
      if (get().initialized) return Promise.resolve();
      if (pending) return pending;
      pending = (async () => {
        const token = localStorage.getItem('token');
        if (!token) {
          set({ initialized: true });
          return;
        }
        set({ token });
        try {
          const res = await fetch('/api/auth/me', {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) {
            localStorage.removeItem('token');
            set({ token: null, initialized: true });
            return;
          }
          const data = await res.json();
          set({
            user: {
              id: data.id,
              nickname: data.nickname,
              role: data.role,
              ageGroup: data.age_group,
              adultVerifiedAt: data.adult_verified_at,
              preferredLlmModelId: data.preferred_llm_model_id,
              creditBalance: data.credit_balance ?? 0,
              subscriptionPlanKey: data.subscription_plan_key ?? null,
            },
            initialized: true,
          });
        } catch {
          localStorage.removeItem('token');
          set({ token: null, initialized: true });
        }
      })();
      return pending;
    };
  })(),
}));
