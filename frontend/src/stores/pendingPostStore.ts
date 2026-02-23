import { create } from 'zustand';
import { api } from '@/lib/api';

type PendingPost = {
  id: string;
  persona_id: string;
  persona_display_name: string | null;
  content_type: string;
  title: string | null;
  content: string;
  target_post_id: string | null;
  target_comment_id: string | null;
  status: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  created_at: string;
  reviewed_at: string | null;
};

type PendingPostState = {
  items: PendingPost[];
  total: number;
  loading: boolean;
  fetchPending: (status?: string) => Promise<void>;
  approve: (pendingId: string) => Promise<void>;
  reject: (pendingId: string) => Promise<void>;
};

export const usePendingPostStore = create<PendingPostState>((set, get) => ({
  items: [],
  total: 0,
  loading: false,
  fetchPending: async (status?: string) => {
    set({ loading: true });
    try {
      const query = status ? `?status=${status}` : '';
      const data = await api.get<{ items: PendingPost[]; total: number }>(
        `/pending-posts/${query}`,
      );
      set({ items: data.items, total: data.total });
    } catch (err) {
      console.error('Failed to fetch pending posts:', err);
    } finally {
      set({ loading: false });
    }
  },
  approve: async (pendingId: string) => {
    await api.post(`/pending-posts/${pendingId}/approve`);
    set((s) => ({
      items: s.items.filter((p) => p.id !== pendingId),
      total: s.total - 1,
    }));
  },
  reject: async (pendingId: string) => {
    await api.post(`/pending-posts/${pendingId}/reject`);
    set((s) => ({
      items: s.items.filter((p) => p.id !== pendingId),
      total: s.total - 1,
    }));
  },
}));

export type { PendingPost };
