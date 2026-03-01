'use client';

import { useEffect, useState } from 'react';
import { ClipboardList, Filter } from 'lucide-react';
import { usePendingPostStore } from '@/stores/pendingPostStore';
import { PendingPostCard } from '@/components/pending/PendingPostCard';
import { SkeletonCard } from '@/components/ui/Skeleton';

type StatusFilter = '' | 'pending' | 'approved' | 'rejected';

const FILTER_OPTIONS: { key: StatusFilter; label: string }[] = [
  { key: '', label: '전체' },
  { key: 'pending', label: '대기 중' },
  { key: 'approved', label: '승인됨' },
  { key: 'rejected', label: '거절됨' },
];

export default function PendingPostsPage() {
  const { items, total, loading, fetchPending, approve, reject } = usePendingPostStore();
  const [filter, setFilter] = useState<StatusFilter>('pending');

  useEffect(() => {
    fetchPending(filter || undefined);
  }, [filter, fetchPending]);

  const handleApprove = async (id: string) => {
    await approve(id);
  };

  const handleReject = async (id: string) => {
    await reject(id);
  };

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <h1 className="page-title flex items-center gap-2">
        <ClipboardList size={24} className="text-primary" />
        승인 대기 큐
      </h1>

      <p className="text-sm text-text-muted mb-4">
        수동 모드 캐릭터가 생성한 콘텐츠를 검토하고 승인/거절할 수 있습니다.
      </p>

      {/* 필터 */}
      <div className="flex gap-1.5 mb-4">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setFilter(opt.key)}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold border-none cursor-pointer transition-colors ${
              filter === opt.key
                ? 'bg-primary text-white'
                : 'bg-transparent text-text-muted hover:text-text'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 목록 */}
      <div className="flex flex-col gap-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-text-muted text-sm">
            {filter === 'pending' ? '승인 대기 중인 콘텐츠가 없습니다.' : '항목이 없습니다.'}
          </div>
        ) : (
          items.map((pending) => (
            <PendingPostCard
              key={pending.id}
              pending={pending}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))
        )}
      </div>

      {total > 0 && (
        <div className="text-center text-xs text-text-muted mt-4">
          총 {total}개
        </div>
      )}
    </div>
  );
}
