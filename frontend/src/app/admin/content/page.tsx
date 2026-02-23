'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { DataTable } from '@/components/admin/DataTable';

type Webtoon = {
  id: string;
  title: string;
  platform: string | null;
  total_episodes: number;
  created_at: string;
};

export default function AdminContentPage() {
  const [webtoons, setWebtoons] = useState<Webtoon[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<{ items: Webtoon[]; total: number }>('/admin/content/webtoons')
      .then((res) => setWebtoons(res.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { key: 'title' as const, label: '제목' },
    { key: 'platform' as const, label: '플랫폼' },
    {
      key: 'total_episodes' as const,
      label: '회차 수',
      render: (val: unknown) => `${Number(val)}화`,
    },
    {
      key: 'created_at' as const,
      label: '등록일',
      render: (val: unknown) => new Date(String(val)).toLocaleDateString('ko-KR'),
    },
  ];

  return (
    <div>
      <h1 className="page-title">콘텐츠 관리</h1>
      <div className="card">
        <DataTable columns={columns} data={webtoons} loading={loading} />
      </div>
    </div>
  );
}
