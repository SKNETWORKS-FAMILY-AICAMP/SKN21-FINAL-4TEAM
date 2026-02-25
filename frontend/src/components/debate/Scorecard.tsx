'use client';

import { useEffect, useState } from 'react';
import { Trophy, AlertTriangle, Award } from 'lucide-react';
import { api } from '@/lib/api';
import type { AgentSummary } from '@/stores/debateStore';

type ScorecardData = {
  agent_a: Record<string, number>;
  agent_b: Record<string, number>;
  reasoning: string;
  winner_id: string | null;
  result: string;
};

type Props = {
  matchId: string;
  agentA: AgentSummary;
  agentB: AgentSummary;
  penaltyA: number;
  penaltyB: number;
};

const CRITERIA: { key: string; label: string; max: number; emoji: string }[] = [
  { key: 'logic', label: '논리성', max: 30, emoji: '🧠' },
  { key: 'evidence', label: '근거 활용', max: 25, emoji: '📚' },
  { key: 'rebuttal', label: '반박력', max: 25, emoji: '⚔️' },
  { key: 'relevance', label: '주제 적합성', max: 20, emoji: '🎯' },
];

export function Scorecard({ matchId, agentA, agentB, penaltyA, penaltyB }: Props) {
  const [data, setData] = useState<ScorecardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<ScorecardData>(`/matches/${matchId}/scorecard`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [matchId]);

  if (loading) {
    return (
      <div className="bg-bg-surface border border-border rounded-xl p-5 animate-pulse">
        <div className="h-4 bg-border rounded w-1/3 mb-4" />
        <div className="h-20 bg-border rounded mb-3" />
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-10 bg-border rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const totalA = Object.values(data.agent_a).reduce((a, b) => a + (Number(b) || 0), 0);
  const totalB = Object.values(data.agent_b).reduce((a, b) => a + (Number(b) || 0), 0);
  const finalA = Math.max(0, totalA - penaltyA);
  const finalB = Math.max(0, totalB - penaltyB);

  const isWinnerA = data.winner_id === agentA.id;
  const isWinnerB = data.winner_id === agentB.id;
  const isDraw = !data.winner_id;

  return (
    <div className="bg-bg-surface border border-border rounded-xl overflow-hidden">
      {/* 헤더 */}
      <div className="px-5 py-3 border-b border-border flex items-center gap-2">
        <Trophy size={16} className="text-yellow-400" />
        <span className="text-sm font-bold text-text">판정 결과</span>
      </div>

      {/* 최종 점수 배너 */}
      <div className="px-5 py-5 bg-gradient-to-b from-gray-900/60 to-transparent">
        <div className="flex items-center justify-between gap-4">
          {/* Agent A */}
          <div
            className={`flex-1 text-center ${isWinnerA ? 'opacity-100' : isDraw ? 'opacity-80' : 'opacity-50'}`}
          >
            {isWinnerA && (
              <div className="flex justify-center mb-1">
                <Award size={18} className="text-yellow-400" />
              </div>
            )}
            <p className="text-xs text-gray-400 truncate mb-1">{agentA.name}</p>
            <p className={`text-3xl font-black ${isWinnerA ? 'text-blue-400' : 'text-gray-300'}`}>
              {finalA}
            </p>
            {penaltyA > 0 && <p className="text-[10px] text-red-400 mt-0.5">벌점 -{penaltyA}</p>}
          </div>

          {/* VS 중앙 */}
          <div className="flex flex-col items-center gap-1 shrink-0">
            {isDraw ? (
              <span className="text-xs font-bold text-gray-400 px-2 py-1 rounded-full bg-gray-700/50">
                무승부
              </span>
            ) : (
              <span className="text-[11px] font-bold text-yellow-400 px-2 py-1 rounded-full bg-yellow-400/10">
                승리
              </span>
            )}
            <span className="text-lg font-mono text-gray-600">vs</span>
          </div>

          {/* Agent B */}
          <div
            className={`flex-1 text-center ${isWinnerB ? 'opacity-100' : isDraw ? 'opacity-80' : 'opacity-50'}`}
          >
            {isWinnerB && (
              <div className="flex justify-center mb-1">
                <Award size={18} className="text-yellow-400" />
              </div>
            )}
            <p className="text-xs text-gray-400 truncate mb-1">{agentB.name}</p>
            <p
              className={`text-3xl font-black ${isWinnerB ? 'text-orange-400' : 'text-gray-300'}`}
            >
              {finalB}
            </p>
            {penaltyB > 0 && <p className="text-[10px] text-red-400 mt-0.5">벌점 -{penaltyB}</p>}
          </div>
        </div>
      </div>

      {/* 항목별 비교 바 */}
      <div className="px-5 py-4 space-y-4">
        <p className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold mb-3">
          항목별 점수
        </p>
        {CRITERIA.map(({ key, label, max, emoji }) => {
          const valA = Number(data.agent_a[key]) || 0;
          const valB = Number(data.agent_b[key]) || 0;
          const pctA = Math.round((valA / max) * 100);
          const pctB = Math.round((valB / max) * 100);

          return (
            <div key={key}>
              {/* 라벨 행 */}
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-bold text-blue-400 min-w-[24px]">{valA}</span>
                <span className="text-[11px] text-gray-400 flex items-center gap-1">
                  {emoji} {label}
                  <span className="text-gray-600">/{max}</span>
                </span>
                <span className="text-sm font-bold text-orange-400 min-w-[24px] text-right">
                  {valB}
                </span>
              </div>
              {/* 바 차트 — 가운데 기준으로 양방향 */}
              <div className="flex items-center gap-1 h-4">
                {/* Agent A 바 (오른쪽→왼쪽 방향으로 채움) */}
                <div className="flex-1 h-full flex items-center justify-end bg-gray-800 rounded-l-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-l-full transition-all duration-700"
                    style={{ width: `${pctA}%` }}
                  />
                </div>
                {/* 중앙 구분선 */}
                <div className="w-px h-4 bg-gray-600 shrink-0" />
                {/* Agent B 바 (왼쪽→오른쪽 방향으로 채움) */}
                <div className="flex-1 h-full bg-gray-800 rounded-r-full overflow-hidden">
                  <div
                    className="h-full bg-orange-500 rounded-r-full transition-all duration-700"
                    style={{ width: `${pctB}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 벌점 (있을 때만) */}
      {(penaltyA > 0 || penaltyB > 0) && (
        <div className="mx-5 mb-4 flex items-center justify-between text-xs px-3 py-2 bg-red-500/5 rounded-lg border border-red-500/20">
          <span className="flex items-center gap-1 text-red-400">
            <AlertTriangle size={11} />
            {agentA.name}: -{penaltyA}점
          </span>
          <span className="text-gray-500 font-semibold">벌점</span>
          <span className="flex items-center gap-1 text-red-400">
            {agentB.name}: -{penaltyB}점
            <AlertTriangle size={11} />
          </span>
        </div>
      )}

      {/* 판정 이유 */}
      <div className="mx-5 mb-5 px-4 py-3 bg-bg rounded-xl border border-border">
        <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-1.5">
          심판 판정 이유
        </p>
        <p className="text-xs text-gray-300 leading-relaxed">{data.reasoning}</p>
      </div>
    </div>
  );
}
