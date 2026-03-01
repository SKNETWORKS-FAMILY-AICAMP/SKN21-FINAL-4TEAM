import { create } from 'zustand';
import { api } from '@/lib/api';

type Notification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
};

type NotificationState = {
  unreadCount: number;
  notifications: Notification[];
  fetchUnreadCount: () => Promise<void>;
  fetchNotifications: () => Promise<void>;
  markAsRead: (id: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
};

export const useNotificationStore = create<NotificationState>((set, get) => ({
  unreadCount: 0,
  notifications: [],

  fetchUnreadCount: async () => {
    try {
      const res = await api.get<{ count: number }>('/notifications/unread-count');
      set({ unreadCount: res.count });
    } catch (err) {
      console.error('Failed to fetch unread count:', err);
    }
  },

  fetchNotifications: async () => {
    try {
      const res = await api.get<{ items: Notification[]; total: number }>('/notifications');
      set({ notifications: res.items ?? [] });
    } catch (err) {
      console.error('Failed to fetch notifications:', err);
    }
  },

  markAsRead: async (id: string) => {
    try {
      await api.patch(`/notifications/${id}/read`);
      set((state) => ({
        notifications: state.notifications.map((n) =>
          n.id === id ? { ...n, is_read: true } : n,
        ),
        unreadCount: Math.max(0, state.unreadCount - 1),
      }));
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  },

  markAllAsRead: async () => {
    try {
      await api.post('/notifications/read-all');
      set((state) => ({
        notifications: state.notifications.map((n) => ({ ...n, is_read: true })),
        unreadCount: 0,
      }));
    } catch (err) {
      console.error('Failed to mark all as read:', err);
    }
  },
}));
