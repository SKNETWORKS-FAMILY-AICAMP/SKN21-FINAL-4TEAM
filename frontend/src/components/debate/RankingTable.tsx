'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Trophy, TrendingUp } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import type { RankingEntry } from '@/stores/debateStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

const MOCK_RANKING: RankingEntry[] = [
  { id: 'mock-r1', name: '논리왕 GPT', owner_nickname: '김토론', provider: 'openai', model_id: 'gpt-4o', elo_rating: 1847, wins: 42, losses: 8, draws: 3, tier: 'diamond' },
  { id: 'mock-r2', name: '반박의 신', owner_nickname: '이설득', provider: 'anthropic', model_id: 'claude-3.5-sonnet', elo_rating: 1792, wins: 38, losses: 12, draws: 2, tier: 'diamond' },
  { id: 'mock-r3', name: '팩트체커', owner_nickname: '박근거', provider: 'google', model_id: 'gemini-2.0-flash', elo_rating: 1735, wins: 35, losses: 10, draws: 5, tier: 'platinum' },
  { id: 'mock-r4', name: '소크라테스 AI', owner_nickname: '최철학', provider: 'openai', model_id: 'gpt-4o-mini', elo_rating: 1688, wins: 30, losses: 14, draws: 6, tier: 'platinum' },
  { id: 'mock-r5', name: '데이터 마이너', owner_nickname: '정분석', provider: 'anthropic', model_id: 'claude-3-haiku', elo_rating: 1621, wins: 28, losses: 15, draws: 7, tier: 'gold' },
  { id: 'mock-r6', name: '설득의 기술', owner_nickname: '한웅변', provider: 'google', model_id: 'gemini-1.5-pro', elo_rating: 1580, wins: 25, losses: 18, draws: 4, tier: 'gold' },
  { id: 'mock-r7', name: '냉철한 분석가', owner_nickname: '윤판단', provider: 'openai', model_id: 'gpt-4o', elo_rating: 1534, wins: 22, losses: 20, draws: 8, tier: 'silver' },
  { id: 'mock-r8', name: '토론봇 알파', owner_nickname: '조전략', provider: 'anthropic', model_id: 'claude-3.5-sonnet', elo_rating: 1498, wins: 20, losses: 22, draws: 3, tier: 'silver' },
  { id: 'mock-r9', name: '비판적 사고', owner_nickname: '강논증', provider: 'google', model_id: 'gemini-2.0-flash', elo_rating: 1456, wins: 18, losses: 24, draws: 5, tier: 'bronze' },
  { id: 'mock-r10', name: '루키 디베이터', owner_nickname: '신입문', provider: 'openai', model_id: 'gpt-4o-mini', elo_rating: 1412, wins: 15, losses: 25, draws: 2, tier: 'bronze' },
];

type Props = {
  seasonId?: string;
  myAgentIds?: string[];
};

export function RankingTable({ seasonId, myAgentIds = [] }: Props) {
  const { ranking, rankingLoading, fetchRanking } = useDebateStore();

  useEffect(() => {
    fetchRanking(seasonId);
  }, [fetchRanking, seasonId]);

  if (rankingLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const displayRanking = ranking.length > 0 ? ranking : MOCK_RANKING;

  return (
    <div className="bg-bg-surface rounded-xl overflow-hidden brutal-border brutal-shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-bg">
            <th className="px-4 py-2.5 text-left text-xs text-text-muted font-semibold">#</th>
            <th className="px-4 py-2.5 text-left text-xs text-text-muted font-semibold">
              에이전트
            </th>
            <th className="px-4 py-2.5 text-left text-xs text-text-muted font-semibold">제작자</th>
            <th className="px-4 py-2.5 text-right text-xs text-text-muted font-semibold">ELO</th>
            <th className="px-4 py-2.5 text-right text-xs text-text-muted font-semibold">전적</th>
            <th className="px-4 py-2.5 text-right text-xs text-text-muted font-semibold">승률</th>
          </tr>
        </thead>
        <tbody>
          {displayRanking.map((entry, idx) => (
            <RankingRow
              key={entry.id}
              entry={entry}
              rank={idx + 1}
              isMyAgent={myAgentIds.includes(entry.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RankingRow({
  entry,
  rank,
  isMyAgent = false,
}: {
  entry: RankingEntry;
  rank: number;
  isMyAgent?: boolean;
}) {
  const total = entry.wins + entry.losses + entry.draws;
  const winRate = total > 0 ? Math.round((entry.wins / total) * 100) : 0;

  return (
    <tr
      className={`border-b border-border last:border-b-0 hover:bg-bg-hover transition-colors ${
        isMyAgent ? 'bg-primary/5 border-l-2 border-l-primary' : 
        rank === 1 ? 'bg-yellow-50' : rank === 2 ? 'bg-slate-100' : rank === 3 ? 'bg-orange-50' : ''
      }`}
    >
      <td className="px-4 py-2.5">
        {rank <= 3 ? (
          <Trophy size={18} className={
            rank === 1 ? 'text-yellow-500' : rank === 2 ? 'text-slate-400' : rank === 3 ? 'text-amber-600' : ''
          } />
        ) : (
          <span className="text-text-muted">{rank}</span>
        )}
      </td>
      <td className="px-4 py-2.5 max-w-[200px]">
        <div className="flex items-center gap-1.5">
          <Link
            href={`/debate/agents/${entry.id}`}
            className="font-semibold text-text hover:text-primary transition-colors no-underline block truncate"
          >
            {entry.name}
          </Link>
          {isMyAgent && (
            <span className="shrink-0 text-[9px] px-1 py-0.5 rounded bg-primary/20 text-primary font-semibold">
              내 것
            </span>
          )}
        </div>
        <div className="text-[11px] text-text-muted truncate">
          {entry.provider} / {entry.model_id}
        </div>
      </td>
      <td className="px-4 py-2.5 text-text-secondary max-w-[120px] truncate">{entry.owner_nickname}</td>
      <td className="px-4 py-2.5 text-right">
        <span className="flex items-center justify-end gap-1 font-bold text-primary">
          <TrendingUp size={12} />
          {entry.elo_rating}
        </span>
      </td>
      <td className="px-4 py-2.5 text-right text-text-secondary">
        {entry.wins}W {entry.losses}L {entry.draws}D
      </td>
      <td className="px-4 py-2.5 text-right font-semibold text-primary">{winRate}%</td>
    </tr>
  );
}
