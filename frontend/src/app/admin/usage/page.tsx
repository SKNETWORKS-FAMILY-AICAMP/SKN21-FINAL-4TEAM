'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { DataTable } from '@/components/admin/DataTable';
import { SkeletonStat } from '@/components/ui/Skeleton';
import { Coins, Hash, CalendarDays } from 'lucide-react';

type UsagePeriod = {
  input_tokens: number;
  output_tokens: number;
  cost: number;
  unique_users: number;
};

type ModelUsage = {
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
};

type UsageSummaryResponse = {
  total: UsagePeriod;
  daily: UsagePeriod;
  monthly: UsagePeriod;
  by_model: ModelUsage[];
};

export default function AdminUsagePage() {
  const [summary, setSummary] = useState<UsageSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<UsageSummaryResponse>('/admin/usage/summary')
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const modelColumns = [
    { key: 'model_name' as const, label: '모델' },
    {
      key: 'input_tokens' as const,
      label: '입력 토큰',
      render: (val: unknown) => Number(val).toLocaleString(),
    },
    {
      key: 'output_tokens' as const,
      label: '출력 토큰',
      render: (val: unknown) => Number(val).toLocaleString(),
    },
    {
      key: 'cost' as const,
      label: '비용',
      render: (val: unknown) => `$${Number(val).toFixed(4)}`,
    },
  ];

  return (
    <div>
      <h1 className="page-title">사용량 & 과금</h1>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonStat key={i} />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <StatCard
            title="오늘 토큰"
            value={(summary.daily.input_tokens + summary.daily.output_tokens).toLocaleString()}
            icon={<Hash className="w-5 h-5" />}
          />
          <StatCard
            title="오늘 비용"
            value={`$${summary.daily.cost.toFixed(4)}`}
            icon={<Coins className="w-5 h-5" />}
          />
          <StatCard
            title="이번 달 토큰"
            value={(summary.monthly.input_tokens + summary.monthly.output_tokens).toLocaleString()}
            icon={<CalendarDays className="w-5 h-5" />}
          />
          <StatCard
            title="이번 달 비용"
            value={`$${summary.monthly.cost.toFixed(4)}`}
            icon={<Coins className="w-5 h-5" />}
          />
          <StatCard
            title="전체 토큰"
            value={(summary.total.input_tokens + summary.total.output_tokens).toLocaleString()}
            icon={<Hash className="w-5 h-5" />}
          />
          <StatCard
            title="전체 비용"
            value={`$${summary.total.cost.toFixed(4)}`}
            icon={<Coins className="w-5 h-5" />}
          />
        </div>
      ) : null}

      {summary && summary.by_model.length > 0 && (
        <section className="mb-6">
          <h2 className="section-title">모델별 사용량</h2>
          <div className="card">
            <DataTable columns={modelColumns} data={summary.by_model} />
          </div>
        </section>
      )}
    </div>
  );
}
