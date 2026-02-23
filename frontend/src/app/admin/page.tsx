'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { SkeletonStat } from '@/components/ui/Skeleton';
import { Users, MessageSquare, Clapperboard, ShieldAlert, MonitorDot, UserPlus } from 'lucide-react';

type DashboardStats = {
  totals: { users: number; sessions: number; messages: number; personas: number };
  today: { active_sessions: number; messages: number };
  weekly: { new_users: number };
  moderation: { pending_personas: number };
};

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<DashboardStats>('/admin/monitoring/stats')
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="page-title">대시보드</h1>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
          {Array.from({ length: 7 }).map((_, i) => (
            <SkeletonStat key={i} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
          <StatCard
            title="전체 사용자"
            value={stats?.totals.users ?? '-'}
            description="등록 사용자 수"
            icon={<Users className="w-5 h-5" />}
          />
          <StatCard
            title="오늘 활성 세션"
            value={stats?.today.active_sessions ?? '-'}
            icon={<MonitorDot className="w-5 h-5" />}
          />
          <StatCard
            title="전체 세션"
            value={stats?.totals.sessions ?? '-'}
            icon={<MonitorDot className="w-5 h-5" />}
          />
          <StatCard
            title="오늘 메시지"
            value={stats?.today.messages ?? '-'}
            icon={<MessageSquare className="w-5 h-5" />}
          />
          <StatCard
            title="전체 메시지"
            value={stats?.totals.messages ?? '-'}
            icon={<MessageSquare className="w-5 h-5" />}
          />
          <StatCard
            title="페르소나"
            value={stats?.totals.personas ?? '-'}
            icon={<Clapperboard className="w-5 h-5" />}
          />
          <StatCard
            title="모더레이션 대기"
            value={stats?.moderation.pending_personas ?? '-'}
            description="검수 대기 중인 페르소나"
            icon={<ShieldAlert className="w-5 h-5" />}
          />
        </div>
      )}

      <section className="mt-8">
        <h2 className="section-title">최근 활동</h2>
        <div className="card">
          <div className="flex flex-col items-center justify-center py-10 text-text-muted">
            <UserPlus className="w-8 h-8 mb-2" />
            <p className="text-sm">최근 활동 데이터를 불러오는 중...</p>
          </div>
        </div>
      </section>
    </div>
  );
}
