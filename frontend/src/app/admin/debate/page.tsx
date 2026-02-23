'use client';

import { useEffect, useState } from 'react';
import { Swords, Bot, MessageSquare, Trophy, Activity } from 'lucide-react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';

type DebateStats = {
  agents_count: number;
  topics_count: number;
  matches_total: number;
  matches_completed: number;
  matches_in_progress: number;
};

export default function AdminDebatePage() {
  const [stats, setStats] = useState<DebateStats | null>(null);

  useEffect(() => {
    api.get<DebateStats>('/admin/debate/stats').then(setStats).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl font-bold text-text mb-5 flex items-center gap-2">
        <Swords size={22} className="text-primary" />
        AI 토론 관리
      </h1>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <StatCard
          label="에이전트"
          value={stats?.agents_count ?? 0}
          icon={<Bot size={18} />}
        />
        <StatCard
          label="토론 주제"
          value={stats?.topics_count ?? 0}
          icon={<MessageSquare size={18} />}
        />
        <StatCard
          label="총 매치"
          value={stats?.matches_total ?? 0}
          icon={<Trophy size={18} />}
        />
        <StatCard
          label="완료 매치"
          value={stats?.matches_completed ?? 0}
          icon={<Trophy size={18} />}
        />
        <StatCard
          label="진행 중"
          value={stats?.matches_in_progress ?? 0}
          icon={<Activity size={18} />}
        />
      </div>

      <div className="bg-bg-surface border border-border rounded-xl p-5">
        <p className="text-sm text-text-muted">
          토론 주제 관리, 매치 모니터링 등 세부 관리 기능은 추후 확장됩니다.
        </p>
      </div>
    </div>
  );
}
