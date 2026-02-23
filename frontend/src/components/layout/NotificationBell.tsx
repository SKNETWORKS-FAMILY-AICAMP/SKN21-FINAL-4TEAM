'use client';

import { useEffect, useState, useRef } from 'react';
import { Bell } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useNotificationStore } from '@/stores/notificationStore';

export function NotificationBell() {
  const router = useRouter();
  const { unreadCount, notifications, fetchUnreadCount, fetchNotifications, markAsRead } =
    useNotificationStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open, fetchNotifications]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleClick = (notif: { id: string; link: string | null }) => {
    markAsRead(notif.id);
    if (notif.link) router.push(notif.link);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-lg hover:bg-bg-hover transition-colors border-none bg-transparent cursor-pointer text-text-secondary hover:text-text"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center px-1">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-[320px] bg-bg-surface border border-border rounded-xl shadow-lg overflow-hidden z-50">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <h3 className="m-0 text-sm font-semibold text-text">알림</h3>
            {unreadCount > 0 && (
              <button
                onClick={() => useNotificationStore.getState().markAllAsRead()}
                className="text-xs text-primary hover:underline border-none bg-transparent cursor-pointer"
              >
                모두 읽음
              </button>
            )}
          </div>
          <div className="max-h-[300px] overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-4 text-center text-text-muted text-sm">알림이 없습니다</div>
            ) : (
              notifications.slice(0, 10).map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleClick(n)}
                  className={`w-full text-left px-4 py-3 border-none cursor-pointer transition-colors hover:bg-bg-hover ${
                    n.is_read ? 'bg-transparent' : 'bg-primary/5'
                  }`}
                >
                  <div className="text-sm font-medium text-text">{n.title}</div>
                  {n.body && <div className="text-xs text-text-secondary mt-0.5">{n.body}</div>}
                  <div className="text-[10px] text-text-muted mt-1">
                    {new Date(n.created_at).toLocaleDateString('ko-KR')}
                  </div>
                </button>
              ))
            )}
          </div>
          <button
            onClick={() => {
              router.push('/notifications');
              setOpen(false);
            }}
            className="w-full px-4 py-2.5 text-center text-xs text-primary hover:bg-bg-hover border-t border-border bg-transparent cursor-pointer font-medium"
          >
            전체 보기
          </button>
        </div>
      )}
    </div>
  );
}
