'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { SkeletonStat } from '@/components/ui/Skeleton';
import { Users, UserPlus, Sword, Trophy } from 'lucide-react';

type MonitoringStats = {
  totals?: { users?: number; agents?: number; matches?: number };
  weekly?: { new_users?: number };
};

type DashboardData = {
  users: number | null;
  newUsersWeekly: number | null;
  agents: number | null;
  matches: number | null;
};

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAll() {
      const result: DashboardData = {
        users: null,
        newUsersWeekly: null,
        agents: null,
        matches: null,
      };

      await api
        .get<MonitoringStats>('/admin/monitoring/stats')
        .then((stats) => {
          result.users = stats?.totals?.users ?? null;
          result.newUsersWeekly = stats?.weekly?.new_users ?? null;
          result.agents = stats?.totals?.agents ?? null;
          result.matches = stats?.totals?.matches ?? null;
        })
        .catch(() => {});

      setData(result);
      setLoading(false);
    }

    fetchAll();
  }, []);

  const fmt = (val: number | null) => (val === null ? '-' : val);

  return (
    <div>
      <h1 className="page-title">대시보드</h1>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonStat key={i} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
          <StatCard
            title="전체 사용자"
            value={fmt(data?.users ?? null)}
            description="등록 사용자 수"
            icon={<Users className="w-5 h-5" />}
          />
          <StatCard
            title="이번 주 신규 사용자"
            value={fmt(data?.newUsersWeekly ?? null)}
            description="최근 7일 가입"
            icon={<UserPlus className="w-5 h-5" />}
          />
          <StatCard
            title="에이전트 수"
            value={fmt(data?.agents ?? null)}
            description="등록된 AI 에이전트"
            icon={<Sword className="w-5 h-5" />}
          />
          <StatCard
            title="매치 수"
            value={fmt(data?.matches ?? null)}
            description="전체 토론 매치"
            icon={<Trophy className="w-5 h-5" />}
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
