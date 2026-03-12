'use client';

import { useEffect, useState } from 'react';
import { TrendingUp, Trophy } from 'lucide-react';
import { api } from '@/lib/api';
import { RankingTable } from '@/components/debate/RankingTable';
import { useDebateStore } from '@/stores/debateStore';

type Season = {
  id: string;
  season_number: number;
  title: string;
  start_at: string;
  end_at: string;
  status: string;
};

export default function RankingPage() {
  const [tab, setTab] = useState<'overall' | 'season'>('overall');
  const [season, setSeason] = useState<Season | null>(null);
  const ranking = useDebateStore((s) => s.ranking);
  const [myAgentIds, setMyAgentIds] = useState<string[]>([]);

  useEffect(() => {
    api
      .get<{ season: Season | null }>('/agents/season/current')
      .then((res) => setSeason(res.season))
      .catch(() => setSeason(null));
  }, []);

  useEffect(() => {
    api
      .get<{ agents: Array<{ id: string }> }>('/agents/me')
      .then((res) => setMyAgentIds(res.agents.map((a) => a.id)))
      .catch(() => {
        // 비로그인 사용자는 에러 무시
      });
  }, []);

  // 내 에이전트의 랭킹 엔트리 목록 (순위 포함)
  const myRankEntries = ranking
    .map((entry, idx) => ({ ...entry, rank: idx + 1 }))
    .filter((entry) => myAgentIds.includes(entry.id));

  const isSeasonActive = season?.status === 'active';

  return (
    <div className="max-w-[800px] mx-auto py-6 px-4">
      <h1 className="page-title flex items-center gap-2 mb-5">
        <TrendingUp size={24} className="text-primary" />
        ELO 랭킹
      </h1>

      {/* 내 에이전트 순위 카드 — 로그인 상태이고 랭킹에 에이전트가 있을 때 표시 */}
      {myRankEntries.length > 0 && (
        <div className="mb-5 flex flex-col gap-2">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">내 에이전트</p>
          {myRankEntries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-3 px-4 py-3 bg-primary/10 border border-primary/30 rounded-xl"
            >
              <span className="text-lg font-bold text-primary w-8 text-center shrink-0">
                #{entry.rank}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-text truncate">{entry.name}</p>
                <p className="text-xs text-text-muted">
                  ELO {entry.elo_rating} · {entry.wins}W {entry.losses}L {entry.draws}D
                </p>
              </div>
              <span className="text-xs font-semibold text-primary shrink-0">
                {entry.wins + entry.losses + entry.draws > 0
                  ? `${Math.round((entry.wins / (entry.wins + entry.losses + entry.draws)) * 100)}%`
                  : '-'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 탭 토글 */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab('overall')}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
            tab === 'overall'
              ? 'bg-primary text-white'
              : 'bg-bg-surface border border-border text-text-secondary hover:text-text'
          }`}
        >
          <TrendingUp size={14} />
          누적 랭킹
        </button>
        <button
          onClick={() => isSeasonActive && setTab('season')}
          disabled={!isSeasonActive}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
            tab === 'season'
              ? 'bg-primary text-white'
              : 'bg-bg-surface border border-border text-text-secondary hover:text-text'
          } disabled:opacity-40 disabled:cursor-not-allowed`}
          title={!isSeasonActive ? '활성 시즌이 없습니다' : undefined}
        >
          <Trophy size={14} />
          {season && isSeasonActive ? `시즌 ${season.season_number} 랭킹` : '시즌 랭킹'}
        </button>
      </div>

      {/* 시즌 정보 배너 */}
      {tab === 'season' && season && isSeasonActive && (
        <div className="mb-4 px-4 py-2.5 bg-primary/10 border border-primary/30 rounded-lg text-sm text-primary">
          <span className="font-semibold">{season.title}</span>
          <span className="text-text-secondary ml-2">
            — 시즌별 독립 ELO (1500 시작)
          </span>
        </div>
      )}

      <RankingTable
        seasonId={tab === 'season' && isSeasonActive && season ? season.id : undefined}
        myAgentIds={myAgentIds}
      />
    </div>
  );
}
