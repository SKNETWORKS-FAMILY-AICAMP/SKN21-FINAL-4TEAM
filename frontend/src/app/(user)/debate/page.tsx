'use client';

import { useEffect, useState } from 'react';
import { Swords, Plus } from 'lucide-react';
import Link from 'next/link';
import { useDebateStore } from '@/stores/debateStore';
import { TopicCard } from '@/components/debate/TopicCard';
import { SkeletonCard } from '@/components/ui/Skeleton';

type StatusFilter = 'all' | 'open' | 'in_progress' | 'closed';

const FILTER_OPTIONS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'open', label: '참가 가능' },
  { key: 'in_progress', label: '진행 중' },
  { key: 'closed', label: '종료' },
];

export default function DebateTopicsPage() {
  const { topics, loading, fetchTopics } = useDebateStore();
  const [filter, setFilter] = useState<StatusFilter>('all');

  useEffect(() => {
    fetchTopics(filter === 'all' ? undefined : filter);
  }, [filter, fetchTopics]);

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-5">
        <h1 className="page-title flex items-center gap-2">
          <Swords size={24} className="text-primary" />
          AI 토론
        </h1>
        <Link
          href="/debate/agents"
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white text-xs font-semibold rounded-lg no-underline hover:bg-primary/90 transition-colors"
        >
          <Plus size={14} />
          내 에이전트
        </Link>
      </div>

      {/* 필터 */}
      <div className="flex gap-1.5 mb-4">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setFilter(opt.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border-none cursor-pointer transition-colors ${
              filter === opt.key
                ? 'bg-primary/10 text-primary'
                : 'bg-transparent text-text-muted hover:text-text'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 토픽 목록 */}
      <div className="flex flex-col gap-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
        ) : topics.length === 0 ? (
          <div className="text-center py-12 text-text-muted text-sm">
            등록된 토론 주제가 없습니다.
          </div>
        ) : (
          topics.map((topic) => <TopicCard key={topic.id} topic={topic} />)
        )}
      </div>

      {/* 랭킹 링크 */}
      <div className="mt-6 text-center">
        <Link
          href="/debate/ranking"
          className="text-sm text-primary font-semibold no-underline hover:underline"
        >
          ELO 랭킹 보기 →
        </Link>
      </div>
    </div>
  );
}
