'use client';

import { useEffect, useState } from 'react';
import { Bell, CheckCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { EmptyState } from '@/components/ui/EmptyState';

type Notification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
};

const TYPE_LABELS: Record<string, string> = {
  persona_approved: '승인',
  persona_blocked: '차단',
  reply: '답글',
  system: '시스템',
  relationship: '관계',
  credit: '크레딧',
};

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  useEffect(() => {
    const params = filter === 'unread' ? '?is_read=false' : '';
    api
      .get<{ items: Notification[]; total: number }>(`/notifications/${params}`)
      .then((res) => setNotifications(res.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filter]);

  const handleMarkAllRead = async () => {
    await api.post('/notifications/read-all');
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  const handleClick = async (n: Notification) => {
    if (!n.is_read) {
      await api.patch(`/notifications/${n.id}/read`);
      setNotifications((prev) => prev.map((item) => (item.id === n.id ? { ...item, is_read: true } : item)));
    }
    if (n.link) router.push(n.link);
  };

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="m-0 text-2xl text-text flex items-center gap-2">
          <Bell size={24} />
          알림
        </h1>
        <button
          onClick={handleMarkAllRead}
          className="flex items-center gap-1 text-sm text-primary hover:underline border-none bg-transparent cursor-pointer"
        >
          <CheckCheck size={16} />
          모두 읽음
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        {(['all', 'unread'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              filter === f
                ? 'bg-primary text-white border-primary'
                : 'bg-bg-surface text-text-secondary border-border hover:border-primary/50'
            }`}
          >
            {f === 'all' ? '전체' : '안읽음'}
          </button>
        ))}
      </div>

      {!loading && notifications.length === 0 && (
        <EmptyState icon={<Bell size={48} />} title="알림이 없습니다" />
      )}

      <div className="flex flex-col gap-2">
        {notifications.map((n) => (
          <button
            key={n.id}
            onClick={() => handleClick(n)}
            className={`w-full text-left p-4 rounded-xl border transition-colors cursor-pointer ${
              n.is_read
                ? 'bg-bg-surface border-border hover:border-primary/30'
                : 'bg-primary/5 border-primary/20 hover:border-primary/40'
            }`}
          >
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-semibold uppercase text-text-muted">
                  {TYPE_LABELS[n.type] || n.type}
                </span>
                <h3 className="m-0 text-sm font-semibold text-text mt-0.5">{n.title}</h3>
                {n.body && <p className="m-0 text-xs text-text-secondary mt-1">{n.body}</p>}
              </div>
              <span className="text-[10px] text-text-muted whitespace-nowrap ml-2">
                {new Date(n.created_at).toLocaleDateString('ko-KR')}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
