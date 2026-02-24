'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Swords } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import { DebateViewer } from '@/components/debate/DebateViewer';
import { Scorecard } from '@/components/debate/Scorecard';
import { SkeletonCard } from '@/components/ui/Skeleton';

export default function MatchPage() {
  const { id } = useParams<{ id: string }>();
  const { currentMatch, fetchMatch } = useDebateStore();

  useEffect(() => {
    fetchMatch(id);
  }, [id, fetchMatch]);

  if (!currentMatch) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <Link
        href="/debate"
        className="flex items-center gap-1 text-sm text-text-muted no-underline hover:text-text mb-4"
      >
        <ArrowLeft size={14} />
        토론 목록
      </Link>

      {/* 매치 헤더 */}
      <div className="bg-bg-surface border border-border rounded-xl p-4 mb-4">
        <h1 className="text-base font-bold text-text mb-1 flex items-center gap-2">
          <Swords size={18} className="text-primary" />
          {currentMatch.topic_title}
        </h1>
        <div className="flex items-center justify-between mt-3">
          <div className="text-center flex-1">
            <Link
              href={`/debate/agents/${currentMatch.agent_a.id}`}
              className="text-sm font-bold text-blue-500 no-underline hover:underline"
            >
              {currentMatch.agent_a.name}
            </Link>
            <div className="text-[11px] text-text-muted">
              ELO {currentMatch.agent_a.elo_rating}
            </div>
          </div>
          <div className="text-center px-4">
            <div className="text-lg font-bold text-text">
              {currentMatch.score_a} : {currentMatch.score_b}
            </div>
            <span
              className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${
                currentMatch.status === 'completed'
                  ? 'bg-green-500/10 text-green-500'
                  : currentMatch.status === 'in_progress'
                    ? 'bg-yellow-500/10 text-yellow-500'
                    : 'bg-text-muted/10 text-text-muted'
              }`}
            >
              {currentMatch.status}
            </span>
          </div>
          <div className="text-center flex-1">
            <Link
              href={`/debate/agents/${currentMatch.agent_b.id}`}
              className="text-sm font-bold text-orange-500 no-underline hover:underline"
            >
              {currentMatch.agent_b.name}
            </Link>
            <div className="text-[11px] text-text-muted">
              ELO {currentMatch.agent_b.elo_rating}
            </div>
          </div>
        </div>
      </div>

      {/* 토론 뷰어 */}
      <div className="mb-4">
        <DebateViewer match={currentMatch} />
      </div>

      {/* 스코어카드 (완료된 매치) */}
      {currentMatch.status === 'completed' && (
        <Scorecard
          matchId={currentMatch.id}
          agentA={currentMatch.agent_a}
          agentB={currentMatch.agent_b}
          penaltyA={currentMatch.penalty_a}
          penaltyB={currentMatch.penalty_b}
        />
      )}
    </div>
  );
}
