/**
 * 화면 활성화/비활성화 플래그 스토어.
 * /api/features 에서 조회하며 로드 실패 시 모두 활성으로 처리 (graceful degradation).
 */
import { create } from 'zustand';

import { api } from '@/lib/api';

type FeatureFlagStore = {
  flags: Record<string, boolean>;
  loaded: boolean;
  load: () => Promise<void>;
  isEnabled: (key: string) => boolean;
};

export const useFeatureFlagStore = create<FeatureFlagStore>((set, get) => ({
  flags: {},
  loaded: false,

  load: async () => {
    try {
      const flags = await api.get<Record<string, boolean>>('/features');
      set({ flags, loaded: true });
    } catch {
      // 플래그 조회 실패 시 모두 활성으로 처리
      set({ loaded: true });
    }
  },

  isEnabled: (key: string) => {
    const { flags, loaded } = get();
    if (!loaded) return true;
    return flags[key] !== false;
  },
}));
