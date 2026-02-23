import { create } from 'zustand';
import { api } from '@/lib/api';

type WorldEvent = {
  id: string;
  created_by: string | null;
  title: string;
  content: string;
  event_type: string;
  priority: number;
  is_active: boolean;
  starts_at: string | null;
  expires_at: string | null;
  age_rating: string;
  created_at: string;
  updated_at: string;
};

type WorldEventCreate = {
  title: string;
  content: string;
  event_type?: string;
  priority?: number;
  starts_at?: string | null;
  expires_at?: string | null;
  age_rating?: string;
};

type WorldEventState = {
  events: WorldEvent[];
  activeEvents: WorldEvent[];
  total: number;
  loading: boolean;
  fetchAll: () => Promise<void>;
  fetchActive: () => Promise<void>;
  create: (data: WorldEventCreate) => Promise<WorldEvent>;
  update: (id: string, data: Partial<WorldEventCreate & { is_active: boolean }>) => Promise<void>;
  remove: (id: string) => Promise<void>;
};

export const useWorldEventStore = create<WorldEventState>((set) => ({
  events: [],
  activeEvents: [],
  total: 0,
  loading: false,
  fetchAll: async () => {
    set({ loading: true });
    try {
      const data = await api.get<{ items: WorldEvent[]; total: number }>('/admin/world-events/');
      set({ events: data.items, total: data.total });
    } catch (err) {
      console.error('Failed to fetch world events:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchActive: async () => {
    set({ loading: true });
    try {
      const data = await api.get<WorldEvent[]>('/world-events/active');
      set({ activeEvents: data });
    } catch (err) {
      console.error('Failed to fetch active events:', err);
    } finally {
      set({ loading: false });
    }
  },
  create: async (data) => {
    const event = await api.post<WorldEvent>('/admin/world-events/', data);
    set((s) => ({ events: [event, ...s.events], total: s.total + 1 }));
    return event;
  },
  update: async (id, data) => {
    const updated = await api.put<WorldEvent>(`/admin/world-events/${id}`, data);
    set((s) => ({
      events: s.events.map((e) => (e.id === id ? updated : e)),
    }));
  },
  remove: async (id) => {
    await api.delete(`/admin/world-events/${id}`);
    set((s) => ({
      events: s.events.filter((e) => e.id !== id),
      total: s.total - 1,
    }));
  },
}));

export type { WorldEvent, WorldEventCreate };
