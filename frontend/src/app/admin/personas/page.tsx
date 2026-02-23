'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { DataTable } from '@/components/admin/DataTable';
import { toast } from '@/stores/toastStore';

type AdminPersona = {
  id: string;
  display_name: string;
  type: string;
  age_rating: string;
  visibility: string;
  moderation_status: string;
  created_by: string;
};

export default function AdminPersonasPage() {
  const [personas, setPersonas] = useState<AdminPersona[]>([]);
  const [filter, setFilter] = useState<string>('pending');
  const [loading, setLoading] = useState(true);

  const fetchPersonas = () => {
    setLoading(true);
    api
      .get<{ items: AdminPersona[]; total: number }>(`/admin/personas?moderation_status=${filter}`)
      .then((res) => setPersonas(res.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchPersonas();
  }, [filter]);

  const handleModeration = async (id: string, action: 'approved' | 'blocked') => {
    try {
      await api.put(`/admin/personas/${id}/moderation`, { action });
      fetchPersonas();
    } catch {
      toast.error('처리에 실패했습니다');
    }
  };

  const ratingColor: Record<string, string> = {
    all: 'bg-success',
    '15+': 'bg-warning',
    '18+': 'bg-danger',
  };

  const statusColor: Record<string, string> = {
    pending: 'bg-warning',
    approved: 'bg-success',
    blocked: 'bg-danger',
  };

  const columns = [
    { key: 'display_name' as const, label: '이름' },
    { key: 'created_by' as const, label: '생성자' },
    {
      key: 'age_rating' as const,
      label: '등급',
      render: (val: unknown) => (
        <span className={`badge ${ratingColor[String(val)] ?? 'bg-text-muted'}`}>
          {String(val) === 'all' ? '전체' : String(val)}
        </span>
      ),
    },
    { key: 'visibility' as const, label: '공개' },
    {
      key: 'moderation_status' as const,
      label: '상태',
      render: (val: unknown) => (
        <span className={`badge ${statusColor[String(val)] ?? 'bg-text-muted'}`}>
          {String(val)}
        </span>
      ),
    },
    {
      key: 'id' as const,
      label: '액션',
      render: (_: unknown, row: AdminPersona) =>
        row.moderation_status === 'pending' ? (
          <div className="flex gap-1.5">
            <button
              onClick={() => handleModeration(row.id, 'approved')}
              className="py-1 px-3 rounded-md border-none bg-success text-white text-xs cursor-pointer"
            >
              승인
            </button>
            <button
              onClick={() => handleModeration(row.id, 'blocked')}
              className="py-1 px-3 rounded-md border-none bg-danger text-white text-xs cursor-pointer"
            >
              차단
            </button>
          </div>
        ) : null,
    },
  ];

  return (
    <div>
      <h1 className="page-title">페르소나 검수</h1>
      <div className="flex gap-2 mb-4">
        {(['pending', 'approved', 'blocked'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`py-2 px-4 rounded-lg text-[13px] cursor-pointer transition-colors duration-200 ${
              filter === f
                ? 'bg-primary text-white border border-primary'
                : 'bg-bg-surface text-text border border-border-input'
            }`}
          >
            {f === 'pending' ? '대기' : f === 'approved' ? '승인' : '차단'}
          </button>
        ))}
      </div>
      <div className="card">
        <DataTable columns={columns} data={personas} loading={loading} />
      </div>
    </div>
  );
}
