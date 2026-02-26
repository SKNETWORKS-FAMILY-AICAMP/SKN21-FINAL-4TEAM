'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Trophy, TrendingUp } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import type { RankingEntry } from '@/stores/debateStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

export function RankingTable() {
  const { ranking, loading, fetchRanking } = useDebateStore();

  useEffect(() => {
    fetchRanking();
  }, [fetchRanking]);

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (ranking.length === 0) {
    return (
      <div className="text-center py-12 text-text-muted text-sm">
        아직 랭킹 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div className="bg-bg-surface border border-border rounded-xl overflow-hidden">
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
          {ranking.map((entry, idx) => (
            <RankingRow key={entry.id} entry={entry} rank={idx + 1} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RankingRow({ entry, rank }: { entry: RankingEntry; rank: number }) {
  const total = entry.wins + entry.losses + entry.draws;
  const winRate = total > 0 ? Math.round((entry.wins / total) * 100) : 0;

  return (
    <tr className="border-b border-border last:border-b-0 hover:bg-bg-hover transition-colors">
      <td className="px-4 py-2.5">
        {rank <= 3 ? (
          <span
            className={`font-bold ${
              rank === 1 ? 'text-yellow-500' : rank === 2 ? 'text-gray-400' : 'text-amber-700'
            }`}
          >
            {rank === 1 ? (
              <Trophy size={14} className="inline" />
            ) : (
              rank
            )}
          </span>
        ) : (
          <span className="text-text-muted">{rank}</span>
        )}
      </td>
      <td className="px-4 py-2.5 max-w-[200px]">
        <Link
          href={`/debate/agents/${entry.id}`}
          className="font-semibold text-text hover:text-primary transition-colors no-underline block truncate"
        >
          {entry.name}
        </Link>
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
