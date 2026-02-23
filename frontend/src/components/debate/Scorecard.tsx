'use client';

import { useEffect, useState } from 'react';
import { Trophy, AlertTriangle } from 'lucide-react';
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

const CRITERIA_LABELS: Record<string, { label: string; max: number }> = {
  logic: { label: '논리성', max: 30 },
  evidence: { label: '근거 활용', max: 25 },
  rebuttal: { label: '반박력', max: 25 },
  relevance: { label: '주제 적합성', max: 20 },
};

export function Scorecard({ matchId, agentA, agentB, penaltyA, penaltyB }: Props) {
  const [data, setData] = useState<ScorecardData | null>(null);

  useEffect(() => {
    api
      .get<ScorecardData>(`/matches/${matchId}/scorecard`)
      .then(setData)
      .catch(() => {});
  }, [matchId]);

  if (!data) return null;

  const totalA = Object.values(data.agent_a).reduce((a, b) => a + b, 0);
  const totalB = Object.values(data.agent_b).reduce((a, b) => a + b, 0);
  const finalA = Math.max(0, totalA - penaltyA);
  const finalB = Math.max(0, totalB - penaltyB);

  return (
    <div className="bg-bg-surface border border-border rounded-xl p-5">
      <h3 className="text-base font-bold text-text mb-4 flex items-center gap-2">
        <Trophy size={18} className="text-primary" />
        스코어카드
      </h3>

      {/* 결과 배너 */}
      <div className="text-center mb-4 px-4 py-3 rounded-lg bg-primary/5 border border-primary/20">
        {data.winner_id ? (
          <span className="text-sm font-bold text-primary">
            {data.winner_id === agentA.id ? agentA.name : agentB.name} 승리!
          </span>
        ) : (
          <span className="text-sm font-bold text-text-muted">무승부</span>
        )}
        <div className="text-lg font-bold text-text mt-1">
          {finalA} : {finalB}
        </div>
      </div>

      {/* 항목별 바 차트 */}
      <div className="flex flex-col gap-3 mb-4">
        {Object.entries(CRITERIA_LABELS).map(([key, { label, max }]) => {
          const valA = data.agent_a[key] ?? 0;
          const valB = data.agent_b[key] ?? 0;
          return (
            <div key={key}>
              <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                <span>{agentA.name}: {valA}</span>
                <span className="font-semibold text-text">{label} (/{max})</span>
                <span>{agentB.name}: {valB}</span>
              </div>
              <div className="flex h-2 gap-0.5">
                <div className="flex-1 bg-border rounded-l overflow-hidden flex justify-end">
                  <div
                    className="bg-blue-500 rounded-l"
                    style={{ width: `${(valA / max) * 100}%` }}
                  />
                </div>
                <div className="flex-1 bg-border rounded-r overflow-hidden">
                  <div
                    className="bg-orange-500 rounded-r"
                    style={{ width: `${(valB / max) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 벌점 */}
      {(penaltyA > 0 || penaltyB > 0) && (
        <div className="flex items-center justify-between text-xs mb-4 px-2 py-1.5 bg-danger/5 rounded border border-danger/20">
          <span className="flex items-center gap-1 text-danger">
            <AlertTriangle size={12} />
            {agentA.name}: -{penaltyA}
          </span>
          <span className="font-semibold text-text-muted">벌점</span>
          <span className="flex items-center gap-1 text-danger">
            {agentB.name}: -{penaltyB}
            <AlertTriangle size={12} />
          </span>
        </div>
      )}

      {/* 판정 이유 */}
      <div className="px-3 py-2.5 bg-bg rounded-lg border border-border">
        <span className="text-[11px] text-text-muted font-semibold uppercase">판정 이유</span>
        <p className="text-xs text-text-secondary mt-1">{data.reasoning}</p>
      </div>
    </div>
  );
}
