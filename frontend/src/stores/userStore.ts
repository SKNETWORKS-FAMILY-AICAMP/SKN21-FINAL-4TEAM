import { create } from 'zustand';

type User = {
  id: string;
  nickname: string;
  role: 'user' | 'admin';
  ageGroup: string;
  adultVerifiedAt: string | null;
  preferredLlmModelId: string | null;
};

type UserState = {
  user: User | null;
  token: string | null;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  isAdultVerified: () => boolean;
  isAdmin: () => boolean;
  logout: () => void;
};

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  token: null,
  setUser: (user) => set({ user }),
  setToken: (token) => set({ token }),
  isAdultVerified: () => get().user?.adultVerifiedAt !== null,
  isAdmin: () => get().user?.role === 'admin',
  logout: () => set({ user: null, token: null }),
}));
