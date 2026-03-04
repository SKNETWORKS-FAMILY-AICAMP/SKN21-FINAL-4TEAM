'use client';

import { useEffect, useState } from 'react';
import { TrendingUp, Trophy } from 'lucide-react';
import { api } from '@/lib/api';
import { RankingTable } from '@/components/debate/RankingTable';

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

  useEffect(() => {
    api
      .get<{ season: Season | null }>('/agents/season/current')
      .then((res) => setSeason(res.season))
      .catch(() => setSeason(null));
  }, []);

  const isSeasonActive = season?.status === 'active';

  return (
    <div className="max-w-[800px] mx-auto py-6 px-4">
      <h1 className="page-title flex items-center gap-2 mb-5">
        <TrendingUp size={24} className="text-primary" />
        ELO 랭킹
      </h1>

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

      <RankingTable seasonId={tab === 'season' && isSeasonActive && season ? season.id : undefined} />
    </div>
  );
}
